"""
Tests for set_display_index on inspection result classes.
"""

import pytest
import pandas as pd

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import ProductInspection, inspect_products


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def columns():
    return SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
    )


@pytest.fixture
def transactions():
    return pd.DataFrame({
        "trans":     ["0100", "2000", "6001"],
        "trans_txt": ["Output", "IC", "Exports"],
        "table":     ["supply", "use", "use"],
        "esa_code":  ["P1", "P2", "P6"],
    })


@pytest.fixture
def supply():
    return pd.DataFrame({
        "year":  [2020, 2020, 2021, 2021],
        "nrnr":  ["A",  "B",  "A",  "B"],
        "trans": ["0100", "0100", "0100", "0100"],
        "brch":  ["X",   "Y",   "X",   "Y"],
        "bas":   [100.0, 50.0, 110.0, 55.0],
        "koeb":  [100.0, 50.0, 110.0, 55.0],
    })


@pytest.fixture
def use():
    return pd.DataFrame({
        "year":  [2020, 2020, 2020, 2020, 2021, 2021, 2021, 2021],
        "nrnr":  ["A",  "A",  "B",  "B",  "A",  "A",  "B",  "B"],
        "trans": ["2000", "6001", "2000", "6001", "2000", "6001", "2000", "6001"],
        "brch":  ["X",   "",    "Y",   "",    "X",   "",    "Y",   ""],
        "bas":   [60.0,  40.0,  30.0,  20.0,  65.0,  45.0,  33.0,  22.0],
        "koeb":  [60.0,  40.0,  30.0,  20.0,  65.0,  45.0,  33.0,  22.0],
    })


@pytest.fixture
def sut(supply, use, columns, transactions):
    classifications = SUTClassifications(transactions=transactions)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def inspection(sut):
    return inspect_products(sut, products=["A", "B"])


# ---------------------------------------------------------------------------
# Return type and identity
# ---------------------------------------------------------------------------


def test_returns_new_product_inspection(inspection):
    result = inspection.set_display_index("transaction", "2000")
    assert isinstance(result, ProductInspection)
    assert result is not inspection


def test_preserves_display_settings(inspection):
    tweaked = inspection.set_display_unit(1000).set_display_rel_base(1000).set_display_decimals(2)
    result = tweaked.set_display_index("transaction", "2000")
    assert result.display_configuration.display_unit == 1000
    assert result.display_configuration.rel_base == 1000
    assert result.display_configuration.decimals == 2


# ---------------------------------------------------------------------------
# Filtering by transaction level
# ---------------------------------------------------------------------------


def test_exact_match_filters_transaction_level(inspection):
    result = inspection.set_display_index("transaction", "2000")
    trans_vals = result.use.data.index.get_level_values("transaction")
    # Total rows (empty string) are also present — only data rows with "2000" remain
    data_rows = trans_vals[trans_vals != ""]
    assert set(data_rows) == {"2000"}


def test_list_of_values_keeps_multiple_transactions(inspection):
    result = inspection.set_display_index("transaction", ["2000", "6001"])
    trans_vals = result.use.data.index.get_level_values("transaction")
    data_rows = set(trans_vals[trans_vals != ""])
    assert data_rows == {"2000", "6001"}


def test_wildcard_pattern(inspection):
    # "2*" should match "2000" but not "6001" or "0100"
    result = inspection.set_display_index("transaction", "2*")
    trans_vals = result.use.data.index.get_level_values("transaction")
    data_rows = set(trans_vals[trans_vals != ""])
    assert data_rows == {"2000"}


def test_negation_pattern(inspection):
    # "~6001" should exclude "6001"
    result = inspection.set_display_index("transaction", "~6001")
    trans_vals = result.use.data.index.get_level_values("transaction")
    assert "6001" not in set(trans_vals)


# ---------------------------------------------------------------------------
# Filtering by product level
# ---------------------------------------------------------------------------


def test_filters_product_level(inspection):
    result = inspection.set_display_index("product", "A")
    # balance is protected — filtering does not apply to it
    for field_name in ("supply", "use"):
        styled = getattr(result, field_name)
        prod_vals = styled.data.index.get_level_values("product")
        assert set(prod_vals) == {"A"}, f"field {field_name!r} still has unexpected products"


# ---------------------------------------------------------------------------
# Tables without the named level are unchanged
# ---------------------------------------------------------------------------


def test_unknown_level_leaves_tables_unchanged(inspection):
    original_balance_shape = inspection.balance.data.shape
    result = inspection.set_display_index("nonexistent_level", "2000")
    assert result.balance.data.shape == original_balance_shape


def test_level_absent_from_some_tables_skips_them(inspection):
    # balance table has no "price_layer" level — filtering by it should leave balance unchanged
    original_balance_shape = inspection.balance.data.shape
    result = inspection.set_display_index("price_layer", "somevalue")
    assert result.balance.data.shape == original_balance_shape


# ---------------------------------------------------------------------------
# Integer values are stringified for matching
# ---------------------------------------------------------------------------


def test_integer_value_matches_string_pattern(sut, columns):
    # id values (years) appear as index levels in UnbalancedProductsInspection
    from sutlab.inspect import inspect_unbalanced_products, UnbalancedProductsInspection
    # Introduce a deliberate imbalance
    supply_unbal = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A", "A"],
        "trans": ["0100", "0100"],
        "brch":  ["X", "X"],
        "bas":   [100.0, 200.0],
        "koeb":  [100.0, 200.0],
    })
    use_unbal = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A", "A"],
        "trans": ["2000", "2000"],
        "brch":  ["X", "X"],
        "bas":   [50.0, 50.0],
        "koeb":  [50.0, 50.0],
    })
    from sutlab.sut import SUTClassifications, SUTMetadata
    from sutlab.inspect._balancing_targets import UnbalancedTargetsData
    metadata = SUTMetadata(columns=columns)
    sut_unbal = SUT(price_basis="current_year", supply=supply_unbal, use=use_unbal, metadata=metadata)
    result = inspect_unbalanced_products(sut_unbal)
    assert isinstance(result, UnbalancedProductsInspection)

    filtered = result.set_display_index("year", 2020)
    id_vals = filtered.imbalances.data.index.get_level_values("year")
    assert set(id_vals) == {2020}
    assert 2021 not in set(id_vals)


def test_string_pattern_for_integer_id(sut, columns):
    from sutlab.inspect import inspect_unbalanced_products
    supply_unbal = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A", "A"],
        "trans": ["0100", "0100"],
        "brch":  ["X", "X"],
        "bas":   [100.0, 200.0],
        "koeb":  [100.0, 200.0],
    })
    use_unbal = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A", "A"],
        "trans": ["2000", "2000"],
        "brch":  ["X", "X"],
        "bas":   [50.0, 50.0],
        "koeb":  [50.0, 50.0],
    })
    metadata = SUTMetadata(columns=columns)
    sut_unbal = SUT(price_basis="current_year", supply=supply_unbal, use=use_unbal, metadata=metadata)
    result = inspect_unbalanced_products(sut_unbal)

    # Pass year as string — should still match the integer index level
    filtered = result.set_display_index("year", "2020")
    id_vals = filtered.imbalances.data.index.get_level_values("year")
    assert set(id_vals) == {2020}
