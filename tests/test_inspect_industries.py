"""
Tests for inspect_industries.
"""

import pytest
import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import IndustryInspection, IndustryInspectionData, inspect_industries


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
def transactions_single():
    """One P1 and one P2 transaction — no Total output / Total input rows."""
    return pd.DataFrame({
        "trans":     ["0100",                    "2000"],
        "trans_txt": ["Output at basic prices",  "Intermediate consumption"],
        "table":     ["supply",                  "use"],
        "esa_code":  ["P1",                      "P2"],
    })


@pytest.fixture
def transactions_multi():
    """Two P1 and two P2 transactions — Total output and Total input rows appear."""
    return pd.DataFrame({
        "trans":     ["0100",    "0150",         "2000",                  "2100"],
        "trans_txt": ["Output",  "Other output", "Int. consumption",      "Other consumption"],
        "table":     ["supply",  "supply",       "use",                   "use"],
        "esa_code":  ["P1",      "P1",           "P2",                    "P2"],
    })


@pytest.fixture
def supply():
    """
    Two industries (X, Y) over two years.
    Products A and B both supply into industry X; product C supplies into Y.
    Values are at basic prices (bas == koeb for supply).
    """
    return pd.DataFrame({
        "year":  [2020,  2020,  2020,  2021,  2021,  2021],
        "nrnr":  ["A",   "B",   "C",   "A",   "B",   "C"],
        "trans": ["0100","0100","0100","0100","0100","0100"],
        "brch":  ["X",   "X",   "Y",   "X",   "X",   "Y"],
        "bas":   [60.0,  40.0, 200.0,  66.0,  44.0, 220.0],
        "koeb":  [60.0,  40.0, 200.0,  66.0,  44.0, 220.0],
    })


@pytest.fixture
def use():
    """
    Industry X uses product A; industry Y uses product C.
    purchasers' prices (koeb) differ from basic prices (bas).
    """
    return pd.DataFrame({
        "year":  [2020,  2020,  2021,  2021],
        "nrnr":  ["A",   "C",   "A",   "C"],
        "trans": ["2000","2000","2000","2000"],
        "brch":  ["X",   "Y",   "X",   "Y"],
        "bas":   [55.0,  90.0,  60.0, 100.0],
        "koeb":  [60.0, 100.0,  66.0, 110.0],
    })


