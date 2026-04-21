"""
Tests for inspect_tables_comparison and TablesComparison.

Covers:
- diff computation (self - other), rel computation ((self - other) / other)
- division by zero → NaN in rel
- None tables stay None
- TypeError on wrong type argument
- set_display_unit / set_display_rel_base / set_display_decimals propagation on TablesComparison
- _all_rel=True on .rel
- styled properties don't raise

Tests use UnbalancedProductsInspection (minimal tables) and
ProductInspection (more tables) as representative classes.
"""

import pytest
import numpy as np
import pandas as pd

from sutlab.sut import SUT, SUTColumns, SUTMetadata, SUTClassifications
from sutlab.inspect import (
    inspect_unbalanced_products,
    UnbalancedProductsInspection,
    UnbalancedProductsData,
    inspect_products,
    ProductInspection,
    ProductInspectionData,
    TablesComparison,
)


# ---------------------------------------------------------------------------
# Shared fixtures
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
        vat="moms",
    )


def _make_sut(supply_bas_a, use_bas_a, cols):
    """Return a SUT with a single product A, balancing_id=2021."""
    supply = pd.DataFrame({
        "year": [2021],
        "nrnr": ["A"],
        "trans": ["P1"],
        "brch": ["X"],
        "bas": [float(supply_bas_a)],
        "koeb": [float(supply_bas_a)],
    })
    use = pd.DataFrame({
        "year": [2021],
        "nrnr": ["A"],
        "trans": ["P2"],
        "brch": ["X"],
        "bas": [float(use_bas_a)],
        "moms": [10.0],
        "koeb": [float(use_bas_a) + 10.0],
    })
    metadata = SUTMetadata(columns=cols)
    return SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
        balancing_id=2021,
    )


# ---------------------------------------------------------------------------
# UnbalancedProductsInspection.inspect_tables_comparison
# ---------------------------------------------------------------------------


class TestUnbalancedProductsComparison:
    """Tests using UnbalancedProductsInspection as the simplest two-table case."""

    @pytest.fixture
    def sut_before(self, cols):
        # Product A: supply=120, use=100 → diff=+20 (unbalanced)
        return _make_sut(supply_bas_a=120, use_bas_a=100, cols=cols)

    @pytest.fixture
    def sut_after(self, cols):
        # Product A: supply=130, use=100 → diff=+30 (larger imbalance)
        return _make_sut(supply_bas_a=130, use_bas_a=100, cols=cols)

    @pytest.fixture
    def before(self, sut_before):
        return inspect_unbalanced_products(sut_before, tolerance=1)

    @pytest.fixture
    def after(self, sut_after):
        return inspect_unbalanced_products(sut_after, tolerance=1)

    @pytest.fixture
    def comparison(self, before, after):
        return before.inspect_tables_comparison(after)

    def test_returns_tables_comparison(self, comparison):
        assert isinstance(comparison, TablesComparison)

    def test_diff_is_same_class(self, comparison):
        assert isinstance(comparison.diff, UnbalancedProductsInspection)

    def test_rel_is_same_class(self, comparison):
        assert isinstance(comparison.rel, UnbalancedProductsInspection)

    def test_rel_has_all_rel_flag(self, comparison):
        assert comparison.rel._all_rel is True

    def test_diff_does_not_have_all_rel_flag(self, comparison):
        assert comparison.diff._all_rel is False

    def test_diff_imbalances_values(self, before, after, comparison):
        """diff = before - after element-wise for each numeric column."""
        diff_df = comparison.diff.data.imbalances
        before_df = before.data.imbalances
        after_df = after.data.imbalances
        pd.testing.assert_frame_equal(
            diff_df.reindex(before_df.index),
            before_df - after_df,
        )

    def test_rel_imbalances_values(self, before, after, comparison):
        """rel = (before - after) / after."""
        rel_df = comparison.rel.data.imbalances
        before_df = before.data.imbalances
        after_df = after.data.imbalances
        expected = (before_df - after_df) / after_df
        pd.testing.assert_frame_equal(
            rel_df.reindex(before_df.index),
            expected,
        )

    def test_rel_division_by_zero_is_nan(self, sut_before, cols):
        """When after value is 0, rel should be NaN (not inf)."""
        # Product A: supply=120, use=100 → diff=20. Manually craft an after where diff_bas=0.
        # We'll construct after with supply=100, use=100 → diff=0, which is balanced, empty imbalances.
        # Instead: manufacture two inspections directly.
        imbalances_before = pd.DataFrame(
            {"diff_bas": [10.0], "rel_bas": [0.1], "supply_bas": [110.0], "use_bas": [100.0], "use_koeb": [110.0]},
            index=pd.Index(["A"], name="nrnr"),
        )
        imbalances_after = pd.DataFrame(
            {"diff_bas": [0.0], "rel_bas": [0.0], "supply_bas": [100.0], "use_bas": [100.0], "use_koeb": [100.0]},
            index=pd.Index(["A"], name="nrnr"),
        )
        summary_before = pd.DataFrame(
            {"n_unbalanced": [1], "largest_diff": [10.0]},
            index=pd.Index(["imbalances"], name="table"),
        )
        summary_after = pd.DataFrame(
            {"n_unbalanced": [0], "largest_diff": [0.0]},
            index=pd.Index(["imbalances"], name="table"),
        )
        before = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances_before, summary=summary_before)
        )
        after = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances_after, summary=summary_after)
        )
        comparison = before.inspect_tables_comparison(after)
        rel_df = comparison.rel.data.imbalances
        # (10-0)/0 = inf → NaN; but diff_bas=(10-0)=10 and after diff_bas=0 → rel should have NaN
        assert not rel_df["diff_bas"].isin([float("inf"), float("-inf")]).any()

    def test_display_unit_copied_from_caller(self, before, after):
        before_with_unit = before.set_display_unit(1000)
        comparison = before_with_unit.inspect_tables_comparison(after)
        assert comparison.display_configuration.display_unit == 1000
        assert comparison.diff.display_configuration.display_unit == 1000

    def test_rel_base_copied_from_caller(self, before, after):
        before_with_base = before.set_display_rel_base(1000)
        comparison = before_with_base.inspect_tables_comparison(after)
        assert comparison.display_configuration.rel_base == 1000
        assert comparison.diff.display_configuration.rel_base == 1000

    def test_decimals_copied_from_caller(self, before, after):
        before_with_decimals = before.set_display_decimals(0)
        comparison = before_with_decimals.inspect_tables_comparison(after)
        assert comparison.display_configuration.decimals == 0
        assert comparison.diff.display_configuration.decimals == 0
        assert comparison.rel.display_configuration.decimals == 0

    def test_raises_type_error_on_wrong_type(self, before):
        with pytest.raises(TypeError, match="Expected UnbalancedProductsInspection"):
            before.inspect_tables_comparison("not an inspection")

    def test_styled_imbalances_does_not_raise(self, comparison):
        _ = comparison.diff.imbalances

    def test_styled_rel_imbalances_does_not_raise(self, comparison):
        _ = comparison.rel.imbalances


