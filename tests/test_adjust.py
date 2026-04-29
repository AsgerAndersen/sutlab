"""
Tests for sutlab/adjust/ — adjust_add_sut.
"""

import math

import pytest
import pandas as pd

from sutlab.adjust import adjust_add_sut, adjust_subtract_sut, adjust_substitute_sut
from sutlab.sut import (
    BalancingTargets,
    BalancingConfig,
    SUT,
    SUTColumns,
    SUTMetadata,
)


# ---------------------------------------------------------------------------
# Shared fixtures
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
        trade_margins="eng",
        wholesale_margins=None,
        retail_margins="det",
        transport_margins=None,
        product_taxes="afg",
        product_subsidies=None,
        product_taxes_less_subsidies=None,
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
        "bas":   [100.0, 200.0, 110.0, 210.0],
    })


@pytest.fixture
def use():
    return pd.DataFrame({
        "year":  [2018, 2018, 2019, 2019],
        "nrnr":  ["P1", "P2", "P1", "P2"],
        "trans": ["2000", "2000", "2000", "2000"],
        "brch":  ["I1", "I1", "I1", "I1"],
        "bas":   [60.0, 120.0, 66.0, 132.0],
        "eng":   [5.0, 10.0, 5.5, 11.0],
        "det":   [3.0, 6.0, 3.3, 6.6],
        "afg":   [2.0, 4.0, 2.2, 4.4],
        "moms":  [10.0, 20.0, 11.0, 22.0],
        "koeb":  [80.0, 160.0, 86.8, 174.0],
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
# Fixtures for adjust_add_sut tests
#
# The base ``sut`` fixture has:
#   supply: years 2018+2019, products P1+P2, trans=0100, brch=I1
#   use:    years 2018+2019, products P1+P2, trans=2000, brch=I1
#
# adjustments has:
#   supply: year=2018, P1/0100/I1 (overlapping) + P3/0100/I1 (new)
#   use:    year=2018, P1/2000/I1 (overlapping) + P3/2000/I1 (new)
# ---------------------------------------------------------------------------

@pytest.fixture
def supply_values():
    return pd.DataFrame({
        "year":  [2018,  2018],
        "nrnr":  ["P1",  "P3"],
        "trans": ["0100", "0100"],
        "brch":  ["I1",  "I1"],
        "bas":   [10.0,  50.0],
    })


@pytest.fixture
def use_values():
    return pd.DataFrame({
        "year":  [2018,  2018],
        "nrnr":  ["P1",  "P3"],
        "trans": ["2000", "2000"],
        "brch":  ["I1",  "I1"],
        "bas":   [6.0,   5.0],
        "eng":   [0.5,   0.4],
        "det":   [0.3,   0.2],
        "afg":   [0.2,   0.1],
        "moms":  [1.0,   0.8],
        "koeb":  [8.0,   6.5],
    })


@pytest.fixture
def adjustments(supply_values, use_values, metadata):
    return SUT(
        price_basis="current_year",
        supply=supply_values,
        use=use_values,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Tests for adjust_add_sut — supply side
# ---------------------------------------------------------------------------

class TestAdjustAddSutSupply:

    def test_matching_row_values_are_summed(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        # 2018/P1/0100/I1: 100.0 + 10.0 = 110.0
        row = result.supply[
            (result.supply["year"] == 2018) &
            (result.supply["nrnr"] == "P1")
        ]
        assert row["bas"].iloc[0] == pytest.approx(110.0)

    def test_unmatched_rows_in_base_unchanged(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        # 2019/P1/0100/I1 only exists in sut → unchanged
        row = result.supply[
            (result.supply["year"] == 2019) &
            (result.supply["nrnr"] == "P1")
        ]
        assert row["bas"].iloc[0] == pytest.approx(110.0)

    def test_new_rows_from_values_appended(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        # P3 only exists in adjustments → should appear in result
        new_row = result.supply[result.supply["nrnr"] == "P3"]
        assert len(new_row) == 1
        assert new_row["bas"].iloc[0] == pytest.approx(50.0)

    def test_total_row_count(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        # base has 4 rows (2 years × 2 products); P3 is appended → 5 rows
        assert len(result.supply) == 5


# ---------------------------------------------------------------------------
# Tests for adjust_add_sut — use side
# ---------------------------------------------------------------------------

class TestAdjustAddSutUse:

    def test_all_price_columns_summed_for_matching_row(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        row = result.use[
            (result.use["year"] == 2018) &
            (result.use["nrnr"] == "P1")
        ]
        # sut has: bas=60, eng=5, det=3, afg=2, moms=10, koeb=80
        # adjustments adds: bas=6, eng=0.5, det=0.3, afg=0.2, moms=1, koeb=8
        assert row["bas"].iloc[0] == pytest.approx(66.0)
        assert row["eng"].iloc[0] == pytest.approx(5.5)
        assert row["det"].iloc[0] == pytest.approx(3.3)
        assert row["afg"].iloc[0] == pytest.approx(2.2)
        assert row["moms"].iloc[0] == pytest.approx(11.0)
        assert row["koeb"].iloc[0] == pytest.approx(88.0)

    def test_new_use_row_appended(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        new_row = result.use[result.use["nrnr"] == "P3"]
        assert len(new_row) == 1
        assert new_row["koeb"].iloc[0] == pytest.approx(6.5)

    def test_unmatched_base_rows_unchanged(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        row = result.use[
            (result.use["year"] == 2019) &
            (result.use["nrnr"] == "P1")
        ]
        assert row["koeb"].iloc[0] == pytest.approx(86.8)


# ---------------------------------------------------------------------------
# Tests for adjust_add_sut — NaN handling
# ---------------------------------------------------------------------------

class TestAdjustAddSutNanHandling:

    def test_nan_in_values_treated_as_zero(self, sut, metadata):
        # adjustments has NaN for eng on the overlapping row → sut's eng preserved
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [10.0],
        })
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [6.0], "eng": [float("nan")], "det": [0.3],
            "afg": [0.2], "moms": [1.0], "koeb": [8.0],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_add_sut(sut, sv)
        row = result.use[
            (result.use["year"] == 2018) & (result.use["nrnr"] == "P1")
        ]
        # eng: 5.0 (sut) + NaN (sv) → 5.0
        assert row["eng"].iloc[0] == pytest.approx(5.0)
        # koeb: 80.0 + 8.0 = 88.0 (regular columns still summed)
        assert row["koeb"].iloc[0] == pytest.approx(88.0)

    def test_nan_in_base_treated_as_zero(self, sut, metadata):
        # Give sut a NaN in eng for 2018/P1; adjustments provides a value
        supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [100.0],
        })
        use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [60.0], "eng": [float("nan")], "det": [3.0],
            "afg": [2.0], "moms": [10.0], "koeb": [80.0],
        })
        base = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [6.0], "eng": [0.5], "det": [0.3],
            "afg": [0.2], "moms": [1.0], "koeb": [8.0],
        })
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [10.0],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_add_sut(base, sv)
        row = result.use[result.use["nrnr"] == "P1"]
        # eng: NaN (base) + 0.5 (sv) → 0.5
        assert row["eng"].iloc[0] == pytest.approx(0.5)

    def test_nan_plus_nan_stays_nan(self, sut, metadata):
        # Both base and values have NaN in eng for the same row
        supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [100.0],
        })
        use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [60.0], "eng": [float("nan")], "det": [3.0],
            "afg": [2.0], "moms": [10.0], "koeb": [80.0],
        })
        base = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [6.0], "eng": [float("nan")], "det": [0.3],
            "afg": [0.2], "moms": [1.0], "koeb": [8.0],
        })
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [10.0],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_add_sut(base, sv)
        row = result.use[result.use["nrnr"] == "P1"]
        assert math.isnan(row["eng"].iloc[0])


