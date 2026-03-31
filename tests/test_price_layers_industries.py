"""
Tests for inspect_industries price layer tables.
"""
import pytest
import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import inspect_industries


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def columns_with_layers():
    return SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
        wholesale_margins="ava",
    )


@pytest.fixture
def columns_no_layers():
    return SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
    )


@pytest.fixture
def transactions_single():
    return pd.DataFrame({
        "trans":     ["0100",   "2000"],
        "trans_txt": ["Output", "Intermediate consumption"],
        "table":     ["supply", "use"],
        "esa_code":  ["P1",     "P2"],
    })


@pytest.fixture
def transactions_multi():
    return pd.DataFrame({
        "trans":     ["0100",    "0150",         "2000",                 "2100"],
        "trans_txt": ["Output",  "Other output", "Int. consumption",     "Other consumption"],
        "table":     ["supply",  "supply",       "use",                  "use"],
        "esa_code":  ["P1",      "P1",           "P2",                   "P2"],
    })


@pytest.fixture
def supply():
    return pd.DataFrame({
        "year":  [2020,   2020,   2020,   2021,   2021,   2021],
        "nrnr":  ["A",    "B",    "C",    "A",    "B",    "C"],
        "trans": ["0100", "0100", "0100", "0100", "0100", "0100"],
        "brch":  ["X",    "X",    "Y",    "X",    "X",    "Y"],
        "bas":   [60.0,   40.0,  200.0,   66.0,   44.0,  220.0],
        "koeb":  [60.0,   40.0,  200.0,   66.0,   44.0,  220.0],
    })


@pytest.fixture
def use_with_layers():
    """
    Industry X uses product A: bas=55, ava=5, koeb=60 (2020); bas=60, ava=6, koeb=66 (2021).
    Industry Y uses product C: bas=90, ava=10, koeb=100 (2020); bas=100, ava=10, koeb=110 (2021).
    """
    return pd.DataFrame({
        "year":  [2020,   2020,   2021,   2021],
        "nrnr":  ["A",    "C",    "A",    "C"],
        "trans": ["2000", "2000", "2000", "2000"],
        "brch":  ["X",    "Y",    "X",    "Y"],
        "bas":   [55.0,   90.0,   60.0,  100.0],
        "ava":   [ 5.0,   10.0,    6.0,   10.0],
        "koeb":  [60.0,  100.0,   66.0,  110.0],
    })


@pytest.fixture
def use_no_layers():
    return pd.DataFrame({
        "year":  [2020,   2020,   2021,   2021],
        "nrnr":  ["A",    "C",    "A",    "C"],
        "trans": ["2000", "2000", "2000", "2000"],
        "brch":  ["X",    "Y",    "X",    "Y"],
        "bas":   [55.0,   90.0,   60.0,  100.0],
        "koeb":  [60.0,  100.0,   66.0,  110.0],
    })


@pytest.fixture
def sut_layers(supply, use_with_layers, columns_with_layers, transactions_single):
    classifications = SUTClassifications(transactions=transactions_single)
    metadata = SUTMetadata(columns=columns_with_layers, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use_with_layers, metadata=metadata)


@pytest.fixture
def sut_no_layers(supply, use_no_layers, columns_no_layers, transactions_single):
    classifications = SUTClassifications(transactions=transactions_single)
    metadata = SUTMetadata(columns=columns_no_layers, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use_no_layers, metadata=metadata)


@pytest.fixture
def sut_layers_multi(supply, columns_with_layers, transactions_multi):
    """Two P1 and two P2 transactions, with wholesale margins."""
    supply_extra = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A",  "A"],
        "trans": ["0150", "0150"],
        "brch":  ["X",   "X"],
        "bas":   [10.0,  11.0],
        "koeb":  [10.0,  11.0],
    })
    use_base = pd.DataFrame({
        "year":  [2020,   2020,   2021,   2021],
        "nrnr":  ["A",    "C",    "A",    "C"],
        "trans": ["2000", "2000", "2000", "2000"],
        "brch":  ["X",    "Y",    "X",    "Y"],
        "bas":   [55.0,   90.0,   60.0,  100.0],
        "ava":   [ 5.0,   10.0,    6.0,   10.0],
        "koeb":  [60.0,  100.0,   66.0,  110.0],
    })
    use_extra = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A",  "A"],
        "trans": ["2100", "2100"],
        "brch":  ["X",   "X"],
        "bas":   [5.0,    6.0],
        "ava":   [1.0,    1.0],
        "koeb":  [6.0,    7.0],
    })
    supply_full = pd.concat([supply, supply_extra], ignore_index=True)
    use_full = pd.concat([use_base, use_extra], ignore_index=True)
    classifications = SUTClassifications(transactions=transactions_multi)
    metadata = SUTMetadata(columns=columns_with_layers, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_full, use=use_full, metadata=metadata)


