"""
Tests for inspect_products.
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
    """Two supply transactions and two use transactions, with names."""
    return pd.DataFrame({
        "code":     ["0100",                    "0700",    "2000",                     "6001"],
        "name":     ["Output at basic prices",  "Imports", "Intermediate consumption", "Exports"],
        "table":    ["supply",                  "supply",  "use",                      "use"],
        "esa_code": ["P1",                       "P7",      "P2",                       "P6"],
    })


@pytest.fixture
def supply():
    """
    Two products over two years:
      A — output (0100) and imports (0700) in both years
      T — output only (0100), no use rows (supply-only product)
    """
    return pd.DataFrame({
        "year":  [2020, 2020, 2020, 2021, 2021, 2021],
        "nrnr":  ["A",  "A",  "T",  "A",  "A",  "T"],
        "trans": ["0100", "0700", "0100", "0100", "0700", "0100"],
        "brch":  ["X",   "",    "Z",   "X",   "",    "Z"],
        "bas":   [100.0, 20.0,  30.0,  110.0, 25.0,  35.0],
        "koeb":  [100.0, 20.0,  30.0,  110.0, 25.0,  35.0],
    })


@pytest.fixture
def use():
    """Product A has two use transactions; product T has none."""
    return pd.DataFrame({
        "year":  [2020, 2020, 2021, 2021],
        "nrnr":  ["A",  "A",  "A",  "A"],
        "trans": ["2000", "6001", "2000", "6001"],
        "brch":  ["X",   "",    "X",   ""],
        "bas":   [80.0,  40.0,  85.0,  50.0],
        "koeb":  [80.0,  40.0,  85.0,  50.0],
    })


@pytest.fixture
def sut(supply, use, columns, transactions):
    classifications = SUTClassifications(transactions=transactions)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def sut_with_product_labels(supply, use, columns, transactions):
    products = pd.DataFrame({
        "code": ["A", "T"],
        "name": ["Agricultural goods", "Trade services"],
    })
    classifications = SUTClassifications(transactions=transactions, products=products)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def supply_multi_cat():
    """Product A has two industry categories for output."""
    return pd.DataFrame({
        "year":  [2020, 2020, 2020, 2021, 2021, 2021],
        "nrnr":  ["A",  "A",  "A",  "A",  "A",  "A"],
        "trans": ["0100", "0100", "0700", "0100", "0100", "0700"],
        "brch":  ["X",   "Y",   "",    "X",   "Y",   ""],
        "bas":   [60.0,  40.0,  20.0,  66.0,  44.0,  25.0],
        "koeb":  [60.0,  40.0,  20.0,  66.0,  44.0,  25.0],
    })


@pytest.fixture
def use_multi_cat():
    """Product A has two industry categories for IC."""
    return pd.DataFrame({
        "year":  [2020, 2020, 2020, 2021, 2021, 2021],
        "nrnr":  ["A",  "A",  "A",  "A",  "A",  "A"],
        "trans": ["2000", "2000", "6001", "2000", "2000", "6001"],
        "brch":  ["X",   "Y",   "",    "X",   "Y",   ""],
        "bas":   [60.0,  20.0,  40.0,  63.0,  22.0,  50.0],
        "koeb":  [60.0,  20.0,  40.0,  63.0,  22.0,  50.0],
    })


@pytest.fixture
def sut_multi_cat(supply_multi_cat, use_multi_cat, columns, transactions):
    classifications = SUTClassifications(transactions=transactions)
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(
        price_basis="current_year",
        supply=supply_multi_cat,
        use=use_multi_cat,
        metadata=metadata,
    )


@pytest.fixture
def sut_with_industry_labels(supply, use, columns, transactions):
    """SUT with both product and industry classification labels."""
    products = pd.DataFrame({
        "code": ["A", "T"],
        "name": ["Agricultural goods", "Trade services"],
    })
    industries = pd.DataFrame({
        "code": ["X", "Y", "Z"],
        "name": ["Industry X", "Industry Y", "Trade industry"],
    })
    classifications = SUTClassifications(
        transactions=transactions, products=products, industries=industries
    )
    metadata = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _level(result, level_name):
    """Return the values of one MultiIndex level as a list."""
    return result.balance.index.get_level_values(level_name).tolist()


def _unique_level(result, level_name):
    return result.balance.index.get_level_values(level_name).unique().tolist()


def _block_level(result, product_code, level_name):
    """Return level values for a single product block."""
    return result.balance.loc[product_code].index.get_level_values(level_name).tolist()


# ---------------------------------------------------------------------------
# Tests: return type
# ---------------------------------------------------------------------------


class TestInspectProductsReturnType:

    def test_returns_product_inspection(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result, ProductInspection)

    def test_balance_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance, pd.DataFrame)

    def test_supply_detail_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.supply_detail, pd.DataFrame)

    def test_use_detail_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.use_detail, pd.DataFrame)


# ---------------------------------------------------------------------------
# Tests: MultiIndex structure
# ---------------------------------------------------------------------------


class TestBalanceTableIndex:

    def test_index_is_multiindex(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance.index, pd.MultiIndex)

    def test_index_has_four_levels(self, sut):
        result = inspect_products(sut, "A")
        assert result.balance.index.nlevels == 4

    def test_index_level_names(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.balance.index.names) == [
            "product", "product_txt", "transaction", "transaction_txt"
        ]

    def test_product_level_contains_code(self, sut):
        result = inspect_products(sut, "A")
        assert _unique_level(result, "product") == ["A"]

    def test_multiple_products_both_in_product_level(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert set(_unique_level(result, "product")) == {"A", "T"}

    def test_multiple_products_in_natural_sort_order(self, sut):
        result = inspect_products(sut, ["T", "A"])  # reversed input
        product_values = _level(result, "product")
        first_a = product_values.index("A")
        first_t = product_values.index("T")
        assert first_a < first_t

    def test_columns_are_sorted_ids(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.balance.columns) == [2020, 2021]


# ---------------------------------------------------------------------------
# Tests: row labels
# ---------------------------------------------------------------------------


class TestBalanceTableRowLabels:

    def test_supply_transaction_code_in_transaction_level(self, sut):
        result = inspect_products(sut, "A")
        assert "0100" in _block_level(result, "A", "transaction")
        assert "0700" in _block_level(result, "A", "transaction")

    def test_supply_transaction_name_in_transaction_txt_level(self, sut):
        result = inspect_products(sut, "A")
        assert "Output at basic prices" in _block_level(result, "A", "transaction_txt")
        assert "Imports" in _block_level(result, "A", "transaction_txt")

    def test_use_transaction_code_in_transaction_level(self, sut):
        result = inspect_products(sut, "A")
        assert "2000" in _block_level(result, "A", "transaction")
        assert "6001" in _block_level(result, "A", "transaction")

    def test_use_transaction_name_in_transaction_txt_level(self, sut):
        result = inspect_products(sut, "A")
        assert "Intermediate consumption" in _block_level(result, "A", "transaction_txt")
        assert "Exports" in _block_level(result, "A", "transaction_txt")

    def test_summary_rows_have_empty_transaction_code(self, sut):
        result = inspect_products(sut, "A")
        tx_codes = _block_level(result, "A", "transaction")
        tx_txts = _block_level(result, "A", "transaction_txt")
        for summary in ("Total supply", "Total use", "Balance"):
            pos = tx_txts.index(summary)
            assert tx_codes[pos] == ""

    def test_summary_rows_in_transaction_txt_level(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        assert "Total supply" in tx_txts
        assert "Total use" in tx_txts
        assert "Balance" in tx_txts

    def test_supply_transactions_before_total_supply(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        total_supply_pos = tx_txts.index("Total supply")
        assert tx_txts.index("Output at basic prices") < total_supply_pos
        assert tx_txts.index("Imports") < total_supply_pos

    def test_total_supply_before_use_transactions(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        total_supply_pos = tx_txts.index("Total supply")
        assert tx_txts.index("Intermediate consumption") > total_supply_pos

    def test_use_transactions_before_total_use(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        total_use_pos = tx_txts.index("Total use")
        assert tx_txts.index("Intermediate consumption") < total_use_pos
        assert tx_txts.index("Exports") < total_use_pos

    def test_balance_is_last_row(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        assert tx_txts[-1] == "Balance"

    def test_supply_transactions_in_natural_sort_order(self, sut):
        result = inspect_products(sut, "A")
        tx_codes = _block_level(result, "A", "transaction")
        # 0100 before 0700
        supply_codes = [c for c in tx_codes if c in ("0100", "0700")]
        assert supply_codes == ["0100", "0700"]


# ---------------------------------------------------------------------------
# Tests: values
# ---------------------------------------------------------------------------


class TestBalanceTableValues:

    def test_supply_transaction_values(self, sut):
        # No product labels in this fixture, so product_txt=""
        result = inspect_products(sut, "A")
        row = result.balance.loc[("A", "", "0100", "Output at basic prices")]
        assert row[2020] == 100.0
        assert row[2021] == 110.0

    def test_total_supply_is_sum_of_supply_transactions(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance.loc[("A", "", "", "Total supply")]
        assert row[2020] == 120.0   # 100 + 20
        assert row[2021] == 135.0   # 110 + 25

    def test_use_transaction_values(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance.loc[("A", "", "2000", "Intermediate consumption")]
        assert row[2020] == 80.0
        assert row[2021] == 85.0

    def test_total_use_is_sum_of_use_transactions(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance.loc[("A", "", "", "Total use")]
        assert row[2020] == 120.0   # 80 + 40
        assert row[2021] == 135.0   # 85 + 50

    def test_balance_is_total_supply_minus_total_use(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance.loc[("A", "", "", "Balance")]
        assert row[2020] == 0.0
        assert row[2021] == 0.0

    def test_supply_only_product_has_zero_total_use(self, sut):
        result = inspect_products(sut, "T")
        row = result.balance.loc[("T", "", "", "Total use")]
        assert row[2020] == 0.0
        assert row[2021] == 0.0

    def test_supply_only_product_balance_equals_total_supply(self, sut):
        result = inspect_products(sut, "T")
        total_supply = result.balance.loc[("T", "", "", "Total supply")]
        balance = result.balance.loc[("T", "", "", "Balance")]
        assert (balance == total_supply).all()


# ---------------------------------------------------------------------------
# Tests: supply-only product row structure
# ---------------------------------------------------------------------------


class TestSupplyOnlyProduct:

    def test_no_use_transaction_rows(self, sut):
        result = inspect_products(sut, "T")
        tx_codes = _block_level(result, "T", "transaction")
        assert "2000" not in tx_codes
        assert "6001" not in tx_codes

    def test_has_supply_transaction_rows(self, sut):
        result = inspect_products(sut, "T")
        assert "0100" in _block_level(result, "T", "transaction")

    def test_has_all_summary_rows(self, sut):
        result = inspect_products(sut, "T")
        tx_txts = _block_level(result, "T", "transaction_txt")
        assert "Total supply" in tx_txts
        assert "Total use" in tx_txts
        assert "Balance" in tx_txts


# ---------------------------------------------------------------------------
# Tests: product_txt level
# ---------------------------------------------------------------------------


class TestProductTxtLevel:

    def test_product_txt_is_empty_when_no_product_classification(self, sut):
        result = inspect_products(sut, "A")
        assert all(v == "" for v in _level(result, "product_txt"))

    def test_product_txt_contains_name_when_classification_present(self, sut_with_product_labels):
        result = inspect_products(sut_with_product_labels, "A")
        assert all(v == "Agricultural goods" for v in _level(result, "product_txt"))

    def test_product_txt_name_format_is_name_only(self, sut_with_product_labels):
        # name only, not "code - name"
        result = inspect_products(sut_with_product_labels, "T")
        assert all(v == "Trade services" for v in _level(result, "product_txt"))

    def test_product_code_still_in_product_level_when_labels_present(self, sut_with_product_labels):
        result = inspect_products(sut_with_product_labels, "A")
        assert _unique_level(result, "product") == ["A"]

    def test_multiple_products_each_with_correct_txt(self, sut_with_product_labels):
        result = inspect_products(sut_with_product_labels, ["A", "T"])
        for product, product_txt in zip(
            _level(result, "product"),
            _level(result, "product_txt"),
        ):
            if product == "A":
                assert product_txt == "Agricultural goods"
            else:
                assert product_txt == "Trade services"

    def test_product_not_in_classification_gets_empty_txt(self, supply, use, columns, transactions):
        products = pd.DataFrame({"code": ["A"], "name": ["Agricultural goods"]})
        classifications = SUTClassifications(transactions=transactions, products=products)
        metadata = SUTMetadata(columns=columns, classifications=classifications)
        sut_partial = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
        result = inspect_products(sut_partial, ["A", "T"])
        pairs = list(zip(_level(result, "product"), _level(result, "product_txt")))
        a_txts = {txt for prod, txt in pairs if prod == "A"}
        t_txts = {txt for prod, txt in pairs if prod == "T"}
        assert a_txts == {"Agricultural goods"}
        assert t_txts == {""}


# ---------------------------------------------------------------------------
# Tests: product selection (pattern syntax)
# ---------------------------------------------------------------------------


class TestProductSelection:

    def test_exact_code(self, sut):
        result = inspect_products(sut, "A")
        assert _unique_level(result, "product") == ["A"]

    def test_list_of_codes(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert set(_unique_level(result, "product")) == {"A", "T"}

    def test_wildcard(self, sut):
        result = inspect_products(sut, "A*")
        products = _unique_level(result, "product")
        assert "A" in products
        assert "T" not in products

    def test_no_match_returns_empty_dataframe(self, sut):
        result = inspect_products(sut, "Z99")
        assert result.balance.empty


# ---------------------------------------------------------------------------
# Tests: supply_detail
# ---------------------------------------------------------------------------


class TestSupplyDetail:

    def test_is_dataframe(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert isinstance(result.supply_detail, pd.DataFrame)

    def test_index_is_multiindex(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert isinstance(result.supply_detail.index, pd.MultiIndex)

    def test_index_has_six_levels(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert result.supply_detail.index.nlevels == 6

    def test_index_level_names(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert list(result.supply_detail.index.names) == [
            "product", "product_txt", "transaction", "transaction_txt",
            "category", "category_txt",
        ]

    def test_columns_are_sorted_ids(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert list(result.supply_detail.columns) == [2020, 2021]

    def test_transaction_with_categories_is_present(self, sut):
        # 0100 (output) has industry categories in the supply fixture
        result = inspect_products(sut, ["A", "T"])
        trans_codes = result.supply_detail.index.get_level_values("transaction").unique().tolist()
        assert "0100" in trans_codes

    def test_transaction_without_categories_is_absent(self, sut):
        # 0700 (imports) has empty category in the supply fixture
        result = inspect_products(sut, ["A", "T"])
        trans_codes = result.supply_detail.index.get_level_values("transaction").unique().tolist()
        assert "0700" not in trans_codes

    def test_transaction_txt_is_populated(self, sut):
        result = inspect_products(sut, ["A", "T"])
        trans_txts = result.supply_detail.index.get_level_values("transaction_txt").unique().tolist()
        assert "Output at basic prices" in trans_txts

    def test_both_products_in_product_level(self, sut):
        result = inspect_products(sut, ["A", "T"])
        products = result.supply_detail.index.get_level_values("product").unique().tolist()
        assert set(products) == {"A", "T"}

    def test_category_codes_for_product_a(self, sut):
        result = inspect_products(sut, ["A", "T"])
        # A has category X for output (0100)
        cats_a = result.supply_detail.loc[("A", "", "0100")].index.get_level_values("category").tolist()
        assert cats_a == ["X"]

    def test_category_codes_for_product_t(self, sut):
        result = inspect_products(sut, ["A", "T"])
        # T has category Z for output (0100)
        cats_t = result.supply_detail.loc[("T", "", "0100")].index.get_level_values("category").tolist()
        assert cats_t == ["Z"]

    def test_values_are_correct(self, sut):
        # A, output (0100), industry X: 100 in 2020, 110 in 2021
        result = inspect_products(sut, "A")
        row = result.supply_detail.loc[("A", "", "0100", "Output at basic prices", "X", "")]
        assert row[2020] == 100.0
        assert row[2021] == 110.0

    def test_product_with_no_category_rows_omitted(self, sut):
        # Selecting only T: T has no 0700 rows with categories
        result = inspect_products(sut, "T")
        trans_codes = result.supply_detail.index.get_level_values("transaction").unique().tolist()
        assert "0700" not in trans_codes

    def test_categories_in_natural_sort_order(self, sut):
        result = inspect_products(sut, ["A", "T"])
        cats_a = result.supply_detail.loc[("A", "", "0100")].index.get_level_values("category").tolist()
        cats_t = result.supply_detail.loc[("T", "", "0100")].index.get_level_values("category").tolist()
        assert cats_a == sorted(cats_a)
        assert cats_t == sorted(cats_t)


# ---------------------------------------------------------------------------
# Tests: use_detail
# ---------------------------------------------------------------------------


class TestUseDetail:

    def test_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.use_detail, pd.DataFrame)

    def test_index_has_six_levels(self, sut):
        result = inspect_products(sut, "A")
        assert result.use_detail.index.nlevels == 6

    def test_index_level_names(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.use_detail.index.names) == [
            "product", "product_txt", "transaction", "transaction_txt",
            "category", "category_txt",
        ]

    def test_columns_are_sorted_ids(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.use_detail.columns) == [2020, 2021]

    def test_transaction_with_categories_is_present(self, sut):
        # 2000 (IC) has industry categories in the use fixture
        result = inspect_products(sut, "A")
        trans_codes = result.use_detail.index.get_level_values("transaction").unique().tolist()
        assert "2000" in trans_codes

    def test_transaction_without_categories_is_absent(self, sut):
        # 6001 (exports) has empty category in the use fixture
        result = inspect_products(sut, "A")
        trans_codes = result.use_detail.index.get_level_values("transaction").unique().tolist()
        assert "6001" not in trans_codes

    def test_values_are_correct(self, sut):
        result = inspect_products(sut, "A")
        row = result.use_detail.loc[("A", "", "2000", "Intermediate consumption", "X", "")]
        assert row[2020] == 80.0
        assert row[2021] == 85.0

    def test_supply_only_product_has_empty_use_detail(self, sut):
        result = inspect_products(sut, "T")
        assert result.use_detail.empty


# ---------------------------------------------------------------------------
# Tests: category labels
# ---------------------------------------------------------------------------


class TestDetailCategoryLabels:

    def test_category_txt_empty_in_supply_without_industry_classification(self, sut):
        result = inspect_products(sut, ["A", "T"])
        cat_txts = result.supply_detail.index.get_level_values("category_txt").tolist()
        assert all(v == "" for v in cat_txts)

    def test_category_txt_populated_in_supply_when_classification_present(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, ["A", "T"])
        cat_txts = result.supply_detail.index.get_level_values("category_txt").tolist()
        assert "Industry X" in cat_txts
        assert "Trade industry" in cat_txts

    def test_can_access_supply_row_by_full_six_tuple_with_labels(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, "A")
        row = result.supply_detail.loc[
            ("A", "Agricultural goods", "0100", "Output at basic prices", "X", "Industry X")
        ]
        assert row[2020] == 100.0
        assert row[2021] == 110.0

    def test_category_txt_empty_in_use_without_classification(self, sut):
        result = inspect_products(sut, "A")
        cat_txts = result.use_detail.index.get_level_values("category_txt").tolist()
        assert all(v == "" for v in cat_txts)

    def test_category_txt_populated_in_use_when_classification_present(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, "A")
        cat_txts = result.use_detail.index.get_level_values("category_txt").tolist()
        assert "Industry X" in cat_txts

    def test_can_access_use_row_by_full_six_tuple_with_labels(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, "A")
        row = result.use_detail.loc[
            ("A", "Agricultural goods", "2000", "Intermediate consumption", "X", "Industry X")
        ]
        assert row[2020] == 80.0
        assert row[2021] == 85.0

    def test_product_txt_consistent_in_detail_tables(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, ["A", "T"])
        for product, product_txt in zip(
            result.supply_detail.index.get_level_values("product"),
            result.supply_detail.index.get_level_values("product_txt"),
        ):
            if product == "A":
                assert product_txt == "Agricultural goods"
            else:
                assert product_txt == "Trade services"


# ---------------------------------------------------------------------------
# Tests: error cases
# ---------------------------------------------------------------------------


class TestErrors:

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            inspect_products(sut_no_meta, "A")

    def test_raises_when_classifications_is_none(self, supply, use, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply, use=use, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            inspect_products(sut_no_class, "A")

    def test_raises_when_transactions_classification_is_none(self, supply, use, columns):
        classifications = SUTClassifications()
        meta = SUTMetadata(columns=columns, classifications=classifications)
        sut_no_trans = SUT(price_basis="current_year", supply=supply, use=use, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            inspect_products(sut_no_trans, "A")

    def test_raises_when_transactions_has_no_name_column(self, supply, use, columns):
        trans_no_name = pd.DataFrame({
            "code":  ["0100"],
            "table": ["supply"],
        })
        classifications = SUTClassifications(transactions=trans_no_name)
        meta = SUTMetadata(columns=columns, classifications=classifications)
        sut_no_name = SUT(price_basis="current_year", supply=supply, use=use, metadata=meta)
        with pytest.raises(ValueError, match="name"):
            inspect_products(sut_no_name, "A")


# ---------------------------------------------------------------------------
# Tests: balance_distribution
# ---------------------------------------------------------------------------


class TestBalanceDistribution:

    def test_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance_distribution, pd.DataFrame)

    def test_same_index_as_balance(self, sut):
        result = inspect_products(sut, "A")
        assert result.balance_distribution.index.equals(result.balance.index)

    def test_same_columns_as_balance(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.balance_distribution.columns) == list(result.balance.columns)

    def test_total_supply_row_is_one(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance_distribution.loc[("A", "", "", "Total supply")]
        assert row[2020] == pytest.approx(1.0)
        assert row[2021] == pytest.approx(1.0)

    def test_total_use_row_is_one(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance_distribution.loc[("A", "", "", "Total use")]
        assert row[2020] == pytest.approx(1.0)
        assert row[2021] == pytest.approx(1.0)

    def test_supply_transaction_value(self, sut):
        # 0100: 100 of 120 in 2020, 110 of 135 in 2021
        result = inspect_products(sut, "A")
        row = result.balance_distribution.loc[("A", "", "0100", "Output at basic prices")]
        assert row[2020] == pytest.approx(100 / 120)
        assert row[2021] == pytest.approx(110 / 135)

    def test_supply_transactions_sum_to_one(self, sut):
        result = inspect_products(sut, "A")
        block = result.balance_distribution.loc["A"]
        total_supply_pos = block.index.get_level_values("transaction_txt").tolist().index("Total supply")
        supply_rows = block.iloc[:total_supply_pos]
        assert supply_rows[2020].sum() == pytest.approx(1.0)
        assert supply_rows[2021].sum() == pytest.approx(1.0)

    def test_use_transaction_value(self, sut):
        # 2000: 80 of 120 in 2020, 85 of 135 in 2021
        result = inspect_products(sut, "A")
        row = result.balance_distribution.loc[("A", "", "2000", "Intermediate consumption")]
        assert row[2020] == pytest.approx(80 / 120)
        assert row[2021] == pytest.approx(85 / 135)

    def test_use_transactions_sum_to_one(self, sut):
        result = inspect_products(sut, "A")
        block = result.balance_distribution.loc["A"]
        txts = block.index.get_level_values("transaction_txt").tolist()
        total_supply_pos = txts.index("Total supply")
        total_use_pos = txts.index("Total use")
        use_rows = block.iloc[total_supply_pos + 1: total_use_pos]
        assert use_rows[2020].sum() == pytest.approx(1.0)
        assert use_rows[2021].sum() == pytest.approx(1.0)

    def test_balance_row_is_zero_for_balanced_sut(self, sut):
        result = inspect_products(sut, "A")
        row = result.balance_distribution.loc[("A", "", "", "Balance")]
        assert row[2020] == pytest.approx(0.0)
        assert row[2021] == pytest.approx(0.0)

    def test_empty_balance_gives_empty_distribution(self, sut):
        result = inspect_products(sut, "Z99")
        assert result.balance_distribution.empty


# ---------------------------------------------------------------------------
# Tests: supply_detail_distribution and use_detail_distribution
# ---------------------------------------------------------------------------


class TestDetailDistribution:

    def test_supply_distribution_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.supply_detail_distribution, pd.DataFrame)

    def test_use_distribution_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.use_detail_distribution, pd.DataFrame)

    def test_supply_distribution_same_index_as_supply_detail(self, sut):
        result = inspect_products(sut, "A")
        assert result.supply_detail_distribution.index.equals(result.supply_detail.index)

    def test_use_distribution_same_index_as_use_detail(self, sut):
        result = inspect_products(sut, "A")
        assert result.use_detail_distribution.index.equals(result.use_detail.index)

    def test_supply_distribution_values_correct(self, sut_multi_cat):
        # 2020: X=60, Y=40, total=100 → X=0.6, Y=0.4
        result = inspect_products(sut_multi_cat, "A")
        dist = result.supply_detail_distribution
        x_row = dist.loc[("A", "", "0100", "Output at basic prices", "X", "")]
        y_row = dist.loc[("A", "", "0100", "Output at basic prices", "Y", "")]
        assert x_row[2020] == pytest.approx(0.6)
        assert y_row[2020] == pytest.approx(0.4)

    def test_supply_distribution_sums_to_one_per_product_per_year(self, sut_multi_cat):
        result = inspect_products(sut_multi_cat, "A")
        dist = result.supply_detail_distribution
        product_data = dist.loc["A"]
        assert product_data[2020].sum() == pytest.approx(1.0)
        assert product_data[2021].sum() == pytest.approx(1.0)

    def test_use_distribution_values_correct(self, sut_multi_cat):
        # 2020: X=60, Y=20, total=80 → X=0.75, Y=0.25
        result = inspect_products(sut_multi_cat, "A")
        dist = result.use_detail_distribution
        x_row = dist.loc[("A", "", "2000", "Intermediate consumption", "X", "")]
        y_row = dist.loc[("A", "", "2000", "Intermediate consumption", "Y", "")]
        assert x_row[2020] == pytest.approx(0.75)
        assert y_row[2020] == pytest.approx(0.25)

    def test_use_distribution_sums_to_one_per_product_per_year(self, sut_multi_cat):
        result = inspect_products(sut_multi_cat, "A")
        dist = result.use_detail_distribution
        product_data = dist.loc["A"]
        assert product_data[2020].sum() == pytest.approx(1.0)
        assert product_data[2021].sum() == pytest.approx(1.0)

    def test_empty_detail_gives_empty_distribution(self, sut):
        result = inspect_products(sut, "T")
        assert result.use_detail_distribution.empty


# ---------------------------------------------------------------------------
# Tests: growth tables
# ---------------------------------------------------------------------------


class TestGrowthTables:

    def test_balance_growth_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance_growth, pd.DataFrame)

    def test_supply_detail_growth_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.supply_detail_growth, pd.DataFrame)

    def test_use_detail_growth_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.use_detail_growth, pd.DataFrame)

    def test_balance_growth_same_index_as_balance(self, sut):
        result = inspect_products(sut, "A")
        assert result.balance_growth.index.equals(result.balance.index)

    def test_balance_growth_first_column_is_nan(self, sut):
        result = inspect_products(sut, "A")
        first_col = result.balance_growth.columns[0]
        assert result.balance_growth[first_col].isna().all()

    def test_balance_growth_value(self, sut):
        # 0100 output: 100 in 2020, 110 in 2021 → growth = 1.1
        result = inspect_products(sut, "A")
        row = result.balance_growth.loc[("A", "", "0100", "Output at basic prices")]
        assert row[2021] == pytest.approx(110 / 100)

    def test_balance_growth_zero_denominator_is_nan(self, sut):
        # Total use for supply-only product T is 0 in both years → 0/0 = NaN
        result = inspect_products(sut, "T")
        row = result.balance_growth.loc[("T", "", "", "Total use")]
        assert row[2021] != row[2021]  # NaN != NaN

    def test_supply_detail_growth_value(self, sut):
        # A, output (0100), category X: 100 in 2020, 110 in 2021 → 1.1
        result = inspect_products(sut, "A")
        row = result.supply_detail_growth.loc[
            ("A", "", "0100", "Output at basic prices", "X", "")
        ]
        assert row[2021] == pytest.approx(110 / 100)

    def test_use_detail_growth_value(self, sut):
        # A, IC (2000), category X: 80 in 2020, 85 in 2021 → 85/80
        result = inspect_products(sut, "A")
        row = result.use_detail_growth.loc[
            ("A", "", "2000", "Intermediate consumption", "X", "")
        ]
        assert row[2021] == pytest.approx(85 / 80)

    def test_empty_balance_gives_empty_growth(self, sut):
        result = inspect_products(sut, "Z99")
        assert result.balance_growth.empty

    def test_empty_detail_gives_empty_growth(self, sut):
        result = inspect_products(sut, "T")
        assert result.use_detail_growth.empty
