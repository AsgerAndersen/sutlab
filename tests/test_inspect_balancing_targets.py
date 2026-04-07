"""
Tests for inspect_balancing_targets.

Fixture data (from test_balancing.py fixture values):

Supply 2021:
  0100/X:  actual bas = 300 (3 × 100),  target bas = 360
           diff = 300 - 360 = -60,  rel = 300/360 - 1 ≈ -0.1667
  0700/"": actual bas =  20 (2 × 10),   target bas = NaN → diff/rel/tol = NaN

Use 2021:
  3110/HH: actual koeb = 78 (13+26+39), target koeb =  90
           diff = 78 - 90 = -12, rel = 78/90 - 1 ≈ -0.1333
  2000/X:  actual koeb = 32 (16+16),    target koeb =  40
           diff = 32 - 40 = -8,  rel = 32/40 - 1 = -0.2

With tolerances (transaction-level; categories override 3110/HH):
  Supply tols:  0100/X: min(0.05*360, 10) = 10;  0700/"": NaN (target NaN)
  Use tols:     3110/HH (cat override): min(0.01*90, 3) = 0.9
                2000/X  (trans fallback): min(0.04*40, 6) = 1.6

Tol violations:
  Supply 0100/X:  diff=-60 < -tol=-10  →  violation = -60 + 10 = -50
  Use   3110/HH:  diff=-12 < -tol=-0.9 →  violation = -12 + 0.9 = -11.1
  Use   2000/X:   diff= -8 < -tol=-1.6 →  violation = -8 + 1.6 = -6.4
"""

import pytest
import pandas as pd
from numpy import nan as NAN

from sutlab.inspect import inspect_balancing_targets, BalancingTargetsInspection
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
# Helper
# ---------------------------------------------------------------------------


