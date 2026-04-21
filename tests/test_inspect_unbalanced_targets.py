"""
Tests for inspect_unbalanced_targets.

Fixture data:

Supply 2021:
  0100/X:  actual bas = 300 (3 × 100),  target bas = 360
           diff = -60,  rel ≈ -0.1667  →  abs(diff)=60 > 1  →  included
  0700/"": actual bas =  20 (2 × 10),   target bas = NaN
           diff = NaN                   →  excluded

Use 2021:
  3110/HH: actual koeb = 78 (13+26+39), target koeb =  90
           diff = -12,  rel ≈ -0.1333  →  included
  2000/X:  actual koeb = 32 (16+16),    target koeb =  40
           diff = -8,   rel = -0.2      →  included

With tolerances (transaction-level; categories override 3110/HH):
  Category-level tols:
    0100/X:  min(0.05*360, 10) = 10
    0700/"": NaN (target NaN)
    3110/HH: min(0.01*90, 3) = 0.9   ← categories override
    2000/X:  min(0.04*40, 6) = 1.6

  Transaction-level tols (uses trans-level only, abs scaled by n_cats=1):
    0100: min(0.05*360, 1*10) = 10
    0700: NaN (target NaN)
    3110: min(0.03*90, 1*8) = 2.7    ← trans-level rel=0.03 (not category override)
    2000: min(0.04*40, 1*6) = 1.6

  Category violations:
    supply 0100/X:  diff=-60, tol=10  → violation=-60+10=-50
    use   3110/HH:  diff=-12, tol=0.9 → violation=-12+0.9=-11.1
    use   2000/X:   diff=-8,  tol=1.6 → violation=-8+1.6=-6.4

  Transaction violations:
    supply 0100: diff=-60, tol=10  → violation=-50
    use   3110:  diff=-12, tol=2.7 → violation=-12+2.7=-9.3
    use   2000:  diff=-8,  tol=1.6 → violation=-6.4

Targets exist only for 2021. With ids=None (default), id=2020 produces empty
per-id tables (no targets), so row counts are unchanged.
"""

import numpy as np
import pytest
import pandas as pd
from numpy import nan as NAN

from sutlab.inspect import inspect_unbalanced_targets, UnbalancedTargetsInspection
from sutlab.sut import (
    SUT,
    SUTColumns,
    SUTMetadata,
    BalancingTargets,
    BalancingConfig,
    TargetTolerances,
    Locks,
)


# ---------------------------------------------------------------------------
# Fixtures
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
def targets(cols):
    NAN_ = float("nan")
    supply = pd.DataFrame({
        "year":  [2021,   2021],
        "trans": ["0100", "0700"],
        "brch":  ["X",    ""],
        "bas":   [360.0,  NAN_],
    })
    use = pd.DataFrame({
        "year":  [2021,   2021],
        "trans": ["3110", "2000"],
        "brch":  ["HH",   "X"],
        "koeb":  [90.0,   40.0],
    })
    return BalancingTargets(supply=supply, use=use)


@pytest.fixture
def tolerances(cols):
    transactions = pd.DataFrame({
        cols.transaction: ["0100", "0700", "3110", "2000"],
        "rel":            [0.05,   0.02,   0.03,   0.04],
        "abs":            [10.0,   5.0,    8.0,    6.0],
    })
    categories = pd.DataFrame({
        cols.transaction: ["3110"],
        cols.category:    ["HH"],
        "rel":            [0.01],
        "abs":            [3.0],
    })
    return TargetTolerances(transactions=transactions, categories=categories)


@pytest.fixture
def sut_no_tol(supply_df, use_df, cols, targets):
    metadata = SUTMetadata(columns=cols)
    return SUT(
        price_basis="current_year",
        supply=supply_df,
        use=use_df,
        balancing_id=2021,
        balancing_targets=targets,
        metadata=metadata,
    )


@pytest.fixture
def sut_with_tol(supply_df, use_df, cols, targets, tolerances):
    metadata = SUTMetadata(columns=cols)
    config = BalancingConfig(target_tolerances=tolerances)
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
#
# Index structure (no labels):
#   supply/use_categories: (year, trans, brch)  → nlevels=3
#   supply/use_transactions: (year, trans)       → nlevels=2
#
# Index structure (with labels):
#   supply/use_categories: (year, trans, trans_txt, brch, brch_txt) → nlevels=5
#   supply/use_transactions: (year, trans, trans_txt)               → nlevels=3