@pytest.fixture
def sut(supply, use, columns, transactions_single):
    classifications = SUTClassifications(transactions=transactions_single)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def sut_with_industry_labels(supply, use, columns, transactions_single):
    industries = pd.DataFrame({
        "brch":     ["X", "Y"],
        "brch_txt": ["Agriculture", "Trade"],
    })
    classifications = SUTClassifications(
        transactions=transactions_single, industries=industries
    )
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def sut_multi(supply, use, columns, transactions_multi):
    """SUT with two P1 and two P2 transactions (triggering total rows)."""
    # Add a second P1 and P2 transaction to supply/use data
    supply_extra = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A",  "A"],
        "trans": ["0150", "0150"],
        "brch":  ["X",  "X"],
        "bas":   [10.0, 11.0],
        "koeb":  [10.0, 11.0],
    })
    use_extra = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A",  "A"],
        "trans": ["2100", "2100"],
        "brch":  ["X",  "X"],
        "bas":   [5.0,   6.0],
        "koeb":  [5.0,   6.0],
    })
    supply_full = pd.concat([supply, supply_extra], ignore_index=True)
    use_full = pd.concat([use, use_extra], ignore_index=True)
    classifications = SUTClassifications(transactions=transactions_multi)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(
        price_basis="current_year",
        supply=supply_full,
        use=use_full,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_industry_inspection(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result, IndustryInspection)
    assert isinstance(result.data, IndustryInspectionData)
    assert isinstance(result.data.balance, pd.DataFrame)


# ---------------------------------------------------------------------------
# MultiIndex structure
# ---------------------------------------------------------------------------


def test_balance_index_names(sut):
    result = inspect_industries(sut, ["X", "Y"])
    idx = result.data.balance.index
    assert idx.names == ["industry", "industry_txt", "transaction", "transaction_txt"]


def test_balance_columns_are_ids(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.balance.columns) == [2020, 2021]


# ---------------------------------------------------------------------------
# Row order (single P1, single P2 — no total rows)
# ---------------------------------------------------------------------------


def test_balance_row_order_single(sut):
    """With one P1 and one P2 transaction: P1 row, P2 row, GVA, Input coeff."""
    result = inspect_industries(sut, "X")
    txts = result.data.balance.index.get_level_values("transaction_txt").tolist()
    assert txts == [
        "Output at basic prices",
        "Intermediate consumption",
        "Gross value added",
        "Input coefficient",
    ]


def test_balance_no_total_output_row_when_single_p1(sut):
    txts = inspect_industries(sut, "X").data.balance.index.get_level_values(
        "transaction_txt"
    ).tolist()
    assert "Total output" not in txts


def test_balance_no_total_input_row_when_single_p2(sut):
    txts = inspect_industries(sut, "X").data.balance.index.get_level_values(
        "transaction_txt"
    ).tolist()
    assert "Total input" not in txts


# ---------------------------------------------------------------------------
# Row order (multiple P1 and P2 — total rows appear)
# ---------------------------------------------------------------------------


def test_balance_row_order_multi(sut_multi):
    """Two P1 and two P2 transactions: total rows present."""
    result = inspect_industries(sut_multi, "X")
    txts = result.data.balance.index.get_level_values("transaction_txt").tolist()
    assert txts == [
        "Output",
        "Other output",
        "Total output",
        "Int. consumption",
        "Other consumption",
        "Total input",
        "Gross value added",
        "Input coefficient",
    ]


# ---------------------------------------------------------------------------
# Values: P1, P2, GVA, input coefficient
# ---------------------------------------------------------------------------


def _get_row(balance: pd.DataFrame, industry: str, transaction: str, transaction_txt: str) -> pd.Series:
    """Helper: extract a single row by its index labels as a Series over ids."""
    idx = balance.index
    mask = (
        (idx.get_level_values("industry") == industry)
        & (idx.get_level_values("transaction") == transaction)
        & (idx.get_level_values("transaction_txt") == transaction_txt)
    )
    return balance[mask].iloc[0]


def test_p1_values_are_basic_prices_summed_across_products(sut):
    """Industry X total output: products A + B, basic prices."""
    balance = inspect_industries(sut, "X").data.balance
    row = _get_row(balance, "X", "0100", "Output at basic prices")
    # A(60) + B(40) = 100 in 2020; A(66) + B(44) = 110 in 2021
    assert row[2020] == pytest.approx(100.0)
    assert row[2021] == pytest.approx(110.0)


def test_p2_values_are_purchasers_prices(sut):
    """Industry X total input: product A at purchasers' prices (koeb)."""
    balance = inspect_industries(sut, "X").data.balance
    row = _get_row(balance, "X", "2000", "Intermediate consumption")
    assert row[2020] == pytest.approx(60.0)
    assert row[2021] == pytest.approx(66.0)


def test_gva_equals_output_minus_input(sut):
    """GVA = P1 sum (basic) - P2 sum (purchasers')."""
    balance = inspect_industries(sut, "X").data.balance
    gva = _get_row(balance, "X", "B1g", "Gross value added")
    # output=100, input=60 → GVA=40 in 2020; output=110, input=66 → GVA=44 in 2021
    assert gva[2020] == pytest.approx(40.0)
    assert gva[2021] == pytest.approx(44.0)


def test_input_coefficient_equals_input_over_output(sut):
    balance = inspect_industries(sut, "X").data.balance
    coeff = _get_row(balance, "X", "", "Input coefficient")
    assert coeff[2020] == pytest.approx(60.0 / 100.0)
    assert coeff[2021] == pytest.approx(66.0 / 110.0)


def test_total_output_row_matches_sum_of_p1_rows(sut_multi):
    """Total output row equals sum of all P1 transaction rows."""
    balance = inspect_industries(sut_multi, "X").data.balance
    idx = balance.index
    p1_mask = idx.get_level_values("esa_code_placeholder") if False else (
        idx.get_level_values("transaction_txt").isin(["Output", "Other output"])
    )
    p1_sum = balance[p1_mask].sum()
    total_output = balance[
        idx.get_level_values("transaction_txt") == "Total output"
    ].squeeze()
    for year in [2020, 2021]:
        assert total_output.loc[year] == pytest.approx(p1_sum.loc[year])


def test_total_input_row_matches_sum_of_p2_rows(sut_multi):
    """Total input row equals sum of all P2 transaction rows."""
    balance = inspect_industries(sut_multi, "X").data.balance
    idx = balance.index
    p2_mask = idx.get_level_values("transaction_txt").isin(
        ["Int. consumption", "Other consumption"]
    )
    p2_sum = balance[p2_mask].sum()
    total_input = balance[
        idx.get_level_values("transaction_txt") == "Total input"
    ].squeeze()
    for year in [2020, 2021]:
        assert total_input.loc[year] == pytest.approx(p2_sum.loc[year])


# ---------------------------------------------------------------------------
# Multiple industries
# ---------------------------------------------------------------------------


def test_multiple_industries_in_result(sut):
    result = inspect_industries(sut, ["X", "Y"])
    industry_vals = result.data.balance.index.get_level_values("industry").tolist()
    # Each industry has 4 rows (P1, P2, GVA, coeff)
    assert industry_vals.count("X") == 4
    assert industry_vals.count("Y") == 4


def test_industry_order_follows_natural_sort(sut):
    """Codes are returned in natural sort order of the input codes, not argument order."""
    result = inspect_industries(sut, ["Y", "X"])
    industry_vals = result.data.balance.index.get_level_values("industry").tolist()
    # _match_codes preserves the order of the candidate codes (naturally sorted),
    # so X comes before Y regardless of argument order.
    assert industry_vals.index("X") < industry_vals.index("Y")


def test_industry_y_values(sut):
    """Industry Y: product C only."""
    balance = inspect_industries(sut, "Y").data.balance
    p1_row = _get_row(balance, "Y", "0100", "Output at basic prices")
    assert p1_row[2020] == pytest.approx(200.0)
    assert p1_row[2021] == pytest.approx(220.0)


# ---------------------------------------------------------------------------
# Industry labels
# ---------------------------------------------------------------------------


def test_industry_txt_empty_when_no_classification(sut):
    result = inspect_industries(sut, "X")
    industry_txt_vals = result.data.balance.index.get_level_values(
        "industry_txt"
    ).unique().tolist()
    assert industry_txt_vals == [""]


def test_industry_txt_populated_when_classification_loaded(sut_with_industry_labels):
    result = inspect_industries(sut_with_industry_labels, "X")
    industry_txt_vals = result.data.balance.index.get_level_values(
        "industry_txt"
    ).unique().tolist()
    assert industry_txt_vals == ["Agriculture"]


# ---------------------------------------------------------------------------
# ids filtering
# ---------------------------------------------------------------------------


def test_ids_filter_single_year(sut):
    result = inspect_industries(sut, "X", ids=2020)
    assert list(result.data.balance.columns) == [2020]


def test_ids_filter_list(sut):
    result = inspect_industries(sut, "X", ids=[2021])
    assert list(result.data.balance.columns) == [2021]


def test_ids_filter_unknown_raises(sut):
    with pytest.raises(ValueError, match="not found in collection"):
        inspect_industries(sut, "X", ids=1999)


# ---------------------------------------------------------------------------
# sort_id validation
# ---------------------------------------------------------------------------


def test_sort_id_unknown_raises(sut):
    with pytest.raises(ValueError, match="not found in collection ids"):
        inspect_industries(sut, "X", sort_id=1999)


# ---------------------------------------------------------------------------
# Missing zero fill — industry with no use data
# ---------------------------------------------------------------------------


def test_industry_with_no_use_data_has_zero_input(supply, columns, transactions_single):
    """Industry Z appears only in supply — P2 row should be 0, GVA = output."""
    supply_extra = pd.DataFrame({
        "year":  [2020],
        "nrnr":  ["D"],
        "trans": ["0100"],
        "brch":  ["Z"],
        "bas":   [50.0],
        "koeb":  [50.0],
    })
    supply_z = pd.concat([supply, supply_extra], ignore_index=True)
    use_empty = pd.DataFrame(
        columns=["year", "nrnr", "trans", "brch", "bas", "koeb"]
    )
    # Need at least one year in use to get all_ids right — reuse supply years
    use_placeholder = pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A", "A"],
        "trans": ["2000", "2000"],
        "brch":  ["X", "X"],
        "bas":   [0.0, 0.0],
        "koeb":  [0.0, 0.0],
    })
    classifications = SUTClassifications(transactions=transactions_single)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    sut_z = SUT(
        price_basis="current_year",
        supply=supply_z,
        use=use_placeholder,
        metadata=metadata,
    )
    balance = inspect_industries(sut_z, "Z").data.balance
    p2_row = _get_row(balance, "Z", "2000", "Intermediate consumption")
    assert p2_row[2020] == pytest.approx(0.0)
    gva_row = _get_row(balance, "Z", "B1g", "Gross value added")
    assert gva_row[2020] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# input_coefficient is NaN when output is zero
