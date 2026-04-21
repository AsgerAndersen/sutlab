"""
Tests for inspect_final_uses (use tables only).
"""

import pytest
import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import FinalUseInspection, FinalUseInspectionData, inspect_final_uses


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
    """Four transactions: P1 (supply), P31 (individual cons.), P32 (collective cons.), P6 (exports)."""
    return pd.DataFrame({
        "trans":     ["0100",   "3110",            "3200",        "6001"],
        "trans_txt": ["Output", "Household cons.", "Govt. cons.", "Exports"],
        "table":     ["supply", "use",             "use",         "use"],
        "esa_code":  ["P1",     "P31",             "P32",         "P6"],
    })


@pytest.fixture
def individual_consumption():
    """Two individual consumption categories (P31) with labels."""
    return pd.DataFrame({
        "brch":     ["FKO1",  "FKO2"],
        "brch_txt": ["Food",  "Clothing"],
    })


@pytest.fixture
def collective_consumption():
    """One collective consumption category (P32) with a label."""
    return pd.DataFrame({
        "brch":     ["GOV"],
        "brch_txt": ["Government"],
    })


@pytest.fixture
def supply():
    """Minimal supply data (not used in use table but required by SUT)."""
    return pd.DataFrame({
        "year":  [2020,   2021],
        "nrnr":  ["A",    "A"],
        "trans": ["0100", "0100"],
        "brch":  ["X",    "X"],
        "bas":   [200.0,  220.0],
        "koeb":  [200.0,  220.0],
    })


@pytest.fixture
def use():
    """
    Use data for two years with:
    - 3110 (P31): two categories (FKO1, FKO2)  koeb: 50+35=85 (2020), 55+38=93 (2021).
    - 3200 (P32): one category (GOV)            koeb: 55 (2020), 60 (2021).
    - 6001 (P6):  no category                   koeb: 60 (2020), 66 (2021).
    """
    return pd.DataFrame({
        "year":  [2020,   2020,   2020,   2020,   2021,   2021,   2021,   2021],
        "nrnr":  ["A",    "B",    "A",    "A",    "A",    "B",    "A",    "A"],
        "trans": ["3110", "3110", "3200", "6001", "3110", "3110", "3200", "6001"],
        "brch":  ["FKO1", "FKO2", "GOV",  "",     "FKO1", "FKO2", "GOV",  ""],
        "bas":   [40.0,   30.0,   50.0,   60.0,   44.0,   33.0,   55.0,   66.0],
        "koeb":  [50.0,   35.0,   55.0,   60.0,   55.0,   38.0,   60.0,   66.0],
    })


@pytest.fixture
def sut(columns, transactions, individual_consumption, collective_consumption, supply, use):
    classifications = SUTClassifications(
        transactions=transactions,
        individual_consumption=individual_consumption,
        collective_consumption=collective_consumption,
    )
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_returns_final_use_inspection(sut):
    result = inspect_final_uses(sut, "3110")
    assert isinstance(result, FinalUseInspection)
    assert isinstance(result.data, FinalUseInspectionData)


