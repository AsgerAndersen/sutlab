"""
Tests for sutlab.compute.
"""
import pytest
from numpy import nan as NAN

import pandas as pd

from sutlab.compute import compute_price_layer_rates
from sutlab.sut import SUT, SUTColumns, SUTMetadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Use data:
#   Product A, two years.
#   2000 (IC):      bas=20, ava=2,   moms=NaN  — year 2020
#   3110 (HHcons):  bas=40, ava=4,   moms=8    — year 2020
#   6001 (exports): bas=20, ava=NaN, moms=NaN  — year 2020
#   Same transactions in 2021 with different values (bas×1.1, ava+1 each).
#
# Columns: ava → wholesale_margins, moms → vat


@pytest.fixture
def columns():
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
def use_df():
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
def supply_df():
    return pd.DataFrame({
        "year":  [2020,    2021],
        "nrnr":  ["A",     "A"],
        "trans": ["0100",  "0100"],
        "brch":  ["IND",   "IND"],
        "bas":   [100.0,   110.0],
    })


@pytest.fixture
def sut(supply_df, use_df, columns):
    metadata = SUTMetadata(columns=columns)
    return SUT(price_basis="current_year", supply=supply_df, use=use_df, metadata=metadata)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_row(df, **kwargs):
    """Return a single row from df where all given column==value conditions hold."""
    mask = pd.Series(True, index=df.index)
    for col, val in kwargs.items():
        mask = mask & (df[col] == val)
    rows = df[mask]
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)} for {kwargs}"
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Tests: output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:

    def test_product_level_columns(self, sut, columns):
        result = compute_price_layer_rates(sut, "product")
        assert list(result.columns) == ["year", "nrnr", "ava", "moms"]

    def test_transaction_level_columns(self, sut, columns):
        result = compute_price_layer_rates(sut, "transaction")
        assert list(result.columns) == ["year", "nrnr", "trans", "ava", "moms"]

    def test_category_level_columns(self, sut, columns):
        result = compute_price_layer_rates(sut, "category")
        assert list(result.columns) == ["year", "nrnr", "trans", "brch", "ava", "moms"]

    def test_product_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, "product")
        # One row per (product, year): 1 product × 2 years = 2 rows
        assert len(result) == 2

    def test_transaction_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, "transaction")
        # One row per (product, transaction, year): 3 transactions × 2 years = 6 rows
        assert len(result) == 6

    def test_category_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, "category")
        # One row per (product, transaction, category, year): 3 × 2 = 6 rows
        assert len(result) == 6

    def test_id_is_first_column(self, sut):
        for level in ("product", "transaction", "category"):
            result = compute_price_layer_rates(sut, level)
            assert result.columns[0] == "year"

    def test_sorted_by_key_columns(self, sut):
        result = compute_price_layer_rates(sut, "transaction")
        years = result["year"].tolist()
        # Sorted by year first: all 2020 rows before all 2021 rows
        assert years == sorted(years)


# ---------------------------------------------------------------------------
# Tests: product-level rates
# ---------------------------------------------------------------------------

# Year 2020:
#   basic_total = 20 + 40 + 20 = 80
#   ava_total   = 2  + 4       = 6   (6001 has NaN → grouped sum = 0, not included)
#   moms_total  =      8       = 8
#
#   ava  rate = 6 / 80
#   moms denom = basic + ava = 80 + 6 = 86
#   moms rate = 8 / 86
#
# Year 2021:
#   basic_total = 22 + 44 + 22 = 88
#   ava_total   = 3  + 5       = 8
#   moms_total  =      9       = 9
#
#   ava  rate = 8 / 88
#   moms denom = 88 + 8 = 96
#   moms rate = 9 / 96


class TestProductLevelRates:

    def test_ava_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, "product")
        row = _get_row(result, nrnr="A", year=2020)
        assert row["ava"] == pytest.approx(6 / 80)

    def test_moms_rate_2020(self, sut):
        """moms denominator = basic + ava = 86."""
        result = compute_price_layer_rates(sut, "product")
        row = _get_row(result, nrnr="A", year=2020)
        assert row["moms"] == pytest.approx(8 / 86)

    def test_ava_rate_2021(self, sut):
        result = compute_price_layer_rates(sut, "product")
        row = _get_row(result, nrnr="A", year=2021)
        assert row["ava"] == pytest.approx(8 / 88)

    def test_moms_rate_2021(self, sut):
        """moms denominator = basic + ava = 96."""
        result = compute_price_layer_rates(sut, "product")
        row = _get_row(result, nrnr="A", year=2021)
        assert row["moms"] == pytest.approx(9 / 96)