# ---------------------------------------------------------------------------
# Tests for adjust_add_sut — field inheritance
# ---------------------------------------------------------------------------

class TestAdjustAddSutFieldInheritance:

    def test_result_carries_base_metadata(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        assert result.metadata is sut.metadata

    def test_result_carries_base_price_basis(self, sut, adjustments):
        result = adjust_add_sut(sut, adjustments)
        assert result.price_basis == sut.price_basis

    def test_result_carries_base_balancing_id(self, sut, adjustments):
        sut_with_id = sut.set_balancing_id(2019)
        result = adjust_add_sut(sut_with_id, adjustments)
        assert result.balancing_id == 2019

    def test_result_carries_base_balancing_config(self, sut, adjustments):
        config = BalancingConfig()
        sut_with_config = sut.set_balancing_config(config)
        result = adjust_add_sut(sut_with_config, adjustments)
        assert result.balancing_config is config

    def test_does_not_mutate_original(self, sut, adjustments):
        original_supply_shape = sut.supply.shape
        adjust_add_sut(sut, adjustments)
        assert sut.supply.shape == original_supply_shape

    def test_adjustments_without_metadata_works(self, sut, supply_values, use_values):
        sv = SUT(
            price_basis="current_year",
            supply=supply_values,
            use=use_values,
        )
        result = adjust_add_sut(sut, sv)
        # P3 row should still be appended
        assert "P3" in result.supply["nrnr"].values


# ---------------------------------------------------------------------------
# Tests for adjust_add_sut — balancing targets
# ---------------------------------------------------------------------------

class TestAdjustAddSutBalancingTargets:

    def test_targets_added_when_both_have_targets(self, sut, adjustments):
        base_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        values_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [10.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [5.0],
            }),
        )
        sut_with_targets = sut.set_balancing_targets(base_targets)
        sv = SUT(
            price_basis="current_year",
            supply=adjustments.supply,
            use=adjustments.use,
            balancing_targets=values_targets,
        )
        result = adjust_add_sut(sut_with_targets, sv)
        assert result.balancing_targets is not None
        # Supply target: 200 + 10 = 210
        supply_row = result.balancing_targets.supply[
            result.balancing_targets.supply["trans"] == "0100"
        ]
        assert supply_row["bas"].iloc[0] == pytest.approx(210.0)
        # Use target: 100 + 5 = 105
        use_row = result.balancing_targets.use[
            result.balancing_targets.use["trans"] == "2000"
        ]
        assert use_row["koeb"].iloc[0] == pytest.approx(105.0)

    def test_new_target_rows_from_values_appended(self, sut, adjustments):
        base_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        values_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2019], "trans": ["0100"], "brch": ["I1"], "bas": [10.0],
            }),
            use=pd.DataFrame({
                "year": [2019], "trans": ["2000"], "brch": ["I1"], "koeb": [5.0],
            }),
        )
        sut_with_targets = sut.set_balancing_targets(base_targets)
        sv = SUT(
            price_basis="current_year",
            supply=adjustments.supply,
            use=adjustments.use,
            balancing_targets=values_targets,
        )
        result = adjust_add_sut(sut_with_targets, sv)
        assert len(result.balancing_targets.supply) == 2

    def test_targets_from_values_used_when_base_has_none(self, sut, adjustments):
        values_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        sv = SUT(
            price_basis="current_year",
            supply=adjustments.supply,
            use=adjustments.use,
            balancing_targets=values_targets,
        )
        result = adjust_add_sut(sut, sv)
        assert result.balancing_targets is values_targets

    def test_base_targets_preserved_when_values_has_none(self, sut, adjustments):
        base_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        sut_with_targets = sut.set_balancing_targets(base_targets)
        result = adjust_add_sut(sut_with_targets, adjustments)
        assert result.balancing_targets is base_targets


