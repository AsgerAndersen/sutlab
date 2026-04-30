"""
Tests for core SUT data structures and set_balancing_id.
"""

import pytest
import pandas as pd

from sutlab.sut import (
    BalancingTargets,
    SUT,
    SUTClassifications,
    SUTColumns,
    SUTMetadata,
    _match_codes,
    _natural_sort_key,
    get_codes_collective_consumption,
    get_ids,
    get_codes_individual_consumption,
    get_codes_industries,
    get_codes_products,
    filter_rows,
    get_codes_transactions,
    set_balancing_id,
    set_balancing_targets,
    set_metadata,
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
# Tests for set_balancing_id
# ---------------------------------------------------------------------------


class TestMarkForBalancing:

    def test_returns_sut_with_correct_balancing_id(self, sut):
        result = set_balancing_id(sut, 2019)
        assert result.balancing_id == 2019

    def test_does_not_mutate_original(self, sut):
        set_balancing_id(sut, 2019)
        assert sut.balancing_id is None

    def test_data_is_shared_not_copied(self, sut):
        # The supply DataFrame in the result should be the same object
        result = set_balancing_id(sut, 2019)
        assert result.supply is sut.supply

    def test_other_fields_are_preserved(self, sut):
        result = set_balancing_id(sut, 2019)
        assert result.price_basis == sut.price_basis
        assert result.metadata is sut.metadata

    def test_can_switch_active_year(self, sut):
        sut_2018 = set_balancing_id(sut, 2018)
        sut_2019 = set_balancing_id(sut, 2019)
        assert sut_2018.balancing_id == 2018
        assert sut_2019.balancing_id == 2019

    def test_raises_for_missing_id(self, sut):
        with pytest.raises(ValueError, match="2025"):
            set_balancing_id(sut, 2025)

    def test_error_message_lists_available_ids(self, sut):
        with pytest.raises(ValueError, match="2018"):
            set_balancing_id(sut, 2025)

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            set_balancing_id(sut_no_meta, 2019)


# ---------------------------------------------------------------------------
# Tests for set_balancing_targets
# ---------------------------------------------------------------------------


def _make_targets(years=None) -> BalancingTargets:
    """Build a BalancingTargets for the supply/use fixtures.

    Fixtures have years 2018 and 2019; transactions 0100/I1 (supply) and
    2000/I1 (use). Supply targets use ``bas``; use targets use ``koeb``.
    """
    if years is None:
        years = [2018, 2019]
    supply_rows = [{"year": y, "trans": "0100", "brch": "I1", "bas": 200.0} for y in years]
    use_rows = [{"year": y, "trans": "2000", "brch": "I1", "koeb": 100.0} for y in years]
    return BalancingTargets(
        supply=pd.DataFrame(supply_rows),
        use=pd.DataFrame(use_rows),
    )


class TestSetBalancingTargets:

    def test_returns_sut_with_targets_set(self, sut):
        targets = _make_targets()
        result = set_balancing_targets(sut, targets)
        assert result.balancing_targets is targets

    def test_does_not_mutate_original(self, sut):
        targets = _make_targets()
        set_balancing_targets(sut, targets)
        assert sut.balancing_targets is None

    def test_data_is_shared_not_copied(self, sut):
        targets = _make_targets()
        result = set_balancing_targets(sut, targets)
        assert result.supply is sut.supply

    def test_other_fields_are_preserved(self, sut):
        targets = _make_targets()
        result = set_balancing_targets(sut, targets)
        assert result.price_basis == sut.price_basis
        assert result.metadata is sut.metadata

    def test_targets_covering_subset_of_ids_is_allowed(self, sut):
        # Targets only cover 2019, but sut has both 2018 and 2019 — should not raise
        targets = _make_targets(years=[2019])
        result = set_balancing_targets(sut, targets)
        assert result.balancing_targets is targets

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            set_balancing_targets(sut_no_meta, _make_targets())

    def test_raises_when_supply_targets_missing_column(self, sut):
        targets = BalancingTargets(
            supply=pd.DataFrame({"year": [2019], "trans": ["0100"]}),  # missing brch, bas
            use=pd.DataFrame({"year": [2019], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0]}),
        )
        with pytest.raises(ValueError, match="supply"):
            set_balancing_targets(sut, targets)

    def test_raises_when_use_targets_missing_column(self, sut):
        targets = BalancingTargets(
            supply=pd.DataFrame({"year": [2019], "trans": ["0100"], "brch": ["I1"], "bas": [200.0]}),
            use=pd.DataFrame({"year": [2019], "trans": ["2000"]}),  # missing brch, koeb
        )
        with pytest.raises(ValueError, match="use"):
            set_balancing_targets(sut, targets)

    def test_error_names_missing_supply_columns(self, sut):
        targets = BalancingTargets(
            supply=pd.DataFrame({"year": [2019], "trans": ["0100"]}),  # missing brch, bas
            use=pd.DataFrame({"year": [2019], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0]}),
        )
        with pytest.raises(ValueError, match="brch"):
            set_balancing_targets(sut, targets)


