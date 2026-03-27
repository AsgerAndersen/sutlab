"""
Tests for sutlab.balancing.
"""

import pytest
from numpy import nan as NAN

import pandas as pd

from sutlab.balancing import balance_columns, _evaluate_locks, _get_use_price_columns
from sutlab.sut import _match_codes
from sutlab.sut import (
    SUT,
    BalancingConfig,
    BalancingTargets,
    Locks,
    SUTColumns,
    SUTMetadata,
)


# ---------------------------------------------------------------------------
# Fixture data
#
# One balancing year (2021) plus one context year (2020) to verify that the
# non-balancing member is untouched.
#
# Supply (2021): products A, B, C; transactions 0100/X and 0700/""
#   A, 0100, X: bas=100
#   B, 0100, X: bas=100
#   C, 0100, X: bas=100   ← locked (product C)
#   A, 0700, "": bas=10
#   B, 0700, "": bas=10
#
# Use (2021): products A, B, C; transactions 3110/HH and 2000/X
#   A, 3110, HH: bas=10, ava=1, moms=2, koeb=13
#   B, 3110, HH: bas=20, ava=2, moms=4, koeb=26
#   C, 3110, HH: bas=30, ava=3, moms=6, koeb=39   ← locked (product C)
#   A, 2000, X:  bas=15, ava=1, moms=NaN, koeb=16
#   B, 2000, X:  bas=15, ava=1, moms=NaN, koeb=16
#
# Locks: product C only (no transaction or cell locks in the default fixture).
#
# Targets (2021):
#   supply  0100/X:  bas=360  (actual=300; C fixed=100 → adj sum=200 → scale=260/200=1.3)
#   use     3110/HH: koeb=90  (actual=78;  C fixed=39  → adj sum=39  → scale=51/39)
#   use     2000/X:  koeb=40  (actual=32;  no locks    → adj sum=32  → scale=40/32=1.25)
# ---------------------------------------------------------------------------


@pytest.fixture
def cols():
    return SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
        wholesale_margins="ava",
        vat="moms",
    )


@pytest.fixture
def supply_df():
    rows_2021 = [
        [2021, "A", "0100", "X",  100.0],
        [2021, "B", "0100", "X",  100.0],
        [2021, "C", "0100", "X",  100.0],
        [2021, "A", "0700", "",    10.0],
        [2021, "B", "0700", "",    10.0],
    ]
    rows_2020 = [
        [2020, "A", "0100", "X",   90.0],
        [2020, "B", "0100", "X",   90.0],
    ]
    return pd.DataFrame(
        rows_2021 + rows_2020,
        columns=["year", "nrnr", "trans", "brch", "bas"],
    )


@pytest.fixture
def use_df():
    rows_2021 = [
        [2021, "A", "3110", "HH",  10.0, 1.0, 2.0,  13.0],
        [2021, "B", "3110", "HH",  20.0, 2.0, 4.0,  26.0],
        [2021, "C", "3110", "HH",  30.0, 3.0, 6.0,  39.0],
        [2021, "A", "2000", "X",   15.0, 1.0, NAN,  16.0],
        [2021, "B", "2000", "X",   15.0, 1.0, NAN,  16.0],
    ]
    rows_2020 = [
        [2020, "A", "3110", "HH",   9.0, 0.9, 1.8,  11.7],
    ]
    return pd.DataFrame(
        rows_2021 + rows_2020,
        columns=["year", "nrnr", "trans", "brch", "bas", "ava", "moms", "koeb"],
    )


@pytest.fixture
def locks(cols):
    return Locks(products=pd.DataFrame({"nrnr": ["C"]}))


@pytest.fixture
def targets(cols):
    NAN_ = float("nan")
    supply = pd.DataFrame({
        "year":  [2021,  2021],
        "trans": ["0100", "0700"],
        "brch":  ["X",    ""],
        "bas":   [360.0,  NAN_],
        "ava":   [NAN_,   NAN_],
        "moms":  [NAN_,   NAN_],
        "koeb":  [NAN_,   NAN_],
    })
    use = pd.DataFrame({
        "year":  [2021,    2021],
        "trans": ["3110",  "2000"],
        "brch":  ["HH",    "X"],
        "bas":   [NAN_,    NAN_],
        "ava":   [NAN_,    NAN_],
        "moms":  [NAN_,    NAN_],
        "koeb":  [90.0,    40.0],
    })
    return BalancingTargets(supply=supply, use=use)