def _get_row_cat(df, trans, brch):
    """Return a single row from a (year, trans, brch, ...) MultiIndex DataFrame."""
    # Level 0 = year (id), level 1 = trans, level 2 = brch (no labels) or 3 (with labels)
    cat_level_idx = 3 if df.index.nlevels == 5 else 2
    trans_vals = pd.Series(df.index.get_level_values(1), index=range(len(df)))
    cat_vals = pd.Series(df.index.get_level_values(cat_level_idx), index=range(len(df)))
    mask = (trans_vals == trans) & (cat_vals == brch)
    rows = df.iloc[mask.values]
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)} for trans={trans!r}, brch={brch!r}"
    return rows.iloc[0]


def _get_row_trans(df, trans):
    """Return a single row from a (year, trans, ...) MultiIndex DataFrame."""
    # Level 0 = year (id), level 1 = trans
    trans_vals = pd.Series(df.index.get_level_values(1), index=range(len(df)))
    mask = trans_vals == trans
    rows = df.iloc[mask.values]
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)} for trans={trans!r}"
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_returns_inspection_object(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert isinstance(result, UnbalancedTargetsInspection)

    def test_supply_categories_columns(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.supply_categories.columns) == [
            "bas", "target_bas", "diff_bas", "rel_bas", "tol_bas", "violation_bas"
        ]

    def test_use_categories_columns(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.use_categories.columns) == [
            "koeb", "target_koeb", "diff_koeb", "rel_koeb", "tol_koeb", "violation_koeb"
        ]

    def test_supply_transactions_columns(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.supply_transactions.columns) == [
            "bas", "target_bas", "diff_bas", "rel_bas", "tol_bas", "violation_bas"
        ]

    def test_use_transactions_columns(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.use_transactions.columns) == [
            "koeb", "target_koeb", "diff_koeb", "rel_koeb", "tol_koeb", "violation_koeb"
        ]


# ---------------------------------------------------------------------------
# abs(diff) > 1 filter
# ---------------------------------------------------------------------------


class TestDiffFilter:
    def test_supply_categories_row_count(self, sut_no_tol):
        # 0100/X diff=-60 → included; 0700/"" diff=NaN → excluded
        result = inspect_unbalanced_targets(sut_no_tol)
        assert len(result.data.supply_categories) == 1

    def test_supply_categories_excludes_nan_diff(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        # trans is at level 1 in the new (year, trans, brch) index
        trans_vals = result.data.supply_categories.index.get_level_values(1)
        assert "0700" not in trans_vals

    def test_use_categories_row_count(self, sut_no_tol):
        # Both 3110/HH and 2000/X have abs(diff) > 1
        result = inspect_unbalanced_targets(sut_no_tol)
        assert len(result.data.use_categories) == 2

    def test_supply_transactions_row_count(self, sut_no_tol):
        # 0100: diff=-60 → included; 0700: target=NaN → diff=NaN → excluded
        result = inspect_unbalanced_targets(sut_no_tol)
        assert len(result.data.supply_transactions) == 1

    def test_use_transactions_row_count(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert len(result.data.use_transactions) == 2


# ---------------------------------------------------------------------------
# Category-level values
# ---------------------------------------------------------------------------


class TestCategoryValues:
    def test_supply_categories_actual_0100(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.supply_categories, "0100", "X")
        assert row["bas"] == pytest.approx(300.0)

    def test_supply_categories_target_0100(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.supply_categories, "0100", "X")
        assert row["target_bas"] == pytest.approx(360.0)

    def test_supply_categories_diff_0100(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.supply_categories, "0100", "X")
        assert row["diff_bas"] == pytest.approx(-60.0)

    def test_supply_categories_rel_0100(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.supply_categories, "0100", "X")
        assert row["rel_bas"] == pytest.approx(300.0 / 360.0 - 1)

    def test_use_categories_actual_3110(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.use_categories, "3110", "HH")
        assert row["koeb"] == pytest.approx(78.0)

    def test_use_categories_diff_3110(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.use_categories, "3110", "HH")
        assert row["diff_koeb"] == pytest.approx(-12.0)

    def test_use_categories_diff_2000(self, sut_no_tol):
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol).data.use_categories, "2000", "X")
        assert row["diff_koeb"] == pytest.approx(-8.0)

    def test_only_active_id_used(self, sut_no_tol):
        # With ids=2021, supply 0100/X actual is 300 (only 2021 rows)
        row = _get_row_cat(inspect_unbalanced_targets(sut_no_tol, ids=2021).data.supply_categories, "0100", "X")
        assert row["bas"] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Transaction-level values
# ---------------------------------------------------------------------------


class TestTransactionValues:
    def test_supply_transactions_actual_0100(self, sut_no_tol):
        row = _get_row_trans(inspect_unbalanced_targets(sut_no_tol).data.supply_transactions, "0100")
        assert row["bas"] == pytest.approx(300.0)

    def test_supply_transactions_target_0100(self, sut_no_tol):
        row = _get_row_trans(inspect_unbalanced_targets(sut_no_tol).data.supply_transactions, "0100")
        assert row["target_bas"] == pytest.approx(360.0)

    def test_supply_transactions_diff_0100(self, sut_no_tol):
        row = _get_row_trans(inspect_unbalanced_targets(sut_no_tol).data.supply_transactions, "0100")
        assert row["diff_bas"] == pytest.approx(-60.0)

    def test_use_transactions_actual_3110(self, sut_no_tol):
        row = _get_row_trans(inspect_unbalanced_targets(sut_no_tol).data.use_transactions, "3110")
        assert row["koeb"] == pytest.approx(78.0)

    def test_use_transactions_diff_3110(self, sut_no_tol):
        row = _get_row_trans(inspect_unbalanced_targets(sut_no_tol).data.use_transactions, "3110")
        assert row["diff_koeb"] == pytest.approx(-12.0)

    def test_use_transactions_diff_2000(self, sut_no_tol):
        row = _get_row_trans(inspect_unbalanced_targets(sut_no_tol).data.use_transactions, "2000")
        assert row["diff_koeb"] == pytest.approx(-8.0)


# ---------------------------------------------------------------------------
# No tolerances: tol columns NaN, violations None
# ---------------------------------------------------------------------------


class TestNoTolerances:
    def test_supply_categories_tol_nan(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.supply_categories["tol_bas"].isna().all()

    def test_use_categories_tol_nan(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.use_categories["tol_koeb"].isna().all()

    def test_supply_transactions_tol_nan(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.supply_transactions["tol_bas"].isna().all()

    def test_use_transactions_tol_nan(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.use_transactions["tol_koeb"].isna().all()

    def test_supply_categories_violation_nan(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.supply_categories["violation_bas"].isna().all()

    def test_supply_categories_violations_none(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).data.supply_categories_violations is None

    def test_use_categories_violations_none(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).data.use_categories_violations is None

    def test_supply_transactions_violations_none(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).data.supply_transactions_violations is None

    def test_use_transactions_violations_none(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).data.use_transactions_violations is None


# ---------------------------------------------------------------------------
# Category-level tolerances and violations
# ---------------------------------------------------------------------------


class TestCategoryTolerances:
    def test_supply_categories_tol_0100(self, sut_with_tol):
        # min(abs(0.05 * 360), 10) = 10
        row = _get_row_cat(inspect_unbalanced_targets(sut_with_tol).data.supply_categories, "0100", "X")
        assert row["tol_bas"] == pytest.approx(10.0)

    def test_use_categories_tol_3110_uses_category_override(self, sut_with_tol):
        # categories override: min(abs(0.01 * 90), 3) = 0.9
        row = _get_row_cat(inspect_unbalanced_targets(sut_with_tol).data.use_categories, "3110", "HH")
        assert row["tol_koeb"] == pytest.approx(0.9)

    def test_use_categories_tol_2000_uses_transaction_fallback(self, sut_with_tol):
        # transaction fallback: min(abs(0.04 * 40), 6) = 1.6
        row = _get_row_cat(inspect_unbalanced_targets(sut_with_tol).data.use_categories, "2000", "X")
        assert row["tol_koeb"] == pytest.approx(1.6)

    def test_supply_categories_violation_0100(self, sut_with_tol):
        # diff=-60, tol=10 → violation=-60+10=-50
        row = _get_row_cat(inspect_unbalanced_targets(sut_with_tol).data.supply_categories, "0100", "X")
        assert row["violation_bas"] == pytest.approx(-50.0)

    def test_use_categories_violation_3110(self, sut_with_tol):
        # diff=-12, tol=0.9 → violation=-12+0.9=-11.1
        row = _get_row_cat(inspect_unbalanced_targets(sut_with_tol).data.use_categories, "3110", "HH")
        assert row["violation_koeb"] == pytest.approx(-11.1)

    def test_use_categories_violation_2000(self, sut_with_tol):
        # diff=-8, tol=1.6 → violation=-8+1.6=-6.4
        row = _get_row_cat(inspect_unbalanced_targets(sut_with_tol).data.use_categories, "2000", "X")
        assert row["violation_koeb"] == pytest.approx(-6.4)

    def test_supply_categories_violations_is_dataframe(self, sut_with_tol):
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).data.supply_categories_violations, pd.DataFrame)

    def test_use_categories_violations_is_dataframe(self, sut_with_tol):
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).data.use_categories_violations, pd.DataFrame)

    def test_supply_categories_violations_contains_0100(self, sut_with_tol):
        violations = inspect_unbalanced_targets(sut_with_tol).data.supply_categories_violations
        # trans is at level 1 in (year, trans, brch)
        assert "0100" in violations.index.get_level_values(1)

    def test_tol_already_resolved_not_called_twice(self, sut_with_tol):
        from sutlab.balancing import resolve_target_tolerances
        pre_resolved = resolve_target_tolerances(sut_with_tol)
        result_pre = inspect_unbalanced_targets(pre_resolved)
        result_auto = inspect_unbalanced_targets(sut_with_tol)
        pd.testing.assert_frame_equal(result_pre.data.supply_categories, result_auto.data.supply_categories)
        pd.testing.assert_frame_equal(result_pre.data.use_categories, result_auto.data.use_categories)


# ---------------------------------------------------------------------------
# Transaction-level tolerances and violations
# ---------------------------------------------------------------------------


class TestTransactionTolerances:
    def test_supply_transactions_tol_0100(self, sut_with_tol):
        # n_cats=1, trans-level: min(0.05*360, 1*10) = 10
        row = _get_row_trans(inspect_unbalanced_targets(sut_with_tol).data.supply_transactions, "0100")
        assert row["tol_bas"] == pytest.approx(10.0)

    def test_use_transactions_tol_3110_uses_transaction_level_not_category(self, sut_with_tol):
        # Transaction-level for 3110: rel=0.03, abs=8; n_cats=1
        # min(0.03*90, 1*8) = min(2.7, 8) = 2.7  (NOT the category override 0.9)
        row = _get_row_trans(inspect_unbalanced_targets(sut_with_tol).data.use_transactions, "3110")
        assert row["tol_koeb"] == pytest.approx(2.7)

    def test_use_transactions_tol_2000(self, sut_with_tol):
        # min(0.04*40, 1*6) = min(1.6, 6) = 1.6
        row = _get_row_trans(inspect_unbalanced_targets(sut_with_tol).data.use_transactions, "2000")
        assert row["tol_koeb"] == pytest.approx(1.6)

    def test_supply_transactions_violation_0100(self, sut_with_tol):
        # diff=-60, tol=10 → violation=-50
        row = _get_row_trans(inspect_unbalanced_targets(sut_with_tol).data.supply_transactions, "0100")
        assert row["violation_bas"] == pytest.approx(-50.0)

    def test_use_transactions_violation_3110(self, sut_with_tol):
        # diff=-12, tol=2.7 → violation=-12+2.7=-9.3
        row = _get_row_trans(inspect_unbalanced_targets(sut_with_tol).data.use_transactions, "3110")
        assert row["violation_koeb"] == pytest.approx(-9.3)

    def test_use_transactions_violation_2000(self, sut_with_tol):
        # diff=-8, tol=1.6 → violation=-6.4
        row = _get_row_trans(inspect_unbalanced_targets(sut_with_tol).data.use_transactions, "2000")
        assert row["violation_koeb"] == pytest.approx(-6.4)

    def test_supply_transactions_violations_is_dataframe(self, sut_with_tol):
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).data.supply_transactions_violations, pd.DataFrame)

    def test_use_transactions_violations_is_dataframe(self, sut_with_tol):
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).data.use_transactions_violations, pd.DataFrame)

    def test_supply_transactions_violations_contains_0100(self, sut_with_tol):
        violations = inspect_unbalanced_targets(sut_with_tol).data.supply_transactions_violations
        # trans is at level 1 in (year, trans) index
        assert "0100" in violations.index.get_level_values(1)

    def test_use_transactions_violations_contains_both(self, sut_with_tol):
        violations = inspect_unbalanced_targets(sut_with_tol).data.use_transactions_violations
        # trans is at level 1 in (year, trans) index
        trans_vals = violations.index.get_level_values(1).tolist()
        assert "3110" in trans_vals
        assert "2000" in trans_vals