# ---------------------------------------------------------------------------
# Tests for set_metadata
# ---------------------------------------------------------------------------


class TestSetMetadata:

    def test_returns_sut_with_metadata_set(self, sut, metadata):
        result = set_metadata(sut, metadata)
        assert result.metadata is metadata

    def test_does_not_mutate_original(self, sut, metadata):
        original_metadata = sut.metadata
        set_metadata(sut, metadata)
        assert sut.metadata is original_metadata

    def test_data_is_shared_not_copied(self, sut, metadata):
        result = set_metadata(sut, metadata)
        assert result.supply is sut.supply
        assert result.use is sut.use

    def test_other_fields_are_preserved(self, sut, metadata):
        result = set_metadata(sut, metadata)
        assert result.price_basis == sut.price_basis
        assert result.balancing_id == sut.balancing_id

    def test_raises_when_not_sut_metadata(self, sut):
        with pytest.raises(TypeError, match="SUTMetadata"):
            set_metadata(sut, "not_metadata")

    def test_delegate_method_equivalent(self, sut, metadata):
        result_free = set_metadata(sut, metadata)
        result_method = sut.set_metadata(metadata)
        assert result_free.metadata is result_method.metadata


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
# Tests for filter_rows
# ---------------------------------------------------------------------------
#
# sut_multi:       single year (2019), five products, trans "0100" (supply)
#                  and "2000" (use), category "I1" throughout
# sut_multi_years: three years (2017-2019), two products, same transactions
#                  and category — used for id filtering tests