# ---------------------------------------------------------------------------
# Tests for adjust_add_sut — errors
# ---------------------------------------------------------------------------

class TestAdjustAddSutErrors:

    def test_raises_when_metadata_is_none(self, supply, use, adjustments):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            adjust_add_sut(sut_no_meta, adjustments)

    def test_raises_on_price_basis_mismatch(self, sut, supply_values, use_values, metadata):
        sv = SUT(
            price_basis="previous_year",
            supply=supply_values,
            use=use_values,
            metadata=metadata,
        )
        with pytest.raises(ValueError, match="price_basis"):
            adjust_add_sut(sut, sv)

    def test_raises_on_sut_columns_mismatch(self, sut, supply_values, use_values):
        different_cols = SUTColumns(
            id="year",
            product="nrnr",
            transaction="trans",
            category="brch",
            price_basic="different_bas",
            price_purchasers="koeb",
        )
        sv = SUT(
            price_basis="current_year",
            supply=supply_values,
            use=use_values,
            metadata=SUTMetadata(columns=different_cols),
        )
        with pytest.raises(ValueError, match="SUTColumns"):
            adjust_add_sut(sut, sv)

    def test_method_delegates_to_free_function(self, sut, adjustments):
        result_method = sut.adjust_add_sut(adjustments)
        result_free = adjust_add_sut(sut, adjustments)
        pd.testing.assert_frame_equal(
            result_method.supply.reset_index(drop=True),
            result_free.supply.reset_index(drop=True),
        )