# ---------------------------------------------------------------------------


def test_input_coefficient_nan_when_output_zero(columns, transactions_single):
    """Industry with zero output: input coefficient should be NaN."""
    supply_zero = pd.DataFrame({
        "year":  [2020],
        "nrnr":  ["A"],
        "trans": ["0100"],
        "brch":  ["X"],
        "bas":   [0.0],
        "koeb":  [0.0],
    })
    use_nonzero = pd.DataFrame({
        "year":  [2020],
        "nrnr":  ["A"],
        "trans": ["2000"],
        "brch":  ["X"],
        "bas":   [10.0],
        "koeb":  [10.0],
    })
    classifications = SUTClassifications(transactions=transactions_single)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    sut_zero = SUT(
        price_basis="current_year",
        supply=supply_zero,
        use=use_nonzero,
        metadata=metadata,
    )
    balance = inspect_industries(sut_zero, "X").data.balance
    coeff = _get_row(balance, "X", "", "Input coefficient")
    import math
    assert math.isnan(coeff[2020])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_raises_when_no_metadata(supply, use):
    sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
    with pytest.raises(ValueError, match="sut.metadata is required"):
        inspect_industries(sut_no_meta, "X")


def test_raises_when_no_transactions_classification(supply, use, columns):
    classifications = SUTClassifications()
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    sut_no_trans = SUT(
        price_basis="current_year", supply=supply, use=use, metadata=metadata
    )
    with pytest.raises(ValueError, match="classifications.transactions is required"):
        inspect_industries(sut_no_trans, "X")


def test_raises_when_transaction_txt_column_missing(supply, use, columns):
    trans_no_txt = pd.DataFrame({
        "trans":    ["0100", "2000"],
        "table":    ["supply", "use"],
        "esa_code": ["P1", "P2"],
        # no trans_txt column
    })
    classifications = SUTClassifications(transactions=trans_no_txt)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    sut_bad = SUT(
        price_basis="current_year", supply=supply, use=use, metadata=metadata
    )
    with pytest.raises(ValueError, match="must have a 'trans_txt' column"):
        inspect_industries(sut_bad, "X")


# ---------------------------------------------------------------------------
# Styled balance property
# ---------------------------------------------------------------------------


def test_balance_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.balance, Styler)


def test_balance_property_multi_industry_returns_styler(sut):
    result = inspect_industries(sut, ["X", "Y"])
    assert isinstance(result.balance, Styler)


def test_balance_property_multi_transaction_returns_styler(sut_multi):
    result = inspect_industries(sut_multi, "X")
    assert isinstance(result.balance, Styler)


def test_balance_property_data_matches_raw(sut):
    """Styled and raw DataFrames have the same shape and index."""
    result = inspect_industries(sut, ["X", "Y"])
    styled_df = result.balance.data
    assert styled_df.shape == result.data.balance.shape
    assert list(styled_df.index) == list(result.data.balance.index)


def test_balance_property_input_coefficient_formatted_as_percentage(sut):
    """Input coefficient row should be formatted as a percentage string."""
    result = inspect_industries(sut, "X")
    rendered = result.balance.to_html()
    # Input coefficient for X in 2020 is 60/100 = 0.6 → formatted as "60,0%"
    assert "60,0%" in rendered


def test_balance_property_p1_row_formatted_as_number(sut):
    """P1 output row should be formatted as a European number string."""
    result = inspect_industries(sut, "X")
    rendered = result.balance.to_html()
    # P1 total for X in 2020 is 100.0 → formatted as "100,0"
    assert "100,0" in rendered


# ---------------------------------------------------------------------------
# supply_products data
# ---------------------------------------------------------------------------


def test_supply_products_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.supply_products, pd.DataFrame)


def test_supply_products_index_names(sut):
    result = inspect_industries(sut, ["X", "Y"])
    idx = result.data.supply_products.index
    assert idx.names == [
        "industry", "industry_txt", "transaction", "transaction_txt", "product", "product_txt"
    ]


def test_supply_products_columns_are_ids(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.supply_products.columns) == [2020, 2021]


def test_supply_products_contains_product_rows_and_total(sut):
    """Industry X has products A and B — two data rows + one Total supply row."""
    sd = inspect_industries(sut, "X").data.supply_products
    idx = sd.index
    product_vals = idx.get_level_values("product").tolist()
    trans_txt_vals = idx.get_level_values("transaction_txt").tolist()
    assert "A" in product_vals
    assert "B" in product_vals
    assert "Total supply" in trans_txt_vals


def test_supply_products_total_row_sums_products(sut):
    """Total supply for industry X = A(60) + B(40) = 100 in 2020."""
    sd = inspect_industries(sut, "X").data.supply_products
    idx = sd.index
    total_mask = idx.get_level_values("transaction_txt") == "Total supply"
    total_row = sd[total_mask].iloc[0]
    assert total_row[2020] == pytest.approx(100.0)
    assert total_row[2021] == pytest.approx(110.0)


