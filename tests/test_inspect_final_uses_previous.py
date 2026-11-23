"""
Tests for inspect_final_uses(previous=...): the .previous and .real inspections.

Fixtures come from tests/test_inspect_final_uses.py. The previous-price SUT is
the 2021 rows with use x 0.95 (purchasers' prices):

  Current 2020:   3110/FKO1 50, 3110/FKO2 35, 3200/GOV 55, 6001 60  (total 200)
  Current 2021:   3110/FKO1 55, 3110/FKO2 38, 3200/GOV 60, 6001 66  (total 219)
  Previous 2021:  3110/FKO1 52.25, 3110/FKO2 36.1, 3200/GOV 57, 6001 62.7  (total 208.05)

With reference year 2020 (default) the real volumes in 2020 are the current
values, and in 2021 the previous-price values.
"""

import pandas as pd
import pytest

from sut_helpers import make_previous_sut
from sutlab.inspect import FinalUseInspection, inspect_final_uses

# Fixtures (columns, transactions, supply, use, sut, ...) are shared with test_inspect_final_uses.py.
from test_inspect_final_uses import (  # noqa: F401
    collective_consumption,
    columns,
    individual_consumption,
    supply,
    sut,
    transactions,
    use,
)

_ALL_TABLES = [
    "use", "use_distribution", "use_growth",
    "use_categories", "use_categories_distribution", "use_categories_growth",
    "use_products", "use_products_distribution", "use_products_growth",
    "use_products_summary",
    "price_layers", "price_layers_rates", "price_layers_distribution",
    "price_layers_growth",
]
_GROWTH_TABLES = {"use_growth", "use_categories_growth", "use_products_growth", "price_layers_growth"}
_REAL_TABLES = {
    "use", "use_growth", "use_categories", "use_categories_growth",
    "use_products", "use_products_growth", "price_layers", "price_layers_growth",
}
_ALL = ["3110", "3200", "6001"]


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
    return make_previous_sut(sut, supply_factor=1.0, use_factor=0.95)


def test_final_uses_without_previous_no_previous_or_real(sut):  # noqa: F811
    result = inspect_final_uses(sut, _ALL)
    assert result.previous is None
    assert result.real is None


def test_final_uses_reference_id_without_previous_raises(sut):  # noqa: F811
    with pytest.raises(ValueError, match="reference_id"):
        inspect_final_uses(sut, _ALL, reference_id=2020)


def test_final_uses_current_tables_unchanged_by_previous(sut, previous_sut):  # noqa: F811
    plain = inspect_final_uses(sut, _ALL)
    with_previous = inspect_final_uses(sut, _ALL, previous=previous_sut)
    for name in _ALL_TABLES:
        pd.testing.assert_frame_equal(getattr(with_previous.data, name), getattr(plain.data, name))


def test_final_uses_previous_and_real_are_same_class(sut, previous_sut):  # noqa: F811
    result = inspect_final_uses(sut, _ALL, previous=previous_sut)
    assert isinstance(result.previous, FinalUseInspection)
    assert isinstance(result.real, FinalUseInspection)


def test_final_uses_previous_has_no_growth_tables(sut, previous_sut):  # noqa: F811
    data = inspect_final_uses(sut, _ALL, previous=previous_sut).previous.data
    for name in _ALL_TABLES:
        if name in _GROWTH_TABLES:
            assert getattr(data, name) is None
        else:
            assert getattr(data, name) is not None


def test_final_uses_real_holds_only_volumes_and_growth(sut, previous_sut):  # noqa: F811
    data = inspect_final_uses(sut, _ALL, previous=previous_sut).real.data
    for name in _ALL_TABLES:
        if name in _REAL_TABLES:
            assert getattr(data, name) is not None
        else:
            assert getattr(data, name) is None


def test_final_uses_previous_values(sut, previous_sut):  # noqa: F811
    previous = inspect_final_uses(sut, _ALL, previous=previous_sut).previous.data
    assert list(previous.use.columns) == [2021]
    assert _value(previous.use, 2021, transaction="3110") == pytest.approx(52.25 + 36.1)
    assert _value(previous.use_categories, 2021, transaction="3110", category="FKO1") == pytest.approx(52.25)
    assert _value(previous.use, 2021, transaction_txt="Total use") == pytest.approx(208.05)


def test_final_uses_real_volumes(sut, previous_sut):  # noqa: F811
    real = inspect_final_uses(sut, _ALL, previous=previous_sut).real.data
    assert list(real.use.columns) == [2020, 2021]
    assert _value(real.use, 2020, transaction_txt="Total use") == pytest.approx(200.0)
    assert _value(real.use, 2021, transaction_txt="Total use") == pytest.approx(208.05)
    assert _value(real.use, 2021, transaction="6001") == pytest.approx(62.7)
    assert _value(real.use_categories, 2021, transaction="3110", category="FKO2") == pytest.approx(36.1)