@pytest.fixture
def sut(supply_df, use_df, cols, locks, targets):
    metadata = SUTMetadata(columns=cols)
    config = BalancingConfig(locks=locks)
    return SUT(
        price_basis="current_year",
        supply=supply_df,
        use=use_df,
        balancing_id=2021,
        balancing_targets=targets,
        balancing_config=config,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_row(df, **kwargs):
    """Return a single row matching all given column==value conditions."""
    mask = pd.Series(True, index=df.index)
    for col, val in kwargs.items():
        mask = mask & (df[col] == val)
    rows = df[mask]
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)} for {kwargs}"
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Tests: supply balancing
# ---------------------------------------------------------------------------


class TestSupplyBalancing:

    def test_adjustable_products_scaled(self, sut):
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B"])
        new_supply = result.supply
        # scale = (360 - 100) / 200 = 1.3
        assert _get_row(new_supply, year=2021, nrnr="A", trans="0100", brch="X")["bas"] == pytest.approx(130.0)
        assert _get_row(new_supply, year=2021, nrnr="B", trans="0100", brch="X")["bas"] == pytest.approx(130.0)

    def test_locked_product_unchanged(self, sut):
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B"])
        assert _get_row(result.supply, year=2021, nrnr="C", trans="0100", brch="X")["bas"] == pytest.approx(100.0)

    def test_column_total_matches_target(self, sut):
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B"])
        total = result.supply[
            (result.supply["year"] == 2021) &
            (result.supply["trans"] == "0100") &
            (result.supply["brch"] == "X")
        ]["bas"].sum()
        assert total == pytest.approx(360.0)

    def test_unfiltered_supply_rows_unchanged(self, sut):
        # Rows for 0700 should not be touched
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B"])
        assert _get_row(result.supply, year=2021, nrnr="A", trans="0700", brch="")["bas"] == pytest.approx(10.0)

    def test_non_balancing_member_unchanged(self, sut):
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B"])
        orig_row = _get_row(sut.supply, year=2020, nrnr="A", trans="0100", brch="X")
        new_row = _get_row(result.supply, year=2020, nrnr="A", trans="0100", brch="X")
        assert new_row["bas"] == pytest.approx(orig_row["bas"])

    def test_locked_in_adjust_products_treated_as_fixed(self, sut):
        # C is locked even though it's in adjust_products
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B", "C"])
        # C still fixed at 100; A and B scaled to hit 360
        assert _get_row(result.supply, year=2021, nrnr="C", trans="0100", brch="X")["bas"] == pytest.approx(100.0)
        total = result.supply[
            (result.supply["year"] == 2021) &
            (result.supply["trans"] == "0100") &
            (result.supply["brch"] == "X")
        ]["bas"].sum()
        assert total == pytest.approx(360.0)

    def test_single_adjustable_product(self, sut):
        # Only A is adjustable; B and C are fixed
        result = balance_columns(sut, "0100", "X", adjust_products=["A"])
        # Fixed = B(100) + C(100) = 200; adjustable = A(100)
        # scale = (360 - 200) / 100 = 1.6
        assert _get_row(result.supply, year=2021, nrnr="A", trans="0100", brch="X")["bas"] == pytest.approx(160.0)
        assert _get_row(result.supply, year=2021, nrnr="B", trans="0100", brch="X")["bas"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Tests: use balancing
# ---------------------------------------------------------------------------


class TestUseBalancing:

    def test_all_price_columns_scaled_equally(self, sut):
        result = balance_columns(sut, "3110", "HH", adjust_products=["A", "B"])
        # scale = (90 - 39) / 39 = 51/39
        scale = 51 / 39
        row_a = _get_row(result.use, year=2021, nrnr="A", trans="3110", brch="HH")
        assert row_a["bas"] == pytest.approx(10.0 * scale)
        assert row_a["ava"] == pytest.approx(1.0 * scale)
        assert row_a["moms"] == pytest.approx(2.0 * scale)
        assert row_a["koeb"] == pytest.approx(13.0 * scale)

    def test_use_column_total_matches_target(self, sut):
        result = balance_columns(sut, "3110", "HH", adjust_products=["A", "B"])
        total = result.use[
            (result.use["year"] == 2021) &
            (result.use["trans"] == "3110") &
            (result.use["brch"] == "HH")
        ]["koeb"].sum()
        assert total == pytest.approx(90.0)

    def test_locked_use_row_unchanged(self, sut):
        result = balance_columns(sut, "3110", "HH", adjust_products=["A", "B"])
        row_c = _get_row(result.use, year=2021, nrnr="C", trans="3110", brch="HH")
        assert row_c["bas"] == pytest.approx(30.0)
        assert row_c["ava"] == pytest.approx(3.0)
        assert row_c["moms"] == pytest.approx(6.0)
        assert row_c["koeb"] == pytest.approx(39.0)

    def test_nan_layer_stays_nan(self, sut):
        # 2000/X rows have moms=NaN; scaling must not change that to a number
        result = balance_columns(sut, "2000", "X", adjust_products=["A", "B"])
        row_a = _get_row(result.use, year=2021, nrnr="A", trans="2000", brch="X")
        import math
        assert math.isnan(row_a["moms"])

    def test_use_scale_from_purchasers_price(self, sut):
        # 2000/X: actual koeb = 32, target = 40, scale = 40/32 = 1.25
        result = balance_columns(sut, "2000", "X", adjust_products=["A", "B"])
        scale = 40 / 32
        row_a = _get_row(result.use, year=2021, nrnr="A", trans="2000", brch="X")
        assert row_a["koeb"] == pytest.approx(16.0 * scale)
        assert row_a["bas"] == pytest.approx(15.0 * scale)
        assert row_a["ava"] == pytest.approx(1.0 * scale)

    def test_use_non_balancing_member_unchanged(self, sut):
        result = balance_columns(sut, "3110", "HH", adjust_products=["A", "B"])
        orig_row = _get_row(sut.use, year=2020, nrnr="A", trans="3110", brch="HH")
        new_row = _get_row(result.use, year=2020, nrnr="A", trans="3110", brch="HH")
        assert new_row["koeb"] == pytest.approx(orig_row["koeb"])


# ---------------------------------------------------------------------------
# Tests: default arguments and pattern syntax
# ---------------------------------------------------------------------------


class TestDefaultsAndPatterns:

    def test_all_none_balances_all_target_columns(self, sut):
        # With all arguments None, every (trans, cat) that has a target is balanced.
        # Targets: 0100/X (supply), 3110/HH (use), 2000/X (use).
        result = balance_columns(sut)
        # Supply 0100/X: scale = (360 - 100) / 200 = 1.3
        supply_total = result.supply[
            (result.supply["year"] == 2021) &
            (result.supply["trans"] == "0100") &
            (result.supply["brch"] == "X")
        ]["bas"].sum()
        assert supply_total == pytest.approx(360.0)
        # Use 3110/HH: scale = 51/39
        use_3110_total = result.use[
            (result.use["year"] == 2021) &
            (result.use["trans"] == "3110") &
            (result.use["brch"] == "HH")
        ]["koeb"].sum()
        assert use_3110_total == pytest.approx(90.0)
        # Use 2000/X: scale = 40/32 = 1.25
        use_2000_total = result.use[
            (result.use["year"] == 2021) &
            (result.use["trans"] == "2000") &
            (result.use["brch"] == "X")
        ]["koeb"].sum()
        assert use_2000_total == pytest.approx(40.0)

    def test_adjust_products_none_uses_all_products(self, sut):
        # With adjust_products=None all products are candidates; C is still fixed (locked).
        result = balance_columns(sut, transactions="0100", categories="X")
        assert _get_row(result.supply, year=2021, nrnr="C", trans="0100", brch="X")["bas"] == pytest.approx(100.0)
        total = result.supply[
            (result.supply["year"] == 2021) &
            (result.supply["trans"] == "0100") &
            (result.supply["brch"] == "X")
        ]["bas"].sum()
        assert total == pytest.approx(360.0)

    def test_transactions_wildcard_pattern(self, sut):
        # "2*" should match "2000" but not "0100" or "3110"
        result = balance_columns(sut, transactions="2*", adjust_products=["A", "B"])
        use_2000_total = result.use[
            (result.use["year"] == 2021) &
            (result.use["trans"] == "2000") &
            (result.use["brch"] == "X")
        ]["koeb"].sum()
        assert use_2000_total == pytest.approx(40.0)
        # 3110 should be unchanged
        assert _get_row(result.use, year=2021, nrnr="A", trans="3110", brch="HH")["koeb"] == pytest.approx(13.0)

    def test_adjust_products_negation_pattern(self, sut):
        # "~C" means all products except C — same outcome as locking C explicitly
        result_negation = balance_columns(sut, transactions="0100", categories="X", adjust_products="~C")
        result_explicit = balance_columns(sut, transactions="0100", categories="X", adjust_products=["A", "B"])
        assert _get_row(result_negation.supply, year=2021, nrnr="A", trans="0100", brch="X")["bas"] == pytest.approx(
            _get_row(result_explicit.supply, year=2021, nrnr="A", trans="0100", brch="X")["bas"]
        )

    def test_categories_none_derives_from_targets(self, sut):
        # transactions="0100", categories=None → should pick up category "X" from targets
        result = balance_columns(sut, transactions="0100", adjust_products=["A", "B"])
        total = result.supply[
            (result.supply["year"] == 2021) &
            (result.supply["trans"] == "0100") &
            (result.supply["brch"] == "X")
        ]["bas"].sum()
        assert total == pytest.approx(360.0)


# ---------------------------------------------------------------------------
# Tests: already balanced (no-op)
# ---------------------------------------------------------------------------


class TestAlreadyBalanced:

    def test_already_balanced_column_unchanged(self, supply_df, use_df, cols):
        # Target equals the actual total → no scaling should happen
        NAN_ = float("nan")
        supply = pd.DataFrame({
            "year": [2021], "trans": ["0100"], "brch": ["X"],
            "bas": [300.0], "ava": [NAN_], "moms": [NAN_], "koeb": [NAN_],
        })
        use = pd.DataFrame({
            "year": [2021], "trans": ["3110"], "brch": ["HH"],
            "bas": [NAN_], "ava": [NAN_], "moms": [NAN_], "koeb": [78.0],
        })
        targets = BalancingTargets(supply=supply, use=use)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
            metadata=SUTMetadata(columns=cols),
        )
        result = balance_columns(sut, "0100", "X", adjust_products=["A", "B", "C"])
        # All products are adjustable, target == actual → scale = 1 → no change
        assert _get_row(result.supply, year=2021, nrnr="A", trans="0100", brch="X")["bas"] == pytest.approx(100.0)
        assert _get_row(result.supply, year=2021, nrnr="B", trans="0100", brch="X")["bas"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestErrors:

    def test_no_metadata_raises(self, supply_df, use_df, targets):
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
        )
        with pytest.raises(ValueError, match="sut.metadata is required"):
            balance_columns(sut, "0100", "X", adjust_products=["A"])

    def test_no_balancing_id_raises(self, supply_df, use_df, cols, targets):
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_targets=targets,
            metadata=SUTMetadata(columns=cols),
        )
        with pytest.raises(ValueError, match="balancing_id is not set"):
            balance_columns(sut, "0100", "X", adjust_products=["A"])

    def test_no_targets_raises(self, supply_df, use_df, cols):
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            metadata=SUTMetadata(columns=cols),
        )
        with pytest.raises(ValueError, match="balancing_targets is not set"):
            balance_columns(sut, "0100", "X", adjust_products=["A"])

    def test_empty_filter_raises(self, sut):
        with pytest.raises(ValueError, match="matched no rows"):
            balance_columns(sut, "9999", "ZZZ", adjust_products=["A"])

    def test_missing_target_raises(self, sut):
        # Request a (trans, cat) that exists in the data but has no target
        with pytest.raises(ValueError, match="No target found"):
            balance_columns(sut, "0700", "", adjust_products=["A"])

    def test_zero_adjustable_raises(self, sut):
        # adjust_products=["X"] — no such product in the data → sum_adj = 0, not column-locked
        with pytest.raises(ValueError, match="adjustable rows sum to zero"):
            balance_columns(sut, "0100", "X", adjust_products=["X"])

    def test_transaction_lock_skips_silently(self, supply_df, use_df, cols, targets):
        # Lock transaction "0100" entirely — balance_columns(sut) should not raise,
        # and the locked column should remain unchanged.
        locks = Locks(transactions=pd.DataFrame({"trans": ["0100"]}))
        config = BalancingConfig(locks=locks)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
            balancing_config=config,
            metadata=SUTMetadata(columns=cols),
        )
        result = balance_columns(sut)
        assert _get_row(result.supply, year=2021, nrnr="A", trans="0100", brch="X")["bas"] == pytest.approx(100.0)
        assert _get_row(result.supply, year=2021, nrnr="B", trans="0100", brch="X")["bas"] == pytest.approx(100.0)

    def test_category_lock_skips_silently(self, supply_df, use_df, cols, targets):
        # Lock (3110, HH) via categories lock — should skip silently, not raise.
        locks = Locks(categories=pd.DataFrame({"trans": ["3110"], "brch": ["HH"]}))
        config = BalancingConfig(locks=locks)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
            balancing_config=config,
            metadata=SUTMetadata(columns=cols),
        )
        result = balance_columns(sut)
        assert _get_row(result.use, year=2021, nrnr="A", trans="3110", brch="HH")["koeb"] == pytest.approx(13.0)

    def test_product_lock_covering_all_rows_raises(self, supply_df, use_df, cols, targets):
        # Lock all products (A, B, C) via product lock — not a column lock, so should raise.
        locks = Locks(products=pd.DataFrame({"nrnr": ["A", "B", "C"]}))
        config = BalancingConfig(locks=locks)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
            balancing_config=config,
            metadata=SUTMetadata(columns=cols),
        )
        with pytest.raises(ValueError, match="adjustable rows sum to zero"):
            balance_columns(sut, transactions="0100", categories="X")

    def test_error_message_names_problematic_pair(self, sut):
        with pytest.raises(ValueError, match="0100"):
            balance_columns(sut, "0100", "X", adjust_products=["X"])