def test_supply_products_total_row_has_empty_transaction_and_product(sut):
    """Total supply row has transaction='' and product=''."""
    sd = inspect_industries(sut, "X").data.supply_products
    idx = sd.index
    total_mask = idx.get_level_values("transaction_txt") == "Total supply"
    total_row_idx = idx[total_mask][0]
    assert total_row_idx[idx.names.index("transaction")] == ""
    assert total_row_idx[idx.names.index("product")] == ""


def test_supply_products_data_rows_at_basic_prices(sut):
    """Product A in industry X: basic price = 60 in 2020."""
    sd = inspect_industries(sut, "X").data.supply_products
    idx = sd.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("product") == "A")
    )
    row = sd[mask].iloc[0]
    assert row[2020] == pytest.approx(60.0)


def test_supply_products_excludes_products_not_in_supply_for_industry(sut):
    """Product C supplies industry Y only — should not appear in industry X's detail."""
    sd = inspect_industries(sut, "X").data.supply_products
    idx = sd.index
    product_vals = idx.get_level_values("product").tolist()
    assert "C" not in product_vals


def test_supply_products_multiple_industries(sut):
    """Both industries X and Y appear in supply_products."""
    sd = inspect_industries(sut, ["X", "Y"]).data.supply_products
    idx = sd.index
    industry_vals = idx.get_level_values("industry").unique().tolist()
    assert "X" in industry_vals
    assert "Y" in industry_vals


def test_supply_products_industry_order(sut):
    """Industry X rows appear before Y rows (natural sort order)."""
    sd = inspect_industries(sut, ["Y", "X"]).data.supply_products
    idx = sd.index
    ind_vals = idx.get_level_values("industry").tolist()
    assert ind_vals.index("X") < ind_vals.index("Y")


def test_supply_products_one_total_per_industry(sut):
    """Each industry block has exactly one Total supply row."""
    sd = inspect_industries(sut, ["X", "Y"]).data.supply_products
    idx = sd.index
    total_mask = idx.get_level_values("transaction_txt") == "Total supply"
    assert total_mask.sum() == 2


def test_supply_products_sort_id(sut):
    """With sort_id=2020, rows within industry X are sorted descending by 2020 value."""
    result = inspect_industries(sut, "X", sort_id=2020)
    sd = result.data.supply_products
    idx = sd.index
    data_mask = idx.get_level_values("transaction_txt") != "Total supply"
    data_rows = sd[data_mask]
    values = data_rows[2020].tolist()
    assert values == sorted(values, reverse=True)


def test_supply_products_industry_txt_populated(sut_with_industry_labels):
    result = inspect_industries(sut_with_industry_labels, "X")
    sd = result.data.supply_products
    idx = sd.index
    data_mask = idx.get_level_values("product") != ""
    ind_txt_vals = idx[data_mask].get_level_values("industry_txt").unique().tolist()
    assert "Agriculture" in ind_txt_vals


def test_supply_products_product_txt_empty_when_no_classification(sut):
    result = inspect_industries(sut, "X")
    sd = result.data.supply_products
    idx = sd.index
    data_mask = idx.get_level_values("product") != ""
    prod_txt_vals = idx[data_mask].get_level_values("product_txt").unique().tolist()
    assert prod_txt_vals == [""]


# ---------------------------------------------------------------------------
# supply_products styled property
# ---------------------------------------------------------------------------


def test_supply_products_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.supply_products, Styler)


def test_supply_products_property_data_matches_raw(sut):
    result = inspect_industries(sut, ["X", "Y"])
    assert result.supply_products.data.shape == result.data.supply_products.shape


def test_supply_products_property_numbers_formatted(sut):
    """Data rows should use European number format."""
    result = inspect_industries(sut, "X")
    rendered = result.supply_products.to_html()
    # Product A in X: 60.0 in 2020 → "60,0"
    assert "60,0" in rendered


# ---------------------------------------------------------------------------
# supply_products_distribution data
# ---------------------------------------------------------------------------


def test_supply_products_distribution_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.supply_products_distribution, pd.DataFrame)


def test_supply_products_distribution_same_index_as_supply_products(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.supply_products_distribution.index) == list(
        result.data.supply_products.index
    )


def test_supply_products_distribution_total_row_is_one(sut):
    """Total supply row should have distribution value 1.0 (100% of itself)."""
    dist = inspect_industries(sut, "X").data.supply_products_distribution
    idx = dist.index
    total_mask = idx.get_level_values("transaction_txt") == "Total supply"
    total_row = dist[total_mask].iloc[0]
    assert total_row[2020] == pytest.approx(1.0)
    assert total_row[2021] == pytest.approx(1.0)


def test_supply_products_distribution_product_shares_sum_to_one(sut):
    """Data rows for industry X should sum to 1.0 per year."""
    dist = inspect_industries(sut, "X").data.supply_products_distribution
    idx = dist.index
    data_mask = idx.get_level_values("transaction") != ""
    data_sum = dist[data_mask].sum()
    assert data_sum[2020] == pytest.approx(1.0)
    assert data_sum[2021] == pytest.approx(1.0)


def test_supply_products_distribution_values_correct(sut):
    """Product A in industry X: 60 / 100 = 0.6 in 2020."""
    dist = inspect_industries(sut, "X").data.supply_products_distribution
    idx = dist.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("product") == "A")
    )
    row = dist[mask].iloc[0]
    assert row[2020] == pytest.approx(0.6)


def test_supply_products_distribution_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.supply_products_distribution, Styler)


def test_supply_products_distribution_formatted_as_percentage(sut):
    """Total supply row = 1.0 → formatted as '100,0%'."""
    result = inspect_industries(sut, "X")
    rendered = result.supply_products_distribution.to_html()
    assert "100,0%" in rendered


# ---------------------------------------------------------------------------
# supply_products_growth data
# ---------------------------------------------------------------------------


def test_supply_products_growth_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.supply_products_growth, pd.DataFrame)


def test_supply_products_growth_same_index_as_supply_products(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.supply_products_growth.index) == list(
        result.data.supply_products.index
    )


def test_supply_products_growth_first_year_is_nan(sut):
    result = inspect_industries(sut, "X")
    assert result.data.supply_products_growth[2020].isna().all()