# ---------------------------------------------------------------------------
# price_layers: structure
# ---------------------------------------------------------------------------


def test_price_layers_is_dataframe(sut_layers):
    result = inspect_industries(sut_layers, "X")
    assert isinstance(result.data.price_layers, pd.DataFrame)


def test_price_layers_empty_when_no_layer_cols(sut_no_layers):
    result = inspect_industries(sut_no_layers, "X")
    assert result.data.price_layers.empty


def test_price_layers_multiindex_names(sut_layers):
    pl = inspect_industries(sut_layers, "X").data.price_layers
    assert list(pl.index.names) == [
        "industry", "industry_txt", "price_layer", "transaction", "transaction_txt"
    ]


def test_price_layers_columns_are_ids(sut_layers):
    pl = inspect_industries(sut_layers, "X").data.price_layers
    assert list(pl.columns) == [2020, 2021]


def test_price_layers_excludes_p1_transactions(sut_layers):
    pl = inspect_industries(sut_layers, "X").data.price_layers
    assert "0100" not in pl.index.get_level_values("transaction").tolist()


def test_price_layers_multiple_industries(sut_layers):
    pl = inspect_industries(sut_layers, ["X", "Y"]).data.price_layers
    industries = pl.index.get_level_values("industry").unique().tolist()
    assert "X" in industries
    assert "Y" in industries


# ---------------------------------------------------------------------------
# price_layers: values
# ---------------------------------------------------------------------------


def test_price_layers_values_industry_x(sut_layers):
    """Industry X, layer=ava, trans=2000: 5 (2020), 6 (2021)."""
    pl = inspect_industries(sut_layers, "X").data.price_layers
    idx = pl.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") == "2000")
    )
    row = pl[mask].iloc[0]
    assert row[2020] == pytest.approx(5.0)
    assert row[2021] == pytest.approx(6.0)


def test_price_layers_values_industry_y(sut_layers):
    """Industry Y, layer=ava, trans=2000: 10 (2020), 10 (2021)."""
    pl = inspect_industries(sut_layers, ["X", "Y"]).data.price_layers
    idx = pl.index
    mask = (
        (idx.get_level_values("industry") == "Y")
        & (idx.get_level_values("transaction") == "2000")
    )
    row = pl[mask].iloc[0]
    assert row[2020] == pytest.approx(10.0)
    assert row[2021] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# price_layers: Total rows
# ---------------------------------------------------------------------------


def test_price_layers_no_total_row_when_single_p2(sut_layers):
    """Single P2 transaction → no Total row."""
    pl = inspect_industries(sut_layers, "X").data.price_layers
    assert "Total" not in pl.index.get_level_values("transaction_txt").tolist()


def test_price_layers_total_row_when_multi_p2(sut_layers_multi):
    """Two P2 transactions → Total row present."""
    pl = inspect_industries(sut_layers_multi, "X").data.price_layers
    assert "Total" in pl.index.get_level_values("transaction_txt").tolist()


def test_price_layers_total_row_value(sut_layers_multi):
    """Total row = sum of per-transaction rows for that (industry, layer)."""
    pl = inspect_industries(sut_layers_multi, "X").data.price_layers
    idx = pl.index
    trans_mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") != "")
    )
    total_mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") == "")
    )
    trans_sum_2020 = pl[trans_mask][2020].sum()
    total_2020 = pl[total_mask].iloc[0][2020]
    assert total_2020 == pytest.approx(trans_sum_2020)


# ---------------------------------------------------------------------------
# price_layers_rates
# ---------------------------------------------------------------------------


def test_price_layers_rates_is_dataframe(sut_layers):
    assert isinstance(inspect_industries(sut_layers, "X").data.price_layers_rates, pd.DataFrame)


def test_price_layers_rates_empty_when_no_layers(sut_no_layers):
    assert inspect_industries(sut_no_layers, "X").data.price_layers_rates.empty


def test_price_layers_rates_no_total_rows(sut_layers_multi):
    """Total rows must not appear in rates table."""
    rates = inspect_industries(sut_layers_multi, "X").data.price_layers_rates
    assert "" not in rates.index.get_level_values("transaction").tolist()