class TestFilterRows:

    # --- products ---

    def test_products_exact_match(self, sut_multi):
        result = filter_rows(sut_multi, products="V10100")
        assert set(result.supply["nrnr"]) == {"V10100"}
        assert set(result.use["nrnr"]) == {"V10100"}

    def test_products_wildcard(self, sut_multi):
        result = filter_rows(sut_multi, products="V10*")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200"}

    def test_products_range(self, sut_multi):
        result = filter_rows(sut_multi, products="V10100:V20200")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200", "V20100", "V20200"}

    def test_products_mixed_patterns(self, sut_multi):
        result = filter_rows(sut_multi, products=["V10*", "V90100"])
        assert set(result.supply["nrnr"]) == {"V10100", "V10200", "V90100"}

    # --- transactions ---

    def test_transactions_supply_code_leaves_use_empty(self, sut_multi):
        result = filter_rows(sut_multi, transactions="0100")
        assert len(result.supply) == 5
        assert len(result.use) == 0

    def test_transactions_use_code_leaves_supply_empty(self, sut_multi):
        result = filter_rows(sut_multi, transactions="2000")
        assert len(result.supply) == 0
        assert len(result.use) == 5

    def test_transactions_wildcard(self, sut_multi):
        result = filter_rows(sut_multi, transactions="0*")
        assert len(result.supply) == 5
        assert len(result.use) == 0

    # --- categories ---

    def test_categories_exact_match(self, sut_multi):
        result = filter_rows(sut_multi, categories="I1")
        assert len(result.supply) == len(sut_multi.supply)
        assert len(result.use) == len(sut_multi.use)

    def test_categories_no_match_returns_empty(self, sut_multi):
        result = filter_rows(sut_multi, categories="I2")
        assert len(result.supply) == 0
        assert len(result.use) == 0

    def test_categories_nan_values_excluded_not_error(self, sut_multi):
        import dataclasses
        supply_with_nan = sut_multi.supply.copy()
        supply_with_nan.loc[0, "brch"] = float("nan")
        sut_with_nan = dataclasses.replace(sut_multi, supply=supply_with_nan)
        result = filter_rows(sut_with_nan, categories="I*")
        assert len(result.supply) == len(sut_multi.supply) - 1

    # --- ids ---

    def test_ids_integer(self, sut_multi_years):
        result = filter_rows(sut_multi_years, ids=2019)
        assert set(result.supply["year"]) == {2019}

    def test_ids_string_matches_integer_column(self, sut_multi_years):
        result = filter_rows(sut_multi_years, ids="2019")
        assert set(result.supply["year"]) == {2019}

    def test_ids_range_builtin(self, sut_multi_years):
        result = filter_rows(sut_multi_years, ids=range(2017, 2019))
        assert set(result.supply["year"]) == {2017, 2018}

    def test_ids_pattern_range(self, sut_multi_years):
        result = filter_rows(sut_multi_years, ids="2017:2018")
        assert set(result.supply["year"]) == {2017, 2018}

    def test_ids_wildcard(self, sut_multi_years):
        result = filter_rows(sut_multi_years, ids="201*")
        assert set(result.supply["year"]) == {2017, 2018, 2019}

    # --- AND logic across dimensions ---

    def test_and_logic_products_and_transactions(self, sut_multi):
        # V10* products in supply only (trans "0100")
        result = filter_rows(sut_multi, products="V10*", transactions="0100")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200"}
        assert len(result.use) == 0

    def test_and_logic_ids_and_products(self, sut_multi_years):
        result = filter_rows(sut_multi_years, ids=2019, products="V10100")
        assert set(result.supply["year"]) == {2019}
        assert set(result.supply["nrnr"]) == {"V10100"}

    # --- empty result ---

    def test_no_match_returns_empty_dataframes(self, sut_multi):
        result = filter_rows(sut_multi, products="V99999")
        assert len(result.supply) == 0
        assert len(result.use) == 0

    # --- return value properties ---

    def test_balancing_id_preserved_when_id_still_present(self, sut_multi):
        sut_with_balancing = set_balancing_id(sut_multi, 2019)
        result = filter_rows(sut_with_balancing, products="V10*")
        assert result.balancing_id == 2019

    def test_balancing_id_cleared_when_id_filtered_out(self, sut_multi_years):
        sut_with_balancing = set_balancing_id(sut_multi_years, 2019)
        result = filter_rows(sut_with_balancing, ids="2017:2018")
        assert result.balancing_id is None

    def test_price_basis_preserved(self, sut_multi):
        result = filter_rows(sut_multi, products="V10*")
        assert result.price_basis == sut_multi.price_basis

    def test_metadata_preserved(self, sut_multi):
        result = filter_rows(sut_multi, products="V10*")
        assert result.metadata is sut_multi.metadata

    def test_does_not_mutate_original(self, sut_multi):
        original_len = len(sut_multi.supply)
        filter_rows(sut_multi, products="V10*")
        assert len(sut_multi.supply) == original_len

    # --- error cases ---

    def test_raises_when_all_arguments_none(self, sut_multi):
        with pytest.raises(ValueError, match="At least one"):
            filter_rows(sut_multi)

    def test_raises_when_metadata_is_none(self, supply_multi, use_multi):
        sut_no_meta = SUT(price_basis="current_year", supply=supply_multi, use=use_multi)
        with pytest.raises(ValueError, match="metadata"):
            filter_rows(sut_no_meta, products="V10*")

    # --- negation ---

    def test_negation_only_excludes_from_all_codes(self, sut_multi):
        result = filter_rows(sut_multi, products="~V10*")
        assert "V10100" not in set(result.supply["nrnr"])
        assert "V10200" not in set(result.supply["nrnr"])
        assert "V20100" in set(result.supply["nrnr"])

    def test_negation_combined_with_positive(self, sut_multi):
        # V10* minus V10100
        result = filter_rows(sut_multi, products=["V10*", "~V10100"])
        assert set(result.supply["nrnr"]) == {"V10200"}

    # --- table argument ---

    def test_table_supply_only_filters_supply(self, sut_multi):
        result = filter_rows(sut_multi, products="V10*", table="supply")
        assert set(result.supply["nrnr"]) == {"V10100", "V10200"}
        # use is unchanged
        pd.testing.assert_frame_equal(result.use, sut_multi.use)

    def test_table_use_only_filters_use(self, sut_multi):
        # trans "2000" is a use-side transaction
        result = filter_rows(sut_multi, transactions="2000", table="use")
        assert len(result.use) == 5
        # supply is unchanged
        pd.testing.assert_frame_equal(result.supply, sut_multi.supply)

    def test_table_none_filters_both(self, sut_multi):
        result = filter_rows(sut_multi, products="V10*", table=None)
        assert set(result.supply["nrnr"]) == {"V10100", "V10200"}
        assert set(result.use["nrnr"]) == {"V10100", "V10200"}

    def test_table_invalid_raises(self, sut_multi):
        with pytest.raises(ValueError, match="table"):
            filter_rows(sut_multi, products="V10*", table="both")

    # --- balancing targets propagation ---

    def test_targets_filtered_by_ids(self, sut_multi_years):
        targets = _make_targets(years=[2017, 2018, 2019])
        sut_with_targets = set_balancing_targets(sut_multi_years, targets)
        result = filter_rows(sut_with_targets, ids="2017:2018")
        assert set(result.balancing_targets.supply["year"]) == {2017, 2018}
        assert set(result.balancing_targets.use["year"]) == {2017, 2018}

    def test_targets_filtered_by_transactions(self, sut_multi_years):
        targets = _make_targets(years=[2017, 2018, 2019])
        sut_with_targets = set_balancing_targets(sut_multi_years, targets)
        result = filter_rows(sut_with_targets, transactions="0100")
        assert len(result.balancing_targets.supply) == 3  # one row per year
        assert len(result.balancing_targets.use) == 0

    def test_targets_filtered_by_categories(self, sut_multi_years):
        targets = _make_targets(years=[2017, 2018, 2019])
        sut_with_targets = set_balancing_targets(sut_multi_years, targets)
        result = filter_rows(sut_with_targets, categories="I1")
        assert len(result.balancing_targets.supply) == 3
        assert len(result.balancing_targets.use) == 3

    def test_targets_not_filtered_by_products(self, sut_multi_years):
        targets = _make_targets(years=[2017, 2018, 2019])
        sut_with_targets = set_balancing_targets(sut_multi_years, targets)
        result = filter_rows(sut_with_targets, products="V10100")
        pd.testing.assert_frame_equal(result.balancing_targets.supply, targets.supply)
        pd.testing.assert_frame_equal(result.balancing_targets.use, targets.use)

    def test_targets_table_supply_leaves_use_targets_unchanged(self, sut_multi_years):
        targets = _make_targets(years=[2017, 2018, 2019])
        sut_with_targets = set_balancing_targets(sut_multi_years, targets)
        result = filter_rows(sut_with_targets, ids="2017", table="supply")
        assert set(result.balancing_targets.supply["year"]) == {2017}
        pd.testing.assert_frame_equal(result.balancing_targets.use, targets.use)

    def test_targets_table_use_leaves_supply_targets_unchanged(self, sut_multi_years):
        targets = _make_targets(years=[2017, 2018, 2019])
        sut_with_targets = set_balancing_targets(sut_multi_years, targets)
        result = filter_rows(sut_with_targets, ids="2017", table="use")
        pd.testing.assert_frame_equal(result.balancing_targets.supply, targets.supply)
        assert set(result.balancing_targets.use["year"]) == {2017}

    def test_no_targets_no_error(self, sut_multi):
        result = filter_rows(sut_multi, products="V10*")
        assert result.balancing_targets is None