def test_supply_products_growth_values_correct(sut):
    """Product A in industry X: 60 → 66, growth = (66-60)/60 = 0.1."""
    growth = inspect_industries(sut, "X").data.supply_products_growth
    idx = growth.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("product") == "A")
    )
    row = growth[mask].iloc[0]
    assert row[2021] == pytest.approx(0.1)


def test_supply_products_growth_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.supply_products_growth, Styler)


def test_supply_products_growth_formatted_as_percentage(sut):
    """Growth of 10% → formatted as '10,0%'."""
    result = inspect_industries(sut, "X")
    rendered = result.supply_products_growth.to_html()
    assert "10,0%" in rendered


# ---------------------------------------------------------------------------
# use_products data
# ---------------------------------------------------------------------------


def test_use_products_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.use_products, pd.DataFrame)


def test_use_products_index_names(sut):
    result = inspect_industries(sut, "X")
    idx = result.data.use_products.index
    assert idx.names == [
        "industry", "industry_txt", "transaction", "transaction_txt", "product", "product_txt"
    ]


def test_use_products_contains_product_rows_and_total(sut):
    """Industry X uses product A — one data row + one Total use row."""
    ud = inspect_industries(sut, "X").data.use_products
    idx = ud.index
    product_vals = idx.get_level_values("product").tolist()
    trans_txt_vals = idx.get_level_values("transaction_txt").tolist()
    assert "A" in product_vals
    assert "Total use" in trans_txt_vals


def test_use_products_values_at_purchasers_prices(sut):
    """Product A in industry X: purchasers' price (koeb) = 60 in 2020."""
    ud = inspect_industries(sut, "X").data.use_products
    idx = ud.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("product") == "A")
    )
    row = ud[mask].iloc[0]
    assert row[2020] == pytest.approx(60.0)


def test_use_products_total_row_sums_products(sut):
    """Total use for industry X = koeb of product A = 60 in 2020."""
    ud = inspect_industries(sut, "X").data.use_products
    idx = ud.index
    total_mask = idx.get_level_values("transaction_txt") == "Total use"
    total_row = ud[total_mask].iloc[0]
    assert total_row[2020] == pytest.approx(60.0)
    assert total_row[2021] == pytest.approx(66.0)


def test_use_products_total_row_has_empty_transaction_and_product(sut):
    ud = inspect_industries(sut, "X").data.use_products
    idx = ud.index
    total_mask = idx.get_level_values("transaction_txt") == "Total use"
    total_row_idx = idx[total_mask][0]
    assert total_row_idx[idx.names.index("transaction")] == ""
    assert total_row_idx[idx.names.index("product")] == ""


def test_use_products_one_total_per_industry(sut):
    ud = inspect_industries(sut, ["X", "Y"]).data.use_products
    idx = ud.index
    total_mask = idx.get_level_values("transaction_txt") == "Total use"
    assert total_mask.sum() == 2


def test_use_products_sort_id(sut):
    """With sort_id, data rows within each industry are sorted descending."""
    result = inspect_industries(sut, ["X", "Y"], sort_id=2020)
    ud = result.data.use_products
    idx = ud.index
    for industry in ["X", "Y"]:
        ind_mask = (idx.get_level_values("industry") == industry) & (
            idx.get_level_values("transaction") != ""
        )
        values = ud[ind_mask][2020].tolist()
        assert values == sorted(values, reverse=True)


def test_use_products_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.use_products, Styler)


def test_use_products_property_numbers_formatted(sut):
    result = inspect_industries(sut, "X")
    rendered = result.use_products.to_html()
    assert "60,0" in rendered


# ---------------------------------------------------------------------------
# use_products_distribution data
# ---------------------------------------------------------------------------


def test_use_products_distribution_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.use_products_distribution, pd.DataFrame)


def test_use_products_distribution_same_index_as_use_products(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.use_products_distribution.index) == list(
        result.data.use_products.index
    )


def test_use_products_distribution_total_row_is_one(sut):
    dist = inspect_industries(sut, "X").data.use_products_distribution
    idx = dist.index
    total_mask = idx.get_level_values("transaction_txt") == "Total use"
    total_row = dist[total_mask].iloc[0]
    assert total_row[2020] == pytest.approx(1.0)


def test_use_products_distribution_property_returns_styler(sut):
    assert isinstance(inspect_industries(sut, "X").use_products_distribution, Styler)


def test_use_products_distribution_formatted_as_percentage(sut):
    rendered = inspect_industries(sut, "X").use_products_distribution.to_html()
    assert "100,0%" in rendered


# ---------------------------------------------------------------------------
# use_products_coefficients data
# ---------------------------------------------------------------------------


def test_use_products_coefficients_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.use_products_coefficients, pd.DataFrame)


def test_use_products_coefficients_same_index_as_use_products(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.use_products_coefficients.index) == list(
        result.data.use_products.index
    )


def test_use_products_coefficients_denominator_is_total_output(sut):
    """Product A in X: koeb=60, total output=100 → coefficient = 0.6 in 2020."""
    coeffs = inspect_industries(sut, "X").data.use_products_coefficients
    idx = coeffs.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("product") == "A")
    )
    row = coeffs[mask].iloc[0]
    assert row[2020] == pytest.approx(60.0 / 100.0)
    assert row[2021] == pytest.approx(66.0 / 110.0)


def test_use_products_coefficients_total_row_equals_input_coefficient(sut):
    """Total use row / total output = overall input coefficient."""
    coeffs = inspect_industries(sut, "X").data.use_products_coefficients
    idx = coeffs.index
    total_mask = idx.get_level_values("transaction_txt") == "Total use"
    total_row = coeffs[total_mask].iloc[0]
    # Total use=60, total output=100 → 0.6
    assert total_row[2020] == pytest.approx(60.0 / 100.0)
    assert total_row[2021] == pytest.approx(66.0 / 110.0)


