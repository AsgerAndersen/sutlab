"""
Tests for set_display_sort_ids_ascending on inspection result classes.
"""

import pytest
import pandas as pd

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import (
    ProductInspection,
    inspect_products,
    inspect_unbalanced_products,
    UnbalancedProductsInspection,
)


# ---------------------------------------------------------------------------
# Shared fixtures
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
        "trans":     ["0100", "2000"],
        "trans_txt": ["Output", "IC"],
        "table":     ["supply", "use"],
        "esa_code":  ["P1", "P2"],
    })


@pytest.fixture
def supply_3yr():
    return pd.DataFrame({
        "year":  [2019, 2019, 2020, 2020, 2021, 2021],
        "nrnr":  ["A",  "B",  "A",  "B",  "A",  "B"],
        "trans": ["0100"] * 6,
        "brch":  ["X"] * 6,
        "bas":   [100.0, 50.0, 110.0, 55.0, 120.0, 60.0],
        "koeb":  [100.0, 50.0, 110.0, 55.0, 120.0, 60.0],
    })


@pytest.fixture
def use_3yr():
    return pd.DataFrame({
        "year":  [2019, 2019, 2020, 2020, 2021, 2021],
        "nrnr":  ["A",  "B",  "A",  "B",  "A",  "B"],
        "trans": ["2000"] * 6,
        "brch":  ["X"] * 6,
        "bas":   [90.0, 45.0, 100.0, 50.0, 110.0, 55.0],
        "koeb":  [90.0, 45.0, 100.0, 50.0, 110.0, 55.0],
    })


@pytest.fixture
def sut_3yr(supply_3yr, use_3yr, columns, transactions):
    classifications = SUTClassifications(transactions=transactions)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_3yr, use=use_3yr, metadata=metadata)


@pytest.fixture
def inspection_3yr(sut_3yr):
    return inspect_products(sut_3yr, products=["A", "B"])


# ---------------------------------------------------------------------------
# ProductInspection — id as columns (wide-format)
# ---------------------------------------------------------------------------


def test_default_ascending(inspection_3yr):
    cols = list(inspection_3yr.data.balance.columns)
    assert cols == sorted(cols)


def test_descending_reverses_columns(inspection_3yr):
    result = inspection_3yr.set_display_sort_ids_ascending(False)
    df = result.data.balance  # .data is unaffected
    assert list(df.columns) == sorted(df.columns)  # .data unchanged

    styler = result.balance  # styled property applies config
    styled_df = styler.data
    assert list(styled_df.columns) == sorted(styled_df.columns, reverse=True)


def test_ascending_true_is_default_order(inspection_3yr):
    result = inspection_3yr.set_display_sort_ids_ascending(True)
    styler = result.balance
    styled_df = styler.data
    assert list(styled_df.columns) == sorted(styled_df.columns)


def test_returns_new_product_inspection(inspection_3yr):
    result = inspection_3yr.set_display_sort_ids_ascending(False)
    assert isinstance(result, ProductInspection)
    assert result is not inspection_3yr


def test_does_not_mutate_original(inspection_3yr):
    inspection_3yr.set_display_sort_ids_ascending(False)
    styler = inspection_3yr.balance
    assert list(styler.data.columns) == sorted(styler.data.columns)


def test_all_tables_affected(inspection_3yr):
    result = inspection_3yr.set_display_sort_ids_ascending(False)
    for table_name in ["supply", "use", "price_layers"]:
        df = getattr(result, table_name).data
        assert list(df.columns) == sorted(df.columns, reverse=True), table_name


def test_data_attribute_unaffected(inspection_3yr):
    result = inspection_3yr.set_display_sort_ids_ascending(False)
    for table_name in ["balance", "supply", "use"]:
        df = getattr(result.data, table_name)
        assert list(df.columns) == sorted(df.columns), f".data.{table_name} should remain ascending"


def test_reset_to_defaults_restores_ascending(inspection_3yr):
    result = (
        inspection_3yr
        .set_display_sort_ids_ascending(False)
        .set_display_configuration_to_defaults()
    )
    styler = result.balance
    assert list(styler.data.columns) == sorted(styler.data.columns)


def test_preserves_other_display_settings(inspection_3yr):
    result = inspection_3yr.set_display_unit(1000).set_display_sort_ids_ascending(False)
    cfg = result.display_configuration
    assert cfg.display_unit == 1000
    assert cfg.sort_ids_ascending is False


# ---------------------------------------------------------------------------
# UnbalancedProductsInspection — id as index (tall-format)
# ---------------------------------------------------------------------------


@pytest.fixture
def supply_imbalance():
    return pd.DataFrame({
        "year": [2019, 2019, 2020, 2020],
        "nrnr": ["A",  "B",  "A",  "B"],
        "trans": ["0100"] * 4,
        "brch":  ["X"] * 4,
        "bas":   [100.0, 50.0, 120.0, 50.0],
        "koeb":  [100.0, 50.0, 120.0, 50.0],
    })


@pytest.fixture
def use_imbalance():
    return pd.DataFrame({
        "year": [2019, 2019, 2020, 2020],
        "nrnr": ["A",  "B",  "A",  "B"],
        "trans": ["2000"] * 4,
        "brch":  ["X"] * 4,
        "bas":   [80.0, 50.0, 80.0, 50.0],  # A unbalanced in both years
        "koeb":  [80.0, 50.0, 80.0, 50.0],
    })


@pytest.fixture
def sut_imbalance(supply_imbalance, use_imbalance, columns, transactions):
    classifications = SUTClassifications(transactions=transactions)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_imbalance, use=use_imbalance, metadata=metadata)


@pytest.fixture
def imbalance_inspection(sut_imbalance):
    return inspect_unbalanced_products(sut_imbalance)


def test_imbalances_default_id_order_ascending(imbalance_inspection):
    df = imbalance_inspection.imbalances.data
    id_vals = df.index.get_level_values("year").unique().tolist()
    assert id_vals == sorted(id_vals)


def test_imbalances_descending_id_order(imbalance_inspection):
    result = imbalance_inspection.set_display_sort_ids_ascending(False)
    styler = result.imbalances
    id_vals = styler.data.index.get_level_values("year").unique().tolist()
    assert id_vals == sorted(id_vals, reverse=True)


def test_imbalances_data_unaffected_by_sort(imbalance_inspection):
    result = imbalance_inspection.set_display_sort_ids_ascending(False)
    raw = result.data.imbalances
    id_vals = raw.index.get_level_values("year").unique().tolist()
    assert id_vals == sorted(id_vals)


def test_imbalances_returns_new_instance(imbalance_inspection):
    result = imbalance_inspection.set_display_sort_ids_ascending(False)
    assert isinstance(result, UnbalancedProductsInspection)
    assert result is not imbalance_inspection


def test_imbalances_reset_restores_ascending(imbalance_inspection):
    result = (
        imbalance_inspection
        .set_display_sort_ids_ascending(False)
        .set_display_configuration_to_defaults()
    )
    styler = result.imbalances
    id_vals = styler.data.index.get_level_values("year").unique().tolist()
    assert id_vals == sorted(id_vals)