# ---------------------------------------------------------------------------
# Tests for adjust_subtract_sut — supply side
# ---------------------------------------------------------------------------

class TestAdjustSubtractSutSupply:

    def test_matching_row_values_are_subtracted(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        # 2018/P1/0100/I1: 100.0 - 10.0 = 90.0
        row = result.supply[
            (result.supply["year"] == 2018) &
            (result.supply["nrnr"] == "P1")
        ]
        assert row["bas"].iloc[0] == pytest.approx(90.0)

    def test_unmatched_rows_in_base_unchanged(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        # 2019/P1/0100/I1 only exists in sut → unchanged
        row = result.supply[
            (result.supply["year"] == 2019) &
            (result.supply["nrnr"] == "P1")
        ]
        assert row["bas"].iloc[0] == pytest.approx(110.0)

    def test_new_rows_from_adjustments_appended_as_negated(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        # P3 only in adjustments → appended as 0 - 50.0 = -50.0
        new_row = result.supply[result.supply["nrnr"] == "P3"]
        assert len(new_row) == 1
        assert new_row["bas"].iloc[0] == pytest.approx(-50.0)

    def test_total_row_count(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        # base 4 rows + P3 appended → 5
        assert len(result.supply) == 5


# ---------------------------------------------------------------------------
# Tests for adjust_subtract_sut — use side
# ---------------------------------------------------------------------------

class TestAdjustSubtractSutUse:

    def test_all_price_columns_subtracted_for_matching_row(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        row = result.use[
            (result.use["year"] == 2018) &
            (result.use["nrnr"] == "P1")
        ]
        # sut: bas=60, eng=5, det=3, afg=2, moms=10, koeb=80
        # adjustments subtracts: bas=6, eng=0.5, det=0.3, afg=0.2, moms=1, koeb=8
        assert row["bas"].iloc[0] == pytest.approx(54.0)
        assert row["eng"].iloc[0] == pytest.approx(4.5)
        assert row["det"].iloc[0] == pytest.approx(2.7)
        assert row["afg"].iloc[0] == pytest.approx(1.8)
        assert row["moms"].iloc[0] == pytest.approx(9.0)
        assert row["koeb"].iloc[0] == pytest.approx(72.0)

    def test_new_use_row_appended_as_negated(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        new_row = result.use[result.use["nrnr"] == "P3"]
        assert len(new_row) == 1
        assert new_row["koeb"].iloc[0] == pytest.approx(-6.5)

    def test_unmatched_base_rows_unchanged(self, sut, adjustments):
        result = adjust_subtract_sut(sut, adjustments)
        row = result.use[
            (result.use["year"] == 2019) &
            (result.use["nrnr"] == "P1")
        ]
        assert row["koeb"].iloc[0] == pytest.approx(86.8)


# ---------------------------------------------------------------------------
# Tests for adjust_subtract_sut — NaN handling
# ---------------------------------------------------------------------------

class TestAdjustSubtractSutNanHandling:

    def test_nan_in_adjustments_treated_as_zero(self, sut, metadata):
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [10.0],
        })
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [6.0], "eng": [float("nan")], "det": [0.3],
            "afg": [0.2], "moms": [1.0], "koeb": [8.0],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_subtract_sut(sut, sv)
        row = result.use[
            (result.use["year"] == 2018) & (result.use["nrnr"] == "P1")
        ]
        # eng: 5.0 - NaN → 5.0
        assert row["eng"].iloc[0] == pytest.approx(5.0)

    def test_nan_minus_nan_stays_nan(self, sut, metadata):
        supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [100.0],
        })
        use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [60.0], "eng": [float("nan")], "det": [3.0],
            "afg": [2.0], "moms": [10.0], "koeb": [80.0],
        })
        base = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [6.0], "eng": [float("nan")], "det": [0.3],
            "afg": [0.2], "moms": [1.0], "koeb": [8.0],
        })
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [10.0],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_subtract_sut(base, sv)
        row = result.use[result.use["nrnr"] == "P1"]
        assert math.isnan(row["eng"].iloc[0])


# ---------------------------------------------------------------------------
# Tests for adjust_subtract_sut — balancing targets
# ---------------------------------------------------------------------------