def test_use_products_coefficients_differs_from_distribution(sut):
    """Coefficients use total output as denominator; distribution uses total use."""
    result = inspect_industries(sut, "X")
    # For industry X: total output=100, total use=60 → denominators differ
    # distribution total row = 1.0; coefficients total row = 60/100 = 0.6
    coeffs = result.data.use_products_coefficients
    dist = result.data.use_products_distribution
    idx = coeffs.index
    total_mask = idx.get_level_values("transaction_txt") == "Total use"
    assert coeffs[total_mask].iloc[0][2020] == pytest.approx(0.6)
    assert dist[total_mask].iloc[0][2020] == pytest.approx(1.0)


def test_use_products_coefficients_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.use_products_coefficients, Styler)


def test_use_products_coefficients_formatted_as_percentage(sut):
    result = inspect_industries(sut, "X")
    rendered = result.use_products_coefficients.to_html()
    # 60/100 = 60.0% → "60,0%"
    assert "60,0%" in rendered


# ---------------------------------------------------------------------------
# use_products_growth data
# ---------------------------------------------------------------------------


def test_use_products_growth_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.use_products_growth, pd.DataFrame)


def test_use_products_growth_same_index_as_use_products(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.use_products_growth.index) == list(
        result.data.use_products.index
    )


def test_use_products_growth_first_year_is_nan(sut):
    result = inspect_industries(sut, "X")
    assert result.data.use_products_growth[2020].isna().all()


def test_use_products_growth_values_correct(sut):
    """Product A in industry X: koeb 60 → 66, growth = 0.1."""
    growth = inspect_industries(sut, "X").data.use_products_growth
    idx = growth.index
    mask = (
        (idx.get_level_values("industry") == "X")
        & (idx.get_level_values("product") == "A")
    )
    row = growth[mask].iloc[0]
    assert row[2021] == pytest.approx(0.1)


def test_use_products_growth_property_returns_styler(sut):
    assert isinstance(inspect_industries(sut, "X").use_products_growth, Styler)


def test_use_products_growth_formatted_as_percentage(sut):
    rendered = inspect_industries(sut, "X").use_products_growth.to_html()
    assert "10,0%" in rendered


# ---------------------------------------------------------------------------
# balance_growth data
# ---------------------------------------------------------------------------


def test_balance_growth_in_data(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.balance_growth, pd.DataFrame)


def test_balance_growth_same_index_as_balance(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.balance_growth.index) == list(result.data.balance.index)


def test_balance_growth_first_year_is_nan(sut):
    result = inspect_industries(sut, "X")
    # All values in the first id column (2020) should be NaN.
    assert result.data.balance_growth[2020].isna().all()


def test_balance_growth_values_correct(sut):
    """P1 output for X: 100 in 2020, 110 in 2021 → growth = (110-100)/100 = 0.1."""
    balance_growth = inspect_industries(sut, "X").data.balance_growth
    idx = balance_growth.index
    p1_mask = idx.get_level_values("transaction_txt") == "Output at basic prices"
    row = balance_growth[p1_mask].iloc[0]
    assert row[2021] == pytest.approx(0.1)


def test_balance_growth_input_coefficient_growth(sut):
    """Input coefficient for X: 0.6 in 2020, 0.6 in 2021 → growth = 0.0."""
    balance_growth = inspect_industries(sut, "X").data.balance_growth
    idx = balance_growth.index
    coeff_mask = idx.get_level_values("transaction_txt") == "Input coefficient"
    row = balance_growth[coeff_mask].iloc[0]
    assert row[2021] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# balance_growth styled property
# ---------------------------------------------------------------------------


def test_balance_growth_property_returns_styler(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.balance_growth, Styler)


def test_balance_growth_property_all_values_percentage_formatted(sut):
    """In the growth table, all values (including GVA and input coeff) are percentages."""
    result = inspect_industries(sut, "X")
    rendered = result.balance_growth.to_html()
    # P1 growth for X in 2021 is 10% → formatted as "10,0%"
    assert "10,0%" in rendered


# ---------------------------------------------------------------------------
# SUT method delegation
# ---------------------------------------------------------------------------


def test_sut_method_delegates(sut):
    result_free = inspect_industries(sut, "X")
    result_method = sut.inspect_industries("X")
    pd.testing.assert_frame_equal(
        result_free.data.balance, result_method.data.balance
    )


# ---------------------------------------------------------------------------
# supply_products_summary data
# ---------------------------------------------------------------------------
#
# Fixture data (supply, industry X, transaction 0100, basic prices):
#   2020: product A = 60, product B = 40  → total=100, n_products=2
#   2021: product A = 66, product B = 44  → total=110, n_products=2
# Both products non-zero in both years.
# ---------------------------------------------------------------------------


def test_supply_products_summary_is_dataframe(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.supply_products_summary, pd.DataFrame)


def test_supply_products_summary_index_names(sut):
    result = inspect_industries(sut, "X")
    assert result.data.supply_products_summary.index.names == [
        "industry", "industry_txt", "transaction", "transaction_txt", "summary"
    ]


def test_supply_products_summary_columns_are_ids(sut):
    result = inspect_industries(sut, "X")
    assert list(result.data.supply_products_summary.columns) == [2020, 2021]


def test_supply_products_summary_default_row_labels(sut):
    """Default percentiles=[0.5, 1.0] and coverage_thresholds=[0.5, 0.8, 0.95]:
    total_supply, n_products, n_products_median, n_products_p80, n_products_p95,
    value_max, value_median, share_max, share_median.
    """
    result = inspect_industries(sut, "X")
    summary_vals = (
        result.data.supply_products_summary.index
        .get_level_values("summary").tolist()
    )
    assert summary_vals == [
        "total_supply", "n_products",
        "n_products_p50", "n_products_p80", "n_products_p95",
        "value_max", "value_median",
        "share_max", "share_median",
    ]


def test_supply_products_summary_total(sut):
    """total_supply = sum of all product values = 100 in 2020, 110 in 2021."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("total_supply", level="summary")
    assert row[2020].iloc[0] == pytest.approx(100.0)
    assert row[2021].iloc[0] == pytest.approx(110.0)


def test_supply_products_summary_n_products(sut):
    """n_products = 2 for industry X (products A and B are non-zero)."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("n_products", level="summary")
    assert row[2020].iloc[0] == 2
    assert row[2021].iloc[0] == 2