# ---------------------------------------------------------------------------
# Tests: _evaluate_locks
# ---------------------------------------------------------------------------


class TestEvaluateLocks:

    def test_none_locks_all_unlocked(self, use_df, cols):
        result = _evaluate_locks(use_df, None, cols)
        assert not result.any()

    def test_product_lock(self, use_df, cols):
        locks = Locks(products=pd.DataFrame({"nrnr": ["C"]}))
        result = _evaluate_locks(use_df, locks, cols)
        locked_rows = use_df[result]
        assert set(locked_rows["nrnr"].unique()) == {"C"}

    def test_transaction_lock(self, use_df, cols):
        locks = Locks(transactions=pd.DataFrame({"trans": ["3110"]}))
        result = _evaluate_locks(use_df, locks, cols)
        locked_rows = use_df[result]
        assert set(locked_rows["trans"].unique()) == {"3110"}

    def test_categories_lock(self, use_df, cols):
        # Lock the (3110, HH) pair only
        locks = Locks(categories=pd.DataFrame({"trans": ["3110"], "brch": ["HH"]}))
        result = _evaluate_locks(use_df, locks, cols)
        locked_rows = use_df[result]
        assert set(locked_rows["trans"].unique()) == {"3110"}
        assert set(locked_rows["brch"].unique()) == {"HH"}

    def test_cells_lock(self, use_df, cols):
        # Lock only product A in transaction 3110/HH
        locks = Locks(
            cells=pd.DataFrame({"nrnr": ["A"], "trans": ["3110"], "brch": ["HH"]})
        )
        # Use only 2021 rows to avoid the same (A, 3110, HH) triple in 2020
        use_2021 = use_df[use_df["year"] == 2021]
        result = _evaluate_locks(use_2021, locks, cols)
        locked_rows = use_2021[result]
        assert len(locked_rows) == 1
        assert locked_rows.iloc[0]["nrnr"] == "A"
        assert locked_rows.iloc[0]["trans"] == "3110"

    def test_or_logic_across_levels(self, use_df, cols):
        # Product C locked (1 row: C/3110/HH) AND transaction 2000 locked (2 rows: A/2000/X, B/2000/X)
        # No overlap, so total locked = 3
        locks = Locks(
            products=pd.DataFrame({"nrnr": ["C"]}),
            transactions=pd.DataFrame({"trans": ["2000"]}),
        )
        result = _evaluate_locks(use_df[use_df["year"] == 2021], locks, cols)
        assert result.sum() == 3


# ---------------------------------------------------------------------------
# Tests: _get_use_price_columns
# ---------------------------------------------------------------------------


class TestGetUsePriceColumns:

    def test_returns_mapped_and_present_columns(self, use_df, cols):
        result = _get_use_price_columns(use_df, cols)
        assert result == ["bas", "ava", "moms", "koeb"]

    def test_respects_chain_order(self, use_df):
        cols_reversed = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
            vat="moms", wholesale_margins="ava",
        )
        result = _get_use_price_columns(use_df, cols_reversed)
        # ava (wholesale_margins) comes before moms (vat) in chain order
        assert result.index("ava") < result.index("moms")

    def test_excludes_unmapped_roles(self, use_df, cols):
        # cols has no retail_margins — should not appear
        result = _get_use_price_columns(use_df, cols)
        assert "det" not in result

    def test_excludes_mapped_but_absent_columns(self, use_df):
        cols_with_extra = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
            wholesale_margins="ava", vat="moms",
            retail_margins="det",  # mapped but not in use_df
        )
        result = _get_use_price_columns(use_df, cols_with_extra)
        assert "det" not in result