class TestAdjustSubtractSutBalancingTargets:

    def test_targets_subtracted_when_both_have_targets(self, sut, adjustments):
        base_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        values_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [10.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [5.0],
            }),
        )
        sut_with_targets = sut.set_balancing_targets(base_targets)
        sv = SUT(
            price_basis="current_year",
            supply=adjustments.supply,
            use=adjustments.use,
            balancing_targets=values_targets,
        )
        result = adjust_subtract_sut(sut_with_targets, sv)
        supply_row = result.balancing_targets.supply[
            result.balancing_targets.supply["trans"] == "0100"
        ]
        # 200 - 10 = 190
        assert supply_row["bas"].iloc[0] == pytest.approx(190.0)
        use_row = result.balancing_targets.use[
            result.balancing_targets.use["trans"] == "2000"
        ]
        # 100 - 5 = 95
        assert use_row["koeb"].iloc[0] == pytest.approx(95.0)

    def test_method_delegates_to_free_function(self, sut, adjustments):
        result_method = sut.adjust_subtract_sut(adjustments)
        result_free = adjust_subtract_sut(sut, adjustments)
        pd.testing.assert_frame_equal(
            result_method.supply.reset_index(drop=True),
            result_free.supply.reset_index(drop=True),
        )


# ---------------------------------------------------------------------------
# Tests for adjust_subtract_sut — errors
# ---------------------------------------------------------------------------

class TestAdjustSubtractSutErrors:

    def test_raises_when_metadata_is_none(self, supply, use, adjustments):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            adjust_subtract_sut(sut_no_meta, adjustments)

    def test_raises_on_price_basis_mismatch(self, sut, supply_values, use_values, metadata):
        sv = SUT(
            price_basis="previous_year",
            supply=supply_values,
            use=use_values,
            metadata=metadata,
        )
        with pytest.raises(ValueError, match="price_basis"):
            adjust_subtract_sut(sut, sv)


# ---------------------------------------------------------------------------
# Tests for adjust_substitute_sut — supply side
# ---------------------------------------------------------------------------

class TestAdjustSubstituteSutSupply:

    def test_matching_row_value_replaced(self, sut, adjustments):
        result = adjust_substitute_sut(sut, adjustments)
        # 2018/P1/0100/I1: replaced with 10.0 from adjustments
        row = result.supply[
            (result.supply["year"] == 2018) &
            (result.supply["nrnr"] == "P1")
        ]
        assert row["bas"].iloc[0] == pytest.approx(10.0)

    def test_unmatched_rows_in_base_unchanged(self, sut, adjustments):
        result = adjust_substitute_sut(sut, adjustments)
        # 2019/P1 not in adjustments → unchanged
        row = result.supply[
            (result.supply["year"] == 2019) &
            (result.supply["nrnr"] == "P1")
        ]
        assert row["bas"].iloc[0] == pytest.approx(110.0)

    def test_new_rows_from_adjustments_appended(self, sut, adjustments):
        result = adjust_substitute_sut(sut, adjustments)
        new_row = result.supply[result.supply["nrnr"] == "P3"]
        assert len(new_row) == 1
        assert new_row["bas"].iloc[0] == pytest.approx(50.0)

    def test_total_row_count(self, sut, adjustments):
        result = adjust_substitute_sut(sut, adjustments)
        # base 4 rows + P3 appended → 5
        assert len(result.supply) == 5


# ---------------------------------------------------------------------------
# Tests for adjust_substitute_sut — use side
# ---------------------------------------------------------------------------

class TestAdjustSubstituteSutUse:

    def test_all_price_columns_replaced_for_matching_row(self, sut, adjustments):
        result = adjust_substitute_sut(sut, adjustments)
        row = result.use[
            (result.use["year"] == 2018) &
            (result.use["nrnr"] == "P1")
        ]
        # adjustments values: bas=6, eng=0.5, det=0.3, afg=0.2, moms=1, koeb=8
        assert row["bas"].iloc[0] == pytest.approx(6.0)
        assert row["eng"].iloc[0] == pytest.approx(0.5)
        assert row["det"].iloc[0] == pytest.approx(0.3)
        assert row["afg"].iloc[0] == pytest.approx(0.2)
        assert row["moms"].iloc[0] == pytest.approx(1.0)
        assert row["koeb"].iloc[0] == pytest.approx(8.0)

    def test_unmatched_base_rows_unchanged(self, sut, adjustments):
        result = adjust_substitute_sut(sut, adjustments)
        row = result.use[
            (result.use["year"] == 2019) &
            (result.use["nrnr"] == "P1")
        ]
        assert row["koeb"].iloc[0] == pytest.approx(86.8)