# ---------------------------------------------------------------------------
# Violations empty when all within tolerance
# ---------------------------------------------------------------------------


class TestViolationsEmpty:
    def test_empty_violations_when_all_in_tolerance(self, supply_df, use_df, cols):
        # Very wide tolerances and exact targets: diff=0, excluded by abs(diff)>1 filter.
        targets = BalancingTargets(
            supply=pd.DataFrame({
                "year":  [2021],
                "trans": ["0100"],
                "brch":  ["X"],
                "bas":   [300.0],
            }),
            use=pd.DataFrame({
                "year":  [2021],
                "trans": ["3110"],
                "brch":  ["HH"],
                "koeb":  [78.0],
            }),
        )
        tolerances = TargetTolerances(
            transactions=pd.DataFrame({
                cols.transaction: ["0100", "3110"],
                "rel":            [1.0,    1.0],
                "abs":            [1000.0, 1000.0],
            })
        )
        metadata = SUTMetadata(columns=cols)
        config = BalancingConfig(target_tolerances=tolerances)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
            balancing_config=config,
            metadata=metadata,
        )
        result = inspect_unbalanced_targets(sut)
        assert isinstance(result.data.supply_categories_violations, pd.DataFrame)
        assert len(result.data.supply_categories_violations) == 0
        assert isinstance(result.data.use_categories_violations, pd.DataFrame)
        assert len(result.data.use_categories_violations) == 0
        assert isinstance(result.data.supply_transactions_violations, pd.DataFrame)
        assert len(result.data.supply_transactions_violations) == 0
        assert isinstance(result.data.use_transactions_violations, pd.DataFrame)
        assert len(result.data.use_transactions_violations) == 0