# ---------------------------------------------------------------------------
# Tests for get_codes_products, get_codes_transactions, get_ids,
# get_codes_industries, get_codes_individual_consumption, get_codes_collective_consumption
# ---------------------------------------------------------------------------


@pytest.fixture
def classified_transactions():
    return pd.DataFrame({
        "trans":     ["0100", "2000", "3110", "3200"],
        "trans_txt": ["Output", "Intermediate", "Household", "Government"],
        "table":     ["supply", "use",    "use",  "use"],
        "esa_code":  ["P1",     "P2",     "P31",  "P32"],
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


@pytest.fixture
def classified_products():
    return pd.DataFrame({
        "nrnr":     ["P1", "P2"],
        "nrnr_txt": ["Product 1", "Product 2"],
    })


@pytest.fixture
def classified_industries():
    return pd.DataFrame({
        "brch":     ["X", "Y"],
        "brch_txt": ["Industry X", "Industry Y"],
    })


@pytest.fixture
def classified_individual_consumption():
    return pd.DataFrame({
        "brch":     ["HH"],
        "brch_txt": ["Households"],
    })


@pytest.fixture
def classified_collective_consumption():
    return pd.DataFrame({
        "brch":     ["GOV"],
        "brch_txt": ["Government"],
    })


@pytest.fixture
def sut_with_product_labels(supply_classified, use_classified, columns, classified_transactions, classified_products):
    classifications = SUTClassifications(transactions=classified_transactions, products=classified_products)
    meta = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)


@pytest.fixture
def sut_with_industry_labels(supply_classified, use_classified, columns, classified_transactions, classified_industries):
    classifications = SUTClassifications(transactions=classified_transactions, industries=classified_industries)
    meta = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)


