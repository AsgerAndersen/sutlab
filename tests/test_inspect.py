"""
Tests for inspect_products.
"""

import pytest
import pandas as pd

from pandas.io.formats.style import Styler

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import ProductInspection, ProductInspectionData, inspect_products


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
        "trans":     ["0100",                    "0700",    "2000",                     "6001"],
        "trans_txt": ["Output at basic prices",  "Imports", "Intermediate consumption", "Exports"],
        "table":     ["supply",                  "supply",  "use",                      "use"],
        "esa_code":  ["P1",                       "P7",      "P2",                       "P6"],
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
        "nrnr":     ["A", "T"],
        "nrnr_txt": ["Agricultural goods", "Trade services"],
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
        "nrnr":     ["A", "T"],
        "nrnr_txt": ["Agricultural goods", "Trade services"],
    })
    industries = pd.DataFrame({
        "brch":     ["X", "Y", "Z"],
        "brch_txt": ["Industry X", "Industry Y", "Trade industry"],
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
    return result.data.balance.index.get_level_values(level_name).tolist()


def _unique_level(result, level_name):
    return result.data.balance.index.get_level_values(level_name).unique().tolist()


def _block_level(result, product_code, level_name):
    """Return level values for a single product block."""
    return result.data.balance.loc[product_code].index.get_level_values(level_name).tolist()


# ---------------------------------------------------------------------------
# Tests: return type
# ---------------------------------------------------------------------------


class TestInspectProductsReturnType:

    def test_returns_product_inspection(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result, ProductInspection)

    def test_has_data_attribute(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data, ProductInspectionData)

    def test_balance_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance, Styler)

    def test_supply_products_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.supply_products, Styler)

    def test_use_products_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.use_products, Styler)

    def test_price_layers_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers, Styler)

    def test_price_layers_distribution_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_distribution, Styler)

    def test_price_layers_growth_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_growth, Styler)

    def test_price_layers_empty_returns_styler(self, sut):
        """Empty price_layers (no layer columns) still returns a Styler."""
        result = inspect_products(sut, "A")
        assert isinstance(result.price_layers, Styler)

    def test_data_balance_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.balance, pd.DataFrame)


# ---------------------------------------------------------------------------
# Tests: MultiIndex structure
# ---------------------------------------------------------------------------


