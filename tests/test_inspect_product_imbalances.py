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
# Products:
#   A — supply_bas=120, use_bas=100 → diff_bas=+20   (unbalanced)
#   B — supply_bas=50,  use_bas=50  → diff_bas=0     (balanced)
#   C — supply_bas=0,   use_bas=30  → diff_bas=-30   (unbalanced, supply-only miss)
#   D — supply_bas=80,  use_bas=0   → diff_bas=+80, rel_bas=NaN (supply only, no use)
#
# Use has two price layers: ava (wholesale margins) and moms (vat).
# price_purchasers column: koeb
#
# balancing_id = 2021; 2020 rows are context and must not affect results.
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
    # A: bas=100, B: bas=50 (balanced), C: bas=30
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


def test_raises_when_no_balancing_id(sut_no_balancing_id):
    with pytest.raises(ValueError, match="sut.balancing_id is not set"):
        inspect_unbalanced_products(sut_no_balancing_id)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_correct_types(sut):
    result = inspect_unbalanced_products(sut)
    assert isinstance(result, UnbalancedProductsInspection)
    assert isinstance(result.data, UnbalancedProductsData)
    assert isinstance(result.data.imbalances, pd.DataFrame)


# ---------------------------------------------------------------------------
# Balanced products are excluded; unbalanced are included
# ---------------------------------------------------------------------------


def test_balanced_product_excluded(sut):
    result = inspect_unbalanced_products(sut)
    assert "B" not in result.data.imbalances.index


def test_unbalanced_products_included(sut):
    result = inspect_unbalanced_products(sut)
    idx = result.data.imbalances.index
    assert "A" in idx
    assert "C" in idx
    assert "D" in idx


def test_only_balancing_id_member_used(sut):
    # A has supply_bas=120 (100+20) in 2021, use_bas=100 in 2021 → diff_bas=+20
    result = inspect_unbalanced_products(sut)
    row = result.data.imbalances.loc["A"]
    assert row["supply_bas"] == 120.0
    assert row["use_bas"] == 100.0
    assert row["diff_bas"] == 20.0


# ---------------------------------------------------------------------------
# Columns: diff, rel, price layers, purchasers
# ---------------------------------------------------------------------------


def test_diff_column(sut):
    df = inspect_unbalanced_products(sut).data.imbalances
    assert df.loc["A", "diff_bas"] == pytest.approx(20.0)
    assert df.loc["C", "diff_bas"] == pytest.approx(-30.0)
    assert df.loc["D", "diff_bas"] == pytest.approx(80.0)


def test_rel_column_normal(sut):
    # A: supply_bas=120, use_bas=100 → rel_bas = 120/100 - 1 = 0.2
    df = inspect_unbalanced_products(sut).data.imbalances
    assert df.loc["A", "rel_bas"] == pytest.approx(0.2)


def test_rel_column_nan_when_use_zero(sut):
    # D: use_bas=0 → rel_bas must be NaN
    df = inspect_unbalanced_products(sut).data.imbalances
    assert np.isnan(df.loc["D", "rel_bas"])


def test_price_layer_columns_present(sut):
    df = inspect_unbalanced_products(sut).data.imbalances
    assert "use_ava" in df.columns
    assert "use_moms" in df.columns


def test_price_layer_totals(sut):
    # A: ava=5, moms=10 in 2021
    df = inspect_unbalanced_products(sut).data.imbalances
    assert df.loc["A", "use_ava"] == pytest.approx(5.0)
    assert df.loc["A", "use_moms"] == pytest.approx(10.0)


def test_price_layer_zero_for_supply_only_product(sut):
    # D has no use rows → price layer totals are 0
    df = inspect_unbalanced_products(sut).data.imbalances
    assert df.loc["D", "use_ava"] == pytest.approx(0.0)
    assert df.loc["D", "use_moms"] == pytest.approx(0.0)


def test_purchasers_price_column_present(sut):
    df = inspect_unbalanced_products(sut).data.imbalances
    assert "use_koeb" in df.columns


def test_purchasers_price_totals(sut):
    # A: koeb=115 in 2021
    df = inspect_unbalanced_products(sut).data.imbalances
    assert df.loc["A", "use_koeb"] == pytest.approx(115.0)


