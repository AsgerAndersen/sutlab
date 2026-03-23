"""
Tests for core SUT data structures and mark_for_balancing.
"""

import pytest
import pandas as pd

from sutlab.sut import (
    SUT,
    SUTClassifications,
    SUTColumns,
    SUTMetadata,
    _match_codes,
    _natural_sort_key,
    get_collective_consumption_codes,
    get_ids,
    get_individual_consumption_codes,
    get_industry_codes,
    get_product_codes,
    get_rows,
    get_transaction_codes,
    mark_for_balancing,
)


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
        wholesale_margins="eng",
        retail_margins="det",
        product_taxes_less_subsidies="afg",
        vat="moms",
    )


@pytest.fixture
def metadata(columns):
    return SUTMetadata(columns=columns)


@pytest.fixture
def supply():
    return pd.DataFrame({
        "year":  [2018, 2018, 2019, 2019],
        "nrnr":  ["P1", "P2", "P1", "P2"],
        "trans": ["0100", "0100", "0100", "0100"],
        "brch":  ["I1", "I1", "I1", "I1"],
        "bas":   [100.0, 80.0, 110.0, 85.0],
    })


@pytest.fixture
def use():
    return pd.DataFrame({
        "year":  [2018, 2018, 2019, 2019],
        "nrnr":  ["P1", "P2", "P1", "P2"],
        "trans": ["2000", "2000", "2000", "2000"],
        "brch":  ["I1", "I1", "I1", "I1"],
        "bas":   [60.0,  40.0,  65.0,  42.0],
        "eng":   [5.0,   3.0,   5.5,   3.2],
        "det":   [3.0,   2.0,   3.2,   2.1],
        "afg":   [2.0,   1.0,   2.1,   1.1],
        "moms":  [10.0,  8.0,   11.0,  8.5],
        "koeb":  [80.0,  54.0,  86.8,  56.9],
    })


@pytest.fixture
def sut(supply, use, metadata):
    return SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Tests for mark_for_balancing
# ---------------------------------------------------------------------------


class TestMarkForBalancing:

    def test_returns_sut_with_correct_balancing_id(self, sut):
        result = mark_for_balancing(sut, 2019)
        assert result.balancing_id == 2019

    def test_does_not_mutate_original(self, sut):
        mark_for_balancing(sut, 2019)
        assert sut.balancing_id is None

    def test_data_is_shared_not_copied(self, sut):
        # The supply DataFrame in the result should be the same object
        result = mark_for_balancing(sut, 2019)
        assert result.supply is sut.supply

    def test_other_fields_are_preserved(self, sut):
        result = mark_for_balancing(sut, 2019)
        assert result.price_basis == sut.price_basis
        assert result.metadata is sut.metadata

    def test_can_switch_active_year(self, sut):
        sut_2018 = mark_for_balancing(sut, 2018)
        sut_2019 = mark_for_balancing(sut, 2019)
        assert sut_2018.balancing_id == 2018
        assert sut_2019.balancing_id == 2019

    def test_raises_for_missing_id(self, sut):
        with pytest.raises(ValueError, match="2025"):
            mark_for_balancing(sut, 2025)

    def test_error_message_lists_available_ids(self, sut):
        with pytest.raises(ValueError, match="2018"):
            mark_for_balancing(sut, 2025)

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            mark_for_balancing(sut_no_meta, 2019)


# ---------------------------------------------------------------------------
# Fixtures for get_products tests
# ---------------------------------------------------------------------------


@pytest.fixture
def supply_multi():
    return pd.DataFrame({
        "year":  [2019, 2019, 2019, 2019, 2019],
        "nrnr":  ["V10100", "V10200", "V20100", "V20200", "V90100"],
        "trans": ["0100"] * 5,
        "brch":  ["I1"] * 5,
        "bas":   [100.0, 80.0, 90.0, 70.0, 60.0],
    })


@pytest.fixture
def use_multi():
    return pd.DataFrame({
        "year":  [2019, 2019, 2019, 2019, 2019],
        "nrnr":  ["V10100", "V10200", "V20100", "V20200", "V90100"],
        "trans": ["2000"] * 5,
        "brch":  ["I1"] * 5,
        "bas":   [50.0, 40.0, 45.0, 35.0, 30.0],
        "koeb":  [55.0, 44.0, 49.0, 38.0, 33.0],
    })