@pytest.fixture
def sut_with_individual_labels(supply_classified, use_classified, columns, classified_transactions, classified_individual_consumption):
    classifications = SUTClassifications(transactions=classified_transactions, individual_consumption=classified_individual_consumption)
    meta = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)


@pytest.fixture
def sut_with_collective_labels(supply_classified, use_classified, columns, classified_transactions, classified_collective_consumption):
    classifications = SUTClassifications(transactions=classified_transactions, collective_consumption=classified_collective_consumption)
    meta = SUTMetadata(columns=columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)


class TestGetProductCodes:

    def test_returns_dataframe_with_product_column(self, sut):
        result = get_codes_products(sut)
        assert list(result.columns) == ["nrnr"]

    def test_returns_unique_values_from_supply_and_use(self, sut):
        result = get_codes_products(sut)
        assert set(result["nrnr"]) == {"P1", "P2"}

    def test_sorted_ascending(self, sut):
        result = get_codes_products(sut)
        assert list(result["nrnr"]) == sorted(result["nrnr"])

    def test_index_is_reset(self, sut):
        result = get_codes_products(sut)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            get_codes_products(sut_no_meta)

    def test_includes_txt_column_when_products_classification_present(self, sut_with_product_labels):
        result = get_codes_products(sut_with_product_labels)
        assert list(result.columns) == ["nrnr", "nrnr_txt"]

    def test_txt_values_match_classification(self, sut_with_product_labels):
        result = get_codes_products(sut_with_product_labels)
        row_p1 = result[result["nrnr"] == "P1"].iloc[0]
        assert row_p1["nrnr_txt"] == "Product 1"

    def test_no_txt_column_when_products_classification_absent(self, sut_classified):
        # sut_classified has transactions classification but no products
        result = get_codes_products(sut_classified)
        assert list(result.columns) == ["nrnr"]

    def test_filter_exact(self, sut):
        result = get_codes_products(sut, products="P1")
        assert list(result["nrnr"]) == ["P1"]

    def test_filter_wildcard(self, sut):
        result = get_codes_products(sut, products="P*")
        assert set(result["nrnr"]) == {"P1", "P2"}

    def test_filter_negation(self, sut):
        result = get_codes_products(sut, products="~P1")
        assert list(result["nrnr"]) == ["P2"]

    def test_filter_returns_empty_when_no_match(self, sut):
        result = get_codes_products(sut, products="ZZZZ")
        assert len(result) == 0

    def test_as_list_returns_list(self, sut):
        result = get_codes_products(sut, as_list=True)
        assert isinstance(result, list)
        assert set(result) == {"P1", "P2"}

    def test_as_list_omits_txt_column(self, sut_with_product_labels):
        result = get_codes_products(sut_with_product_labels, as_list=True)
        assert isinstance(result, list)
        assert all(isinstance(v, str) for v in result)

    def test_table_supply_returns_only_supply_products(self, sut):
        result = get_codes_products(sut, table="supply")
        assert set(result["nrnr"]) == set(sut.supply["nrnr"].dropna().unique())

    def test_table_use_returns_only_use_products(self, sut):
        result = get_codes_products(sut, table="use")
        assert set(result["nrnr"]) == set(sut.use["nrnr"].dropna().unique())

    def test_table_supply_as_list(self, sut):
        result = get_codes_products(sut, as_list=True, table="supply")
        assert isinstance(result, list)
        assert set(result) == set(sut.supply["nrnr"].dropna().unique())


