"""
Tests for inspect_unbalanced_products.
"""

import pytest
import pandas as pd
import numpy as np

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import (
    inspect_unbalanced_products,
    UnbalancedProductsInspection,
    UnbalancedProductsData,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
#
# Products in 2021:
#   A — supply_bas=120, use_bas=100 → diff_bas=+20   (unbalanced)
#   B — supply_bas=50,  use_bas=50  → diff_bas=0     (balanced)
#   C — supply_bas=0,   use_bas=30  → diff_bas=-30   (unbalanced, supply-only miss)
#   D — supply_bas=80,  use_bas=0   → diff_bas=+80, rel_bas=NaN (supply only, no use)
#
# Products in 2020:
#   A — supply_bas=90, use_bas=80 → diff_bas=+10     (unbalanced)
#
# Use has two price layers: ava (wholesale margins) and moms (vat).
# price_purchasers column: koeb
#
# With ids=2021, only 2021 data is used.
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
def supply():
    return pd.DataFrame({
        "year": [2021, 2021, 2021, 2021, 2020],
        "nrnr": ["A",  "B",  "D",  "A",  "A"],
        "trans": ["0100", "0100", "0100", "0700", "0100"],
        "brch": ["X", "X", "X", "", "X"],
        "bas":  [100.0, 50.0, 80.0, 20.0, 90.0],
        "koeb": [100.0, 50.0, 80.0, 20.0, 90.0],
    })


@pytest.fixture
def use():
    # 2021: A: bas=100, B: bas=50 (balanced), C: bas=30
    # 2020: A: bas=80
    # ava and moms present for context
    return pd.DataFrame({
        "year": [2021, 2021, 2021, 2020],
        "nrnr": ["A",  "B",  "C",  "A"],
        "trans": ["2000", "2000", "2000", "2000"],
        "brch": ["X", "X", "X", "X"],
        "bas":  [100.0, 50.0, 30.0, 80.0],
        "ava":  [5.0,   3.0,  2.0,  4.0],
        "moms": [10.0,  6.0,  4.0,  8.0],
        "koeb": [115.0, 59.0, 36.0, 92.0],
    })


@pytest.fixture
def sut(supply, use, cols):
    metadata = SUTMetadata(columns=cols)
    return SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
        balancing_id=2021,
    )


@pytest.fixture
def sut_no_balancing_id(supply, use, cols):
    metadata = SUTMetadata(columns=cols)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def sut_with_product_labels(supply, use, cols):
    products = pd.DataFrame({
        "nrnr":     ["A", "B", "C", "D"],
        "nrnr_txt": ["Agricultural goods", "Buildings", "Cars", "Digital services"],
    })
    classifications = SUTClassifications(products=products)
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    return SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
        balancing_id=2021,
    )


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_raises_when_no_metadata(supply, use):
    sut = SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=None,
        balancing_id=2021,
    )
    with pytest.raises(ValueError, match="sut.metadata is required"):
        inspect_unbalanced_products(sut)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_correct_types(sut):
    result = inspect_unbalanced_products(sut, ids=2021)
    assert isinstance(result, UnbalancedProductsInspection)
    assert isinstance(result.data, UnbalancedProductsData)
    assert isinstance(result.data.imbalances, pd.DataFrame)


# ---------------------------------------------------------------------------
# Balanced products are excluded; unbalanced are included
# ---------------------------------------------------------------------------


def test_balanced_product_excluded(sut):
    result = inspect_unbalanced_products(sut, ids=2021)
    products = result.data.imbalances.index.get_level_values("nrnr")
    assert "B" not in products


def test_unbalanced_products_included(sut):
    result = inspect_unbalanced_products(sut, ids=2021)
    products = result.data.imbalances.index.get_level_values("nrnr")
    assert "A" in products
    assert "C" in products
    assert "D" in products


def test_only_selected_id_member_used(sut):
    # A has supply_bas=120 (100+20) in 2021, use_bas=100 in 2021 → diff_bas=+20
    result = inspect_unbalanced_products(sut, ids=2021)
    row = result.data.imbalances.loc[(2021, "A")]
    assert row["supply_bas"] == 120.0
    assert row["use_bas"] == 100.0
    assert row["diff_bas"] == 20.0