def test_properties_return_styler(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert isinstance(result.use, Styler)
    assert isinstance(result.use_distribution, Styler)
    assert isinstance(result.use_growth, Styler)
    assert isinstance(result.use_categories, Styler)
    assert isinstance(result.use_categories_distribution, Styler)
    assert isinstance(result.use_categories_growth, Styler)


def test_use_categories_index_levels(sut):
    result = inspect_final_uses(sut, "3110")
    assert result.data.use_categories.index.names == [
        "transaction", "transaction_txt", "category", "category_txt"
    ]


def test_use_categories_columns_are_ids(sut):
    result = inspect_final_uses(sut, "3110")
    assert list(result.data.use_categories.columns) == [2020, 2021]


# ---------------------------------------------------------------------------
# "Total use" row — always at the bottom, single grand total
# ---------------------------------------------------------------------------


def test_total_use_row_always_present_single_transaction(sut):
    result = inspect_final_uses(sut, "3110")
    trans_txt = result.data.use_categories.index.get_level_values("transaction_txt").tolist()
    assert trans_txt[-1] == "Total use"


def test_total_use_row_always_present_uncategorised(sut):
    result = inspect_final_uses(sut, "6001")
    trans_txt = result.data.use_categories.index.get_level_values("transaction_txt").tolist()
    assert trans_txt[-1] == "Total use"


def test_total_use_row_is_last_row(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    last = result.data.use_categories.index[-1]
    assert last[1] == "Total use"  # transaction_txt level


def test_total_use_row_label(sut):
    result = inspect_final_uses(sut, "3110")
    last = result.data.use_categories.index[-1]
    assert last == ("", "Total use", "", "")


def test_total_use_row_equals_grand_sum(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    use = result.data.use_categories
    total_row = use.iloc[-1]
    data_rows_sum = use.iloc[:-1].sum(axis=0)
    assert total_row[2020] == pytest.approx(data_rows_sum[2020])
    assert total_row[2021] == pytest.approx(data_rows_sum[2021])


def test_exactly_one_total_use_row(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    trans_txt = result.data.use_categories.index.get_level_values("transaction_txt").tolist()
    assert trans_txt.count("Total use") == 1


# ---------------------------------------------------------------------------
# P31 (categorised, two categories)
# ---------------------------------------------------------------------------


def test_p31_two_data_rows(sut):
    result = inspect_final_uses(sut, "3110")
    # FKO1 + FKO2 + Total use = 3 rows
    assert len(result.data.use_categories) == 3


def test_p31_category_labels_from_classification(sut):
    result = inspect_final_uses(sut, "3110")
    cat_txt = result.data.use_categories.index.get_level_values("category_txt").tolist()
    assert "Food" in cat_txt
    assert "Clothing" in cat_txt


def test_p31_values_at_purchasers_prices(sut):
    result = inspect_final_uses(sut, "3110")
    use = result.data.use_categories
    fko1_row = use[use.index.get_level_values("category") == "FKO1"].iloc[0]
    assert fko1_row[2020] == pytest.approx(50.0)
    assert fko1_row[2021] == pytest.approx(55.0)


def test_p31_total_use_values(sut):
    result = inspect_final_uses(sut, "3110")
    total_row = result.data.use_categories.iloc[-1]
    # 50 + 35 = 85 (2020), 55 + 38 = 93 (2021)
    assert total_row[2020] == pytest.approx(85.0)
    assert total_row[2021] == pytest.approx(93.0)


# ---------------------------------------------------------------------------
# P32 (categorised, one category)
# ---------------------------------------------------------------------------


def test_p32_one_data_row_plus_total(sut):
    result = inspect_final_uses(sut, "3200")
    # GOV + Total use = 2 rows
    assert len(result.data.use_categories) == 2


def test_p32_category_label_from_classification(sut):
    result = inspect_final_uses(sut, "3200")
    cat_txt = result.data.use_categories.index.get_level_values("category_txt").tolist()
    assert "Government" in cat_txt


# ---------------------------------------------------------------------------
# P6 (uncategorised)
# ---------------------------------------------------------------------------


def test_p6_one_data_row_plus_total(sut):
    result = inspect_final_uses(sut, "6001")
    # single uncategorised row + Total use = 2 rows
    assert len(result.data.use_categories) == 2


def test_p6_empty_category_labels(sut):
    result = inspect_final_uses(sut, "6001")
    use = result.data.use_categories
    data_row = use.iloc[0]
    assert use.index[0] == ("6001", "Exports", "", "")
    assert data_row[2020] == pytest.approx(60.0)


def test_p6_total_equals_data_row(sut):
    result = inspect_final_uses(sut, "6001")
    use = result.data.use_categories
    assert use.iloc[-1][2020] == pytest.approx(use.iloc[0][2020])
    assert use.iloc[-1][2021] == pytest.approx(use.iloc[0][2021])


# ---------------------------------------------------------------------------
# Multiple transactions together
# ---------------------------------------------------------------------------


def test_mixed_transactions_row_order(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    use = result.data.use_categories
    trans_vals = use.index.get_level_values("transaction").tolist()
    # 3110 (FKO1, FKO2), 3200 (GOV), 6001 (""), Total use ("")
    assert trans_vals[:2] == ["3110", "3110"]
    assert trans_vals[2] == "3200"
    assert trans_vals[3] == "6001"
    assert trans_vals[4] == ""  # Total use


def test_mixed_transactions_grand_total(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    total_row = result.data.use_categories.iloc[-1]
    # 2020: 50+35+55+60 = 200; 2021: 55+38+60+66 = 219
    assert total_row[2020] == pytest.approx(200.0)
    assert total_row[2021] == pytest.approx(219.0)


# ---------------------------------------------------------------------------
# ids filter
# ---------------------------------------------------------------------------


def test_ids_filter_single_year(sut):
    result = inspect_final_uses(sut, "3110", ids=2021)
    assert list(result.data.use_categories.columns) == [2021]


def test_ids_filter_list(sut):
    result = inspect_final_uses(sut, "3110", ids=[2020])
    assert list(result.data.use_categories.columns) == [2020]


def test_ids_filter_unknown_raises(sut):
    with pytest.raises(ValueError, match="not found"):
        inspect_final_uses(sut, "3110", ids=1999)


# ---------------------------------------------------------------------------
# categories filter
# ---------------------------------------------------------------------------


def test_categories_filter_restricts_p31(sut):
    result = inspect_final_uses(sut, "3110", categories="FKO1")
    use = result.data.use_categories
    cat_vals = use.index.get_level_values("category").tolist()
    # FKO1 data row + Total use row (empty category)
    assert cat_vals == ["FKO1", ""]


def test_categories_filter_keeps_uncategorised_transactions(sut):
    # categories filter should not exclude uncategorised transactions like P6.
    result = inspect_final_uses(sut, ["3110", "6001"], categories="FKO1")
    use = result.data.use_categories
    trans_vals = use.index.get_level_values("transaction").tolist()
    assert "6001" in trans_vals


# ---------------------------------------------------------------------------
# use_categories_distribution
# ---------------------------------------------------------------------------


def test_distribution_grand_total_row_is_one(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_categories_distribution
    total_row = dist.iloc[-1]
    assert list(total_row) == pytest.approx([1.0, 1.0])


def test_distribution_sums_to_one(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_categories_distribution
    data_rows = dist.iloc[:-1]  # exclude Total use row
    sums = data_rows.sum(axis=0)
    assert sums[2020] == pytest.approx(1.0)
    assert sums[2021] == pytest.approx(1.0)


def test_distribution_values_correct(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_categories_distribution
    use = result.data.use_categories
    # FKO1 share of grand total in 2020: 50 / 200 = 0.25
    fko1_share = dist[dist.index.get_level_values("category") == "FKO1"].iloc[0][2020]
    assert fko1_share == pytest.approx(50.0 / 200.0)


def test_distribution_single_transaction_total_is_one(sut):
    # Single transaction: grand total = transaction total, so all shares sum to 1.
    result = inspect_final_uses(sut, "6001")
    dist = result.data.use_categories_distribution
    assert list(dist.iloc[-1]) == pytest.approx([1.0, 1.0])


def test_distribution_same_index_as_use(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert result.data.use_categories.index.equals(result.data.use_categories_distribution.index)


# ---------------------------------------------------------------------------
# use_categories_growth
# ---------------------------------------------------------------------------


def test_growth_first_year_is_nan(sut):
    result = inspect_final_uses(sut, "3110")
    growth = result.data.use_categories_growth
    assert growth[2020].isna().all()


def test_growth_second_year_correct(sut):
    result = inspect_final_uses(sut, "3110")
    growth = result.data.use_categories_growth
    cat = growth.index.get_level_values("category")
    fko1_growth = growth[cat == "FKO1"].iloc[0][2021]
    # FKO1: 50 → 55 → growth = (55 - 50) / 50 = 0.10
    assert fko1_growth == pytest.approx(0.10)


def test_growth_total_use_row_correct(sut):
    result = inspect_final_uses(sut, "3110")
    growth = result.data.use_categories_growth
    total_growth = growth.iloc[-1][2021]
    # Total: 85 → 93 → growth = (93 - 85) / 85
    assert total_growth == pytest.approx((93.0 - 85.0) / 85.0)


def test_growth_same_index_as_use(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert result.data.use_categories.index.equals(result.data.use_categories_growth.index)


# ---------------------------------------------------------------------------
# use — transaction-level
# ---------------------------------------------------------------------------


def test_use_index_levels(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert result.data.use.index.names == ["transaction", "transaction_txt"]


def test_use_columns_are_ids(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert list(result.data.use.columns) == [2020, 2021]


def test_use_row_per_transaction_plus_total(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    # 3 transactions + 1 Total use = 4 rows.
    assert len(result.data.use) == 4


def test_use_total_row_label(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    last = result.data.use.index[-1]
    assert last == ("", "Total use")


def test_use_values_sum_across_categories(sut):
    # 3110 total: FKO1(50)+FKO2(35)=85 (2020), FKO1(55)+FKO2(38)=93 (2021).
    result = inspect_final_uses(sut, "3110")
    row = result.data.use.loc[("3110", "Household cons.")]
    assert row[2020] == pytest.approx(85.0)
    assert row[2021] == pytest.approx(93.0)


def test_use_total_equals_sum_of_transactions(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    # grand total: 200 (2020), 219 (2021).
    total = result.data.use.iloc[-1]
    assert total[2020] == pytest.approx(200.0)
    assert total[2021] == pytest.approx(219.0)


def test_use_distribution_total_row_is_one(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    total_row = result.data.use_distribution.iloc[-1]
    assert list(total_row) == pytest.approx([1.0, 1.0])


def test_use_distribution_values_correct(sut):
    # 3110 share: 85/200=0.425 (2020), 93/219≈0.4247 (2021).
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_distribution
    row_3110 = dist.loc[("3110", "Household cons.")]
    assert row_3110[2020] == pytest.approx(85 / 200)
    assert row_3110[2021] == pytest.approx(93 / 219)


def test_use_growth_first_year_nan(sut):
    result = inspect_final_uses(sut, "3110")
    growth = result.data.use_growth
    assert growth[2020].isna().all()


def test_use_growth_values_correct(sut):
    # 3110 growth: (93-85)/85 ≈ 0.09412.
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    growth = result.data.use_growth
    row_3110 = growth.loc[("3110", "Household cons.")]
    assert row_3110[2021] == pytest.approx((93 - 85) / 85)


def test_use_properties_return_styler(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert isinstance(result.use, Styler)
    assert isinstance(result.use_distribution, Styler)
    assert isinstance(result.use_growth, Styler)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_error_no_metadata(supply, use):
    sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
    with pytest.raises(ValueError, match="sut.metadata is required"):
        inspect_final_uses(sut_no_meta, "3110")


def test_error_no_classifications(columns, supply, use):
    metadata = SUTMetadata(columns=columns)
    sut_no_cls = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
    with pytest.raises(ValueError, match="classifications.transactions is required"):
        inspect_final_uses(sut_no_cls, "3110")


def test_error_no_transaction_match(sut):
    with pytest.raises(ValueError, match="No final use transactions matched"):
        inspect_final_uses(sut, "9999")


def test_error_p2_code_excluded_from_candidates(sut):
    with pytest.raises(ValueError, match="No final use transactions matched"):
        inspect_final_uses(sut, "2000")


def test_error_p1_code_excluded_from_candidates(sut):
    with pytest.raises(ValueError, match="No final use transactions matched"):
        inspect_final_uses(sut, "0100")


def test_error_unknown_id(sut):
    with pytest.raises(ValueError, match="not found"):
        inspect_final_uses(sut, "3110", ids=1999)


# ---------------------------------------------------------------------------
# use_products — basic structure
# ---------------------------------------------------------------------------


def test_use_products_index_levels(sut):
    result = inspect_final_uses(sut, "3110")
    assert result.data.use_products.index.names == [
        "transaction", "transaction_txt", "category", "category_txt",
        "product", "product_txt",
    ]


def test_use_products_columns_are_ids(sut):
    result = inspect_final_uses(sut, "3110")
    assert list(result.data.use_products.columns) == [2020, 2021]


def test_use_products_total_use_row_last(sut):
    result = inspect_final_uses(sut, "3110")
    assert result.data.use_products.index[-1] == ("", "Total use", "", "", "", "")


def test_use_products_total_use_row_equals_grand_sum(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    ud = result.data.use_products
    total_row = ud.iloc[-1]
    data_sum = ud.iloc[:-1].sum(axis=0)
    assert total_row[2020] == pytest.approx(data_sum[2020])
    assert total_row[2021] == pytest.approx(data_sum[2021])


def test_use_products_single_transaction_row_count(sut):
    result = inspect_final_uses(sut, "3110")
    # (FKO1, A) + (FKO2, B) + Total use = 3 rows
    assert len(result.data.use_products) == 3


def test_use_products_all_transactions_row_count(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    # (FKO1,A) + (FKO2,B) + (GOV,A) + ("","",A) + Total use = 5 rows
    assert len(result.data.use_products) == 5


# ---------------------------------------------------------------------------
# use_products — values and labels
# ---------------------------------------------------------------------------


def test_use_products_values_at_purchasers_prices(sut):
    result = inspect_final_uses(sut, "3110")
    ud = result.data.use_products
    fko1_row = ud[ud.index.get_level_values("category") == "FKO1"].iloc[0]
    assert fko1_row[2020] == pytest.approx(50.0)
    assert fko1_row[2021] == pytest.approx(55.0)


def test_use_products_category_labels(sut):
    result = inspect_final_uses(sut, "3110")
    ud = result.data.use_products
    cat_txt = [t for t in ud.index.get_level_values("category_txt") if t != ""]
    assert "Food" in cat_txt
    assert "Clothing" in cat_txt


def test_use_products_product_codes_present(sut):
    result = inspect_final_uses(sut, "3110")
    ud = result.data.use_products
    prod_vals = ud.index.get_level_values("product").tolist()
    assert "A" in prod_vals
    assert "B" in prod_vals


def test_use_products_product_total_correct(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    total_row = result.data.use_products.iloc[-1]
    # 2020: 50+35+55+60 = 200; 2021: 55+38+60+66 = 219
    assert total_row[2020] == pytest.approx(200.0)
    assert total_row[2021] == pytest.approx(219.0)


# ---------------------------------------------------------------------------
# use_products — uncategorised transactions
# ---------------------------------------------------------------------------


def test_use_products_uncategorised_row_structure(sut):
    result = inspect_final_uses(sut, "6001")
    ud = result.data.use_products
    # 1 product row (empty category) + Total use = 2 rows
    assert len(ud) == 2
    first = ud.index[0]
    assert first[:4] == ("6001", "Exports", "", "")
    assert first[4] == "A"


def test_use_products_uncategorised_values(sut):
    result = inspect_final_uses(sut, "6001")
    ud = result.data.use_products
    data_row = ud.iloc[0]
    assert data_row[2020] == pytest.approx(60.0)
    assert data_row[2021] == pytest.approx(66.0)


# ---------------------------------------------------------------------------
# use_products — product ordering with classification
# ---------------------------------------------------------------------------


def test_use_products_product_names_from_classification(columns, transactions,
                                                        individual_consumption,
                                                        collective_consumption,
                                                        supply, use):
    products = pd.DataFrame({
        "nrnr":     ["A",     "B"],
        "nrnr_txt": ["Prod A", "Prod B"],
    })
    classifications = SUTClassifications(
        transactions=transactions,
        individual_consumption=individual_consumption,
        collective_consumption=collective_consumption,
        products=products,
    )
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    sut_with_prods = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
    result = inspect_final_uses(sut_with_prods, "3110")
    ud = result.data.use_products
    prod_txt = [t for t in ud.index.get_level_values("product_txt") if t != ""]
    assert "Prod A" in prod_txt
    assert "Prod B" in prod_txt


def test_use_products_product_classification_order(columns, transactions,
                                                   individual_consumption,
                                                   collective_consumption,
                                                   supply, use):
    # B listed first in classification → B should appear before A.
    products = pd.DataFrame({
        "nrnr":     ["B",     "A"],
        "nrnr_txt": ["Prod B", "Prod A"],
    })
    classifications = SUTClassifications(
        transactions=transactions,
        individual_consumption=individual_consumption,
        collective_consumption=collective_consumption,
        products=products,
    )
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    sut_with_prods = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
    result = inspect_final_uses(sut_with_prods, "3110")
    ud = result.data.use_products
    # FKO2 has B, FKO1 has A. Classification order is B then A.
    # Since categories are in classification order (FKO1 first), FKO1 row comes
    # first (product A). FKO2 comes second (product B, first in prod classification).
    # Within FKO1 block, only A is present; within FKO2, only B is present.
    prod_vals = ud.index.get_level_values("product").tolist()[:-1]  # exclude Total use
    assert prod_vals == ["A", "B"]  # FKO1 block (A) before FKO2 block (B)


# ---------------------------------------------------------------------------
# use_products_distribution
# ---------------------------------------------------------------------------


def test_use_products_distribution_grand_total_is_one(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_products_distribution
    total_row = dist.iloc[-1]
    assert list(total_row) == pytest.approx([1.0, 1.0])


def test_use_products_distribution_sums_to_one(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_products_distribution
    data_sum = dist.iloc[:-1].sum(axis=0)
    assert data_sum[2020] == pytest.approx(1.0)
    assert data_sum[2021] == pytest.approx(1.0)


def test_use_products_distribution_value_correct(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    dist = result.data.use_products_distribution
    # FKO1+A share of grand total in 2020: 50 / 200 = 0.25
    fko1_share = dist[dist.index.get_level_values("category") == "FKO1"].iloc[0][2020]
    assert fko1_share == pytest.approx(50.0 / 200.0)


# ---------------------------------------------------------------------------
# use_products_growth
# ---------------------------------------------------------------------------


def test_use_products_growth_first_year_nan(sut):
    result = inspect_final_uses(sut, "3110")
    growth = result.data.use_products_growth
    assert growth[2020].isna().all()


def test_use_products_growth_second_year_correct(sut):
    result = inspect_final_uses(sut, "3110")
    growth = result.data.use_products_growth
    fko1_row = growth[growth.index.get_level_values("category") == "FKO1"].iloc[0]
    # FKO1+A: 50 → 55 → (55-50)/50 = 0.10
    assert fko1_row[2021] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# use_products — Styler properties
# ---------------------------------------------------------------------------


def test_use_products_properties_return_styler(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert isinstance(result.use_products, Styler)
    assert isinstance(result.use_products_distribution, Styler)
    assert isinstance(result.use_products_growth, Styler)


# ---------------------------------------------------------------------------
# price_layers fixtures — use data extended with a VAT column
# ---------------------------------------------------------------------------


import dataclasses as _dc


@pytest.fixture
def columns_with_layers(columns):
    return _dc.replace(columns, vat="vat")


@pytest.fixture
def use_with_layers():
    """Use data with a VAT column.

    - 3110/FKO1 (A): bas=40/44, vat=10/11, koeb=50/55
    - 3110/FKO2 (B): bas=30/33, vat=5/5,   koeb=35/38
    - 3200/GOV  (A): bas=50/55, vat=5/5,   koeb=55/60
    - 6001/""   (A): bas=60/66, vat=0/0,   koeb=60/66  (exports have no VAT)
    """
    return pd.DataFrame({
        "year":  [2020,   2020,   2020,   2020,   2021,   2021,   2021,   2021],
        "nrnr":  ["A",    "B",    "A",    "A",    "A",    "B",    "A",    "A"],
        "trans": ["3110", "3110", "3200", "6001", "3110", "3110", "3200", "6001"],
        "brch":  ["FKO1", "FKO2", "GOV",  "",     "FKO1", "FKO2", "GOV",  ""],
        "bas":   [40.0,   30.0,   50.0,   60.0,   44.0,   33.0,   55.0,   66.0],
        "vat":   [10.0,    5.0,    5.0,    0.0,   11.0,    5.0,    5.0,    0.0],
        "koeb":  [50.0,   35.0,   55.0,   60.0,   55.0,   38.0,   60.0,   66.0],
    })


@pytest.fixture
def sut_with_layers(columns_with_layers, transactions, individual_consumption,
                    collective_consumption, supply, use_with_layers):
    classifications = SUTClassifications(
        transactions=transactions,
        individual_consumption=individual_consumption,
        collective_consumption=collective_consumption,
    )
    metadata = SUTMetadata(columns=columns_with_layers, classifications=classifications)
    return SUT(
        price_basis="current_year",
        supply=supply,
        use=use_with_layers,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# price_layers — empty when no price layer columns
# ---------------------------------------------------------------------------


def test_price_layers_empty_without_layer_columns(sut):
    result = inspect_final_uses(sut, ["3110", "3200", "6001"])
    assert result.data.price_layers.empty


# ---------------------------------------------------------------------------
# price_layers — basic structure
# ---------------------------------------------------------------------------


def test_price_layers_index_levels(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    assert result.data.price_layers.index.names == [
        "transaction", "transaction_txt", "category", "category_txt", "price_layer",
    ]


def test_price_layers_columns_are_ids(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    assert list(result.data.price_layers.columns) == [2020, 2021]


def test_price_layers_excludes_price_basic(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    layers = result.data.price_layers.index.get_level_values("price_layer").tolist()
    assert "bas" not in layers


def test_price_layers_has_vat_row(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    layers = result.data.price_layers.index.get_level_values("price_layer").tolist()
    assert "vat" in layers


def test_price_layers_no_total_rows(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    layers = result.data.price_layers.index.get_level_values("price_layer").tolist()
    assert "" not in layers


def test_price_layers_row_count_all_transactions(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    # FKO1: vat=1, FKO2: vat=1, GOV: vat=1, 6001/"": vat=0 (all zeros) → 3 total.
    assert len(result.data.price_layers) == 3


def test_price_layers_vat_values_correct(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    pl = result.data.price_layers
    fko1_vat = pl[
        (pl.index.get_level_values("category") == "FKO1")
        & (pl.index.get_level_values("price_layer") == "vat")
    ].iloc[0]
    assert fko1_vat[2020] == pytest.approx(10.0)
    assert fko1_vat[2021] == pytest.approx(11.0)


# ---------------------------------------------------------------------------
# price_layers_rates
# ---------------------------------------------------------------------------


def test_price_layers_rates_excludes_price_basic(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    rates = result.data.price_layers_rates
    assert not rates.empty
    layers = rates.index.get_level_values("price_layer").tolist()
    assert "bas" not in layers


def test_price_layers_rates_excludes_total_rows(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    rates = result.data.price_layers_rates
    layers = rates.index.get_level_values("price_layer").tolist()
    assert "" not in layers


def test_price_layers_rates_vat_correct(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    rates = result.data.price_layers_rates
    fko1_vat = rates[
        (rates.index.get_level_values("category") == "FKO1")
        & (rates.index.get_level_values("price_layer") == "vat")
    ].iloc[0]
    # VAT rate = vat / price_basic: 10/40 = 0.25 (2020), 11/44 = 0.25 (2021).
    assert fko1_vat[2020] == pytest.approx(0.25)
    assert fko1_vat[2021] == pytest.approx(0.25)


def test_price_layers_rates_empty_when_no_layer_columns(sut):
    result = inspect_final_uses(sut, "3110")
    assert result.data.price_layers_rates.empty


# ---------------------------------------------------------------------------
# price_layers_distribution
# ---------------------------------------------------------------------------


def test_price_layers_distribution_values_correct(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    dist = result.data.price_layers_distribution
    # FKO1 has only vat as layer → distribution = vat / vat = 1.0.
    fko1_vat = dist[
        (dist.index.get_level_values("category") == "FKO1")
        & (dist.index.get_level_values("price_layer") == "vat")
    ].iloc[0]
    assert fko1_vat[2020] == pytest.approx(1.0)
    assert fko1_vat[2021] == pytest.approx(1.0)


def test_price_layers_distribution_same_index_as_price_layers(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    assert result.data.price_layers.index.equals(
        result.data.price_layers_distribution.index
    )


# ---------------------------------------------------------------------------
# price_layers_growth
# ---------------------------------------------------------------------------


def test_price_layers_growth_first_year_nan(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    growth = result.data.price_layers_growth
    assert growth[2020].isna().all()


def test_price_layers_growth_values_correct(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, "3110")
    growth = result.data.price_layers_growth
    # FKO1 vat: (11-10)/10 = 0.1.
    fko1_vat = growth[
        (growth.index.get_level_values("category") == "FKO1")
        & (growth.index.get_level_values("price_layer") == "vat")
    ].iloc[0]
    assert fko1_vat[2021] == pytest.approx(0.1)


def test_price_layers_growth_same_index_as_price_layers(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    assert result.data.price_layers.index.equals(
        result.data.price_layers_growth.index
    )


# ---------------------------------------------------------------------------
# price_layers — Styler properties
# ---------------------------------------------------------------------------


def test_price_layers_properties_return_styler(sut_with_layers):
    result = inspect_final_uses(sut_with_layers, ["3110", "3200", "6001"])
    assert isinstance(result.price_layers, Styler)
    assert isinstance(result.price_layers_rates, Styler)
    assert isinstance(result.price_layers_distribution, Styler)
    assert isinstance(result.price_layers_growth, Styler)
