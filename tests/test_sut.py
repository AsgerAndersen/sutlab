"""
Tests for core SUT data structures and mark_for_balancing.
"""

import pytest
import pandas as pd

from sutlab.sut import SUT, SUTColumns, SUTMetadata, mark_for_balancing


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
        product_taxes="afg",
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


class TestSetActive:

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