@pytest.fixture
def sut_multi(supply_multi, use_multi, metadata):
    return SUT(
        price_basis="current_year",
        supply=supply_multi,
        use=use_multi,
        metadata=metadata,
    )


@pytest.fixture
def sut_multi_years(metadata):
    """SUT with integer id values across three years, for get_ids tests."""
    products = ["V10100", "V20100"]
    years = [2017, 2018, 2019]
    supply_rows = [
        {"year": y, "nrnr": p, "trans": "0100", "brch": "I1", "bas": 100.0}
        for y in years for p in products
    ]
    use_rows = [
        {"year": y, "nrnr": p, "trans": "2000", "brch": "I1", "bas": 50.0, "koeb": 55.0}
        for y in years for p in products
    ]
    return SUT(
        price_basis="current_year",
        supply=pd.DataFrame(supply_rows),
        use=pd.DataFrame(use_rows),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Tests for _natural_sort_key
# ---------------------------------------------------------------------------


class TestNaturalSortKey:

    def test_digits_compared_numerically_not_lexically(self):
        # Lexically "9" > "1", so "V9100" > "V10100" — natural sort reverses this
        assert _natural_sort_key("V9100") < _natural_sort_key("V10100")

    def test_same_string_is_equal(self):
        assert _natural_sort_key("V10100") == _natural_sort_key("V10100")

    def test_text_part_compared_lexically(self):
        assert _natural_sort_key("A10") < _natural_sort_key("B10")

    def test_longer_number_sorts_higher(self):
        assert _natural_sort_key("V10100") < _natural_sort_key("V20100")


# ---------------------------------------------------------------------------
# Tests for _match_codes
# ---------------------------------------------------------------------------


class TestMatchProductCodes:

    def test_exact_match(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["V10100"])
        assert result == ["V10100"]

    def test_exact_match_no_false_positives(self):
        result = _match_codes(["V10100", "V10200"], ["V10100"])
        assert "V10200" not in result

    def test_wildcard_match(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["V10*"])
        assert set(result) == {"V10100", "V10200"}

    def test_wildcard_no_false_positives(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["V10*"])
        assert "V20100" not in result

    def test_range_match_inclusive(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["V10100:V10200"])
        assert set(result) == {"V10100", "V10200"}

    def test_range_excludes_codes_outside_bounds(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["V10100:V10200"])
        assert "V20100" not in result

    def test_range_uses_natural_sort(self):
        # V9100 < V10100 by natural sort (9 < 10); lexical order would give the opposite
        result = _match_codes(["V9100", "V10100", "V20100"], ["V9100:V10100"])
        assert set(result) == {"V9100", "V10100"}
        assert "V20100" not in result

    def test_mixed_patterns(self):
        codes = ["V10100", "V10200", "V20100", "V90100"]
        result = _match_codes(codes, ["V10*", "V90100"])
        assert set(result) == {"V10100", "V10200", "V90100"}

    def test_code_matching_multiple_patterns_appears_once(self):
        result = _match_codes(["V10100"], ["V10100", "V10*"])
        assert result == ["V10100"]

    def test_no_match_returns_empty_list(self):
        result = _match_codes(["V10100", "V10200"], ["V99999"])
        assert result == []

    def test_empty_patterns_returns_empty_list(self):
        result = _match_codes(["V10100"], [])
        assert result == []

    def test_empty_codes_returns_empty_list(self):
        result = _match_codes([], ["V10*"])
        assert result == []

    def test_negation_exact(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["~V10100"])
        assert set(result) == {"V10200", "V20100"}

    def test_negation_wildcard(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["~V10*"])
        assert set(result) == {"V20100"}

    def test_negation_range(self):
        result = _match_codes(["V10100", "V10200", "V20100"], ["~V10100:V10200"])
        assert set(result) == {"V20100"}

    def test_negation_only_starts_from_all_codes(self):
        # No positive patterns — starting set is all codes
        result = _match_codes(["V10100", "V10200", "V20100"], ["~V10*"])
        assert set(result) == {"V20100"}

    def test_positive_then_negation(self):
        # Positive narrows to V10*, negation removes V10100
        codes = ["V10100", "V10200", "V20100", "V90100"]
        result = _match_codes(codes, ["V10*", "~V10100"])
        assert result == ["V10200"]

    def test_negation_removes_nothing_when_no_match(self):
        result = _match_codes(["V10100", "V10200"], ["~V99999"])
        assert set(result) == {"V10100", "V10200"}


# ---------------------------------------------------------------------------
# Tests for get_rows
# ---------------------------------------------------------------------------
#
# sut_multi:       single year (2019), five products, trans "0100" (supply)
#                  and "2000" (use), category "I1" throughout
# sut_multi_years: three years (2017-2019), two products, same transactions
#                  and category — used for id filtering tests


class TestGetRows:

    # --- products ---

    def test_products_exact_match(self, sut_multi):
        result = get_rows(sut_multi, products="V10100")
        assert set(result.supply["nrnr"]) == {"V10100"}
        assert set(result.use["nrnr"]) == {"V10100"}

    def test_products_wildcard(self, sut_multi):
        result = get_rows(sut_multi, products="V10*")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200"}

    def test_products_range(self, sut_multi):
        result = get_rows(sut_multi, products="V10100:V20200")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200", "V20100", "V20200"}

    def test_products_mixed_patterns(self, sut_multi):
        result = get_rows(sut_multi, products=["V10*", "V90100"])
        assert set(result.supply["nrnr"]) == {"V10100", "V10200", "V90100"}

    # --- transactions ---

    def test_transactions_supply_code_leaves_use_empty(self, sut_multi):
        result = get_rows(sut_multi, transactions="0100")
        assert len(result.supply) == 5
        assert len(result.use) == 0

    def test_transactions_use_code_leaves_supply_empty(self, sut_multi):
        result = get_rows(sut_multi, transactions="2000")
        assert len(result.supply) == 0
        assert len(result.use) == 5

    def test_transactions_wildcard(self, sut_multi):
        result = get_rows(sut_multi, transactions="0*")
        assert len(result.supply) == 5
        assert len(result.use) == 0

    # --- categories ---

    def test_categories_exact_match(self, sut_multi):
        result = get_rows(sut_multi, categories="I1")
        assert len(result.supply) == len(sut_multi.supply)
        assert len(result.use) == len(sut_multi.use)

    def test_categories_no_match_returns_empty(self, sut_multi):
        result = get_rows(sut_multi, categories="I2")
        assert len(result.supply) == 0
        assert len(result.use) == 0

    def test_categories_nan_values_excluded_not_error(self, sut_multi):
        import dataclasses
        supply_with_nan = sut_multi.supply.copy()
        supply_with_nan.loc[0, "brch"] = float("nan")
        sut_with_nan = dataclasses.replace(sut_multi, supply=supply_with_nan)
        result = get_rows(sut_with_nan, categories="I*")
        assert len(result.supply) == len(sut_multi.supply) - 1

    # --- ids ---

    def test_ids_integer(self, sut_multi_years):
        result = get_rows(sut_multi_years, ids=2019)
        assert set(result.supply["year"]) == {2019}

    def test_ids_string_matches_integer_column(self, sut_multi_years):
        result = get_rows(sut_multi_years, ids="2019")
        assert set(result.supply["year"]) == {2019}

    def test_ids_range_builtin(self, sut_multi_years):
        result = get_rows(sut_multi_years, ids=range(2017, 2019))
        assert set(result.supply["year"]) == {2017, 2018}

    def test_ids_pattern_range(self, sut_multi_years):
        result = get_rows(sut_multi_years, ids="2017:2018")
        assert set(result.supply["year"]) == {2017, 2018}

    def test_ids_wildcard(self, sut_multi_years):
        result = get_rows(sut_multi_years, ids="201*")
        assert set(result.supply["year"]) == {2017, 2018, 2019}

    # --- AND logic across dimensions ---

    def test_and_logic_products_and_transactions(self, sut_multi):
        # V10* products in supply only (trans "0100")
        result = get_rows(sut_multi, products="V10*", transactions="0100")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200"}
        assert len(result.use) == 0

    def test_and_logic_ids_and_products(self, sut_multi_years):
        result = get_rows(sut_multi_years, ids=2019, products="V10100")
        assert set(result.supply["year"]) == {2019}
        assert set(result.supply["nrnr"]) == {"V10100"}

    # --- empty result ---

    def test_no_match_returns_empty_dataframes(self, sut_multi):
        result = get_rows(sut_multi, products="V99999")
        assert len(result.supply) == 0
        assert len(result.use) == 0

    # --- return value properties ---

    def test_balancing_id_is_dropped(self, sut_multi):
        sut_with_balancing = mark_for_balancing(sut_multi, 2019)
        result = get_rows(sut_with_balancing, products="V10*")
        assert result.balancing_id is None

    def test_price_basis_preserved(self, sut_multi):
        result = get_rows(sut_multi, products="V10*")
        assert result.price_basis == sut_multi.price_basis

    def test_metadata_preserved(self, sut_multi):
        result = get_rows(sut_multi, products="V10*")
        assert result.metadata is sut_multi.metadata

    def test_does_not_mutate_original(self, sut_multi):
        original_len = len(sut_multi.supply)
        get_rows(sut_multi, products="V10*")
        assert len(sut_multi.supply) == original_len

    # --- error cases ---

    def test_raises_when_all_arguments_none(self, sut_multi):
        with pytest.raises(ValueError, match="At least one"):
            get_rows(sut_multi)

    def test_raises_when_metadata_is_none(self, supply_multi, use_multi):
        sut_no_meta = SUT(price_basis="current_year", supply=supply_multi, use=use_multi)
        with pytest.raises(ValueError, match="metadata"):
            get_rows(sut_no_meta, products="V10*")

    # --- negation ---

    def test_negation_only_excludes_from_all_codes(self, sut_multi):
        result = get_rows(sut_multi, products="~V10*")
        assert "V10100" not in set(result.supply["nrnr"])
        assert "V10200" not in set(result.supply["nrnr"])
        assert "V20100" in set(result.supply["nrnr"])

    def test_negation_combined_with_positive(self, sut_multi):
        # V10* minus V10100
        result = get_rows(sut_multi, products=["V10*", "~V10100"])
        assert set(result.supply["nrnr"]) == {"V10200"}


# ---------------------------------------------------------------------------
# Tests for get_product_codes, get_transaction_codes, get_ids,
# get_industry_codes, get_individual_consumption_codes, get_collective_consumption_codes
# ---------------------------------------------------------------------------


@pytest.fixture
def classified_transactions():
    return pd.DataFrame({
        "code":     ["0100", "2000", "3110", "3200"],
        "name":     ["Output", "Intermediate", "Household", "Government"],
        "table":    ["supply", "use",    "use",  "use"],
        "esa_code": ["P1",     "P2",     "P31",  "P32"],
    })


@pytest.fixture
def supply_classified():
    return pd.DataFrame({
        "year":  [2021, 2021],
        "nrnr":  ["P1", "P2"],
        "trans": ["0100", "0100"],
        "brch":  ["X", "Y"],
        "bas":   [100.0, 80.0],
    })


@pytest.fixture
def use_classified():
    return pd.DataFrame({
        "year":  [2021, 2021, 2021, 2021, 2021],
        "nrnr":  ["P1", "P2", "P1",  "P2",  "P1"],
        "trans": ["2000", "2000", "3110", "3110", "3200"],
        "brch":  ["X",    "Y",    "HH",   "HH",   "GOV"],
        "bas":   [30.0,   20.0,   40.0,   30.0,   20.0],
        "koeb":  [30.0,   20.0,   40.0,   30.0,   20.0],
    })


@pytest.fixture
def sut_classified(supply_classified, use_classified, columns, classified_transactions):
    classifications = SUTClassifications(transactions=classified_transactions)
    meta = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)