def test_supply_products_summary_value_max(sut):
    """value_max = 60 in 2020 (product A), 66 in 2021."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("value_max", level="summary")
    assert row[2020].iloc[0] == pytest.approx(60.0)
    assert row[2021].iloc[0] == pytest.approx(66.0)


def test_supply_products_summary_value_median(sut):
    """value_median over [40, 60] = 50.0 in 2020."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("value_median", level="summary")
    assert row[2020].iloc[0] == pytest.approx(50.0)


def test_supply_products_summary_share_max(sut):
    """share_max = 60/100 = 0.6 in 2020."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("share_max", level="summary")
    assert row[2020].iloc[0] == pytest.approx(0.6)


def test_supply_products_summary_coverage_both_products_needed(sut):
    """For 80% coverage: product A alone gives 60/100=60% < 80%, so need both → 2."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("n_products_p80", level="summary")
    assert row[2020].iloc[0] == 2


def test_supply_products_summary_coverage_p95(sut):
    """For 95% coverage: also need both products → 2."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("n_products_p95", level="summary")
    assert row[2020].iloc[0] == 2


def test_supply_products_summary_coverage_p50(sut):
    """Default coverage_thresholds includes 0.5: product A alone = 60% >= 50% → 1."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    row = summary.xs("n_products_p50", level="summary")
    assert row[2020].iloc[0] == 1


def test_supply_products_summary_multiple_industries(sut):
    """Both industries X and Y appear with their own summary blocks."""
    summary = inspect_industries(sut, ["X", "Y"]).data.supply_products_summary
    industry_vals = summary.index.get_level_values("industry").unique().tolist()
    assert "X" in industry_vals
    assert "Y" in industry_vals


def test_supply_products_summary_custom_percentiles(sut):
    """Custom percentiles=[0.0, 1.0] produce value_min and value_max rows."""
    result = inspect_industries(sut, "X", percentiles=[0.0, 1.0])
    summary_vals = (
        result.data.supply_products_summary.index
        .get_level_values("summary").tolist()
    )
    assert "value_min" in summary_vals
    assert "value_max" in summary_vals
    assert "value_median" not in summary_vals


def test_supply_products_summary_custom_coverage(sut):
    """Custom coverage_thresholds=[0.9] produces n_products_p90 row only."""
    result = inspect_industries(sut, "X", coverage_thresholds=[0.9])
    summary_vals = (
        result.data.supply_products_summary.index
        .get_level_values("summary").tolist()
    )
    assert "n_products_p90" in summary_vals
    assert "n_products_p80" not in summary_vals
    assert "n_products_p50" not in summary_vals


def test_supply_products_summary_excludes_total_row_from_stats(sut):
    """The Total supply row must not inflate n_products or skew percentiles."""
    summary = inspect_industries(sut, "X").data.supply_products_summary
    # n_products should be 2 (A and B), not 3 (A, B, Total supply row).
    row = summary.xs("n_products", level="summary")
    assert row[2020].iloc[0] == 2


def test_supply_products_summary_total_not_bold(sut):
    """total_supply row should not be bold."""
    rendered = inspect_industries(sut, "X").supply_products_summary.to_html()
    # Find the total_supply row and confirm font-weight: bold is not set on it.
    # We check that bold does not appear anywhere in the rendered output.
    assert "font-weight: bold" not in rendered


def test_supply_products_summary_share_formatted_as_percentage(sut):
    """share_max row should be rendered as a percentage string."""
    rendered = inspect_industries(sut, "X").supply_products_summary.to_html()
    # share_max for X in 2020 = 60/100 = 0.6 → "60,0%"
    assert "60,0%" in rendered


def test_supply_products_summary_n_products_formatted_as_int(sut):
    """n_products row should render as an integer (no decimal point)."""
    rendered = inspect_industries(sut, "X").supply_products_summary.to_html()
    assert ">2<" in rendered


def test_supply_products_summary_property_returns_styler(sut):
    assert isinstance(inspect_industries(sut, "X").supply_products_summary, Styler)


# ---------------------------------------------------------------------------
# use_products_summary data
# ---------------------------------------------------------------------------
#
# Fixture data (use, industry X, transaction 2000, purchasers' prices):
#   2020: product A = 60   (only one non-zero product)
#   2021: product A = 66
# ---------------------------------------------------------------------------


def test_use_products_summary_is_dataframe(sut):
    result = inspect_industries(sut, "X")
    assert isinstance(result.data.use_products_summary, pd.DataFrame)


def test_use_products_summary_index_names(sut):
    result = inspect_industries(sut, "X")
    assert result.data.use_products_summary.index.names == [
        "industry", "industry_txt", "transaction", "transaction_txt", "summary"
    ]


def test_use_products_summary_total(sut):
    """total_use = purchasers' price sum = 60 in 2020."""
    summary = inspect_industries(sut, "X").data.use_products_summary
    row = summary.xs("total_use", level="summary")
    assert row[2020].iloc[0] == pytest.approx(60.0)


def test_use_products_summary_n_products_single(sut):
    """Only one non-zero product for industry X use."""
    summary = inspect_industries(sut, "X").data.use_products_summary
    row = summary.xs("n_products", level="summary")
    assert row[2020].iloc[0] == 1


def test_use_products_summary_coverage_single_product(sut):
    """With a single product, coverage is 1 for any threshold."""
    summary = inspect_industries(sut, "X").data.use_products_summary
    row80 = summary.xs("n_products_p80", level="summary")
    row95 = summary.xs("n_products_p95", level="summary")
    assert row80[2020].iloc[0] == 1
    assert row95[2020].iloc[0] == 1


def test_use_products_summary_property_returns_styler(sut):
    assert isinstance(inspect_industries(sut, "X").use_products_summary, Styler)


# ---------------------------------------------------------------------------
# display_products_n_largest
# ---------------------------------------------------------------------------
#
# Fixture data (supply, industry X, transaction 0100, basic prices, 2020):
#   product A = 60, product B = 40  → A is largest
# Fixture data (use, industry X, transaction 2000, purchasers' prices, 2020):
#   product A = 60  (only product)
# ---------------------------------------------------------------------------


