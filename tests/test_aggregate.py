"""
Tests for sutlab/aggregate/ — aggregate_classification_products.
"""

import math

import pytest
import pandas as pd

from sutlab.aggregate import aggregate_classification_products
from sutlab.sut import (
    BalancingConfig,
    BalancingTargets,
    Locks,
    SUT,
    SUTClassifications,
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
    # 2 years × 3 products × 1 supply transaction × 1 category = 6 rows
    return pd.DataFrame({
        "year":  [2018, 2018, 2018, 2019, 2019, 2019],
        "nrnr":  ["P1", "P2", "P3", "P1", "P2", "P3"],
        "trans": ["0100"] * 6,
        "brch":  ["I1"] * 6,
        "bas":   [100.0, 200.0, 300.0, 110.0, 210.0, 310.0],
    })


@pytest.fixture
def use():
    # 2 years × 3 products × 1 use transaction × 1 category = 6 rows
    return pd.DataFrame({
        "year":  [2018, 2018, 2018, 2019, 2019, 2019],
        "nrnr":  ["P1", "P2", "P3", "P1", "P2", "P3"],
        "trans": ["2000"] * 6,
        "brch":  ["I1"] * 6,
        "bas":   [60.0, 120.0, 180.0, 66.0, 132.0, 198.0],
        "eng":   [5.0, 10.0, 15.0, 5.5, 11.0, 16.5],
        "det":   [3.0, 6.0, 9.0, 3.3, 6.6, 9.9],
        "afg":   [2.0, 4.0, 6.0, 2.2, 4.4, 6.6],
        "moms":  [10.0, 20.0, 30.0, 11.0, 22.0, 33.0],
        "koeb":  [80.0, 160.0, 240.0, 88.0, 176.0, 264.0],
    })


@pytest.fixture
def sut(supply, use, metadata):
    return SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)


@pytest.fixture
def full_mapping():
    # P1 + P2 → AGG (many-to-one), P3 → B (one-to-one rename)
    return pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})


@pytest.fixture
def partial_mapping():
    # Only P1 + P2 → AGG; P3 is unmapped (pass-through)
    return pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})


# ---------------------------------------------------------------------------
# Supply aggregation
# ---------------------------------------------------------------------------