# ---------------------------------------------------------------------------
# Tests: transaction-level rates
# ---------------------------------------------------------------------------

# Year 2020:
#   (A, 2000): basic=20, ava=2,  moms=0(NaN→0)
#     ava  rate = 2/20 = 0.1
#     moms rate = 0/(20+2) = 0
#
#   (A, 3110): basic=40, ava=4,  moms=8
#     ava  rate = 4/40 = 0.1
#     moms denom = 40 + 4 = 44
#     moms rate = 8/44
#
#   (A, 6001): basic=20, ava=0(NaN→0), moms=0(NaN→0)
#     ava  rate = 0/20 = 0
#     moms rate = 0/(20+0) = 0


class TestTransactionLevelRates:

    def test_ic_ava_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, "transaction")
        row = _get_row(result, nrnr="A", trans="2000", year=2020)
        assert row["ava"] == pytest.approx(2 / 20)

    def test_ic_moms_rate_2020(self, sut):
        """IC has no moms — rate should be 0."""
        result = compute_price_layer_rates(sut, "transaction")
        row = _get_row(result, nrnr="A", trans="2000", year=2020)
        assert row["moms"] == pytest.approx(0.0)

    def test_hhcons_ava_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, "transaction")
        row = _get_row(result, nrnr="A", trans="3110", year=2020)
        assert row["ava"] == pytest.approx(4 / 40)

    def test_hhcons_moms_rate_2020(self, sut):
        """HHcons moms denominator = basic + ava = 40 + 4 = 44."""
        result = compute_price_layer_rates(sut, "transaction")
        row = _get_row(result, nrnr="A", trans="3110", year=2020)
        assert row["moms"] == pytest.approx(8 / 44)

    def test_exports_ava_rate_2020(self, sut):
        """Exports have no ava — grouped sum is 0, rate is 0."""
        result = compute_price_layer_rates(sut, "transaction")
        row = _get_row(result, nrnr="A", trans="6001", year=2020)
        assert row["ava"] == pytest.approx(0.0)

    def test_hhcons_moms_rate_2021(self, sut):
        """Year 2021: basic=44, ava=5 → moms denom = 49."""
        result = compute_price_layer_rates(sut, "transaction")
        row = _get_row(result, nrnr="A", trans="3110", year=2021)
        assert row["moms"] == pytest.approx(9 / 49)


# ---------------------------------------------------------------------------
# Tests: category-level rates
# ---------------------------------------------------------------------------

# Each (product, transaction) has exactly one category in this fixture, so
# category-level results equal transaction-level results.


class TestCategoryLevelRates:

    def test_hhcons_ava_rate_category_2020(self, sut):
        result = compute_price_layer_rates(sut, "category")
        row = _get_row(result, nrnr="A", trans="3110", brch="HH", year=2020)
        assert row["ava"] == pytest.approx(4 / 40)

    def test_hhcons_moms_rate_category_2020(self, sut):
        result = compute_price_layer_rates(sut, "category")
        row = _get_row(result, nrnr="A", trans="3110", brch="HH", year=2020)
        assert row["moms"] == pytest.approx(8 / 44)


# ---------------------------------------------------------------------------
# Tests: missing intermediate layers
# ---------------------------------------------------------------------------


class TestMissingIntermediateLayers:

    def test_vat_denom_skips_absent_layers(self, supply_df, columns):
        """If wholesale and retail are absent, vat denominator is just basic."""
        cols_vat_only = SUTColumns(
            id="year",
            product="nrnr",
            transaction="trans",
            category="brch",
            price_basic="bas",
            price_purchasers="koeb",
            vat="moms",
        )
        use_vat_only = pd.DataFrame({
            "year":  [2020],
            "nrnr":  ["A"],
            "trans": ["3110"],
            "brch":  ["HH"],
            "bas":   [40.0],
            "moms":  [8.0],
            "koeb":  [48.0],
        })
        sut_vat_only = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_vat_only,
            metadata=SUTMetadata(columns=cols_vat_only),
        )
        result = compute_price_layer_rates(sut_vat_only, "product")
        row = _get_row(result, nrnr="A", year=2020)
        # vat denom = only price_basic = 40 (wholesale/retail/ptls absent)
        assert row["moms"] == pytest.approx(8 / 40)

    def test_retail_denom_skips_absent_wholesale(self, supply_df):
        """If wholesale is absent, retail denominator is just basic."""
        cols_retail_only = SUTColumns(
            id="year",
            product="nrnr",
            transaction="trans",
            category="brch",
            price_basic="bas",
            price_purchasers="koeb",
            retail_margins="det",
        )
        use_retail_only = pd.DataFrame({
            "year":  [2020],
            "nrnr":  ["A"],
            "trans": ["3110"],
            "brch":  ["HH"],
            "bas":   [40.0],
            "det":   [3.0],
            "koeb":  [43.0],
        })
        sut_retail_only = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_retail_only,
            metadata=SUTMetadata(columns=cols_retail_only),
        )
        result = compute_price_layer_rates(sut_retail_only, "product")
        row = _get_row(result, nrnr="A", year=2020)
        assert row["det"] == pytest.approx(3 / 40)