def test_final_uses_real_growth(sut, previous_sut):  # noqa: F811
    real = inspect_final_uses(sut, _ALL, previous=previous_sut).real.data
    assert _value(real.use_growth, 2021, transaction_txt="Total use") == pytest.approx(208.05 / 200.0 - 1)
    assert _value(real.use_growth, 2021, transaction="6001") == pytest.approx(62.7 / 60.0 - 1)


def test_final_uses_real_other_reference_year(sut, previous_sut):  # noqa: F811
    real = inspect_final_uses(sut, _ALL, previous=previous_sut, reference_id=2021).real.data
    assert _value(real.use, 2021, transaction_txt="Total use") == pytest.approx(219.0)


def test_final_uses_category_filter_applies_to_previous(sut, previous_sut):  # noqa: F811
    result = inspect_final_uses(sut, "3110", categories="FKO1", previous=previous_sut)
    assert _value(result.previous.data.use, 2021, transaction_txt="Total use") == pytest.approx(52.25)
    assert _value(result.real.data.use, 2021, transaction_txt="Total use") == pytest.approx(52.25)


def test_final_uses_previous_wrong_price_basis_raises(sut):  # noqa: F811
    with pytest.raises(ValueError, match="previous_year"):
        inspect_final_uses(sut, _ALL, previous=sut)


def test_final_uses_styled_properties_none_for_absent_tables(sut, previous_sut):  # noqa: F811
    result = inspect_final_uses(sut, _ALL, previous=previous_sut)
    assert result.previous.use_growth is None
    assert result.real.use_products_summary is None
    assert result.real.use is not None
    assert result.previous.use is not None


def test_final_uses_tables_description_lists_present_tables_only(sut, previous_sut):  # noqa: F811
    result = inspect_final_uses(sut, _ALL, previous=previous_sut)
    assert "use_distribution" not in set(result.real.data.tables_description.index)
    assert "use_growth" not in set(result.previous.data.tables_description.index)
    assert "use" in set(result.real.data.tables_description.index)


def test_final_uses_display_setters_reach_previous_and_real(sut, previous_sut):  # noqa: F811
    result = inspect_final_uses(sut, _ALL, previous=previous_sut).set_display_decimals(3)
    assert result.previous.display_configuration.decimals == 3
    assert result.real.display_configuration.decimals == 3


def test_final_uses_comparison_includes_previous_and_real(sut, previous_sut):  # noqa: F811
    first = inspect_final_uses(sut, _ALL, previous=previous_sut)
    comparison = first.inspect_tables_comparison(first)
    assert comparison.diff.previous.data.use is not None
    assert comparison.rel.real.data.use is not None
    assert (comparison.diff.real.data.use.fillna(0) == 0).all().all()


def test_final_uses_comparison_none_when_either_side_lacks_previous(sut, previous_sut):  # noqa: F811
    with_previous = inspect_final_uses(sut, _ALL, previous=previous_sut)
    without_previous = inspect_final_uses(sut, _ALL)
    comparison = with_previous.inspect_tables_comparison(without_previous)
    assert comparison.diff.previous is None
    assert comparison.rel.real is None


def test_final_uses_comparison_setters_reach_nested(sut, previous_sut):  # noqa: F811
    first = inspect_final_uses(sut, _ALL, previous=previous_sut)
    comparison = first.inspect_tables_comparison(first).set_display_decimals(3)
    assert comparison.diff.real.display_configuration.decimals == 3
    assert comparison.rel.previous.display_configuration.decimals == 3


def test_final_uses_previous_and_real_write_to_excel(sut, previous_sut, tmp_path):  # noqa: F811
    result = inspect_final_uses(sut, _ALL, previous=previous_sut)
    result.previous.write_to_excel(tmp_path / "previous.xlsx")
    result.real.write_to_excel(tmp_path / "real.xlsx")
    previous_sheets = pd.ExcelFile(tmp_path / "previous.xlsx").sheet_names
    real_sheets = pd.ExcelFile(tmp_path / "real.xlsx").sheet_names
    assert "use" in previous_sheets
    assert "use_growth" not in previous_sheets
    assert "use_growth" in real_sheets
    assert "use_distribution" not in real_sheets


def test_final_uses_sut_method_passes_arguments(sut, previous_sut):  # noqa: F811
    result = sut.inspect_final_uses(
        _ALL, previous=previous_sut, reference_id=2021,
        percentiles=[0.0], coverage_thresholds=[0.9],
    )
    assert _value(result.real.data.use, 2021, transaction_txt="Total use") == pytest.approx(219.0)
    rows = set(result.data.use_products_summary.index.get_level_values("summary"))
    assert "value_min" in rows
    assert "value_median" not in rows