# ---------------------------------------------------------------------------
# Transaction / category filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_transactions_filter_categories_table(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol, transactions="0100")
        assert len(result.data.supply_categories) == 1
        # trans is at level 1 in (year, trans, brch)
        assert result.data.supply_categories.index.get_level_values(1)[0] == "0100"

    def test_transactions_filter_transactions_table(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol, transactions="0100")
        assert len(result.data.supply_transactions) == 1
        # trans is at level 1 in (year, trans)
        assert result.data.supply_transactions.index.get_level_values(1)[0] == "0100"

    def test_categories_filter_applies_to_categories_table(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol, categories="HH")
        assert len(result.data.use_categories) == 1
        # cat level: 3 if 5 levels (with labels), 2 if 3 levels (no labels)
        cat_level = 3 if result.data.use_categories.index.nlevels == 5 else 2
        assert result.data.use_categories.index.get_level_values(cat_level)[0] == "HH"

    def test_categories_filter_does_not_apply_to_transactions_table(self, sut_no_tol):
        # With categories="HH", use_categories has only 3110/HH.
        # use_transactions should still include both 3110 and 2000.
        result = inspect_unbalanced_targets(sut_no_tol, categories="HH")
        # trans is at level 1 in (year, trans)
        trans_vals = result.data.use_transactions.index.get_level_values(1).tolist()
        assert "3110" in trans_vals
        assert "2000" in trans_vals