def test_ids_filter_isolates_year(sut):
    # ids=2021 gives only 2021 rows; ids=2020 gives only 2020 rows
    result_2021 = inspect_unbalanced_products(sut, ids=2021)
    result_2020 = inspect_unbalanced_products(sut, ids=2020)
    ids_2021 = set(result_2021.data.imbalances.index.get_level_values("year"))
    ids_2020 = set(result_2020.data.imbalances.index.get_level_values("year"))
    assert ids_2021 == {2021}
    assert ids_2020 == {2020}


# ---------------------------------------------------------------------------
# Columns: diff, rel, price layers, purchasers
# ---------------------------------------------------------------------------


def test_diff_column(sut):
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.loc[(2021, "A"), "diff_bas"] == pytest.approx(20.0)
    assert df.loc[(2021, "C"), "diff_bas"] == pytest.approx(-30.0)
    assert df.loc[(2021, "D"), "diff_bas"] == pytest.approx(80.0)


def test_rel_column_normal(sut):
    # A: supply_bas=120, use_bas=100 → rel_bas = 120/100 - 1 = 0.2
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.loc[(2021, "A"), "rel_bas"] == pytest.approx(0.2)


def test_rel_column_nan_when_use_zero(sut):
    # D: use_bas=0 → rel_bas must be NaN
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert np.isnan(df.loc[(2021, "D"), "rel_bas"])


def test_price_layer_columns_present(sut):
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert "use_ava" in df.columns
    assert "use_moms" in df.columns


def test_price_layer_totals(sut):
    # A: ava=5, moms=10 in 2021
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.loc[(2021, "A"), "use_ava"] == pytest.approx(5.0)
    assert df.loc[(2021, "A"), "use_moms"] == pytest.approx(10.0)


def test_price_layer_zero_for_supply_only_product(sut):
    # D has no use rows → price layer totals are 0
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.loc[(2021, "D"), "use_ava"] == pytest.approx(0.0)
    assert df.loc[(2021, "D"), "use_moms"] == pytest.approx(0.0)


def test_purchasers_price_column_present(sut):
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert "use_koeb" in df.columns


def test_purchasers_price_totals(sut):
    # A: koeb=115 in 2021
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.loc[(2021, "A"), "use_koeb"] == pytest.approx(115.0)


def test_purchasers_price_zero_for_supply_only_product(sut):
    # D has no use rows → use_koeb = 0
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.loc[(2021, "D"), "use_koeb"] == pytest.approx(0.0)


def test_column_order(sut):
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    # First four fixed columns, then price layers, then purchasers
    assert list(df.columns[:4]) == ["diff_bas", "rel_bas", "supply_bas", "use_bas"]
    assert df.columns[-1] == "use_koeb"


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------


def test_tolerance_default_excludes_zero_diff(sut):
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    products = df.index.get_level_values("nrnr")
    assert "B" not in products


def test_tolerance_custom_filters_small_imbalances(sut):
    # A has diff_bas=20; with tolerance=25 it should be excluded
    # C has diff_bas=-30 (abs=30 > 25), D has diff_bas=80 → both stay
    df = inspect_unbalanced_products(sut, ids=2021, tolerance=25).data.imbalances
    products = df.index.get_level_values("nrnr")
    assert "A" not in products
    assert "C" in products
    assert "D" in products


def test_tolerance_zero_includes_all_nonzero(sut):
    df = inspect_unbalanced_products(sut, ids=2021, tolerance=0).data.imbalances
    # B is balanced (diff_bas=0), all others unbalanced
    products = df.index.get_level_values("nrnr")
    assert "B" not in products
    assert "A" in products


# ---------------------------------------------------------------------------
# Sort argument
# ---------------------------------------------------------------------------