def _get_row(df, **kwargs):
    """Return a single row matching all given index-level conditions.

    Works with both 2-level (trans, brch) and 4-level
    (trans, trans_txt, brch, brch_txt) MultiIndex structures.
    """
    # Transaction is always level 0; category is level 1 (2-level) or 2 (4-level).
    cat_level_idx = 2 if df.index.nlevels == 4 else 1
    trans_vals = pd.Series(df.index.get_level_values(0), index=range(len(df)))
    cat_vals = pd.Series(df.index.get_level_values(cat_level_idx), index=range(len(df)))
    mask = pd.Series(True, index=range(len(df)))
    if "trans" in kwargs:
        mask = mask & (trans_vals == kwargs["trans"])
    if "brch" in kwargs:
        mask = mask & (cat_vals == kwargs["brch"])
    rows = df.iloc[mask.values]
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)} for {kwargs}"
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_returns_inspection_object(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert isinstance(result, BalancingTargetsInspection)

    def test_supply_has_expected_columns(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert list(result.data.supply.columns) == ["bas", "target_bas", "diff_bas", "rel_bas", "tol_bas", "violation_bas"]

    def test_use_has_expected_columns(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert list(result.data.use.columns) == ["koeb", "target_koeb", "diff_koeb", "rel_koeb", "tol_koeb", "violation_koeb"]

    def test_supply_row_count(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert len(result.data.supply) == 2

    def test_use_row_count(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert len(result.data.use) == 2


# ---------------------------------------------------------------------------
# Correct values (no tolerances)
# ---------------------------------------------------------------------------


class TestValues:
    def test_supply_actual_0100(self, sut_no_tol):
        row = _get_row(result := inspect_balancing_targets(sut_no_tol).data.supply, trans="0100", brch="X")
        assert row["bas"] == pytest.approx(300.0)

    def test_supply_target_0100(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.supply, trans="0100", brch="X")
        assert row["target_bas"] == pytest.approx(360.0)

    def test_supply_diff_0100(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.supply, trans="0100", brch="X")
        assert row["diff_bas"] == pytest.approx(-60.0)

    def test_supply_rel_0100(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.supply, trans="0100", brch="X")
        assert row["rel_bas"] == pytest.approx(300.0 / 360.0 - 1)

    def test_supply_nan_target_gives_nan_diff(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.supply, trans="0700", brch="")
        assert pd.isna(row["diff_bas"])

    def test_use_actual_3110(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.use, trans="3110", brch="HH")
        assert row["koeb"] == pytest.approx(78.0)

    def test_use_diff_3110(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.use, trans="3110", brch="HH")
        assert row["diff_koeb"] == pytest.approx(-12.0)

    def test_use_diff_2000(self, sut_no_tol):
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.use, trans="2000", brch="X")
        assert row["diff_koeb"] == pytest.approx(-8.0)

    def test_only_active_id_used(self, sut_no_tol):
        # 2020 rows must not contribute to 2021 totals.
        row = _get_row(inspect_balancing_targets(sut_no_tol).data.supply, trans="0100", brch="X")
        assert row["bas"] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Tolerances absent: tol columns NaN, violations None
# ---------------------------------------------------------------------------


class TestNoTolerances:
    def test_supply_tol_col_nan(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert result.data.supply["tol_bas"].isna().all()

    def test_use_tol_col_nan(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert result.data.use["tol_koeb"].isna().all()

    def test_supply_tol_violation_nan(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert result.data.supply["violation_bas"].isna().all()

    def test_supply_violations_none(self, sut_no_tol):
        assert inspect_balancing_targets(sut_no_tol).data.supply_violations is None

    def test_use_violations_none(self, sut_no_tol):
        assert inspect_balancing_targets(sut_no_tol).data.use_violations is None


# ---------------------------------------------------------------------------
# Tolerances present: resolved silently, violations computed
# ---------------------------------------------------------------------------


class TestWithTolerances:
    def test_supply_tol_resolved_0100(self, sut_with_tol):
        # min(abs(0.05 * 360), 10) = 10
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.supply, trans="0100", brch="X")
        assert row["tol_bas"] == pytest.approx(10.0)

    def test_supply_tol_nan_for_nan_target(self, sut_with_tol):
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.supply, trans="0700", brch="")
        assert pd.isna(row["tol_bas"])

    def test_use_tol_categories_override_3110(self, sut_with_tol):
        # min(abs(0.01 * 90), 3) = 0.9
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.use, trans="3110", brch="HH")
        assert row["tol_koeb"] == pytest.approx(0.9)

    def test_use_tol_transaction_fallback_2000(self, sut_with_tol):
        # min(abs(0.04 * 40), 6) = 1.6
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.use, trans="2000", brch="X")
        assert row["tol_koeb"] == pytest.approx(1.6)

    def test_supply_violation_0100(self, sut_with_tol):
        # diff=-60, tol=10 → violation = -60 + 10 = -50
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.supply, trans="0100", brch="X")
        assert row["violation_bas"] == pytest.approx(-50.0)

    def test_supply_violation_nan_for_nan_target(self, sut_with_tol):
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.supply, trans="0700", brch="")
        assert pd.isna(row["violation_bas"])

    def test_use_violation_3110(self, sut_with_tol):
        # diff=-12, tol=0.9 → violation = -12 + 0.9 = -11.1
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.use, trans="3110", brch="HH")
        assert row["violation_koeb"] == pytest.approx(-11.1)

    def test_use_violation_2000(self, sut_with_tol):
        # diff=-8, tol=1.6 → violation = -8 + 1.6 = -6.4
        row = _get_row(inspect_balancing_targets(sut_with_tol).data.use, trans="2000", brch="X")
        assert row["violation_koeb"] == pytest.approx(-6.4)

    def test_supply_violations_is_dataframe(self, sut_with_tol):
        assert isinstance(inspect_balancing_targets(sut_with_tol).data.supply_violations, pd.DataFrame)

    def test_use_violations_is_dataframe(self, sut_with_tol):
        assert isinstance(inspect_balancing_targets(sut_with_tol).data.use_violations, pd.DataFrame)

    def test_supply_violations_contains_0100(self, sut_with_tol):
        violations = inspect_balancing_targets(sut_with_tol).data.supply_violations
        trans_vals = violations.index.get_level_values(0)
        assert "0100" in trans_vals

    def test_supply_violations_excludes_nan_target_row(self, sut_with_tol):
        # 0700/"" has NaN tol_violation → should not appear in violations table.
        violations = inspect_balancing_targets(sut_with_tol).data.supply_violations
        trans_vals = violations.index.get_level_values(0)
        assert "0700" not in trans_vals

    def test_tol_already_resolved_not_called_twice(self, sut_with_tol):
        # Pre-resolve: if tol column is already present, result should be identical.
        from sutlab.balancing import resolve_target_tolerances
        pre_resolved = resolve_target_tolerances(sut_with_tol)
        result_pre = inspect_balancing_targets(pre_resolved)
        result_auto = inspect_balancing_targets(sut_with_tol)
        pd.testing.assert_frame_equal(result_pre.data.supply, result_auto.data.supply)
        pd.testing.assert_frame_equal(result_pre.data.use, result_auto.data.use)