class TestGetTransactionCodes:

    def test_returns_dataframe_with_transaction_column(self, sut):
        result = get_codes_transactions(sut)
        assert list(result.columns) == ["trans"]

    def test_includes_codes_from_both_supply_and_use(self, sut):
        # supply has "0100", use has "2000"
        result = get_codes_transactions(sut)
        assert set(result["trans"]) == {"0100", "2000"}

    def test_sorted_ascending(self, sut):
        result = get_codes_transactions(sut)
        assert list(result["trans"]) == sorted(result["trans"])

    def test_index_is_reset(self, sut):
        result = get_codes_transactions(sut)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply, use):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            get_codes_transactions(sut_no_meta)

    def test_includes_txt_column_when_transactions_classification_present(self, sut_classified):
        result = get_codes_transactions(sut_classified)
        assert list(result.columns) == ["trans", "trans_txt"]

    def test_txt_values_match_classification(self, sut_classified):
        result = get_codes_transactions(sut_classified)
        row = result[result["trans"] == "0100"].iloc[0]
        assert row["trans_txt"] == "Output"

    def test_no_txt_column_when_classifications_absent(self, sut):
        # sut has no classifications at all
        result = get_codes_transactions(sut)
        assert list(result.columns) == ["trans"]

    def test_filter_exact(self, sut):
        result = get_codes_transactions(sut, transactions="0100")
        assert list(result["trans"]) == ["0100"]

    def test_filter_wildcard(self, sut):
        result = get_codes_transactions(sut, transactions="0*")
        assert list(result["trans"]) == ["0100"]

    def test_filter_negation(self, sut):
        result = get_codes_transactions(sut, transactions="~0100")
        assert list(result["trans"]) == ["2000"]

    def test_as_list_returns_list(self, sut):
        result = get_codes_transactions(sut, as_list=True)
        assert isinstance(result, list)
        assert set(result) == {"0100", "2000"}

    def test_as_list_omits_txt_column(self, sut_classified):
        result = get_codes_transactions(sut_classified, as_list=True)
        assert isinstance(result, list)
        assert all(isinstance(v, str) for v in result)

    def test_table_supply_returns_only_supply_transactions(self, sut):
        # supply has "0100", use has "2000"
        result = get_codes_transactions(sut, table="supply")
        assert list(result["trans"]) == ["0100"]

    def test_table_use_returns_only_use_transactions(self, sut):
        result = get_codes_transactions(sut, table="use")
        assert list(result["trans"]) == ["2000"]

    def test_table_supply_as_list(self, sut):
        result = get_codes_transactions(sut, as_list=True, table="supply")
        assert result == ["0100"]


