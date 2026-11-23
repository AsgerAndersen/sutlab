"""
Tests for inspect_products(previous=...): the .previous and .real inspections.

The fixtures come from tests/test_inspect.py. The previous-price SUT is the
2021 rows with supply x 0.9 and use x 0.95.

Hand-computed values for product A (no price layers in these fixtures):
  Current 2020:   supply 0100 = 100, 0700 = 20 (total 120); use 2000 = 80, 6001 = 40 (total 120)
  Current 2021:   supply 0100 = 110, 0700 = 25 (total 135); use 2000 = 85, 6001 = 50 (total 135)
  Previous 2021:  supply 0100 =  99, 0700 = 22.5 (total 121.5); use 2000 = 80.75, 6001 = 47.5 (total 128.25)
With reference year 2020 (default) the real volumes in 2020 are the current
values, and in 2021 the previous-price values.
"""

import pandas as pd
import pytest

from sut_helpers import make_previous_sut
from sutlab.inspect import ProductInspection, inspect_products

# Fixtures (columns, transactions, supply, use, sut, ...) are shared with test_inspect.py.
from test_inspect import columns, sut, supply, transactions, use  # noqa: F401


_ALL_PRODUCT_TABLES = [
    "balance", "supply", "use", "supply_summary", "use_summary",
    "balance_distribution", "supply_distribution", "use_distribution",
    "balance_growth", "supply_growth", "use_growth",
    "price_layers", "price_layers_distribution", "price_layers_growth",
    "price_layers_rates",
]
_GROWTH_TABLES = {"balance_growth", "supply_growth", "use_growth", "price_layers_growth"}
_REAL_TABLES = {
    "balance", "supply", "use", "balance_growth", "supply_growth", "use_growth",
}


def _value(df, year, **levels):
    """The single value in column ``year`` of the row matching the given index level values."""
    mask = pd.Series(True, index=df.index)
    for level, value in levels.items():
        mask &= df.index.get_level_values(level) == value
    selected = df.loc[mask.to_numpy(), year]
    assert len(selected) == 1, f"expected one row for {levels}, got {len(selected)}"
    return selected.iloc[0]


@pytest.fixture
def previous_sut(sut):  # noqa: F811
    return make_previous_sut(sut)


def test_products_without_previous_no_previous_or_real(sut):  # noqa: F811
    result = inspect_products(sut, "A")
    assert result.previous is None
    assert result.real is None


def test_products_reference_id_without_previous_raises(sut):  # noqa: F811
    with pytest.raises(ValueError, match="reference_id"):
        inspect_products(sut, "A", reference_id=2020)


def test_products_current_tables_unchanged_by_previous(sut, previous_sut):  # noqa: F811
    plain = inspect_products(sut, "A")
    with_previous = inspect_products(sut, "A", previous=previous_sut)
    for name in _ALL_PRODUCT_TABLES:
        pd.testing.assert_frame_equal(getattr(with_previous.data, name), getattr(plain.data, name))


def test_products_previous_and_real_are_same_class(sut, previous_sut):  # noqa: F811
    result = inspect_products(sut, "A", previous=previous_sut)
    assert isinstance(result.previous, ProductInspection)
    assert isinstance(result.real, ProductInspection)


def test_products_previous_has_no_growth_tables(sut, previous_sut):  # noqa: F811
    data = inspect_products(sut, "A", previous=previous_sut).previous.data
    for name in _ALL_PRODUCT_TABLES:
        if name in _GROWTH_TABLES:
            assert getattr(data, name) is None
        else:
            assert getattr(data, name) is not None


def test_products_real_holds_only_volumes_and_growth(sut, previous_sut):  # noqa: F811
    data = inspect_products(sut, "A", previous=previous_sut).real.data
    for name in _ALL_PRODUCT_TABLES:
        if name in _REAL_TABLES:
            assert getattr(data, name) is not None
        elif name.startswith("price_layers") and name in {"price_layers", "price_layers_growth"}:
            # No price layer columns in these fixtures: empty, as in current prices.
            assert getattr(data, name).empty
        else:
            assert getattr(data, name) is None


def test_products_previous_values(sut, previous_sut):  # noqa: F811
    previous = inspect_products(sut, "A", previous=previous_sut).previous.data
    assert list(previous.balance.columns) == [2021]
    assert _value(previous.balance, 2021, transaction_txt="Total supply") == pytest.approx(121.5)
    assert _value(previous.balance, 2021, transaction_txt="Total use") == pytest.approx(128.25)
    assert _value(previous.balance, 2021, transaction_txt="Balance") == pytest.approx(-6.75)
    assert _value(previous.use, 2021, transaction="2000") == pytest.approx(80.75)


def test_products_real_volumes(sut, previous_sut):  # noqa: F811
    real = inspect_products(sut, "A", previous=previous_sut).real.data
    assert list(real.balance.columns) == [2020, 2021]
    assert _value(real.supply, 2020, transaction="0100") == pytest.approx(100.0)
    assert _value(real.supply, 2021, transaction="0100") == pytest.approx(99.0)
    assert _value(real.use, 2021, transaction="6001") == pytest.approx(47.5)
    assert _value(real.balance, 2021, transaction_txt="Total supply") == pytest.approx(121.5)
    assert _value(real.balance, 2021, transaction_txt="Total use") == pytest.approx(128.25)


def test_products_real_balance_row_is_difference_of_chained_totals(sut, previous_sut):  # noqa: F811
    real = inspect_products(sut, "A", previous=previous_sut).real.data
    assert _value(real.balance, 2020, transaction_txt="Balance") == pytest.approx(0.0)
    assert _value(real.balance, 2021, transaction_txt="Balance") == pytest.approx(121.5 - 128.25)


