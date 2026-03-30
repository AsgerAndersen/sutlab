"""
Tests for price_layers_detailed, price_layers_detailed_distribution,
price_layers_detailed_growth, and price_layers_detailed_rates tables
returned by inspect_products.
"""
import math

import pytest
from numpy import nan as NAN
from pandas.io.formats.style import Styler

import pandas as pd

from sutlab.inspect import inspect_products
from sutlab.sut import SUT, SUTColumns, SUTMetadata, SUTClassifications


# ---------------------------------------------------------------------------
# Fixtures (mirror sut_with_layers from test_inspect.py)
# ---------------------------------------------------------------------------

# Use data for product A over two years:
#   2000 (IC):     bas=20, ava=2,  moms=NaN, cat=X   → 2020
#   3110 (HHcons): bas=40, ava=4,  moms=8,   cat=HH  → 2020
#   6001 (exports):bas=20, ava=NaN,moms=NaN, cat=""  → excluded (NaN layer)
#
# price_layers_detailed "ava" block (2020):
#   (2000, X)  → ava = 2
#   (3110, HH) → ava = 4
#   Total      → ava = 6  (same as price_layers Total)
#
# price_layers_detailed "moms" block (2020):
#   (3110, HH) → moms = 8
#   Total      → moms = 8


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
    return pd.DataFrame({
        "trans":     ["0100",   "2000", "3110",   "6001"],
        "trans_txt": ["Output", "IC",   "HHcons", "Exports"],
        "table":     ["supply", "use",  "use",    "use"],
        "esa_code":  ["P1",     "P2",   "P31",    "P6"],
    })


@pytest.fixture
def supply_with_layers():
    return pd.DataFrame({
        "year":  [2020,   2021],
        "nrnr":  ["A",    "A"],
        "trans": ["0100", "0100"],
        "brch":  ["X",    "X"],
        "bas":   [100.0,  110.0],
        "ava":   [NAN,    NAN],
        "moms":  [NAN,    NAN],
        "koeb":  [100.0,  110.0],
    })