# ---------------------------------------------------------------------------
# MultiIndex structure
# ---------------------------------------------------------------------------


class TestMultiIndex:
    def test_supply_categories_three_level_index(self, sut_no_tol):
        # (year, trans, brch) = 3 levels
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.supply_categories.index.nlevels == 3

    def test_supply_categories_index_names(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.supply_categories.index.names) == ["year", "trans", "brch"]

    def test_supply_transactions_two_level_index(self, sut_no_tol):
        # (year, trans) = 2 levels
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.supply_transactions.index.nlevels == 2
        assert isinstance(result.data.supply_transactions.index, pd.MultiIndex)

    def test_supply_transactions_index_names(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert "trans" in result.data.supply_transactions.index.names
        assert "year" in result.data.supply_transactions.index.names

    def test_use_transactions_two_level_index(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.use_transactions.index.nlevels == 2


# ---------------------------------------------------------------------------
# Raises
# ---------------------------------------------------------------------------


class TestRaises:
    def test_raises_no_metadata(self, supply_df, use_df, targets):
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            balancing_targets=targets,
        )
        with pytest.raises(ValueError, match="metadata"):
            inspect_unbalanced_targets(sut)

    def test_raises_no_balancing_targets(self, supply_df, use_df, cols):
        metadata = SUTMetadata(columns=cols)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_id=2021,
            metadata=metadata,
        )
        with pytest.raises(ValueError, match="balancing_targets"):
            inspect_unbalanced_targets(sut)