# ---------------------------------------------------------------------------
# Tests for adjust_substitute_sut — NaN handling
# ---------------------------------------------------------------------------

class TestAdjustSubstituteSutNanHandling:

    def test_nan_in_adjustments_sets_to_nan(self, sut, metadata):
        # adjustments has NaN for eng on the overlapping row → result eng is NaN
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [10.0],
        })
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [6.0], "eng": [float("nan")], "det": [0.3],
            "afg": [0.2], "moms": [1.0], "koeb": [8.0],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_substitute_sut(sut, sv)
        row = result.use[
            (result.use["year"] == 2018) & (result.use["nrnr"] == "P1")
        ]
        # eng: NaN in adjustments → set to NaN (true replacement, not treated as 0)
        assert math.isnan(row["eng"].iloc[0])
        # other columns substituted normally
        assert row["koeb"].iloc[0] == pytest.approx(8.0)

    def test_nan_does_not_affect_unmatched_base_rows(self, sut, metadata):
        # adjustments only touches 2018/P1; 2019/P1 in sut is untouched
        values_supply = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["0100"], "brch": ["I1"],
            "bas": [float("nan")],
        })
        values_use = pd.DataFrame({
            "year": [2018], "nrnr": ["P1"], "trans": ["2000"], "brch": ["I1"],
            "bas": [float("nan")], "eng": [float("nan")], "det": [float("nan")],
            "afg": [float("nan")], "moms": [float("nan")], "koeb": [float("nan")],
        })
        sv = SUT(price_basis="current_year", supply=values_supply, use=values_use, metadata=metadata)
        result = adjust_substitute_sut(sut, sv)
        row = result.use[
            (result.use["year"] == 2019) & (result.use["nrnr"] == "P1")
        ]
        assert row["koeb"].iloc[0] == pytest.approx(86.8)


# ---------------------------------------------------------------------------
# Tests for adjust_substitute_sut — balancing targets
# ---------------------------------------------------------------------------

class TestAdjustSubstituteSutBalancingTargets:

    def test_targets_substituted_when_both_have_targets(self, sut, adjustments):
        base_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        values_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [999.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [888.0],
            }),
        )
        sut_with_targets = sut.set_balancing_targets(base_targets)
        sv = SUT(
            price_basis="current_year",
            supply=adjustments.supply,
            use=adjustments.use,
            balancing_targets=values_targets,
        )
        result = adjust_substitute_sut(sut_with_targets, sv)
        supply_row = result.balancing_targets.supply[
            result.balancing_targets.supply["trans"] == "0100"
        ]
        assert supply_row["bas"].iloc[0] == pytest.approx(999.0)
        use_row = result.balancing_targets.use[
            result.balancing_targets.use["trans"] == "2000"
        ]
        assert use_row["koeb"].iloc[0] == pytest.approx(888.0)

    def test_base_targets_preserved_when_adjustments_has_none(self, sut, adjustments):
        base_targets = BalancingTargets(
            supply=pd.DataFrame({
                "year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [200.0],
            }),
            use=pd.DataFrame({
                "year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [100.0],
            }),
        )
        sut_with_targets = sut.set_balancing_targets(base_targets)
        result = adjust_substitute_sut(sut_with_targets, adjustments)
        assert result.balancing_targets is base_targets

    def test_method_delegates_to_free_function(self, sut, adjustments):
        result_method = sut.adjust_substitute_sut(adjustments)
        result_free = adjust_substitute_sut(sut, adjustments)
        pd.testing.assert_frame_equal(
            result_method.supply.reset_index(drop=True),
            result_free.supply.reset_index(drop=True),
        )


# ---------------------------------------------------------------------------
# Tests for adjust_substitute_sut — errors
# ---------------------------------------------------------------------------

class TestAdjustSubstituteSutErrors:

    def test_raises_when_metadata_is_none(self, supply, use, adjustments):
        sut_no_meta = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            adjust_substitute_sut(sut_no_meta, adjustments)

    def test_raises_on_price_basis_mismatch(self, sut, supply_values, use_values, metadata):
        sv = SUT(
            price_basis="previous_year",
            supply=supply_values,
            use=use_values,
            metadata=metadata,
        )
        with pytest.raises(ValueError, match="price_basis"):
            adjust_substitute_sut(sut, sv)