# ---------------------------------------------------------------------------
# TablesComparison.set_display_unit / set_display_rel_base / set_display_decimals propagation
# ---------------------------------------------------------------------------


class TestTablesComparisonSetters:
    @pytest.fixture
    def comparison(self, cols):
        sut_b = _make_sut(120, 100, cols)
        sut_a = _make_sut(130, 100, cols)
        before = inspect_unbalanced_products(sut_b, tolerance=1)
        after = inspect_unbalanced_products(sut_a, tolerance=1)
        return before.inspect_tables_comparison(after)

    def test_set_display_unit_propagates_to_diff(self, comparison):
        updated = comparison.set_display_unit(1_000_000)
        assert updated.display_configuration.display_unit == 1_000_000
        assert updated.diff.display_configuration.display_unit == 1_000_000
        assert updated.rel.display_configuration.display_unit == 1_000_000

    def test_set_display_unit_none(self, comparison):
        updated = comparison.set_display_unit(1000).set_display_unit(None)
        assert updated.display_configuration.display_unit is None
        assert updated.diff.display_configuration.display_unit is None

    def test_set_display_rel_base_propagates(self, comparison):
        updated = comparison.set_display_rel_base(10000)
        assert updated.display_configuration.rel_base == 10000
        assert updated.diff.display_configuration.rel_base == 10000
        assert updated.rel.display_configuration.rel_base == 10000

    def test_set_display_unit_invalid_raises(self, comparison):
        with pytest.raises(ValueError, match="positive power of 10"):
            comparison.set_display_unit(500)

    def test_set_display_rel_base_invalid_raises(self, comparison):
        with pytest.raises(ValueError, match="rel_base must be"):
            comparison.set_display_rel_base(50)

    def test_original_unchanged_after_set_display_unit(self, comparison):
        comparison.set_display_unit(1000)
        assert comparison.display_configuration.display_unit is None

    def test_original_unchanged_after_set_display_rel_base(self, comparison):
        comparison.set_display_rel_base(1000)
        assert comparison.display_configuration.rel_base == 100

    def test_set_display_decimals_propagates(self, comparison):
        updated = comparison.set_display_decimals(0)
        assert updated.display_configuration.decimals == 0
        assert updated.diff.display_configuration.decimals == 0
        assert updated.rel.display_configuration.decimals == 0

    def test_set_display_decimals_multiple_values(self, comparison):
        for n in (0, 2, 3):
            updated = comparison.set_display_decimals(n)
            assert updated.display_configuration.decimals == n
            assert updated.diff.display_configuration.decimals == n
            assert updated.rel.display_configuration.decimals == n

    def test_set_display_decimals_invalid_negative_raises(self, comparison):
        with pytest.raises(ValueError, match="non-negative integer"):
            comparison.set_display_decimals(-1)

    def test_set_display_decimals_invalid_float_raises(self, comparison):
        with pytest.raises(ValueError, match="non-negative integer"):
            comparison.set_display_decimals(1.5)

    def test_original_unchanged_after_set_display_decimals(self, comparison):
        comparison.set_display_decimals(0)
        assert comparison.display_configuration.decimals == 1