def test_purchasers_price_zero_for_supply_only_product(sut):
    # D has no use rows → use_koeb = 0
    df = inspect_unbalanced_products(sut).data.imbalances
    assert df.loc["D", "use_koeb"] == pytest.approx(0.0)


def test_column_order(sut):
    df = inspect_unbalanced_products(sut).data.imbalances
    # First four fixed columns, then price layers, then purchasers
    assert list(df.columns[:4]) == ["diff_bas", "rel_bas", "supply_bas", "use_bas"]
    assert df.columns[-1] == "use_koeb"


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------


def test_tolerance_default_excludes_zero_diff(sut):
    df = inspect_unbalanced_products(sut).data.imbalances
    assert "B" not in df.index


def test_tolerance_custom_filters_small_imbalances(sut):
    # A has diff_bas=20; with tolerance=25 it should be excluded
    # C has diff_bas=-30 (abs=30 > 25), D has diff_bas=80 → both stay
    df = inspect_unbalanced_products(sut, tolerance=25).data.imbalances
    assert "A" not in df.index
    assert "C" in df.index
    assert "D" in df.index


def test_tolerance_zero_includes_all_nonzero(sut):
    df = inspect_unbalanced_products(sut, tolerance=0).data.imbalances
    # B is balanced (diff_bas=0), all others unbalanced
    assert "B" not in df.index
    assert "A" in df.index


# ---------------------------------------------------------------------------
# Sort argument
# ---------------------------------------------------------------------------


def test_sort_false_preserves_natural_order(sut):
    df = inspect_unbalanced_products(sut, sort=False).data.imbalances
    # Natural order: A, C, D
    assert list(df.index) == ["A", "C", "D"]


def test_sort_true_orders_by_abs_diff_descending(sut):
    # abs diffs: A=20, C=30, D=80 → sorted: D, C, A
    df = inspect_unbalanced_products(sut, sort=True).data.imbalances
    assert list(df.index) == ["D", "C", "A"]


# ---------------------------------------------------------------------------
# products argument
# ---------------------------------------------------------------------------


def test_products_none_checks_all(sut):
    df = inspect_unbalanced_products(sut, products=None).data.imbalances
    assert set(df.index) == {"A", "C", "D"}


def test_products_pattern_restricts_check(sut):
    # Only check A and B — C and D not considered even though unbalanced
    df = inspect_unbalanced_products(sut, products=["A", "B"]).data.imbalances
    assert "C" not in df.index
    assert "D" not in df.index
    assert "A" in df.index


def test_products_wildcard_pattern(sut):
    # Pattern "A*" matches only A
    df = inspect_unbalanced_products(sut, products="A*").data.imbalances
    assert list(df.index) == ["A"]


def test_products_string_shorthand(sut):
    df_str = inspect_unbalanced_products(sut, products="A").data.imbalances
    df_list = inspect_unbalanced_products(sut, products=["A"]).data.imbalances
    pd.testing.assert_frame_equal(df_str, df_list)


# ---------------------------------------------------------------------------
# Index: simple vs MultiIndex
# ---------------------------------------------------------------------------


def test_index_simple_when_no_product_labels(sut):
    df = inspect_unbalanced_products(sut).data.imbalances
    assert not isinstance(df.index, pd.MultiIndex)
    assert df.index.name == "nrnr"


def test_index_multiindex_when_product_labels_available(sut_with_product_labels):
    df = inspect_unbalanced_products(sut_with_product_labels).data.imbalances
    assert isinstance(df.index, pd.MultiIndex)
    assert df.index.names == ["nrnr", "nrnr_txt"]


def test_multiindex_labels_correct(sut_with_product_labels):
    df = inspect_unbalanced_products(sut_with_product_labels).data.imbalances
    # A → "Agricultural goods", C → "Cars", D → "Digital services"
    labels = dict(df.index.tolist())
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
    df = inspect_unbalanced_products(sut_e).data.imbalances
    labels = dict(df.index.tolist())
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
    df = inspect_unbalanced_products(sut_plain).data.imbalances
    assert list(df.columns) == ["diff_bas", "rel_bas", "supply_bas", "use_bas", "use_koeb"]