@pytest.fixture
def use_with_layers():
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
def sut_with_layers(supply_with_layers, use_with_layers,
                    columns_with_layers, transactions_with_layers):
    classifications = SUTClassifications(transactions=transactions_with_layers)
    metadata = SUTMetadata(
        columns=columns_with_layers, classifications=classifications
    )
    return SUT(
        price_basis="current_year",
        supply=supply_with_layers,
        use=use_with_layers,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block(df, layer):
    return df[df.index.get_level_values("price_layer") == layer]


def _trans_cat_row(block_df, trans, cat):
    return block_df[
        (block_df.index.get_level_values("transaction") == trans) &
        (block_df.index.get_level_values("category") == cat)
    ]


# ---------------------------------------------------------------------------
# Tests: price_layers_detailed — structure
# ---------------------------------------------------------------------------


class TestPriceLayersDetailedStructure:

    def test_index_names(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert result.data.price_layers_detailed.index.names == [
            "product", "product_txt", "price_layer",
            "transaction", "transaction_txt",
            "category", "category_txt",
        ]

    def test_columns_are_ids(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert list(result.data.price_layers_detailed.columns) == [2020, 2021]

    def test_one_total_row_per_layer_block(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers_detailed
        product_vals = df.index.get_level_values("product")
        layer_vals = df.index.get_level_values("price_layer")
        trans_vals = df.index.get_level_values("transaction")
        for product in df.index.get_level_values("product").unique():
            for layer in (
                df[product_vals == product]
                .index.get_level_values("price_layer").unique()
            ):
                block_mask = (product_vals == product) & (layer_vals == layer)
                n_total = (trans_vals[block_mask] == "").sum()
                assert n_total == 1

    def test_total_row_is_last_in_block(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        df = result.data.price_layers_detailed
        layer_vals = df.index.get_level_values("price_layer")
        trans_vals = df.index.get_level_values("transaction")
        for layer in df.index.get_level_values("price_layer").unique():
            positions = [i for i, v in enumerate(layer_vals) if v == layer]
            assert trans_vals[positions[-1]] == ""

    def test_exports_excluded_no_ava(self, sut_with_layers):
        """Exports (6001) have NaN ava — should not appear in ava block."""
        result = inspect_products(sut_with_layers, "A")
        ava = _block(result.data.price_layers_detailed, "ava")
        assert "6001" not in ava.index.get_level_values("transaction").tolist()

    def test_empty_when_no_layers(self, sut_with_layers):
        """SUT with no price layer columns → empty detailed table."""
        cols_no_layers = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
        )
        import dataclasses
        sut_no_layers = dataclasses.replace(
            sut_with_layers,
            metadata=dataclasses.replace(
                sut_with_layers.metadata,
                columns=cols_no_layers,
            ),
        )
        result = inspect_products(sut_no_layers, "A")
        assert result.data.price_layers_detailed.empty


# ---------------------------------------------------------------------------
# Tests: price_layers_detailed — values
# ---------------------------------------------------------------------------


class TestPriceLayersDetailedValues:

    def test_ava_ic_category_x_2020(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(_block(result.data.price_layers_detailed, "ava"), "2000", "X")
        assert row[2020].item() == pytest.approx(2.0)

    def test_ava_hhcons_category_hh_2020(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(_block(result.data.price_layers_detailed, "ava"), "3110", "HH")
        assert row[2020].item() == pytest.approx(4.0)

    def test_ava_total_matches_price_layers_total(self, sut_with_layers):
        """Detailed Total = undetailed Total for the same (product, layer)."""
        result = inspect_products(sut_with_layers, "A")
        ava_det = _block(result.data.price_layers_detailed, "ava")
        det_total = (
            ava_det[ava_det.index.get_level_values("transaction") == ""][2020].item()
        )
        ava_pl = _block(result.data.price_layers, "ava")
        pl_total = (
            ava_pl[ava_pl.index.get_level_values("transaction_txt") == "Total"][2020].item()
        )
        assert det_total == pytest.approx(pl_total)

    def test_moms_hhcons_category_hh_2020(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(_block(result.data.price_layers_detailed, "moms"), "3110", "HH")
        assert row[2020].item() == pytest.approx(8.0)

    def test_ava_ic_category_x_2021(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(_block(result.data.price_layers_detailed, "ava"), "2000", "X")
        assert row[2021].item() == pytest.approx(3.0)

    def test_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_detailed, Styler)


# ---------------------------------------------------------------------------
# Tests: price_layers_detailed_distribution
# ---------------------------------------------------------------------------


class TestPriceLayersDetailedDistribution:

    def test_total_row_is_one(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        ava = _block(result.data.price_layers_detailed_distribution, "ava")
        total = ava[ava.index.get_level_values("transaction") == ""]
        assert total[2020].item() == pytest.approx(1.0)

    def test_ic_ava_share_2020(self, sut_with_layers):
        """IC/X ava=2, Total ava=6 → share = 2/6."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_distribution, "ava"), "2000", "X"
        )
        assert row[2020].item() == pytest.approx(2 / 6)

    def test_hhcons_ava_share_2020(self, sut_with_layers):
        """HHcons/HH ava=4, Total ava=6 → share = 4/6."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_distribution, "ava"), "3110", "HH"
        )
        assert row[2020].item() == pytest.approx(4 / 6)

    def test_shares_sum_to_one(self, sut_with_layers):
        """Non-total rows in a block should sum to 1.0 per year."""
        result = inspect_products(sut_with_layers, "A")
        ava = _block(result.data.price_layers_detailed_distribution, "ava")
        non_total = ava[ava.index.get_level_values("transaction") != ""]
        assert non_total[2020].sum() == pytest.approx(1.0)

    def test_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_detailed_distribution, Styler)


# ---------------------------------------------------------------------------
# Tests: price_layers_detailed_growth
# ---------------------------------------------------------------------------


class TestPriceLayersDetailedGrowth:

    def test_first_year_is_nan(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_growth, "ava"), "2000", "X"
        )
        assert math.isnan(row[2020].item())

    def test_hhcons_ava_growth_2021(self, sut_with_layers):
        """HHcons/HH ava: 4 in 2020, 5 in 2021 → growth = (5-4)/4 = 0.25."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_growth, "ava"), "3110", "HH"
        )
        assert row[2021].item() == pytest.approx(0.25)

    def test_hhcons_moms_growth_2021(self, sut_with_layers):
        """HHcons/HH moms: 8 in 2020, 9 in 2021 → growth = (9-8)/8 = 0.125."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_growth, "moms"), "3110", "HH"
        )
        assert row[2021].item() == pytest.approx(1 / 8)

    def test_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_detailed_growth, Styler)


# ---------------------------------------------------------------------------
# Tests: price_layers_detailed_rates
# ---------------------------------------------------------------------------


class TestPriceLayersDetailedRates:

    def test_no_total_rows(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        trans_vals = (
            result.data.price_layers_detailed_rates
            .index.get_level_values("transaction")
        )
        assert "" not in trans_vals

    def test_index_names(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert result.data.price_layers_detailed_rates.index.names == [
            "product", "product_txt", "price_layer",
            "transaction", "transaction_txt",
            "category", "category_txt",
        ]

    def test_ic_ava_rate_2020(self, sut_with_layers):
        """IC/X ava=2, basic=20 → rate = 2/20."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_rates, "ava"), "2000", "X"
        )
        assert row[2020].item() == pytest.approx(2 / 20)

    def test_hhcons_ava_rate_2020(self, sut_with_layers):
        """HHcons/HH ava=4, basic=40 → rate = 4/40."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_rates, "ava"), "3110", "HH"
        )
        assert row[2020].item() == pytest.approx(4 / 40)

    def test_hhcons_moms_rate_2020(self, sut_with_layers):
        """HHcons/HH moms=8, denom=basic+ava=40+4=44 → rate = 8/44."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_rates, "moms"), "3110", "HH"
        )
        assert row[2020].item() == pytest.approx(8 / 44)

    def test_hhcons_moms_rate_2021(self, sut_with_layers):
        """HHcons/HH 2021: moms=9, denom=basic+ava=44+5=49 → rate = 9/49."""
        result = inspect_products(sut_with_layers, "A")
        row = _trans_cat_row(
            _block(result.data.price_layers_detailed_rates, "moms"), "3110", "HH"
        )
        assert row[2021].item() == pytest.approx(9 / 49)

    def test_returns_styler(self, sut_with_layers):
        result = inspect_products(sut_with_layers, "A")
        assert isinstance(result.price_layers_detailed_rates, Styler)

    def test_empty_when_no_layers(self, sut_with_layers):
        cols_no_layers = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
        )
        import dataclasses
        sut_no_layers = dataclasses.replace(
            sut_with_layers,
            metadata=dataclasses.replace(
                sut_with_layers.metadata,
                columns=cols_no_layers,
            ),
        )
        result = inspect_products(sut_no_layers, "A")
        assert result.data.price_layers_detailed_rates.empty