def test_sort_false_preserves_natural_order(sut):
    df = inspect_unbalanced_products(sut, ids=2021, sort=False).data.imbalances
    # Natural order: A, C, D (within 2021)
    assert list(df.index.get_level_values("nrnr")) == ["A", "C", "D"]


def test_sort_true_orders_by_abs_diff_descending(sut):
    # abs diffs: A=20, C=30, D=80 → sorted: D, C, A (within 2021)
    df = inspect_unbalanced_products(sut, ids=2021, sort=True).data.imbalances
    assert list(df.index.get_level_values("nrnr")) == ["D", "C", "A"]


# ---------------------------------------------------------------------------
# products argument
# ---------------------------------------------------------------------------


def test_products_none_checks_all(sut):
    df = inspect_unbalanced_products(sut, ids=2021, products=None).data.imbalances
    assert set(df.index.get_level_values("nrnr")) == {"A", "C", "D"}


def test_products_pattern_restricts_check(sut):
    # Only check A and B — C and D not considered even though unbalanced
    df = inspect_unbalanced_products(sut, ids=2021, products=["A", "B"]).data.imbalances
    products = df.index.get_level_values("nrnr")
    assert "C" not in products
    assert "D" not in products
    assert "A" in products


def test_products_wildcard_pattern(sut):
    # Pattern "A*" matches only A
    df = inspect_unbalanced_products(sut, ids=2021, products="A*").data.imbalances
    assert list(df.index.get_level_values("nrnr")) == ["A"]


def test_products_string_shorthand(sut):
    df_str = inspect_unbalanced_products(sut, ids=2021, products="A").data.imbalances
    df_list = inspect_unbalanced_products(sut, ids=2021, products=["A"]).data.imbalances
    pd.testing.assert_frame_equal(df_str, df_list)


# ---------------------------------------------------------------------------
# Index: always MultiIndex with id as outermost level
# ---------------------------------------------------------------------------


def test_index_is_multiindex(sut):
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert isinstance(df.index, pd.MultiIndex)


def test_index_nlevels_without_labels(sut):
    # Without product labels: 2 levels (year, nrnr)
    df = inspect_unbalanced_products(sut, ids=2021).data.imbalances
    assert df.index.nlevels == 2
    assert df.index.names[0] == "year"
    assert df.index.names[1] == "nrnr"


def test_index_nlevels_with_labels(sut_with_product_labels):
    # With product labels: 3 levels (year, nrnr, nrnr_txt)
    df = inspect_unbalanced_products(sut_with_product_labels, ids=2021).data.imbalances
    assert isinstance(df.index, pd.MultiIndex)
    assert df.index.names == ["year", "nrnr", "nrnr_txt"]


def test_multiindex_labels_correct(sut_with_product_labels):
    df = inspect_unbalanced_products(sut_with_product_labels, ids=2021).data.imbalances
    # A → "Agricultural goods", C → "Cars", D → "Digital services"
    labels = {t[1]: t[2] for t in df.index.tolist()}
    assert labels["A"] == "Agricultural goods"
    assert labels["C"] == "Cars"
    assert labels["D"] == "Digital services"


def test_multiindex_missing_label_is_empty_string(sut_with_product_labels, supply, use, cols):
    # Build sut where product E has no label entry
    extra_supply = pd.concat([
        supply,
        pd.DataFrame({
            "year": [2021], "nrnr": ["E"], "trans": ["0100"],
            "brch": ["X"], "bas": [99.0], "koeb": [99.0],
        })
    ], ignore_index=True)
    products = pd.DataFrame({
        "nrnr":     ["A", "B", "C", "D"],
        "nrnr_txt": ["Agricultural goods", "Buildings", "Cars", "Digital services"],
    })
    classifications = SUTClassifications(products=products)
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    sut_e = SUT(
        price_basis="current_year",
        supply=extra_supply,
        use=use,
        metadata=metadata,
        balancing_id=2021,
    )
    df = inspect_unbalanced_products(sut_e, ids=2021).data.imbalances
    labels = {t[1]: t[2] for t in df.index.tolist()}
    assert labels["E"] == ""