# ---------------------------------------------------------------------------
# SUT method delegation
# ---------------------------------------------------------------------------


class TestSUTMethod:
    def test_method_matches_free_function(self, sut_with_tol):
        via_method = sut_with_tol.inspect_unbalanced_targets()
        via_function = inspect_unbalanced_targets(sut_with_tol)
        pd.testing.assert_frame_equal(via_method.data.supply_categories, via_function.data.supply_categories)
        pd.testing.assert_frame_equal(via_method.data.use_categories, via_function.data.use_categories)
        pd.testing.assert_frame_equal(via_method.data.supply_transactions, via_function.data.supply_transactions)
        pd.testing.assert_frame_equal(via_method.data.use_transactions, via_function.data.use_transactions)


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_is_dataframe(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert isinstance(result.data.summary, pd.DataFrame)

    def test_summary_column_name(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.summary.columns) == ["n_unbalanced", "largest_diff"]

    def test_summary_index_name(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert result.data.summary.index.name == "table"

    def test_summary_no_tol_has_four_rows(self, sut_no_tol):
        # Without tolerances: 4 main tables, violations omitted.
        result = inspect_unbalanced_targets(sut_no_tol)
        assert len(result.data.summary) == 4

    def test_summary_no_tol_row_names(self, sut_no_tol):
        result = inspect_unbalanced_targets(sut_no_tol)
        assert list(result.data.summary.index) == [
            "supply_transactions",
            "supply_categories",
            "use_transactions",
            "use_categories",
        ]

    def test_summary_with_tol_has_eight_rows(self, sut_with_tol):
        # With tolerances: 4 main + 4 violations tables.
        result = inspect_unbalanced_targets(sut_with_tol)
        assert len(result.data.summary) == 8

    def test_summary_with_tol_row_names(self, sut_with_tol):
        result = inspect_unbalanced_targets(sut_with_tol)
        assert list(result.data.summary.index) == [
            "supply_transactions",
            "supply_categories",
            "use_transactions",
            "use_categories",
            "supply_transactions_violations",
            "supply_categories_violations",
            "use_transactions_violations",
            "use_categories_violations",
        ]

    def test_summary_counts_match_table_lengths(self, sut_with_tol):
        result = inspect_unbalanced_targets(sut_with_tol)
        d = result.data
        assert result.data.summary.loc["supply_categories", "n_unbalanced"] == len(d.supply_categories)
        assert result.data.summary.loc["use_categories", "n_unbalanced"] == len(d.use_categories)
        assert result.data.summary.loc["supply_transactions", "n_unbalanced"] == len(d.supply_transactions)
        assert result.data.summary.loc["use_transactions", "n_unbalanced"] == len(d.use_transactions)
        assert result.data.summary.loc["supply_categories_violations", "n_unbalanced"] == len(d.supply_categories_violations)
        assert result.data.summary.loc["use_categories_violations", "n_unbalanced"] == len(d.use_categories_violations)
        assert result.data.summary.loc["supply_transactions_violations", "n_unbalanced"] == len(d.supply_transactions_violations)
        assert result.data.summary.loc["use_transactions_violations", "n_unbalanced"] == len(d.use_transactions_violations)

    def test_summary_largest_diff_main_tables(self, sut_no_tol):
        # supply 0100/X: diff_bas = 300 - 360 = -60 (only unbalanced supply row)
        # use 3110/HH: diff_koeb = 78 - 90 = -12 (larger abs than 2000/X at -8)
        result = inspect_unbalanced_targets(sut_no_tol)
        s = result.data.summary
        assert s.loc["supply_transactions", "largest_diff"] == pytest.approx(-60.0)
        assert s.loc["supply_categories", "largest_diff"] == pytest.approx(-60.0)
        assert s.loc["use_transactions", "largest_diff"] == pytest.approx(-12.0)
        assert s.loc["use_categories", "largest_diff"] == pytest.approx(-12.0)

    def test_summary_largest_diff_violations(self, sut_with_tol):
        # Violations tables have non-empty rows; largest_diff should not be NaN.
        result = inspect_unbalanced_targets(sut_with_tol)
        s = result.data.summary
        for row in ["supply_transactions_violations", "supply_categories_violations",
                    "use_transactions_violations", "use_categories_violations"]:
            assert not np.isnan(s.loc[row, "largest_diff"]), f"{row} largest_diff is NaN"

    def test_summary_largest_diff_matches_violation_column(self, sut_with_tol):
        # For violation tables the largest_diff reflects the violation column, not diff.
        result = inspect_unbalanced_targets(sut_with_tol)
        d = result.data
        s = result.data.summary
        supply_viol = d.supply_categories_violations
        expected = supply_viol["violation_bas"].loc[supply_viol["violation_bas"].abs().idxmax()]
        assert s.loc["supply_categories_violations", "largest_diff"] == pytest.approx(expected)

    def test_summary_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_no_tol).summary, Styler)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------