# ---------------------------------------------------------------------------
# Tests: division by zero
# ---------------------------------------------------------------------------


class TestDivisionByZero:

    def test_zero_basic_price_gives_nan(self, supply_df, columns):
        use_zero_basic = pd.DataFrame({
            "year":  [2020],
            "nrnr":  ["A"],
            "trans": ["3110"],
            "brch":  ["HH"],
            "bas":   [0.0],
            "ava":   [4.0],
            "moms":  [NAN],
            "koeb":  [4.0],
        })
        sut_zero = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_zero_basic,
            metadata=SUTMetadata(columns=columns),
        )
        result = compute_price_layer_rates(sut_zero, "product")
        import math
        assert math.isnan(result.iloc[0]["ava"])


# ---------------------------------------------------------------------------
# Tests: empty result
# ---------------------------------------------------------------------------


class TestEmptyResult:

    def test_no_layer_columns_returns_empty(self, supply_df):
        cols_no_layers = SUTColumns(
            id="year",
            product="nrnr",
            transaction="trans",
            category="brch",
            price_basic="bas",
            price_purchasers="koeb",
        )
        use_no_layers = pd.DataFrame({
            "year":  [2020],
            "nrnr":  ["A"],
            "trans": ["3110"],
            "brch":  ["HH"],
            "bas":   [40.0],
            "koeb":  [40.0],
        })
        sut_no_layers = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_no_layers,
            metadata=SUTMetadata(columns=cols_no_layers),
        )
        result = compute_price_layer_rates(sut_no_layers, "product")
        assert result.empty

    def test_layer_mapped_but_not_in_use_columns_returns_empty(self, supply_df, columns):
        """ava and moms are mapped in SUTColumns but absent from use DataFrame."""
        use_no_layer_cols = pd.DataFrame({
            "year":  [2020],
            "nrnr":  ["A"],
            "trans": ["3110"],
            "brch":  ["HH"],
            "bas":   [40.0],
            "koeb":  [40.0],
        })
        sut_missing_cols = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_no_layer_cols,
            metadata=SUTMetadata(columns=columns),
        )
        result = compute_price_layer_rates(sut_missing_cols, "product")
        assert result.empty


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestErrors:

    def test_no_metadata_raises(self, use_df, supply_df):
        sut_no_meta = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
        )
        with pytest.raises(ValueError, match="sut.metadata is required"):
            compute_price_layer_rates(sut_no_meta, "product")

    def test_bad_aggregation_level_raises(self, sut):
        with pytest.raises(ValueError, match="aggregation_level must be"):
            compute_price_layer_rates(sut, "industry")

    def test_unmapped_layer_role_raises(self, supply_df, use_df):
        """trade_margins is mapped and present — no default denominator → error."""
        cols_with_trade = SUTColumns(
            id="year",
            product="nrnr",
            transaction="trans",
            category="brch",
            price_basic="bas",
            price_purchasers="koeb",
            trade_margins="ava",
        )
        sut_trade = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            metadata=SUTMetadata(columns=cols_with_trade),
        )
        with pytest.raises(ValueError, match="trade_margins"):
            compute_price_layer_rates(sut_trade, "product")

    def test_error_message_names_available_defaults(self, supply_df, use_df):
        cols_with_trade = SUTColumns(
            id="year",
            product="nrnr",
            transaction="trans",
            category="brch",
            price_basic="bas",
            price_purchasers="koeb",
            trade_margins="ava",
        )
        sut_trade = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
            metadata=SUTMetadata(columns=cols_with_trade),
        )
        with pytest.raises(ValueError, match="wholesale_margins"):
            compute_price_layer_rates(sut_trade, "product")