# ---------------------------------------------------------------------------
# No price layers in metadata → only fixed columns plus purchasers
# ---------------------------------------------------------------------------


def test_no_price_layer_columns_when_none_in_metadata(supply, use):
    cols_no_layers = SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
    )
    metadata = SUTMetadata(columns=cols_no_layers)
    sut_plain = SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
        balancing_id=2021,
    )
    df = inspect_unbalanced_products(sut_plain, ids=2021).data.imbalances
    assert list(df.columns) == ["diff_bas", "rel_bas", "supply_bas", "use_bas", "use_koeb"]


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


def test_summary_shape(sut):
    summary = inspect_unbalanced_products(sut, ids=2021).data.summary
    assert summary.shape == (1, 2)
    assert list(summary.columns) == ["n_unbalanced", "largest_diff"]
    assert summary.index.name == "table"
    assert list(summary.index) == ["imbalances"]


def test_summary_n_unbalanced(sut):
    # Default tolerance=1: A (diff=20), C (diff=-30), D (diff=80) are unbalanced
    summary = inspect_unbalanced_products(sut, ids=2021).data.summary
    assert summary.loc["imbalances", "n_unbalanced"] == 3


def test_summary_largest_diff_is_signed(sut):
    # D has the largest abs diff (80), and it is positive
    summary = inspect_unbalanced_products(sut, ids=2021).data.summary
    assert summary.loc["imbalances", "largest_diff"] == pytest.approx(80.0)


def test_summary_largest_diff_signed_negative(sut):
    # With products=["C"] only C remains (diff=-30); largest_diff should be -30
    summary = inspect_unbalanced_products(sut, ids=2021, products=["C"]).data.summary
    assert summary.loc["imbalances", "largest_diff"] == pytest.approx(-30.0)


def test_summary_nan_when_all_balanced(sut):
    # Tolerance=100 excludes all products → largest_diff is NaN
    summary = inspect_unbalanced_products(sut, ids=2021, tolerance=100).data.summary
    assert summary.loc["imbalances", "n_unbalanced"] == 0
    assert np.isnan(summary.loc["imbalances", "largest_diff"])


def test_summary_respects_tolerance(sut):
    # tolerance=25: only C (abs=30) and D (abs=80) remain → n=2
    summary = inspect_unbalanced_products(sut, ids=2021, tolerance=25).data.summary
    assert summary.loc["imbalances", "n_unbalanced"] == 2


# ---------------------------------------------------------------------------
# ids=None: includes all years; summary collapses across ids
# ---------------------------------------------------------------------------


class TestMultipleIds:
    def test_ids_none_includes_both_years(self, sut):
        result = inspect_unbalanced_products(sut)
        id_values = set(result.data.imbalances.index.get_level_values("year"))
        assert 2021 in id_values
        assert 2020 in id_values

    def test_ids_2021_gives_only_2021(self, sut):
        result = inspect_unbalanced_products(sut, ids=2021)
        id_values = set(result.data.imbalances.index.get_level_values("year"))
        assert id_values == {2021}

    def test_ids_2020_gives_only_2020(self, sut):
        result = inspect_unbalanced_products(sut, ids=2020)
        id_values = set(result.data.imbalances.index.get_level_values("year"))
        assert id_values == {2020}

    def test_ids_2020_product_a_diff(self, sut):
        # 2020: A supply=90, use=80 → diff=10
        result = inspect_unbalanced_products(sut, ids=2020)
        row = result.data.imbalances.loc[(2020, "A")]
        assert row["diff_bas"] == pytest.approx(10.0)

    def test_summary_n_unbalanced_all_ids(self, sut):
        # ids=None: 2021 has 3 (A, C, D), 2020 has 1 (A) → total 4
        result = inspect_unbalanced_products(sut)
        assert result.data.summary.loc["imbalances", "n_unbalanced"] == 4

    def test_summary_largest_diff_across_ids(self, sut):
        # ids=None: largest abs diff is D in 2021 with +80
        result = inspect_unbalanced_products(sut)
        assert result.data.summary.loc["imbalances", "largest_diff"] == pytest.approx(80.0)