# ---------------------------------------------------------------------------
# Violations empty when all within tolerance
# ---------------------------------------------------------------------------


class TestViolationsEmpty:
    def test_empty_violations_when_all_in_tolerance(self, supply_df, use_df, cols):
        # Very wide tolerances: nothing is violated.
        targets = BalancingTargets(
            supply=pd.DataFrame({
                "year":  [2021],
                "trans": ["0100"],
                "brch":  ["X"],
                "bas":   [300.0],  # exact match → diff=0, tol=100 → no violation
            }),
            use=pd.DataFrame({
                "year":  [2021],
                "trans": ["3110"],
                "brch":  ["HH"],
                "koeb":  [78.0],  # exact match → diff=0
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
        result = inspect_balancing_targets(sut)
        assert isinstance(result.data.supply_violations, pd.DataFrame)
        assert len(result.data.supply_violations) == 0
        assert isinstance(result.data.use_violations, pd.DataFrame)
        assert len(result.data.use_violations) == 0


# ---------------------------------------------------------------------------
# Transaction / category filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_transactions_filter(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol, transactions="0100")
        assert len(result.data.supply) == 1
        assert result.data.supply.index.get_level_values(0)[0] == "0100"

    def test_categories_filter(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol, categories="HH")
        assert len(result.data.use) == 1
        # Category is level 1 in the 2-level (no-classifications) MultiIndex.
        assert result.data.use.index.get_level_values(1)[0] == "HH"


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


class TestSort:
    def test_sort_supply_by_abs_diff(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol, sort=True)
        # 0100/X diff=-60 (abs 60) should come before 0700/"" diff=NaN.
        first_trans = result.data.supply.index.get_level_values(0)[0]
        assert first_trans == "0100"

    def test_sort_use_by_abs_diff(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol, sort=True)
        # 3110/HH diff=-12 (abs 12) > 2000/X diff=-8 (abs 8).
        first_trans = result.data.use.index.get_level_values(0)[0]
        assert first_trans == "3110"


# ---------------------------------------------------------------------------
# MultiIndex structure (no classifications)
# ---------------------------------------------------------------------------


class TestMultiIndex:
    def test_supply_two_level_index(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert result.data.supply.index.nlevels == 2

    def test_use_two_level_index(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert result.data.use.index.nlevels == 2

    def test_supply_index_names(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert list(result.data.supply.index.names) == ["trans", "brch"]

    def test_use_index_names(self, sut_no_tol):
        result = inspect_balancing_targets(sut_no_tol)
        assert list(result.data.use.index.names) == ["trans", "brch"]


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
            inspect_balancing_targets(sut)

    def test_raises_no_balancing_id(self, supply_df, use_df, cols, targets):
        metadata = SUTMetadata(columns=cols)
        sut = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            balancing_targets=targets,
            metadata=metadata,
        )
        with pytest.raises(ValueError, match="balancing_id"):
            inspect_balancing_targets(sut)

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
            inspect_balancing_targets(sut)


# ---------------------------------------------------------------------------
# SUT method delegation
# ---------------------------------------------------------------------------


class TestSUTMethod:
    def test_method_matches_free_function(self, sut_with_tol):
        via_method = sut_with_tol.inspect_balancing_targets()
        via_function = inspect_balancing_targets(sut_with_tol)
        pd.testing.assert_frame_equal(via_method.data.supply, via_function.data.supply)
        pd.testing.assert_frame_equal(via_method.data.use, via_function.data.use)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------


class TestStyling:
    from pandas.io.formats.style import Styler as _Styler

    def test_supply_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_balancing_targets(sut_no_tol).supply, Styler)

    def test_use_property_returns_styler(self, sut_no_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_balancing_targets(sut_no_tol).use, Styler)

    def test_supply_violations_property_returns_styler_when_tolerances_set(self, sut_with_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_balancing_targets(sut_with_tol).supply_violations, Styler)

    def test_use_violations_property_returns_styler_when_tolerances_set(self, sut_with_tol):
        from pandas.io.formats.style import Styler
        assert isinstance(inspect_balancing_targets(sut_with_tol).use_violations, Styler)

    def test_supply_violations_property_returns_none_when_no_tolerances(self, sut_no_tol):
        assert inspect_balancing_targets(sut_no_tol).supply_violations is None

    def test_use_violations_property_returns_none_when_no_tolerances(self, sut_no_tol):
        assert inspect_balancing_targets(sut_no_tol).use_violations is None