def test_products_real_growth(sut, previous_sut):  # noqa: F811
    real = inspect_products(sut, "A", previous=previous_sut).real.data
    assert _value(real.supply_growth, 2021, transaction="0100") == pytest.approx(99.0 / 100.0 - 1)
    assert _value(real.balance_growth, 2021, transaction_txt="Total use") == pytest.approx(128.25 / 120.0 - 1)


def test_products_real_balance_growth_has_no_balance_row(sut, previous_sut):  # noqa: F811
    real = inspect_products(sut, "A", previous=previous_sut).real.data
    assert "Balance" not in real.balance_growth.index.get_level_values("transaction_txt")


def test_products_real_other_reference_year(sut, previous_sut):  # noqa: F811
    real = inspect_products(sut, "A", previous=previous_sut, reference_id=2021).real.data
    # Reference year 2021: 2021 volumes are the current values.
    assert _value(real.supply, 2021, transaction="0100") == pytest.approx(110.0)
    assert _value(real.balance, 2021, transaction_txt="Total supply") == pytest.approx(135.0)


def test_products_previous_wrong_price_basis_raises(sut):  # noqa: F811
    with pytest.raises(ValueError, match="previous_year"):
        inspect_products(sut, "A", previous=sut)


def test_products_previous_missing_column_raises(sut, previous_sut):  # noqa: F811
    broken = previous_sut.__class__(
        price_basis="previous_year",
        supply=previous_sut.supply.drop(columns=["bas"]),
        use=previous_sut.use,
        metadata=previous_sut.metadata,
    )
    with pytest.raises(ValueError, match="missing column"):
        inspect_products(sut, "A", previous=broken)


def test_products_styled_properties_none_for_absent_tables(sut, previous_sut):  # noqa: F811
    result = inspect_products(sut, "A", previous=previous_sut)
    assert result.previous.balance_growth is None
    assert result.real.supply_summary is None
    assert result.real.balance is not None
    assert result.previous.balance is not None


def test_products_tables_description_lists_present_tables_only(sut, previous_sut):  # noqa: F811
    result = inspect_products(sut, "A", previous=previous_sut)
    names = set(result.real.data.tables_description.index)
    assert "balance" in names
    assert "supply_summary" not in names
    assert "balance_growth" not in set(result.previous.data.tables_description.index)


def test_products_display_setters_reach_previous_and_real(sut, previous_sut):  # noqa: F811
    result = inspect_products(sut, "A", previous=previous_sut).set_display_decimals(3)
    assert result.display_configuration.decimals == 3
    assert result.previous.display_configuration.decimals == 3
    assert result.real.display_configuration.decimals == 3


def test_products_comparison_includes_previous_and_real(sut, previous_sut):  # noqa: F811
    first = inspect_products(sut, "A", previous=previous_sut)
    second = inspect_products(sut, "A", previous=previous_sut)
    comparison = first.inspect_tables_comparison(second)
    assert comparison.diff.previous.data.balance is not None
    assert comparison.rel.real.data.supply is not None
    assert comparison.diff.previous.data.balance_growth is None
    assert (comparison.diff.real.data.supply.fillna(0) == 0).all().all()


def test_products_comparison_none_when_either_side_lacks_previous(sut, previous_sut):  # noqa: F811
    with_previous = inspect_products(sut, "A", previous=previous_sut)
    without_previous = inspect_products(sut, "A")
    comparison = with_previous.inspect_tables_comparison(without_previous)
    assert comparison.diff.previous is None
    assert comparison.rel.real is None


def test_products_comparison_setters_reach_nested(sut, previous_sut):  # noqa: F811
    first = inspect_products(sut, "A", previous=previous_sut)
    comparison = first.inspect_tables_comparison(first).set_display_decimals(3)
    assert comparison.diff.real.display_configuration.decimals == 3
    assert comparison.rel.previous.display_configuration.decimals == 3


def test_products_ids_selection_applies_to_previous(sut, previous_sut):  # noqa: F811
    result = inspect_products(sut, "A", ids=[2020, 2021], previous=previous_sut)
    assert list(result.previous.data.balance.columns) == [2021]
    assert list(result.real.data.balance.columns) == [2020, 2021]


def test_products_previous_and_real_write_to_excel(sut, previous_sut, tmp_path):  # noqa: F811
    result = inspect_products(sut, "A", previous=previous_sut)
    previous_path = tmp_path / "previous.xlsx"
    real_path = tmp_path / "real.xlsx"
    result.previous.write_to_excel(previous_path)
    result.real.write_to_excel(real_path)
    previous_sheets = pd.ExcelFile(previous_path).sheet_names
    real_sheets = pd.ExcelFile(real_path).sheet_names
    assert "balance" in previous_sheets
    assert "balance_growth" not in previous_sheets
    assert "balance_growth" in real_sheets
    assert "supply_summary" not in real_sheets


def test_products_sut_method_passes_previous_and_reference_id(sut, previous_sut):  # noqa: F811
    result = sut.inspect_products("A", previous=previous_sut, reference_id=2021)
    assert _value(result.real.data.supply, 2021, transaction="0100") == pytest.approx(110.0)


def test_products_sut_method_passes_percentiles_and_coverage_thresholds(sut):  # noqa: F811
    result = sut.inspect_products("A", percentiles=[0.0], coverage_thresholds=[0.9])
    rows = set(result.data.supply_summary.index.get_level_values("summary"))
    assert "value_min" in rows
    assert "n_categories_p90" in rows
    assert "value_median" not in rows