class TestGetIndustryCodes:

    def test_returns_dataframe_with_category_column(self, sut_classified):
        result = get_codes_industries(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_returns_codes_from_p1_and_p2_transactions(self, sut_classified):
        # supply has X, Y (P1); use has X, Y (P2); HH and GOV are P31/P32
        result = get_codes_industries(sut_classified)
        assert set(result["brch"]) == {"X", "Y"}

    def test_sorted_ascending(self, sut_classified):
        result = get_codes_industries(sut_classified)
        assert list(result["brch"]) == sorted(result["brch"])

    def test_index_is_reset(self, sut_classified):
        result = get_codes_industries(sut_classified)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_metadata_is_none(self, supply_classified, use_classified):
        sut_no_meta = SUT(price_basis="current_year", supply=supply_classified, use=use_classified)
        with pytest.raises(ValueError, match="metadata"):
            get_codes_industries(sut_no_meta)

    def test_raises_when_classifications_is_none(self, supply_classified, use_classified, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            get_codes_industries(sut_no_class)

    def test_includes_txt_column_when_industries_classification_present(self, sut_with_industry_labels):
        result = get_codes_industries(sut_with_industry_labels)
        assert list(result.columns) == ["brch", "brch_txt"]

    def test_txt_values_match_classification(self, sut_with_industry_labels):
        result = get_codes_industries(sut_with_industry_labels)
        row = result[result["brch"] == "X"].iloc[0]
        assert row["brch_txt"] == "Industry X"

    def test_no_txt_column_when_industries_classification_absent(self, sut_classified):
        result = get_codes_industries(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_filter_exact(self, sut_classified):
        result = get_codes_industries(sut_classified, industries="X")
        assert list(result["brch"]) == ["X"]

    def test_filter_negation(self, sut_classified):
        result = get_codes_industries(sut_classified, industries="~X")
        assert list(result["brch"]) == ["Y"]

    def test_as_list_returns_list(self, sut_classified):
        result = get_codes_industries(sut_classified, as_list=True)
        assert isinstance(result, list)
        assert set(result) == {"X", "Y"}

    def test_as_list_omits_txt_column(self, sut_with_industry_labels):
        result = get_codes_industries(sut_with_industry_labels, as_list=True)
        assert isinstance(result, list)
        assert all(isinstance(v, str) for v in result)

    def test_table_supply_returns_codes_from_p1_rows(self, sut_classified):
        # supply has P1 rows with brch X, Y
        result = get_codes_industries(sut_classified, table="supply")
        assert set(result["brch"]) == {"X", "Y"}

    def test_table_use_returns_codes_from_p2_rows(self, sut_classified):
        # use has P2 rows with brch X, Y
        result = get_codes_industries(sut_classified, table="use")
        assert set(result["brch"]) == {"X", "Y"}

    def test_table_supply_as_list(self, sut_classified):
        result = get_codes_industries(sut_classified, as_list=True, table="supply")
        assert isinstance(result, list)
        assert set(result) == {"X", "Y"}


class TestGetIndividualConsumptionCodes:

    def test_returns_dataframe_with_category_column(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_returns_codes_from_p31_transactions(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified)
        assert set(result["brch"]) == {"HH"}

    def test_sorted_ascending(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified)
        assert list(result["brch"]) == sorted(result["brch"])

    def test_index_is_reset(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_classifications_is_none(self, supply_classified, use_classified, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            get_codes_individual_consumption(sut_no_class)

    def test_includes_txt_column_when_individual_consumption_classification_present(self, sut_with_individual_labels):
        result = get_codes_individual_consumption(sut_with_individual_labels)
        assert list(result.columns) == ["brch", "brch_txt"]

    def test_txt_values_match_classification(self, sut_with_individual_labels):
        result = get_codes_individual_consumption(sut_with_individual_labels)
        row = result[result["brch"] == "HH"].iloc[0]
        assert row["brch_txt"] == "Households"

    def test_no_txt_column_when_individual_consumption_classification_absent(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_filter_exact(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified, categories="HH")
        assert list(result["brch"]) == ["HH"]

    def test_filter_no_match(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified, categories="GOV")
        assert len(result) == 0

    def test_as_list_returns_list(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified, as_list=True)
        assert isinstance(result, list)
        assert set(result) == {"HH"}

    def test_table_supply_returns_empty_dataframe(self, sut_classified):
        # P31 never appears in supply
        result = get_codes_individual_consumption(sut_classified, table="supply")
        assert len(result) == 0

    def test_table_supply_returns_empty_list(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified, as_list=True, table="supply")
        assert result == []

    def test_table_use_returns_codes(self, sut_classified):
        result = get_codes_individual_consumption(sut_classified, table="use")
        assert set(result["brch"]) == {"HH"}


class TestGetCollectiveConsumptionCodes:

    def test_returns_dataframe_with_category_column(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_returns_codes_from_p32_transactions(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified)
        assert set(result["brch"]) == {"GOV"}

    def test_sorted_ascending(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified)
        assert list(result["brch"]) == sorted(result["brch"])

    def test_index_is_reset(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified)
        assert list(result.index) == list(range(len(result)))

    def test_raises_when_classifications_is_none(self, supply_classified, use_classified, columns):
        meta = SUTMetadata(columns=columns)
        sut_no_class = SUT(price_basis="current_year", supply=supply_classified, use=use_classified, metadata=meta)
        with pytest.raises(ValueError, match="classifications"):
            get_codes_collective_consumption(sut_no_class)

    def test_includes_txt_column_when_collective_consumption_classification_present(self, sut_with_collective_labels):
        result = get_codes_collective_consumption(sut_with_collective_labels)
        assert list(result.columns) == ["brch", "brch_txt"]

    def test_txt_values_match_classification(self, sut_with_collective_labels):
        result = get_codes_collective_consumption(sut_with_collective_labels)
        row = result[result["brch"] == "GOV"].iloc[0]
        assert row["brch_txt"] == "Government"

    def test_no_txt_column_when_collective_consumption_classification_absent(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified)
        assert list(result.columns) == ["brch"]

    def test_filter_exact(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified, categories="GOV")
        assert list(result["brch"]) == ["GOV"]

    def test_filter_no_match(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified, categories="HH")
        assert len(result) == 0

    def test_as_list_returns_list(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified, as_list=True)
        assert isinstance(result, list)
        assert set(result) == {"GOV"}

    def test_table_supply_returns_empty_dataframe(self, sut_classified):
        # P32 never appears in supply
        result = get_codes_collective_consumption(sut_classified, table="supply")
        assert len(result) == 0

    def test_table_supply_returns_empty_list(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified, as_list=True, table="supply")
        assert result == []

    def test_table_use_returns_codes(self, sut_classified):
        result = get_codes_collective_consumption(sut_classified, table="use")
        assert set(result["brch"]) == {"GOV"}


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