class TestStyling:
    def test_supply_categories_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_no_tol).supply_categories, Styler)

    def test_use_categories_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_no_tol).use_categories, Styler)

    def test_supply_transactions_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_no_tol).supply_transactions, Styler)

    def test_use_transactions_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_no_tol).use_transactions, Styler)

    def test_supply_categories_violations_returns_styler_when_tolerances_set(self, sut_with_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).supply_categories_violations, Styler)

    def test_use_categories_violations_returns_styler_when_tolerances_set(self, sut_with_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).use_categories_violations, Styler)

    def test_supply_transactions_violations_returns_styler_when_tolerances_set(self, sut_with_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).supply_transactions_violations, Styler)

    def test_use_transactions_violations_returns_styler_when_tolerances_set(self, sut_with_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_unbalanced_targets(sut_with_tol).use_transactions_violations, Styler)

    def test_supply_categories_violations_returns_none_when_no_tolerances(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).supply_categories_violations is None

    def test_use_categories_violations_returns_none_when_no_tolerances(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).use_categories_violations is None

    def test_supply_transactions_violations_returns_none_when_no_tolerances(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).supply_transactions_violations is None

    def test_use_transactions_violations_returns_none_when_no_tolerances(self, sut_no_tol):
        assert inspect_unbalanced_targets(sut_no_tol).use_transactions_violations is None


# ---------------------------------------------------------------------------
# ids parameter: multi-id behaviour
# ---------------------------------------------------------------------------


class TestMultipleIds:
    def test_ids_none_same_row_count_as_ids_2021(self, sut_no_tol):
        # Targets only exist for 2021; 2020 produces empty per-id tables.
        # So ids=None gives the same rows as ids=2021.
        result_all = inspect_unbalanced_targets(sut_no_tol)
        result_2021 = inspect_unbalanced_targets(sut_no_tol, ids=2021)
        assert len(result_all.data.supply_categories) == len(result_2021.data.supply_categories)
        assert len(result_all.data.use_categories) == len(result_2021.data.use_categories)
        assert len(result_all.data.supply_transactions) == len(result_2021.data.supply_transactions)
        assert len(result_all.data.use_transactions) == len(result_2021.data.use_transactions)

    def test_ids_2021_explicit_matches_default(self, sut_no_tol):
        result_2021 = inspect_unbalanced_targets(sut_no_tol, ids=2021)
        assert len(result_2021.data.supply_categories) == 1
        assert len(result_2021.data.use_categories) == 2
        assert len(result_2021.data.supply_transactions) == 1
        assert len(result_2021.data.use_transactions) == 2

    def test_ids_2020_gives_empty_tables(self, sut_no_tol):
        # No targets exist for 2020, so all result tables are empty.
        result_2020 = inspect_unbalanced_targets(sut_no_tol, ids=2020)
        assert len(result_2020.data.supply_categories) == 0
        assert len(result_2020.data.use_categories) == 0
        assert len(result_2020.data.supply_transactions) == 0
        assert len(result_2020.data.use_transactions) == 0