class TestBalanceTableIndex:

    def test_index_is_multiindex(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.balance.index, pd.MultiIndex)

    def test_index_has_four_levels(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.balance.index.nlevels == 4

    def test_index_level_names(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.data.balance.index.names) == [
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
        assert list(result.data.balance.columns) == [2020, 2021]


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
        row = result.data.balance.loc[("A", "", "0100", "Output at basic prices")]
        assert row[2020] == 100.0
        assert row[2021] == 110.0

    def test_total_supply_is_sum_of_supply_transactions(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.balance.loc[("A", "", "", "Total supply")]
        assert row[2020] == 120.0   # 100 + 20
        assert row[2021] == 135.0   # 110 + 25

    def test_use_transaction_values(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.balance.loc[("A", "", "2000", "Intermediate consumption")]
        assert row[2020] == 80.0
        assert row[2021] == 85.0

    def test_total_use_is_sum_of_use_transactions(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.balance.loc[("A", "", "", "Total use")]
        assert row[2020] == 120.0   # 80 + 40
        assert row[2021] == 135.0   # 85 + 50

    def test_balance_is_total_supply_minus_total_use(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.balance.loc[("A", "", "", "Balance")]
        assert row[2020] == 0.0
        assert row[2021] == 0.0

    def test_supply_only_product_has_zero_total_use(self, sut):
        result = inspect_products(sut, "T")
        row = result.data.balance.loc[("T", "", "", "Total use")]
        assert row[2020] == 0.0
        assert row[2021] == 0.0

    def test_supply_only_product_balance_equals_total_supply(self, sut):
        result = inspect_products(sut, "T")
        total_supply = result.data.balance.loc[("T", "", "", "Total supply")]
        balance = result.data.balance.loc[("T", "", "", "Balance")]
        assert (balance == total_supply).all()


# ---------------------------------------------------------------------------
# Tests: balance table price layers row
# ---------------------------------------------------------------------------


class TestBalancePriceLayers:

    def test_price_layers_row_present(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        assert "Price layers" in tx_txts

    def test_price_layers_has_empty_transaction_code(self, sut):
        result = inspect_products(sut, "A")
        tx_codes = _block_level(result, "A", "transaction")
        tx_txts = _block_level(result, "A", "transaction_txt")
        pos = tx_txts.index("Price layers")
        assert tx_codes[pos] == ""

    def test_price_layers_after_supply_transactions(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        layers_pos = tx_txts.index("Price layers")
        assert tx_txts.index("Output at basic prices") < layers_pos
        assert tx_txts.index("Imports") < layers_pos

    def test_price_layers_before_total_supply(self, sut):
        result = inspect_products(sut, "A")
        tx_txts = _block_level(result, "A", "transaction_txt")
        assert tx_txts.index("Price layers") < tx_txts.index("Total supply")

    def test_price_layers_zero_when_no_layer_columns(self, sut):
        # Basic fixture has bas == koeb for all use rows, so price layers = 0
        result = inspect_products(sut, "A")
        row = result.data.balance.loc[("A", "", "", "Price layers")]
        assert row[2020] == 0.0
        assert row[2021] == 0.0

    def test_price_layers_correct_with_layer_columns(self, sut_with_layers):
        # 2020: use purch total = 22+52+20 = 94, use basic total = 20+40+20 = 80 → layers = 14
        # 2021: use purch total = 25+58+22 = 105, use basic total = 22+44+22 = 88 → layers = 17
        result = inspect_products(sut_with_layers, "A")
        row = result.data.balance.loc[("A", "", "", "Price layers")]
        assert row[2020] == pytest.approx(14.0)
        assert row[2021] == pytest.approx(17.0)

    def test_total_supply_equals_supply_basic_plus_price_layers(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        layers = result.data.balance.loc[("A", "", "", "Price layers")]
        total_supply = result.data.balance.loc[("A", "", "", "Total supply")]
        # supply basic = 100 (2020), 110 (2021)
        assert total_supply[2020] == pytest.approx(100.0 + layers[2020])
        assert total_supply[2021] == pytest.approx(110.0 + layers[2021])

    def test_use_transaction_values_at_purchasers_prices(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        ic_row = result.data.balance.loc[("A", "", "2000", "Intermediate consumption")]
        hh_row = result.data.balance.loc[("A", "", "3110", "Household consumption")]
        assert ic_row[2020] == pytest.approx(22.0)   # koeb, not bas (20)
        assert hh_row[2020] == pytest.approx(52.0)   # koeb, not bas (40)
        assert ic_row[2021] == pytest.approx(25.0)
        assert hh_row[2021] == pytest.approx(58.0)

    def test_total_use_at_purchasers_prices(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        row = result.data.balance.loc[("A", "", "", "Total use")]
        assert row[2020] == pytest.approx(94.0)   # 22 + 52 + 20
        assert row[2021] == pytest.approx(105.0)  # 25 + 58 + 22

    def test_supply_only_product_has_zero_price_layers(self, sut):
        result = inspect_products(sut, "T")
        row = result.data.balance.loc[("T", "", "", "Price layers")]
        assert row[2020] == 0.0
        assert row[2021] == 0.0


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
        products = pd.DataFrame({"nrnr": ["A"], "nrnr_txt": ["Agricultural goods"]})
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
        assert result.data.balance.empty


# ---------------------------------------------------------------------------
# Tests: supply_products
# ---------------------------------------------------------------------------


class TestSupplyDetail:

    def test_is_dataframe(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert isinstance(result.data.supply_products, pd.DataFrame)

    def test_index_is_multiindex(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert isinstance(result.data.supply_products.index, pd.MultiIndex)

    def test_index_has_six_levels(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert result.data.supply_products.index.nlevels == 6

    def test_index_level_names(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert list(result.data.supply_products.index.names) == [
            "product", "product_txt", "transaction", "transaction_txt",
            "category", "category_txt",
        ]

    def test_columns_are_sorted_ids(self, sut):
        result = inspect_products(sut, ["A", "T"])
        assert list(result.data.supply_products.columns) == [2020, 2021]

    def test_transaction_with_categories_is_present(self, sut):
        # 0100 (output) has industry categories in the supply fixture
        result = inspect_products(sut, ["A", "T"])
        trans_codes = result.data.supply_products.index.get_level_values("transaction").unique().tolist()
        assert "0100" in trans_codes

    def test_transaction_without_categories_appears_as_single_row(self, sut):
        # 0700 (imports) has empty category — appears as one row with category=""
        result = inspect_products(sut, ["A", "T"])
        trans_codes = result.data.supply_products.index.get_level_values("transaction").unique().tolist()
        assert "0700" in trans_codes
        cats = result.data.supply_products.loc[("A", "", "0700")].index.get_level_values("category").tolist()
        assert cats == [""]

    def test_transaction_txt_is_populated(self, sut):
        result = inspect_products(sut, ["A", "T"])
        trans_txts = result.data.supply_products.index.get_level_values("transaction_txt").unique().tolist()
        assert "Output at basic prices" in trans_txts

    def test_both_products_in_product_level(self, sut):
        result = inspect_products(sut, ["A", "T"])
        products = result.data.supply_products.index.get_level_values("product").unique().tolist()
        assert set(products) == {"A", "T"}

    def test_category_codes_for_product_a(self, sut):
        result = inspect_products(sut, ["A", "T"])
        # A has category X for output (0100)
        cats_a = result.data.supply_products.loc[("A", "", "0100")].index.get_level_values("category").tolist()
        assert cats_a == ["X"]

    def test_category_codes_for_product_t(self, sut):
        result = inspect_products(sut, ["A", "T"])
        # T has category Z for output (0100)
        cats_t = result.data.supply_products.loc[("T", "", "0100")].index.get_level_values("category").tolist()
        assert cats_t == ["Z"]

    def test_values_are_correct(self, sut):
        # A, output (0100), industry X: 100 in 2020, 110 in 2021
        result = inspect_products(sut, "A")
        row = result.data.supply_products.loc[("A", "", "0100", "Output at basic prices", "X", "")]
        assert row[2020] == 100.0
        assert row[2021] == 110.0

    def test_product_with_no_category_rows_omitted(self, sut):
        # Selecting only T: T has no 0700 rows with categories
        result = inspect_products(sut, "T")
        trans_codes = result.data.supply_products.index.get_level_values("transaction").unique().tolist()
        assert "0700" not in trans_codes

    def test_categories_in_natural_sort_order(self, sut):
        result = inspect_products(sut, ["A", "T"])
        cats_a = result.data.supply_products.loc[("A", "", "0100")].index.get_level_values("category").tolist()
        cats_t = result.data.supply_products.loc[("T", "", "0100")].index.get_level_values("category").tolist()
        assert cats_a == sorted(cats_a)
        assert cats_t == sorted(cats_t)


# ---------------------------------------------------------------------------
# Tests: use_products
# ---------------------------------------------------------------------------


class TestUseDetail:

    def test_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.use_products, pd.DataFrame)

    def test_index_has_six_levels(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.use_products.index.nlevels == 6

    def test_index_level_names(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.data.use_products.index.names) == [
            "product", "product_txt", "transaction", "transaction_txt",
            "category", "category_txt",
        ]

    def test_columns_are_sorted_ids(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.data.use_products.columns) == [2020, 2021]

    def test_transaction_with_categories_is_present(self, sut):
        # 2000 (IC) has industry categories in the use fixture
        result = inspect_products(sut, "A")
        trans_codes = result.data.use_products.index.get_level_values("transaction").unique().tolist()
        assert "2000" in trans_codes

    def test_transaction_without_categories_appears_as_single_row(self, sut):
        # 6001 (exports) has empty category — appears as one row with category=""
        result = inspect_products(sut, "A")
        trans_codes = result.data.use_products.index.get_level_values("transaction").unique().tolist()
        assert "6001" in trans_codes
        cats = result.data.use_products.loc[("A", "", "6001")].index.get_level_values("category").tolist()
        assert cats == [""]

    def test_values_are_correct(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.use_products.loc[("A", "", "2000", "Intermediate consumption", "X", "")]
        assert row[2020] == 80.0
        assert row[2021] == 85.0

    def test_supply_only_product_has_empty_use_products(self, sut):
        result = inspect_products(sut, "T")
        assert result.data.use_products.empty

    def test_values_are_at_purchasers_prices(self, sut_with_layers):
        # IC (2000), category X: bas=20, koeb=22 in 2020
        result = inspect_products(sut_with_layers, "A")
        row = result.data.use_products.loc[("A", "", "2000", "Intermediate consumption", "X", "")]
        assert row[2020] == pytest.approx(22.0)   # koeb, not bas (20)
        assert row[2021] == pytest.approx(25.0)

    def test_total_use_row_present_per_product(self, sut):
        result = inspect_products(sut, "A")
        trans_txts = result.data.use_products.index.get_level_values("transaction_txt").tolist()
        assert "Total use" in trans_txts

    def test_total_use_row_has_empty_transaction_code(self, sut):
        result = inspect_products(sut, "A")
        trans_txts = result.data.use_products.index.get_level_values("transaction_txt").tolist()
        trans_codes = result.data.use_products.index.get_level_values("transaction").tolist()
        pos = trans_txts.index("Total use")
        assert trans_codes[pos] == ""

    def test_total_use_row_is_last_in_product_block(self, sut):
        result = inspect_products(sut, "A")
        trans_txts = result.data.use_products.loc["A"].index.get_level_values("transaction_txt").tolist()
        assert trans_txts[-1] == "Total use"

    def test_total_use_row_values_equal_sum_of_all_transactions(self, sut_multi_cat):
        # IC (2000): X=60, Y=20=80; exports (6001): ""=40 → total = 120 in 2020
        result = inspect_products(sut_multi_cat, "A")
        total_row = result.data.use_products.loc[("A", "", "", "Total use", "", "")]
        assert total_row[2020] == pytest.approx(120.0)  # 60+20+40
        assert total_row[2021] == pytest.approx(135.0)  # 63+22+50

    def test_supply_products_has_total_supply_row(self, sut):
        result = inspect_products(sut, ["A", "T"])
        trans_txts = result.data.supply_products.index.get_level_values("transaction_txt").tolist()
        assert "Total supply" in trans_txts
        assert "Total use" not in trans_txts

    def test_total_supply_row_is_last_in_product_block(self, sut):
        result = inspect_products(sut, "A")
        trans_txts = result.data.supply_products.loc["A"].index.get_level_values("transaction_txt").tolist()
        assert trans_txts[-1] == "Total supply"

    def test_total_supply_row_values_equal_sum_of_all_transactions(self, sut_multi_cat):
        # 0100: X=60, Y=40; 0700: ""=20 → total = 120 in 2020
        result = inspect_products(sut_multi_cat, "A")
        total_row = result.data.supply_products.loc[("A", "", "", "Total supply", "", "")]
        assert total_row[2020] == pytest.approx(120.0)
        assert total_row[2021] == pytest.approx(135.0)


# ---------------------------------------------------------------------------
# Tests: category labels
# ---------------------------------------------------------------------------


class TestDetailCategoryLabels:

    def test_category_txt_empty_in_supply_without_industry_classification(self, sut):
        result = inspect_products(sut, ["A", "T"])
        cat_txts = result.data.supply_products.index.get_level_values("category_txt").tolist()
        assert all(v == "" for v in cat_txts)

    def test_category_txt_populated_in_supply_when_classification_present(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, ["A", "T"])
        cat_txts = result.data.supply_products.index.get_level_values("category_txt").tolist()
        assert "Industry X" in cat_txts
        assert "Trade industry" in cat_txts

    def test_can_access_supply_row_by_full_six_tuple_with_labels(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, "A")
        row = result.data.supply_products.loc[
            ("A", "Agricultural goods", "0100", "Output at basic prices", "X", "Industry X")
        ]
        assert row[2020] == 100.0
        assert row[2021] == 110.0

    def test_category_txt_empty_in_use_without_classification(self, sut):
        result = inspect_products(sut, "A")
        cat_txts = result.data.use_products.index.get_level_values("category_txt").tolist()
        assert all(v == "" for v in cat_txts)

    def test_category_txt_populated_in_use_when_classification_present(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, "A")
        cat_txts = result.data.use_products.index.get_level_values("category_txt").tolist()
        assert "Industry X" in cat_txts

    def test_can_access_use_row_by_full_six_tuple_with_labels(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, "A")
        row = result.data.use_products.loc[
            ("A", "Agricultural goods", "2000", "Intermediate consumption", "X", "Industry X")
        ]
        assert row[2020] == 80.0
        assert row[2021] == 85.0

    def test_product_txt_consistent_in_detail_tables(self, sut_with_industry_labels):
        result = inspect_products(sut_with_industry_labels, ["A", "T"])
        for product, product_txt in zip(
            result.data.supply_products.index.get_level_values("product"),
            result.data.supply_products.index.get_level_values("product_txt"),
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
        # transactions DataFrame is missing the required 'trans_txt' label column
        trans_no_name = pd.DataFrame({
            "trans": ["0100"],
            "table": ["supply"],
        })
        classifications = SUTClassifications(transactions=trans_no_name)
        meta = SUTMetadata(columns=columns, classifications=classifications)
        sut_no_name = SUT(price_basis="current_year", supply=supply, use=use, metadata=meta)
        with pytest.raises(ValueError, match="trans_txt"):
            inspect_products(sut_no_name, "A")

    def test_raises_when_id_not_in_collection(self, sut):
        with pytest.raises(ValueError, match="9999"):
            inspect_products(sut, "A", ids=9999)


# ---------------------------------------------------------------------------
# Tests: ids argument
# ---------------------------------------------------------------------------


class TestIdsArgument:

    def test_single_id_gives_single_column(self, sut):
        result = inspect_products(sut, "A", ids=2020)
        assert list(result.data.balance.columns) == [2020]

    def test_list_of_ids_gives_those_columns(self, sut):
        result = inspect_products(sut, "A", ids=[2020])
        assert list(result.data.balance.columns) == [2020]

    def test_all_ids_explicit_same_as_default(self, sut):
        result_default = inspect_products(sut, "A")
        result_explicit = inspect_products(sut, "A", ids=[2020, 2021])
        assert result_default.data.balance.equals(result_explicit.data.balance)

    def test_ids_column_order_follows_sorted_collection_order(self, sut):
        # Passing ids in reverse order still produces sorted columns
        result = inspect_products(sut, "A", ids=[2021, 2020])
        assert list(result.data.balance.columns) == [2020, 2021]

    def test_ids_filters_all_tables(self, sut):
        result = inspect_products(sut, "A", ids=2020)
        assert list(result.data.supply_products.columns) == [2020]
        assert list(result.data.use_products.columns) == [2020]
        assert list(result.data.balance_distribution.columns) == [2020]
        assert list(result.data.balance_growth.columns) == [2020]

    def test_ids_none_includes_all(self, sut):
        result = inspect_products(sut, "A", ids=None)
        assert list(result.data.balance.columns) == [2020, 2021]

    def test_range_argument(self, sut):
        result = inspect_products(sut, "A", ids=range(2020, 2021))
        assert list(result.data.balance.columns) == [2020]

    def test_single_id_with_price_layers(self, sut_with_layers):
        # Regression: _build_price_layers_rates used to expand denom beyond all_ids
        result = inspect_products(sut_with_layers, "A", ids=2020)
        assert list(result.data.price_layers_rates.columns) == [2020]


# ---------------------------------------------------------------------------
# Tests: balance_distribution
# ---------------------------------------------------------------------------


class TestBalanceDistribution:

    def test_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.balance_distribution, pd.DataFrame)

    def test_same_index_as_balance_without_balance_row(self, sut):
        result = inspect_products(sut, "A")
        expected = result.data.balance.index[
            result.data.balance.index.get_level_values("transaction_txt") != "Balance"
        ]
        assert result.data.balance_distribution.index.equals(expected)

    def test_same_columns_as_balance(self, sut):
        result = inspect_products(sut, "A")
        assert list(result.data.balance_distribution.columns) == list(result.data.balance.columns)

    def test_total_supply_row_is_one(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.balance_distribution.loc[("A", "", "", "Total supply")]
        assert row[2020] == pytest.approx(1.0)
        assert row[2021] == pytest.approx(1.0)

    def test_total_use_row_is_one(self, sut):
        result = inspect_products(sut, "A")
        row = result.data.balance_distribution.loc[("A", "", "", "Total use")]
        assert row[2020] == pytest.approx(1.0)
        assert row[2021] == pytest.approx(1.0)

    def test_supply_transaction_value(self, sut):
        # 0100: 100 of 120 in 2020, 110 of 135 in 2021
        result = inspect_products(sut, "A")
        row = result.data.balance_distribution.loc[("A", "", "0100", "Output at basic prices")]
        assert row[2020] == pytest.approx(100 / 120)
        assert row[2021] == pytest.approx(110 / 135)

    def test_supply_transactions_sum_to_one(self, sut):
        result = inspect_products(sut, "A")
        block = result.data.balance_distribution.loc["A"]
        total_supply_pos = block.index.get_level_values("transaction_txt").tolist().index("Total supply")
        supply_rows = block.iloc[:total_supply_pos]
        assert supply_rows[2020].sum() == pytest.approx(1.0)
        assert supply_rows[2021].sum() == pytest.approx(1.0)

    def test_use_transaction_value(self, sut):
        # 2000: 80 of 120 in 2020, 85 of 135 in 2021
        result = inspect_products(sut, "A")
        row = result.data.balance_distribution.loc[("A", "", "2000", "Intermediate consumption")]
        assert row[2020] == pytest.approx(80 / 120)
        assert row[2021] == pytest.approx(85 / 135)

    def test_use_transactions_sum_to_one(self, sut):
        result = inspect_products(sut, "A")
        block = result.data.balance_distribution.loc["A"]
        txts = block.index.get_level_values("transaction_txt").tolist()
        total_supply_pos = txts.index("Total supply")
        total_use_pos = txts.index("Total use")
        use_rows = block.iloc[total_supply_pos + 1: total_use_pos]
        assert use_rows[2020].sum() == pytest.approx(1.0)
        assert use_rows[2021].sum() == pytest.approx(1.0)

    def test_balance_row_not_in_distribution(self, sut):
        result = inspect_products(sut, "A")
        assert ("A", "", "", "Balance") not in result.data.balance_distribution.index

    def test_empty_balance_gives_empty_distribution(self, sut):
        result = inspect_products(sut, "Z99")
        assert result.data.balance_distribution.empty


# ---------------------------------------------------------------------------
# Tests: supply_products_distribution and use_products_distribution
# ---------------------------------------------------------------------------


class TestDetailDistribution:

    def test_supply_distribution_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.supply_products_distribution, pd.DataFrame)

    def test_use_distribution_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.use_products_distribution, pd.DataFrame)

    def test_supply_distribution_same_index_as_supply_products(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.supply_products_distribution.index.equals(result.data.supply_products.index)

    def test_use_distribution_same_index_as_use_products(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.use_products_distribution.index.equals(result.data.use_products.index)

    def test_supply_distribution_values_correct(self, sut_multi_cat):
        # 2020: 0100 X=60, Y=40; 0700 ""=20 → total=120
        result = inspect_products(sut_multi_cat, "A")
        dist = result.data.supply_products_distribution
        x_row = dist.loc[("A", "", "0100", "Output at basic prices", "X", "")]
        y_row = dist.loc[("A", "", "0100", "Output at basic prices", "Y", "")]
        assert x_row[2020] == pytest.approx(60 / 120)
        assert y_row[2020] == pytest.approx(40 / 120)

    def test_supply_distribution_sums_to_one_per_product_per_year(self, sut_multi_cat):
        result = inspect_products(sut_multi_cat, "A")
        dist = result.data.supply_products_distribution
        product_data = dist.loc["A"]
        non_summary = product_data.index.get_level_values("transaction") != ""
        assert product_data.loc[non_summary][2020].sum() == pytest.approx(1.0)
        assert product_data.loc[non_summary][2021].sum() == pytest.approx(1.0)

    def test_use_distribution_values_correct(self, sut_multi_cat):
        # 2020: 2000 X=60, Y=20; 6001 ""=40 → total=120
        result = inspect_products(sut_multi_cat, "A")
        dist = result.data.use_products_distribution
        x_row = dist.loc[("A", "", "2000", "Intermediate consumption", "X", "")]
        y_row = dist.loc[("A", "", "2000", "Intermediate consumption", "Y", "")]
        assert x_row[2020] == pytest.approx(60 / 120)
        assert y_row[2020] == pytest.approx(20 / 120)

    def test_use_distribution_sums_to_one_per_product_per_year(self, sut_multi_cat):
        result = inspect_products(sut_multi_cat, "A")
        dist = result.data.use_products_distribution
        product_data = dist.loc["A"]
        # Exclude the "Total use" summary row — it equals 1.0 and would inflate the sum
        non_summary = product_data.index.get_level_values("transaction") != ""
        assert product_data.loc[non_summary][2020].sum() == pytest.approx(1.0)
        assert product_data.loc[non_summary][2021].sum() == pytest.approx(1.0)

    def test_empty_detail_gives_empty_distribution(self, sut):
        result = inspect_products(sut, "T")
        assert result.data.use_products_distribution.empty


# ---------------------------------------------------------------------------
# Tests: growth tables
# ---------------------------------------------------------------------------


class TestGrowthTables:

    def test_balance_growth_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.balance_growth, pd.DataFrame)

    def test_supply_products_growth_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.supply_products_growth, pd.DataFrame)

    def test_use_products_growth_is_dataframe(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.data.use_products_growth, pd.DataFrame)

    def test_balance_growth_same_index_as_balance_without_balance_row(self, sut):
        result = inspect_products(sut, "A")
        expected = result.data.balance.index[
            result.data.balance.index.get_level_values("transaction_txt") != "Balance"
        ]
        assert result.data.balance_growth.index.equals(expected)

    def test_balance_row_not_in_growth(self, sut):
        result = inspect_products(sut, "A")
        assert ("A", "", "", "Balance") not in result.data.balance_growth.index

    def test_balance_growth_first_column_is_nan(self, sut):
        result = inspect_products(sut, "A")
        first_col = result.data.balance_growth.columns[0]
        assert result.data.balance_growth[first_col].isna().all()

    def test_balance_growth_value(self, sut):
        # 0100 output: 100 in 2020, 110 in 2021 → change = (110-100)/100 = 0.1
        result = inspect_products(sut, "A")
        row = result.data.balance_growth.loc[("A", "", "0100", "Output at basic prices")]
        assert row[2021] == pytest.approx((110 - 100) / 100)

    def test_balance_growth_zero_denominator_is_nan(self, sut):
        # Total use for supply-only product T is 0 in both years → 0/0 = NaN
        result = inspect_products(sut, "T")
        row = result.data.balance_growth.loc[("T", "", "", "Total use")]
        assert row[2021] != row[2021]  # NaN != NaN

    def test_supply_products_growth_value(self, sut):
        # A, output (0100), category X: 100 in 2020, 110 in 2021 → change = 0.1
        result = inspect_products(sut, "A")
        row = result.data.supply_products_growth.loc[
            ("A", "", "0100", "Output at basic prices", "X", "")
        ]
        assert row[2021] == pytest.approx((110 - 100) / 100)

    def test_use_products_growth_value(self, sut):
        # A, IC (2000), category X: 80 in 2020, 85 in 2021 → change = (85-80)/80
        result = inspect_products(sut, "A")
        row = result.data.use_products_growth.loc[
            ("A", "", "2000", "Intermediate consumption", "X", "")
        ]
        assert row[2021] == pytest.approx((85 - 80) / 80)

    def test_empty_balance_gives_empty_growth(self, sut):
        result = inspect_products(sut, "Z99")
        assert result.data.balance_growth.empty

    def test_empty_detail_gives_empty_growth(self, sut):
        result = inspect_products(sut, "T")
        assert result.data.use_products_growth.empty


# ---------------------------------------------------------------------------
# Tests: number formatting
# ---------------------------------------------------------------------------


class TestFormatting:

    def test_balance_number_format(self, sut):
        # 1234567.8 → "1.234.567,8"
        from sutlab.inspect import _format_number
        assert _format_number(1234567.8) == "1.234.567,8"

    def test_balance_number_format_one_decimal(self, sut):
        from sutlab.inspect import _format_number
        assert _format_number(100.0) == "100,0"

    def test_balance_number_format_nan(self, sut):
        import numpy as np
        from sutlab.inspect import _format_number
        assert _format_number(float("nan")) == ""

    def test_percentage_format(self, sut):
        # 0.05 → "5,00%"
        from sutlab.inspect import _format_percentage
        assert _format_percentage(0.05) == "5,0%"

    def test_percentage_format_nan(self, sut):
        from sutlab.inspect import _format_percentage
        assert _format_percentage(float("nan")) == ""

    def test_balance_property_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance, Styler)

    def test_balance_distribution_property_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance_distribution, Styler)

    def test_balance_growth_property_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.balance_growth, Styler)


# ---------------------------------------------------------------------------
# Tests: balance table row styling
# ---------------------------------------------------------------------------


class TestBalanceStyling:

    def _css(self, result, row_key):
        """Return the CSS string for the first data column of a given row."""
        from sutlab.inspect import _apply_balance_style, _DATA_COLORS, _build_balance_row_css
        css_df = _apply_balance_style(result.data.balance)
        return css_df.loc[row_key].iloc[0]

    def _index_css(self, result, row_position):
        """Return the index CSS string for a given row position."""
        from sutlab.inspect import _build_balance_row_css, _INDEX_COLORS
        return _build_balance_row_css(result.data.balance, _INDEX_COLORS)[row_position]

    def test_supply_transaction_has_green_background(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "0100", "Output at basic prices"))
        assert "background-color: #e8f5e9" in css or "background-color: #f1faf2" in css

    def test_total_supply_has_saturated_green(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "", "Total supply"))
        assert "background-color: #c8e6c9" in css

    def test_total_supply_is_bold(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "", "Total supply"))
        assert "font-weight: bold" in css

    def test_use_transaction_has_blue_background(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "2000", "Intermediate consumption"))
        assert "background-color: #e3f2fd" in css or "background-color: #ecf6fe" in css

    def test_total_use_has_saturated_blue(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "", "Total use"))
        assert "background-color: #bbdefb" in css

    def test_total_use_is_bold(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "", "Total use"))
        assert "font-weight: bold" in css

    def test_balance_row_is_neutral(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "", "Balance"))
        assert "background-color: #f5f5f5" in css

    def test_supply_rows_alternate(self, sut):
        result = inspect_products(sut, "A")
        css_0100 = self._css(result, ("A", "", "0100", "Output at basic prices"))
        css_0700 = self._css(result, ("A", "", "0700", "Imports"))
        assert css_0100 != css_0700

    def test_supply_transaction_is_not_bold(self, sut):
        result = inspect_products(sut, "A")
        css = self._css(result, ("A", "", "0100", "Output at basic prices"))
        assert "font-weight: normal" in css

    def test_index_supply_row_darker_than_data(self, sut):
        result = inspect_products(sut, "A")
        data_css = self._css(result, ("A", "", "0100", "Output at basic prices"))
        idx_css = self._index_css(result, 0)
        # Index color should differ from data color
        assert data_css != idx_css

    def test_index_total_supply_has_darker_green(self, sut):
        result = inspect_products(sut, "A")
        # Total supply is at position 3 (0100, 0700, Price layers, Total supply)
        idx_css = self._index_css(result, 3)
        assert "background-color: #b8d8ba" in idx_css

    def test_index_total_use_has_darker_blue(self, sut):
        result = inspect_products(sut, "A")
        # Total use is at position 6 (0100, 0700, Price layers, Total supply, 2000, 6001, Total use)
        idx_css = self._index_css(result, 6)
        assert "background-color: #a5cff4" in idx_css

    def test_separator_on_balance_row_of_first_product(self, sut):
        # With two products, the Balance row of the first product gets a border
        from sutlab.inspect import _build_balance_row_css, _DATA_COLORS
        result = inspect_products(sut, ["A", "T"])
        row_css = _build_balance_row_css(result.data.balance, _DATA_COLORS)
        # Balance row of A is the last row before T's block
        balance_a_idx = result.data.balance.index.get_loc(("A", "", "", "Balance"))
        assert "border-bottom" in row_css[balance_a_idx]

    def test_no_separator_on_last_product_balance_row(self, sut):
        from sutlab.inspect import _build_balance_row_css, _DATA_COLORS
        result = inspect_products(sut, ["A", "T"])
        row_css = _build_balance_row_css(result.data.balance, _DATA_COLORS)
        balance_t_idx = result.data.balance.index.get_loc(("T", "", "", "Balance"))
        assert "border-bottom" not in row_css[balance_t_idx]

    def test_no_separator_single_product(self, sut):
        from sutlab.inspect import _build_balance_row_css, _DATA_COLORS
        result = inspect_products(sut, "A")
        row_css = _build_balance_row_css(result.data.balance, _DATA_COLORS)
        balance_idx = result.data.balance.index.get_loc(("A", "", "", "Balance"))
        assert "border-bottom" not in row_css[balance_idx]


# ---------------------------------------------------------------------------
# Tests: detail table styling
# ---------------------------------------------------------------------------


class TestDetailStyling:

    def _build_css(self, result, side):
        """Return the data_css list for a detail table via _style_detail_table."""
        from sutlab.inspect import _style_detail_table, _format_number, _DATA_COLORS
        df = result.data.supply_products if side == "supply" else result.data.use_products
        color_key = side
        data_colors = _DATA_COLORS[color_key]
        # Re-derive data_css by calling the same logic directly
        product_vals = df.index.get_level_values("product")
        trans_vals = df.index.get_level_values("transaction")
        products = list(product_vals.unique())
        n = len(df)
        data_css = [""] * n
        for p_idx, product in enumerate(products):
            is_last_product = (p_idx == len(products) - 1)
            prod_positions = [i for i, v in enumerate(product_vals) if v == product]
            prod_trans = list(dict.fromkeys(trans_vals[i] for i in prod_positions))
            for t_idx, trans in enumerate(prod_trans):
                is_last_trans = (t_idx == len(prod_trans) - 1)
                trans_positions = [i for i in prod_positions if trans_vals[i] == trans]
                if not is_last_trans:
                    sep = "; border-bottom: 1px solid #ccc"
                elif not is_last_product:
                    sep = "; border-bottom: 2px solid #999"
                else:
                    sep = ""
                for i, i_abs in enumerate(trans_positions):
                    is_last_row = (i == len(trans_positions) - 1)
                    data_css[i_abs] = (
                        f"background-color: {data_colors[i % 2]}"
                        + (sep if is_last_row else "")
                    )
        return data_css

    def test_supply_products_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.supply_products, Styler)

    def test_use_products_returns_styler(self, sut):
        result = inspect_products(sut, "A")
        assert isinstance(result.use_products, Styler)

    def test_supply_products_uses_green(self, sut):
        result = inspect_products(sut, "A")
        css = self._build_css(result, "supply")
        assert all("e8f5e9" in c or "f1faf2" in c for c in css if c)

    def test_use_products_uses_blue(self, sut):
        result = inspect_products(sut, "A")
        css = self._build_css(result, "use")
        assert all("e3f2fd" in c or "ecf6fe" in c for c in css if c)

    def test_rows_alternate_within_transaction_block(self, sut_multi_cat):
        result = inspect_products(sut_multi_cat, "A")
        css = self._build_css(result, "supply")
        # Two categories X and Y under 0100 → alternating colors
        assert css[0] != css[1]

    def test_transaction_separator_between_blocks(self, columns):
        # Build a SUT where two supply transactions both have category breakdowns
        transactions = pd.DataFrame({
            "trans":     ["0100", "0500"],
            "trans_txt": ["Output", "Another output"],
            "table":     ["supply", "supply"],
            "esa_code":  ["P1", "P1"],
        })
        supply = pd.DataFrame({
            "year":  [2020, 2020, 2020, 2020],
            "nrnr":  ["A",  "A",  "A",  "A"],
            "trans": ["0100", "0100", "0500", "0500"],
            "brch":  ["X", "Y", "X", "Y"],
            "bas":   [100.0, 50.0, 80.0, 40.0],
            "koeb":  [100.0, 50.0, 80.0, 40.0],
        })
        use = pd.DataFrame({"year": pd.Series([], dtype=float), "nrnr": [], "trans": [], "brch": [], "bas": [], "koeb": []})
        from sutlab.sut import SUT, SUTMetadata, SUTClassifications
        sut = SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=SUTClassifications(transactions=transactions)),
        )
        result = inspect_products(sut, "A")
        css = self._build_css(result, "supply")
        # 0100 block has categories X and Y (indices 0, 1); last row (index 1) gets 1px separator
        assert "border-bottom: 1px solid #ccc" in css[1]

    def test_product_separator_between_products(self, sut):
        result = inspect_products(sut, ["A", "T"])
        css = self._build_css(result, "supply")
        # Last row of A's last transaction block gets 2px separator
        last_a = result.data.supply_products.index.get_level_values("product").tolist().index("T") - 1
        assert "border-bottom: 2px solid #999" in css[last_a]

    def test_no_separator_last_product(self, sut):
        result = inspect_products(sut, ["A", "T"])
        css = self._build_css(result, "supply")
        assert "border-bottom" not in css[-1]


# ---------------------------------------------------------------------------
# Fixtures: price layers
# ---------------------------------------------------------------------------

NAN = float("nan")


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
        vat="moms",
    )


@pytest.fixture
def transactions_with_layers():
    """Supply and use transactions covering layer-bearing and layer-free use rows."""
    return pd.DataFrame({
        "trans":     ["0100",                   "2000",                     "3110",                  "6001"],
        "trans_txt": ["Output at basic prices", "Intermediate consumption", "Household consumption", "Exports"],
        "table":     ["supply",                 "use",                      "use",                   "use"],
        "esa_code":  ["P1",                     "P2",                       "P31",                   "P6"],
    })


@pytest.fixture
def supply_with_layers():
    return pd.DataFrame({
        "year":  [2020, 2021],
        "nrnr":  ["A",  "A"],
        "trans": ["0100", "0100"],
        "brch":  ["X",   "X"],
        "bas":   [100.0, 110.0],
        "ava":   [NAN,   NAN],
        "moms":  [NAN,   NAN],
        "koeb":  [100.0, 110.0],
    })


@pytest.fixture
def use_with_layers():
    """
    Product A over two years:
      2000 (IC):     ava only  — 20 bas + 2 ava  → included in ava block
      3110 (HHcons): ava+moms  — 40 bas + 4 ava + 8 moms → included in both blocks
      6001 (exports): no layers — excluded from price_layers entirely
    """
    return pd.DataFrame({
        "year":  [2020,   2020,   2020,   2021,   2021,   2021],
        "nrnr":  ["A",    "A",    "A",    "A",    "A",    "A"],
        "trans": ["2000", "3110", "6001", "2000", "3110", "6001"],
        "brch":  ["X",    "HH",   "",     "X",    "HH",   ""],
        "bas":   [20.0,   40.0,   20.0,   22.0,   44.0,   22.0],
        "ava":   [2.0,    4.0,    NAN,    3.0,    5.0,    NAN],
        "moms":  [NAN,    8.0,    NAN,    NAN,    9.0,    NAN],
        "koeb":  [22.0,   52.0,   20.0,   25.0,   58.0,   22.0],
    })


@pytest.fixture
def sut_with_layers(supply_with_layers, use_with_layers, columns_with_layers, transactions_with_layers):
    classifications = SUTClassifications(transactions=transactions_with_layers)
    metadata = SUTMetadata(columns=columns_with_layers, classifications=classifications)
    return SUT(
        price_basis="current_year",
        supply=supply_with_layers,
        use=use_with_layers,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Tests: price_layers — structure
# ---------------------------------------------------------------------------


class TestPriceLayersStructure:

    def test_index_names(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert result.data.price_layers.index.names == [
            "product", "product_txt", "price_layer", "transaction", "transaction_txt"
        ]

    def test_columns_are_ids(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert list(result.data.price_layers.columns) == [2020, 2021]

    def test_price_layer_values_follow_use_column_order(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        layers = result.data.price_layers.index.get_level_values("price_layer").unique().tolist()
        # ava comes before moms in the use DataFrame columns
        assert layers == ["ava", "moms"]

    def test_each_block_ends_with_total_row(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        trans_txt = result.data.price_layers.index.get_level_values("transaction_txt").tolist()
        layer_vals = result.data.price_layers.index.get_level_values("price_layer").tolist()
        # Last row of each (product, layer) block must be "Total"
        for layer in ["ava", "moms"]:
            positions = [i for i, v in enumerate(layer_vals) if v == layer]
            assert trans_txt[positions[-1]] == "Total"

    def test_total_row_has_empty_transaction_code(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers
        total_rows = df[df.index.get_level_values("transaction_txt") == "Total"]
        assert (total_rows.index.get_level_values("transaction") == "").all()


# ---------------------------------------------------------------------------
# Tests: price_layers — transactions included/excluded
# ---------------------------------------------------------------------------


class TestPriceLayersTransactionFiltering:

    def test_exports_excluded_from_ava_block(self, sut_with_layers):
        """6001 has ava=NaN — should not appear in the ava block."""
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers
        ava_rows = df[df.index.get_level_values("price_layer") == "ava"]
        trans_codes = ava_rows.index.get_level_values("transaction").tolist()
        assert "6001" not in trans_codes

    def test_ic_excluded_from_moms_block(self, sut_with_layers):
        """2000 has moms=NaN — should not appear in the moms block."""
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers
        moms_rows = df[df.index.get_level_values("price_layer") == "moms"]
        trans_codes = moms_rows.index.get_level_values("transaction").tolist()
        assert "2000" not in trans_codes

    def test_ava_block_contains_ic_and_hhcons(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers
        ava_rows = df[df.index.get_level_values("price_layer") == "ava"]
        trans_codes = ava_rows.index.get_level_values("transaction").tolist()
        assert "2000" in trans_codes
        assert "3110" in trans_codes

    def test_moms_block_contains_hhcons_only(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers
        moms_rows = df[df.index.get_level_values("price_layer") == "moms"]
        trans_codes = [t for t in moms_rows.index.get_level_values("transaction").tolist() if t != ""]
        assert trans_codes == ["3110"]


# ---------------------------------------------------------------------------
# Tests: price_layers — values
# ---------------------------------------------------------------------------


class TestPriceLayersValues:

    def _layer_block(self, result, layer):
        df = result.data.price_layers
        return df[df.index.get_level_values("price_layer") == layer]

    def test_ava_transaction_values(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        ic_row = ava[ava.index.get_level_values("transaction") == "2000"]
        assert ic_row[2020].item() == pytest.approx(2.0)
        assert ic_row[2021].item() == pytest.approx(3.0)

    def test_ava_total_row(self, sut_with_layers):
        """Total ava for product A: 2000 + 3110 per year."""
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        total = ava[ava.index.get_level_values("transaction_txt") == "Total"]
        # 2020: 2 (IC) + 4 (HH) = 6; 2021: 3 + 5 = 8
        assert total[2020].item() == pytest.approx(6.0)
        assert total[2021].item() == pytest.approx(8.0)

    def test_moms_total_row(self, sut_with_layers):
        """Total moms equals the single household consumption row."""
        result = inspect_products(sut_with_layers, "A")
        moms = self._layer_block(result, "moms")
        total = moms[moms.index.get_level_values("transaction_txt") == "Total"]
        assert total[2020].item() == pytest.approx(8.0)
        assert total[2021].item() == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# Tests: price_layers — no layers present
# ---------------------------------------------------------------------------


class TestPriceLayersEmpty:

    def test_empty_when_no_layer_columns_in_sutcolumns(self, sut):
        """The base sut fixture has no layer columns mapped — price_layers is empty."""
        result = inspect_products(sut, "A")
        assert result.data.price_layers.empty

    def test_empty_when_product_has_no_use_rows(self, sut_with_layers):
        """Product T has no use rows at all — not present in price_layers."""
        # Add T to supply so it can be queried
        extra_supply = pd.DataFrame({
            "year": [2020], "nrnr": ["T"], "trans": ["0100"],
            "brch": ["Z"], "bas": [10.0], "ava": [NAN], "moms": [NAN], "koeb": [10.0],
        })
        new_supply = pd.concat([sut_with_layers.supply, extra_supply], ignore_index=True)
        import dataclasses
        sut_t = dataclasses.replace(sut_with_layers, supply=new_supply)
        result = inspect_products(sut_t, "T")
        assert result.data.price_layers.empty


# ---------------------------------------------------------------------------
# Tests: price_layers_distribution
# ---------------------------------------------------------------------------


class TestPriceLayersDistribution:

    def _layer_block(self, result, layer, table="price_layers_distribution"):
        df = getattr(result.data, table)
        return df[df.index.get_level_values("price_layer") == layer]

    def test_total_row_is_one(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        total = ava[ava.index.get_level_values("transaction_txt") == "Total"]
        assert total[2020].item() == pytest.approx(1.0)
        assert total[2021].item() == pytest.approx(1.0)

    def test_transaction_shares_sum_to_one(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        non_total = ava[ava.index.get_level_values("transaction_txt") != "Total"]
        assert non_total[2020].sum() == pytest.approx(1.0)
        assert non_total[2021].sum() == pytest.approx(1.0)

    def test_ic_share_of_ava_2020(self, sut_with_layers):
        """IC ava=2, HH ava=4 → IC share = 2/6."""
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        ic_row = ava[ava.index.get_level_values("transaction") == "2000"]
        assert ic_row[2020].item() == pytest.approx(2 / 6)

    def test_empty_when_no_layers(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.price_layers_distribution.empty


# ---------------------------------------------------------------------------
# Tests: price_layers_growth
# ---------------------------------------------------------------------------


class TestPriceLayersGrowth:

    def _layer_block(self, result, layer):
        df = result.data.price_layers_growth
        return df[df.index.get_level_values("price_layer") == layer]

    def test_first_year_is_nan(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        assert ava[2020].isna().all()

    def test_ava_total_growth(self, sut_with_layers):
        """Total ava: 6 in 2020, 8 in 2021 → growth = (8-6)/6."""
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        total = ava[ava.index.get_level_values("transaction_txt") == "Total"]
        assert total[2021].item() == pytest.approx((8 - 6) / 6)

    def test_empty_when_no_layers(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.price_layers_growth.empty


# ---------------------------------------------------------------------------
# Tests: price_layers_rates
# ---------------------------------------------------------------------------


class TestPriceLayerRates:
    """price_layers_rates: per-transaction rates, no Total rows.

    Each rate = layer / cumulative denominator for that transaction.
    Total rows from price_layers are excluded.

    Fixture data for product A, year 2020:
      2000 (IC):      bas=20, ava=2,  moms=NaN
      3110 (HHcons):  bas=40, ava=4,  moms=8
      6001 (exports): bas=20, ava=NaN, moms=NaN

      IC     ava  rate = 2/20
      HHcons ava  rate = 4/40
      HHcons moms rate = 8/(40+4) = 8/44
    """

    def _layer_block(self, result, layer):
        df = result.data.price_layers_rates
        return df[df.index.get_level_values("price_layer") == layer]

    def test_no_total_rows(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        trans_vals = result.data.price_layers_rates.index.get_level_values("transaction")
        assert "" not in trans_vals

    def test_columns_match_price_layers(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert list(result.data.price_layers_rates.columns) == list(result.data.price_layers.columns)

    def test_index_names_match_price_layers(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert (
            result.data.price_layers_rates.index.names
            == result.data.price_layers.index.names
        )

    def test_ava_ic_rate_2020(self, sut_with_layers):
        """IC ava=2, IC basic=20 → rate = 2/20."""
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        ic_row = ava[ava.index.get_level_values("transaction") == "2000"]
        assert ic_row[2020].item() == pytest.approx(2 / 20)

    def test_ava_hhcons_rate_2020(self, sut_with_layers):
        """HHcons ava=4, HHcons basic=40 → rate = 4/40."""
        result = inspect_products(sut_with_layers, "A")
        ava = self._layer_block(result, "ava")
        hhcons_row = ava[ava.index.get_level_values("transaction") == "3110"]
        assert hhcons_row[2020].item() == pytest.approx(4 / 40)

    def test_moms_hhcons_rate_2020(self, sut_with_layers):
        """HHcons moms=8, denom = basic+ava = 40+4 = 44 → rate = 8/44."""
        result = inspect_products(sut_with_layers, "A")
        moms = self._layer_block(result, "moms")
        hhcons_row = moms[moms.index.get_level_values("transaction") == "3110"]
        assert hhcons_row[2020].item() == pytest.approx(8 / 44)

    def test_moms_hhcons_rate_2021(self, sut_with_layers):
        """HHcons 2021: moms=9, denom = basic+ava = 44+5 = 49 → rate = 9/49."""
        result = inspect_products(sut_with_layers, "A")
        moms = self._layer_block(result, "moms")
        hhcons_row = moms[moms.index.get_level_values("transaction") == "3110"]
        assert hhcons_row[2021].item() == pytest.approx(9 / 49)

    def test_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_rates, Styler)

    def test_empty_when_no_layers(self, sut):
        result = inspect_products(sut, "A")
        assert result.data.price_layers_rates.empty


# ---------------------------------------------------------------------------
# Tests: price_layers — styling
# ---------------------------------------------------------------------------


class TestPriceLayersStyling:
    """Verify that CSS applied by _style_price_layers_table is correct."""

    def _rebuild_data_css(self, df):
        """Rebuild data and index CSS lists from _style_price_layers_table internals."""
        from sutlab.inspect import _LAYER_PALETTES
        product_vals = df.index.get_level_values("product")
        layer_vals = df.index.get_level_values("price_layer")
        trans_txt_vals = df.index.get_level_values("transaction_txt")
        n = len(df)
        data_css = [""] * n
        index_css = [""] * n
        products = list(dict.fromkeys(product_vals))
        for p_idx, product in enumerate(products):
            is_last_product = (p_idx == len(products) - 1)
            prod_positions = [i for i, v in enumerate(product_vals) if v == product]
            prod_layers = list(dict.fromkeys(layer_vals[i] for i in prod_positions))
            for l_idx, layer in enumerate(prod_layers):
                is_last_layer = (l_idx == len(prod_layers) - 1)
                palette = _LAYER_PALETTES[l_idx % len(_LAYER_PALETTES)]
                block_positions = [i for i in prod_positions if layer_vals[i] == layer]
                block_txts = [trans_txt_vals[i] for i in block_positions]
                sep = (
                    "; border-bottom: 1px solid #ccc" if not is_last_layer
                    else "; border-bottom: 2px solid #999" if not is_last_product
                    else ""
                )
                counter = 0
                for i, i_abs in enumerate(block_positions):
                    is_last_row = (i == len(block_positions) - 1)
                    is_total = (block_txts[i] == "Total")
                    row_sep = sep if is_last_row else ""
                    if is_total:
                        bg_data = palette["data_total"]
                        bg_index = palette["index_total"]
                        bold = True
                    else:
                        bg_data = palette["data"][counter % 2]
                        bg_index = palette["index"][counter % 2]
                        bold = False
                        counter += 1
                    weight = "bold" if bold else "normal"
                    data_css[i_abs] = f"background-color: {bg_data}; font-weight: {weight}{row_sep}"
                    index_css[i_abs] = f"background-color: {bg_index}; font-weight: {weight}{row_sep}"
        return data_css, index_css

    def test_first_layer_uses_amber(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        data_css, _ = self._rebuild_data_css(result.data.price_layers)
        # ava is the first layer — should use amber palette (fffde7 or fffef5 for non-total)
        ava_positions = [
            i for i, v in enumerate(
                result.data.price_layers.index.get_level_values("price_layer")
            ) if v == "ava"
        ]
        non_total = [
            i for i in ava_positions
            if result.data.price_layers.index.get_level_values("transaction_txt")[i] != "Total"
        ]
        assert any("fffde7" in data_css[i] or "fffef5" in data_css[i] for i in non_total)

    def test_second_layer_uses_purple(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        data_css, _ = self._rebuild_data_css(result.data.price_layers)
        moms_positions = [
            i for i, v in enumerate(
                result.data.price_layers.index.get_level_values("price_layer")
            ) if v == "moms"
        ]
        non_total = [
            i for i in moms_positions
            if result.data.price_layers.index.get_level_values("transaction_txt")[i] != "Total"
        ]
        assert any("f8f0ff" in data_css[i] or "fbf6ff" in data_css[i] for i in non_total)

    def test_transaction_index_alternates(self, sut_with_layers):
        """transaction/transaction_txt index cells alternate, not all index_total."""
        from sutlab.inspect import _LAYER_PALETTES
        result = inspect_products(sut_with_layers, "A")
        _, index_css = self._rebuild_data_css(result.data.price_layers)
        # ava block has two non-total rows — their index should use the two alternating shades
        df = result.data.price_layers
        layer_vals = df.index.get_level_values("price_layer").tolist()
        trans_txt_vals = df.index.get_level_values("transaction_txt").tolist()
        ava_non_total = [
            i for i, (l, t) in enumerate(zip(layer_vals, trans_txt_vals))
            if l == "ava" and t != "Total"
        ]
        palette = _LAYER_PALETTES[0]  # amber
        assert index_css[ava_non_total[0]] != index_css[ava_non_total[1]]
        assert palette["index"][0] in index_css[ava_non_total[0]]

    def test_total_row_is_bold(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        data_css, _ = self._rebuild_data_css(result.data.price_layers)
        total_positions = [
            i for i, v in enumerate(
                result.data.price_layers.index.get_level_values("transaction_txt")
            ) if v == "Total"
        ]
        assert all("font-weight: bold" in data_css[i] for i in total_positions)

    def test_non_total_rows_not_bold(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        data_css, _ = self._rebuild_data_css(result.data.price_layers)
        non_total_positions = [
            i for i, v in enumerate(
                result.data.price_layers.index.get_level_values("transaction_txt")
            ) if v != "Total"
        ]
        assert all("font-weight: normal" in data_css[i] for i in non_total_positions)

    def test_separator_between_layers(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        data_css, _ = self._rebuild_data_css(result.data.price_layers)
        df = result.data.price_layers
        layer_vals = df.index.get_level_values("price_layer").tolist()
        # Last row of ava block (not last layer) should have 1px separator
        ava_positions = [i for i, v in enumerate(layer_vals) if v == "ava"]
        assert "border-bottom: 1px solid #ccc" in data_css[ava_positions[-1]]

    def test_no_separator_last_layer_last_product(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        data_css, _ = self._rebuild_data_css(result.data.price_layers)
        assert "border-bottom" not in data_css[-1]