class TestAggregateSupply:

    def test_many_to_one_values_are_summed(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        agg_row = result.supply[
            (result.supply["year"] == 2018) & (result.supply["nrnr"] == "AGG")
        ]
        # P1(100) + P2(200) → AGG(300)
        assert agg_row["bas"].iloc[0] == pytest.approx(300.0)

    def test_one_to_one_value_unchanged(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        b_row = result.supply[
            (result.supply["year"] == 2018) & (result.supply["nrnr"] == "B")
        ]
        assert b_row["bas"].iloc[0] == pytest.approx(300.0)

    def test_original_codes_absent_from_result(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        assert "P1" not in result.supply["nrnr"].values
        assert "P2" not in result.supply["nrnr"].values
        assert "P3" not in result.supply["nrnr"].values

    def test_result_row_count(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        # 2 years × 2 new codes (AGG, B) = 4 rows
        assert len(result.supply) == 4

    def test_result_is_sorted(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        # sort key is (year, nrnr, trans, brch) — year is primary
        expected_years = [2018, 2018, 2019, 2019]
        expected_codes = ["AGG", "B", "AGG", "B"]
        assert result.supply["year"].tolist() == expected_years
        assert result.supply["nrnr"].tolist() == expected_codes

    def test_unmapped_code_passes_through(self, sut, partial_mapping):
        result = aggregate_classification_products(
            sut, partial_mapping, full_coverage=False
        )
        p3_rows = result.supply[result.supply["nrnr"] == "P3"]
        assert len(p3_rows) == 2
        assert p3_rows["bas"].tolist() == pytest.approx([300.0, 310.0])

    def test_full_coverage_false_has_correct_row_count(self, sut, partial_mapping):
        result = aggregate_classification_products(
            sut, partial_mapping, full_coverage=False
        )
        # 2 years × 2 codes (AGG, P3) = 4 rows
        assert len(result.supply) == 4


# ---------------------------------------------------------------------------
# Use aggregation
# ---------------------------------------------------------------------------

class TestAggregateUse:

    def test_all_price_columns_summed(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        agg_row = result.use[
            (result.use["year"] == 2018) & (result.use["nrnr"] == "AGG")
        ]
        assert agg_row["bas"].iloc[0] == pytest.approx(180.0)   # 60+120
        assert agg_row["eng"].iloc[0] == pytest.approx(15.0)    # 5+10
        assert agg_row["det"].iloc[0] == pytest.approx(9.0)     # 3+6
        assert agg_row["afg"].iloc[0] == pytest.approx(6.0)     # 2+4
        assert agg_row["moms"].iloc[0] == pytest.approx(30.0)   # 10+20
        assert agg_row["koeb"].iloc[0] == pytest.approx(240.0)  # 80+160

    def test_nan_plus_nan_stays_nan(self, columns, metadata):
        supply = pd.DataFrame({
            "year": [2018, 2018], "nrnr": ["P1", "P2"],
            "trans": ["0100", "0100"], "brch": ["I1", "I1"],
            "bas": [100.0, 200.0],
        })
        use = pd.DataFrame({
            "year": [2018, 2018], "nrnr": ["P1", "P2"],
            "trans": ["2000", "2000"], "brch": ["I1", "I1"],
            "bas": [float("nan"), float("nan")],
            "koeb": [80.0, 160.0],
        })
        s = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
        mapping = pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})
        result = aggregate_classification_products(s, mapping)
        agg_row = result.use[result.use["nrnr"] == "AGG"]
        assert math.isnan(agg_row["bas"].iloc[0])
        assert agg_row["koeb"].iloc[0] == pytest.approx(240.0)

    def test_nan_plus_value_gives_value(self, columns, metadata):
        supply = pd.DataFrame({
            "year": [2018, 2018], "nrnr": ["P1", "P2"],
            "trans": ["0100", "0100"], "brch": ["I1", "I1"],
            "bas": [100.0, 200.0],
        })
        use = pd.DataFrame({
            "year": [2018, 2018], "nrnr": ["P1", "P2"],
            "trans": ["2000", "2000"], "brch": ["I1", "I1"],
            "bas": [float("nan"), 120.0],
            "koeb": [80.0, 160.0],
        })
        s = SUT(price_basis="current_year", supply=supply, use=use, metadata=metadata)
        mapping = pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})
        result = aggregate_classification_products(s, mapping)
        agg_row = result.use[result.use["nrnr"] == "AGG"]
        assert agg_row["bas"].iloc[0] == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# Products classification handling
# ---------------------------------------------------------------------------

class TestProductsClassification:

    def test_metadata_replaces_classification(self, sut, full_mapping, columns):
        new_cls = pd.DataFrame({
            "nrnr": ["AGG", "B"],
            "nrnr_txt": ["Aggregated", "B product"],
        })
        result = aggregate_classification_products(sut, full_mapping, metadata=new_cls)
        assert result.metadata.classifications.products is new_cls

    def test_no_metadata_sets_classification_to_none(self, sut, full_mapping, columns):
        cls_with_products = SUTClassifications(
            products=pd.DataFrame({"nrnr": ["P1", "P2", "P3"], "nrnr_txt": ["a", "b", "c"]})
        )
        sut_with_cls = SUT(
            price_basis="current_year",
            supply=sut.supply,
            use=sut.use,
            metadata=SUT(price_basis="current_year", supply=sut.supply, use=sut.use,
                         metadata=SUTMetadata(columns=sut.metadata.columns,
                                              classifications=cls_with_products)).metadata,
        )
        result = aggregate_classification_products(sut_with_cls, full_mapping)
        assert result.metadata.classifications.products is None

    def test_metadata_merged_with_unmapped_for_partial(self, supply, use, columns):
        cls = SUTClassifications(
            products=pd.DataFrame({
                "nrnr": ["P1", "P2", "P3"],
                "nrnr_txt": ["Product 1", "Product 2", "Product 3"],
            })
        )
        s = SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=cls),
        )
        mapping = pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})
        new_meta = pd.DataFrame({"nrnr": ["AGG"], "nrnr_txt": ["Aggregated"]})
        result = aggregate_classification_products(
            s, mapping, metadata=new_meta, full_coverage=False
        )
        products_cls = result.metadata.classifications.products
        assert set(products_cls["nrnr"].tolist()) == {"AGG", "P3"}
        p3_row = products_cls[products_cls["nrnr"] == "P3"]
        assert p3_row["nrnr_txt"].iloc[0] == "Product 3"
        agg_row = products_cls[products_cls["nrnr"] == "AGG"]
        assert agg_row["nrnr_txt"].iloc[0] == "Aggregated"

    def test_classification_name_is_updated(self, supply, use, columns):
        cls = SUTClassifications(
            classification_names=pd.DataFrame({
                "dimension": ["nrnr", "trans"],
                "classification": ["NRNR07", "ESA2010"],
            })
        )
        s = SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=cls),
        )
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        result = aggregate_classification_products(s, mapping, classification_name="AGG2")
        cls_names = result.metadata.classifications.classification_names
        nrnr_row = cls_names[cls_names["dimension"] == "nrnr"]
        assert nrnr_row["classification"].iloc[0] == "AGG2"
        # other dimensions unchanged
        trans_row = cls_names[cls_names["dimension"] == "trans"]
        assert trans_row["classification"].iloc[0] == "ESA2010"

    def test_classification_name_none_sets_nan(self, supply, use, columns):
        cls = SUTClassifications(
            classification_names=pd.DataFrame({
                "dimension": ["nrnr"],
                "classification": ["NRNR07"],
            })
        )
        s = SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=cls),
        )
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        result = aggregate_classification_products(s, mapping, classification_name=None)
        cls_names = result.metadata.classifications.classification_names
        nrnr_row = cls_names[cls_names["dimension"] == "nrnr"]
        assert pd.isna(nrnr_row["classification"].iloc[0])

    def test_classification_name_ignored_when_no_dimension_row(self, supply, use, columns):
        cls = SUTClassifications(
            classification_names=pd.DataFrame({
                "dimension": ["trans"],
                "classification": ["ESA2010"],
            })
        )
        s = SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=cls),
        )
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        result = aggregate_classification_products(s, mapping, classification_name="NEW")
        cls_names = result.metadata.classifications.classification_names
        # trans row unchanged, no nrnr row
        assert list(cls_names["dimension"]) == ["trans"]