def test_price_layers_rates_values_industry_x(sut_layers):
    """Industry X, trans=2000: ava_rate = 5/55 (2020), 6/60 (2021)."""
    rates = inspect_industries(sut_layers, "X").data.price_layers_rates
    idx = rates.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") == "2000")
    )
    row = rates[mask].iloc[0]
    assert row[2020] == pytest.approx(5.0 / 55.0)
    assert row[2021] == pytest.approx(6.0 / 60.0)


def test_price_layers_rates_values_industry_y(sut_layers):
    """Industry Y, trans=2000: ava_rate = 10/90 (2020), 10/100 (2021)."""
    rates = inspect_industries(sut_layers, ["X", "Y"]).data.price_layers_rates
    idx = rates.index
    mask = (
        (idx.get_level_values("industry") == "Y")
        & (idx.get_level_values("transaction") == "2000")
    )
    row = rates[mask].iloc[0]
    assert row[2020] == pytest.approx(10.0 / 90.0)
    assert row[2021] == pytest.approx(10.0 / 100.0)


def test_price_layers_rates_differ_between_industries(sut_layers):
    rates = inspect_industries(sut_layers, ["X", "Y"]).data.price_layers_rates
    idx = rates.index
    row_x = rates[idx.get_level_values("industry") == "X"].iloc[0]
    row_y = rates[idx.get_level_values("industry") == "Y"].iloc[0]
    assert row_x[2020] != pytest.approx(row_y[2020])


# ---------------------------------------------------------------------------
# price_layers_distribution
# ---------------------------------------------------------------------------


def test_price_layers_distribution_is_dataframe(sut_layers):
    assert isinstance(
        inspect_industries(sut_layers, "X").data.price_layers_distribution, pd.DataFrame
    )


def test_price_layers_distribution_empty_when_single_p2(sut_layers):
    """Single P2 transaction → distribution would be 1.0 everywhere → return empty."""
    dist = inspect_industries(sut_layers, "X").data.price_layers_distribution
    assert dist.empty


def test_price_layers_distribution_total_row_is_one(sut_layers_multi):
    dist = inspect_industries(sut_layers_multi, "X").data.price_layers_distribution
    idx = dist.index
    total_mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") == "")
    )
    total_row = dist[total_mask].iloc[0]
    assert total_row[2020] == pytest.approx(1.0)
    assert total_row[2021] == pytest.approx(1.0)


def test_price_layers_distribution_transaction_rows_sum_to_one(sut_layers_multi):
    dist = inspect_industries(sut_layers_multi, "X").data.price_layers_distribution
    idx = dist.index
    trans_mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") != "")
    )
    assert dist[trans_mask][2020].sum() == pytest.approx(1.0)
    assert dist[trans_mask][2021].sum() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# price_layers_growth
# ---------------------------------------------------------------------------


def test_price_layers_growth_is_dataframe(sut_layers):
    assert isinstance(
        inspect_industries(sut_layers, "X").data.price_layers_growth, pd.DataFrame
    )


def test_price_layers_growth_first_column_nan(sut_layers):
    growth = inspect_industries(sut_layers, "X").data.price_layers_growth
    assert growth[2020].isna().all()


def test_price_layers_growth_value(sut_layers):
    """Industry X, trans=2000, layer=ava: growth = (6 - 5) / 5 = 0.2."""
    growth = inspect_industries(sut_layers, "X").data.price_layers_growth
    idx = growth.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("transaction") == "2000")
    )
    row = growth[mask].iloc[0]
    assert row[2021] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Styled properties
# ---------------------------------------------------------------------------


def test_price_layers_property_returns_styler(sut_layers):
    assert isinstance(inspect_industries(sut_layers, "X").price_layers, Styler)


def test_price_layers_rates_property_returns_styler(sut_layers):
    assert isinstance(inspect_industries(sut_layers, "X").price_layers_rates, Styler)


def test_price_layers_distribution_property_returns_styler(sut_layers):
    assert isinstance(inspect_industries(sut_layers, "X").price_layers_distribution, Styler)


def test_price_layers_growth_property_returns_styler(sut_layers):
    assert isinstance(inspect_industries(sut_layers, "X").price_layers_growth, Styler)


def test_price_layers_property_handles_empty(sut_no_layers):
    """Styled property must not raise even when underlying data is empty."""
    assert isinstance(inspect_industries(sut_no_layers, "X").price_layers, Styler)