class TestGetProductCodes:

    def test_returns_dataframe_with_product_column(self, sut):
        result = get_product_codes(sut)
        assert list(result.columns) == ["nrnr"]

    def test_returns_unique_values_from_supply_and_use(self, sut):
        result = get_product_codes(sut)
        assert set(result["nrnr"]) == {"P1", "P2"}

    def test_sorted_ascending(self, sut):
        result = get_product_codes(sut)
        assert list(result["nrnr"]) == sorted(result["nrnr"])

    def test_index_is_reset(self, sut):
        result = get_product_codes(sut)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            get_product_codes(sut_no_meta)


class TestGetTransactionCodes:

    def test_returns_dataframe_with_transaction_column(self, sut):
        result = get_transaction_codes(sut)
        assert list(result.columns) == ["trans"]

    def test_includes_codes_from_both_supply_and_use(self, sut):
        # supply has "0100", use has "2000"
        result = get_transaction_codes(sut)
        assert set(result["trans"]) == {"0100", "2000"}

    def test_sorted_ascending(self, sut):
        result = get_transaction_codes(sut)
        assert list(result["trans"]) == sorted(result["trans"])

    def test_index_is_reset(self, sut):
        result = get_transaction_codes(sut)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            get_transaction_codes(sut_no_meta)