# ---------------------------------------------------------------------------
# Balancing state
# ---------------------------------------------------------------------------

class TestBalancingState:

    def test_balancing_targets_cleared(self, sut, full_mapping):
        targets = BalancingTargets(
            supply=pd.DataFrame({"year": [2018], "trans": ["0100"], "brch": ["I1"], "bas": [500.0]}),
            use=pd.DataFrame({"year": [2018], "trans": ["2000"], "brch": ["I1"], "koeb": [400.0]}),
        )
        s = sut.set_balancing_targets(targets)
        result = aggregate_classification_products(s, full_mapping)
        assert result.balancing_targets is None

    def test_balancing_config_cleared(self, sut, full_mapping):
        config = BalancingConfig()
        s = sut.set_balancing_config(config)
        result = aggregate_classification_products(s, full_mapping)
        assert result.balancing_config is None

    def test_balancing_id_preserved(self, sut, full_mapping):
        s = sut.set_balancing_id(2019)
        result = aggregate_classification_products(s, full_mapping)
        assert result.balancing_id == 2019

    def test_price_basis_preserved(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        assert result.price_basis == "current_year"

    def test_does_not_mutate_original(self, sut, full_mapping):
        original_shape = sut.supply.shape
        aggregate_classification_products(sut, full_mapping)
        assert sut.supply.shape == original_shape


# ---------------------------------------------------------------------------
# Margin products
# ---------------------------------------------------------------------------

class TestMarginProducts:

    def _make_sut_with_margins(self, supply, use, columns, margin_products):
        cls = SUTClassifications(
            products=pd.DataFrame({"nrnr": ["P1", "P2", "P3"], "nrnr_txt": ["a", "b", "c"]}),
            margin_products=margin_products,
        )
        return SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=cls),
        )

    def test_margin_product_remapped(self, supply, use, columns):
        margin_products = pd.DataFrame({
            "nrnr": ["P1", "P2"],
            "price_layer": ["eng", "eng"],
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        result = aggregate_classification_products(s, mapping)
        mp = result.metadata.classifications.margin_products
        assert mp is not None
        assert set(mp["nrnr"].tolist()) == {"AGG"}
        assert mp[mp["nrnr"] == "AGG"]["price_layer"].iloc[0] == "eng"

    def test_passthrough_margin_product_preserved(self, supply, use, columns):
        # P3 is a margin product and is not in the mapping (pass-through)
        margin_products = pd.DataFrame({
            "nrnr": ["P3"],
            "price_layer": ["det"],
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        mapping = pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})
        result = aggregate_classification_products(
            s, mapping, full_coverage=False
        )
        mp = result.metadata.classifications.margin_products
        assert mp is not None
        assert set(mp["nrnr"].tolist()) == {"P3"}

    def test_margin_products_none_stays_none(self, sut, full_mapping):
        result = aggregate_classification_products(sut, full_mapping)
        assert result.metadata is not None
        # metadata has no classifications; margin_products can't exist
        assert result.metadata.classifications is None

    def test_txt_column_preserved_for_passthrough(self, supply, use, columns):
        margin_products = pd.DataFrame({
            "nrnr": ["P3"],
            "nrnr_txt": ["Margin P3"],
            "price_layer": ["det"],
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        mapping = pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})
        result = aggregate_classification_products(
            s, mapping, full_coverage=False
        )
        mp = result.metadata.classifications.margin_products
        p3_row = mp[mp["nrnr"] == "P3"]
        assert p3_row["nrnr_txt"].iloc[0] == "Margin P3"

    def test_txt_set_to_none_for_aggregated(self, supply, use, columns):
        margin_products = pd.DataFrame({
            "nrnr": ["P1", "P2"],
            "nrnr_txt": ["Margin P1", "Margin P2"],
            "price_layer": ["eng", "eng"],
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        result = aggregate_classification_products(s, mapping)
        mp = result.metadata.classifications.margin_products
        agg_row = mp[mp["nrnr"] == "AGG"]
        assert pd.isna(agg_row["nrnr_txt"].iloc[0])

    def test_raises_on_mixed_margin_non_margin(self, supply, use, columns):
        margin_products = pd.DataFrame({
            "nrnr": ["P1"],
            "price_layer": ["eng"],
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        # P1 is a margin product, P2 is not — both aggregate into AGG
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        with pytest.raises(ValueError, match="margin products"):
            aggregate_classification_products(s, mapping)

    def test_raises_on_inconsistent_price_layers(self, supply, use, columns):
        margin_products = pd.DataFrame({
            "nrnr": ["P1", "P2"],
            "price_layer": ["eng", "det"],  # different layers
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        with pytest.raises(ValueError, match="price layers"):
            aggregate_classification_products(s, mapping)

    def test_all_margin_products_mapped_result_is_none(self, supply, use, columns):
        # All margin products are mapped, and the result has no pass-throughs
        margin_products = pd.DataFrame({
            "nrnr": ["P1"],
            "price_layer": ["eng"],
        })
        s = self._make_sut_with_margins(supply, use, columns, margin_products)
        # P1 is a margin product; P2 and P3 are not; P1 maps alone to AGG1
        mapping = pd.DataFrame(
            {"from": ["P1", "P2", "P3"], "to": ["AGG1", "AGG2", "AGG3"]}
        )
        result = aggregate_classification_products(s, mapping)
        mp = result.metadata.classifications.margin_products
        assert mp is not None
        assert set(mp["nrnr"].tolist()) == {"AGG1"}


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestValidationErrors:

    def test_raises_when_sut_metadata_is_none(self, supply, use, full_mapping):
        s = SUT(price_basis="current_year", supply=supply, use=use)
        with pytest.raises(ValueError, match="metadata"):
            aggregate_classification_products(s, full_mapping)

    def test_raises_when_mapping_not_dataframe(self, sut):
        with pytest.raises(TypeError, match="mapping must be a DataFrame"):
            aggregate_classification_products(sut, {"from": ["P1"], "to": ["A"]})

    def test_raises_on_missing_from_column(self, sut):
        bad = pd.DataFrame({"FROM": ["P1"], "to": ["A"]})
        with pytest.raises(ValueError, match="'from'"):
            aggregate_classification_products(sut, bad)

    def test_raises_on_missing_to_column(self, sut):
        bad = pd.DataFrame({"from": ["P1"], "TO": ["A"]})
        with pytest.raises(ValueError, match="'to'"):
            aggregate_classification_products(sut, bad)

    def test_raises_on_nan_in_from(self, sut):
        bad = pd.DataFrame({"from": ["P1", float("nan")], "to": ["A", "B"]})
        with pytest.raises(ValueError, match=r"mapping\['from'\].*NaN"):
            aggregate_classification_products(sut, bad)

    def test_raises_on_nan_in_to(self, sut):
        bad = pd.DataFrame({"from": ["P1", "P2"], "to": ["A", float("nan")]})
        with pytest.raises(ValueError, match=r"mapping\['to'\].*NaN"):
            aggregate_classification_products(sut, bad)

    def test_raises_on_duplicate_from(self, sut):
        bad = pd.DataFrame({"from": ["P1", "P1", "P2", "P3"], "to": ["A", "A", "A", "B"]})
        with pytest.raises(ValueError, match="duplicate"):
            aggregate_classification_products(sut, bad)

    def test_raises_on_missing_coverage(self, sut):
        # P3 not covered
        incomplete = pd.DataFrame({"from": ["P1", "P2"], "to": ["AGG", "AGG"]})
        with pytest.raises(ValueError, match="full_coverage"):
            aggregate_classification_products(sut, incomplete, full_coverage=True)

    def test_raises_when_from_code_not_in_classification(self, supply, use, columns):
        cls = SUTClassifications(
            products=pd.DataFrame({"nrnr": ["P1", "P2"], "nrnr_txt": ["a", "b"]})
            # P3 is absent from the classification
        )
        s = SUT(
            price_basis="current_year",
            supply=supply,
            use=use,
            metadata=SUTMetadata(columns=columns, classifications=cls),
        )
        mapping = pd.DataFrame({"from": ["P1", "P2", "P3"], "to": ["AGG", "AGG", "B"]})
        with pytest.raises(ValueError, match="products classification"):
            aggregate_classification_products(s, mapping)

    def test_raises_on_metadata_missing_product_column(self, sut, full_mapping):
        bad_meta = pd.DataFrame({"wrong_col": ["AGG", "B"]})
        with pytest.raises(ValueError, match="'nrnr'"):
            aggregate_classification_products(sut, full_mapping, metadata=bad_meta)

    def test_raises_on_metadata_unexpected_column(self, sut, full_mapping):
        bad_meta = pd.DataFrame({"nrnr": ["AGG", "B"], "extra": [1, 2]})
        with pytest.raises(ValueError, match="unexpected columns"):
            aggregate_classification_products(sut, full_mapping, metadata=bad_meta)

    def test_raises_on_passthrough_collision(self, sut):
        # P3 is unmapped (pass-through), but "P3" is also a "to" value
        bad_mapping = pd.DataFrame(
            {"from": ["P1", "P2"], "to": ["P3", "P3"]}  # "to" = P3 which is a pass-through
        )
        with pytest.raises(ValueError, match="pass-through"):
            aggregate_classification_products(sut, bad_mapping, full_coverage=False)

    def test_from_codes_absent_from_data_are_allowed(self, sut):
        # P4 is in "from" but not in the data — should not raise
        extended = pd.DataFrame(
            {"from": ["P1", "P2", "P3", "P4"], "to": ["AGG", "AGG", "B", "B"]}
        )
        result = aggregate_classification_products(sut, extended)
        assert len(result.supply) == 4  # 2 years × 2 codes


# ---------------------------------------------------------------------------
# Method delegation
# ---------------------------------------------------------------------------

class TestMethodDelegation:

    def test_method_delegates_to_free_function(self, sut, full_mapping):
        result_method = sut.aggregate_classification_products(full_mapping)
        result_free = aggregate_classification_products(sut, full_mapping)
        pd.testing.assert_frame_equal(
            result_method.supply.reset_index(drop=True),
            result_free.supply.reset_index(drop=True),
        )
        pd.testing.assert_frame_equal(
            result_method.use.reset_index(drop=True),
            result_free.use.reset_index(drop=True),
        )