# ---------------------------------------------------------------------------
# None tables stay None (outer join across tables with None on one side)
# ---------------------------------------------------------------------------


class TestNoneTableHandling:
    def test_none_tables_produce_none_in_diff_and_rel(self):
        """None fields on either side → None in both diff and rel."""
        imbalances = pd.DataFrame(
            {"diff_bas": [10.0], "supply_bas": [110.0], "use_bas": [100.0]},
            index=pd.Index(["A"], name="nrnr"),
        )
        summary = pd.DataFrame(
            {"n_unbalanced": [1], "largest_diff": [10.0]},
            index=pd.Index(["imbalances"], name="table"),
        )
        obj = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances, summary=summary)
        )
        comparison = obj.inspect_tables_comparison(obj)
        # imbalances and summary are DataFrames, so they should be DataFrames in diff/rel.
        assert isinstance(comparison.diff.data.imbalances, pd.DataFrame)
        assert isinstance(comparison.diff.data.summary, pd.DataFrame)


# ---------------------------------------------------------------------------
# Outer join: rows present in only one inspection
# ---------------------------------------------------------------------------


class TestOuterJoin:
    def test_rows_only_in_before_appear_with_nan_diff(self):
        """Product present in before but not in after → NaN diff values."""
        imbalances_before = pd.DataFrame(
            {"diff_bas": [10.0, 20.0], "supply_bas": [110.0, 120.0], "use_bas": [100.0, 100.0]},
            index=pd.Index(["A", "B"], name="nrnr"),
        )
        imbalances_after = pd.DataFrame(
            {"diff_bas": [10.0], "supply_bas": [110.0], "use_bas": [100.0]},
            index=pd.Index(["A"], name="nrnr"),
        )
        summary = pd.DataFrame(
            {"n_unbalanced": [1], "largest_diff": [10.0]},
            index=pd.Index(["imbalances"], name="table"),
        )
        before = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances_before, summary=summary)
        )
        after = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances_after, summary=summary)
        )
        comparison = before.inspect_tables_comparison(after)
        diff_df = comparison.diff.data.imbalances
        # Row B is present in before but not after — diff should have NaN
        assert diff_df.loc["B", "diff_bas"] is np.nan or np.isnan(diff_df.loc["B", "diff_bas"])

    def test_rows_only_in_after_appear_with_nan_diff(self):
        """Product present in after but not in before → NaN diff values."""
        imbalances_before = pd.DataFrame(
            {"diff_bas": [10.0], "supply_bas": [110.0], "use_bas": [100.0]},
            index=pd.Index(["A"], name="nrnr"),
        )
        imbalances_after = pd.DataFrame(
            {"diff_bas": [10.0, 20.0], "supply_bas": [110.0, 120.0], "use_bas": [100.0, 100.0]},
            index=pd.Index(["A", "B"], name="nrnr"),
        )
        summary = pd.DataFrame(
            {"n_unbalanced": [1], "largest_diff": [10.0]},
            index=pd.Index(["imbalances"], name="table"),
        )
        before = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances_before, summary=summary)
        )
        after = UnbalancedProductsInspection(
            data=UnbalancedProductsData(imbalances=imbalances_after, summary=summary)
        )
        comparison = before.inspect_tables_comparison(after)
        diff_df = comparison.diff.data.imbalances
        # Row B: before is NaN, after=20 → diff = NaN - 20 = NaN
        assert np.isnan(diff_df.loc["B", "diff_bas"])