def test_n_largest_returns_industry_inspection(sut):
    result = inspect_industries(sut, "X").display_products_n_largest(1, 2020)
    assert isinstance(result, IndustryInspection)


def test_n_largest_supply_keeps_top_product(sut):
    """n=1 for supply X in 2020 keeps product A (60) and drops B (40)."""
    result = inspect_industries(sut, "X").display_products_n_largest(1, 2020)
    products = result.data.supply_products.index.get_level_values("product").tolist()
    assert "A" in products
    assert "B" not in products


def test_n_largest_supply_keeps_total_row(sut):
    """Total supply row must always be kept regardless of n."""
    result = inspect_industries(sut, "X").display_products_n_largest(1, 2020)
    trans_txts = result.data.supply_products.index.get_level_values("transaction_txt").tolist()
    assert "Total supply" in trans_txts


def test_n_largest_supply_keeps_all_when_n_gte_count(sut):
    """n=10 keeps both products A and B."""
    result = inspect_industries(sut, "X").display_products_n_largest(10, 2020)
    products = result.data.supply_products.index.get_level_values("product").tolist()
    assert "A" in products
    assert "B" in products


def test_n_largest_distribution_sliced_in_lockstep(sut):
    """supply_products_distribution keeps the same product rows as supply_products."""
    result = inspect_industries(sut, "X").display_products_n_largest(1, 2020)
    sp_products = result.data.supply_products.index.get_level_values("product").tolist()
    dist_products = result.data.supply_products_distribution.index.get_level_values("product").tolist()
    assert sp_products == dist_products


def test_n_largest_growth_sliced_in_lockstep(sut):
    """supply_products_growth keeps the same product rows as supply_products."""
    result = inspect_industries(sut, "X").display_products_n_largest(1, 2020)
    sp_products = result.data.supply_products.index.get_level_values("product").tolist()
    growth_products = result.data.supply_products_growth.index.get_level_values("product").tolist()
    assert sp_products == growth_products


def test_n_largest_summary_unchanged(sut):
    """supply_products_summary is not affected by the filter."""
    base = inspect_industries(sut, "X")
    filtered = base.display_products_n_largest(1, 2020)
    pd.testing.assert_frame_equal(
        filtered.data.supply_products_summary, base.data.supply_products_summary
    )


def test_n_largest_balance_unchanged(sut):
    """balance table is not affected by the filter."""
    base = inspect_industries(sut, "X")
    filtered = base.display_products_n_largest(1, 2020)
    pd.testing.assert_frame_equal(filtered.data.balance, base.data.balance)


def test_n_largest_use_filtered_independently(sut):
    """use_products filtered independently; single product kept when n=1."""
    result = inspect_industries(sut, "X").display_products_n_largest(1, 2020)
    products = result.data.use_products.index.get_level_values("product").tolist()
    assert "A" in products


# ---------------------------------------------------------------------------
# display_products_threshold_value
# ---------------------------------------------------------------------------


def test_threshold_value_keeps_above_threshold(sut):
    """threshold=50: keeps A (60 >= 50) and drops B (40 < 50) in supply."""
    result = inspect_industries(sut, "X").display_products_threshold_value(50.0, 2020)
    products = result.data.supply_products.index.get_level_values("product").tolist()
    assert "A" in products
    assert "B" not in products


def test_threshold_value_keeps_total_row(sut):
    """Total supply row always kept."""
    result = inspect_industries(sut, "X").display_products_threshold_value(50.0, 2020)
    trans_txts = result.data.supply_products.index.get_level_values("transaction_txt").tolist()
    assert "Total supply" in trans_txts


def test_threshold_value_keeps_all_when_low(sut):
    """threshold=0 keeps both products."""
    result = inspect_industries(sut, "X").display_products_threshold_value(0.0, 2020)
    products = result.data.supply_products.index.get_level_values("product").tolist()
    assert "A" in products
    assert "B" in products


def test_threshold_value_distribution_sliced_in_lockstep(sut):
    result = inspect_industries(sut, "X").display_products_threshold_value(50.0, 2020)
    sp_products = result.data.supply_products.index.get_level_values("product").tolist()
    dist_products = result.data.supply_products_distribution.index.get_level_values("product").tolist()
    assert sp_products == dist_products


# ---------------------------------------------------------------------------
# display_products_threshold_share
# ---------------------------------------------------------------------------
#
# supply X 2020: A=60/100=0.6, B=40/100=0.4
# ---------------------------------------------------------------------------


def test_threshold_share_keeps_above_threshold(sut):
    """threshold=0.5: keeps A (share=0.6 >= 0.5), drops B (share=0.4 < 0.5)."""
    result = inspect_industries(sut, "X").display_products_threshold_share(0.5, 2020)
    products = result.data.supply_products.index.get_level_values("product").tolist()
    assert "A" in products
    assert "B" not in products


def test_threshold_share_keeps_total_row(sut):
    """Total supply row always kept."""
    result = inspect_industries(sut, "X").display_products_threshold_share(0.5, 2020)
    trans_txts = result.data.supply_products.index.get_level_values("transaction_txt").tolist()
    assert "Total supply" in trans_txts


def test_threshold_share_keeps_all_when_zero(sut):
    """threshold=0 keeps both products."""
    result = inspect_industries(sut, "X").display_products_threshold_share(0.0, 2020)
    products = result.data.supply_products.index.get_level_values("product").tolist()
    assert "A" in products
    assert "B" in products


def test_threshold_share_distribution_sliced_in_lockstep(sut):
    result = inspect_industries(sut, "X").display_products_threshold_share(0.5, 2020)
    sp_products = result.data.supply_products.index.get_level_values("product").tolist()
    dist_products = result.data.supply_products_distribution.index.get_level_values("product").tolist()
    assert sp_products == dist_products


def test_threshold_share_coefficients_sliced_in_lockstep(sut):
    result = inspect_industries(sut, "X").display_products_threshold_share(0.5, 2020)
    sp_products = result.data.use_products.index.get_level_values("product").tolist()
    coeff_products = result.data.use_products_coefficients.index.get_level_values("product").tolist()
    assert sp_products == coeff_products