class TestGetIndustryCodes:

    def test_returns_dataframe_with_category_column(self, sut_classified):
        result = get_industry_codes(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_returns_codes_from_p1_and_p2_transactions(self, sut_classified):
        # supply has X, Y (P1); use has X, Y (P2); HH and GOV are P31/P32
        result = get_industry_codes(sut_classified)
        assert set(result["brch"]) == {"X", "Y"}

    def test_sorted_ascending(self, sut_classified):
        result = get_industry_codes(sut_classified)
        assert list(result["brch"]) == sorted(result["brch"])

    def test_index_is_reset(self, sut_classified):
        result = get_industry_codes(sut_classified)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply_classified, use_classified):
        sut_no_meta = SUT(price_basis="current_year", supply=supply_classified, use=use_classified)
        with pytest.raises(ValueError, match="metadata"):
            get_industry_codes(sut_no_meta)

    def test_raises_when_classifications_is_none(self, supply_classified, use_classified, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            get_industry_codes(sut_no_class)


class TestGetIndividualConsumptionCodes:

    def test_returns_dataframe_with_category_column(self, sut_classified):
        result = get_individual_consumption_codes(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_returns_codes_from_p31_transactions(self, sut_classified):
        result = get_individual_consumption_codes(sut_classified)
        assert set(result["brch"]) == {"HH"}

    def test_sorted_ascending(self, sut_classified):
        result = get_individual_consumption_codes(sut_classified)
        assert list(result["brch"]) == sorted(result["brch"])

    def test_index_is_reset(self, sut_classified):
        result = get_individual_consumption_codes(sut_classified)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_classifications_is_none(self, supply_classified, use_classified, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            get_individual_consumption_codes(sut_no_class)


class TestGetCollectiveConsumptionCodes:

    def test_returns_dataframe_with_category_column(self, sut_classified):
        result = get_collective_consumption_codes(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_returns_codes_from_p32_transactions(self, sut_classified):
        result = get_collective_consumption_codes(sut_classified)
        assert set(result["brch"]) == {"GOV"}

    def test_sorted_ascending(self, sut_classified):
        result = get_collective_consumption_codes(sut_classified)
        assert list(result["brch"]) == sorted(result["brch"])

    def test_index_is_reset(self, sut_classified):
        result = get_collective_consumption_codes(sut_classified)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_classifications_is_none(self, supply_classified, use_classified, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            get_collective_consumption_codes(sut_no_class)


class TestGetIds:

    def test_returns_dataframe_with_id_column(self, sut):
        result = get_ids(sut)
        assert list(result.columns) == ["year"]

    def test_returns_unique_values(self, sut):
        result = get_ids(sut)
        assert set(result["year"]) == {2018, 2019}

    def test_sorted_ascending(self, sut):
        result = get_ids(sut)
        assert list(result["year"]) == sorted(result["year"])

    def test_index_is_reset(self, sut):
        result = get_ids(sut)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            get_ids(sut_no_meta)
