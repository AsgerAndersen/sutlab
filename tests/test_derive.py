"""
Tests for sutlab.derive.
"""
import pytest
from numpy import nan as NAN

import pandas as pd

from sutlab.derive import compute_price_layer_rates, compute_totals
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

    def test_product_transaction_level_columns(self, sut, columns):
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        assert list(result.columns) == ["year", "nrnr", "trans", "ava", "moms"]

    def test_product_transaction_category_level_columns(self, sut, columns):
        result = compute_price_layer_rates(sut, ["product", "transaction", "category"])
        assert list(result.columns) == ["year", "nrnr", "trans", "brch", "ava", "moms"]

    def test_transaction_category_level_columns(self, sut, columns):
        """Industry-style aggregation: no product dimension."""
        result = compute_price_layer_rates(sut, ["transaction", "category"])
        assert list(result.columns) == ["year", "trans", "brch", "ava", "moms"]

    def test_product_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, "product")
        # One row per (id, product): 1 product × 2 years = 2 rows
        assert len(result) == 2

    def test_product_transaction_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        # One row per (id, product, transaction): 3 transactions × 2 years = 6 rows
        assert len(result) == 6

    def test_product_transaction_category_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction", "category"])
        # One row per (id, product, transaction, category): 3 × 2 = 6 rows
        assert len(result) == 6

    def test_transaction_category_level_row_count(self, sut):
        result = compute_price_layer_rates(sut, ["transaction", "category"])
        # One row per (id, transaction, category): 3 × 2 = 6 rows
        assert len(result) == 6

    def test_id_is_first_column(self, sut):
        for level in ("product", ["product", "transaction"], ["product", "transaction", "category"]):
            result = compute_price_layer_rates(sut, level)
            assert result.columns[0] == "year"

    def test_sorted_by_key_columns(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        years = result["year"].tolist()
        # Sorted by year first: all 2020 rows before all 2021 rows
        assert years == sorted(years)

    def test_string_shorthand_equals_single_element_list(self, sut):
        """'product' and ['product'] must produce identical results."""
        result_str = compute_price_layer_rates(sut, "product")
        result_list = compute_price_layer_rates(sut, ["product"])
        pd.testing.assert_frame_equal(result_str, result_list)


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
# Tests: product × transaction level rates
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


class TestProductTransactionLevelRates:

    def test_ic_ava_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        row = _get_row(result, nrnr="A", trans="2000", year=2020)
        assert row["ava"] == pytest.approx(2 / 20)

    def test_ic_moms_rate_2020(self, sut):
        """IC has no moms — rate should be 0."""
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        row = _get_row(result, nrnr="A", trans="2000", year=2020)
        assert row["moms"] == pytest.approx(0.0)

    def test_hhcons_ava_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        row = _get_row(result, nrnr="A", trans="3110", year=2020)
        assert row["ava"] == pytest.approx(4 / 40)

    def test_hhcons_moms_rate_2020(self, sut):
        """HHcons moms denominator = basic + ava = 40 + 4 = 44."""
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        row = _get_row(result, nrnr="A", trans="3110", year=2020)
        assert row["moms"] == pytest.approx(8 / 44)

    def test_exports_ava_rate_2020(self, sut):
        """Exports have no ava — grouped sum is 0, rate is 0."""
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        row = _get_row(result, nrnr="A", trans="6001", year=2020)
        assert row["ava"] == pytest.approx(0.0)

    def test_hhcons_moms_rate_2021(self, sut):
        """Year 2021: basic=44, ava=5 → moms denom = 49."""
        result = compute_price_layer_rates(sut, ["product", "transaction"])
        row = _get_row(result, nrnr="A", trans="3110", year=2021)
        assert row["moms"] == pytest.approx(9 / 49)


# ---------------------------------------------------------------------------
# Tests: product × transaction × category level rates
# ---------------------------------------------------------------------------

# Each (product, transaction) has exactly one category in this fixture, so
# results equal product × transaction level results.


class TestProductTransactionCategoryLevelRates:

    def test_hhcons_ava_rate_category_2020(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction", "category"])
        row = _get_row(result, nrnr="A", trans="3110", brch="HH", year=2020)
        assert row["ava"] == pytest.approx(4 / 40)

    def test_hhcons_moms_rate_category_2020(self, sut):
        result = compute_price_layer_rates(sut, ["product", "transaction", "category"])
        row = _get_row(result, nrnr="A", trans="3110", brch="HH", year=2020)
        assert row["moms"] == pytest.approx(8 / 44)


# ---------------------------------------------------------------------------
# Tests: transaction × category level rates (industry-style, no product dim)
# ---------------------------------------------------------------------------

# Aggregating without product: sums across all products first.
# With only product A in the fixture, values equal product × transaction × category.


class TestTransactionCategoryLevelRates:

    def test_columns_exclude_product(self, sut):
        result = compute_price_layer_rates(sut, ["transaction", "category"])
        assert "nrnr" not in result.columns

    def test_hhcons_ava_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, ["transaction", "category"])
        row = _get_row(result, trans="3110", brch="HH", year=2020)
        assert row["ava"] == pytest.approx(4 / 40)

    def test_hhcons_moms_rate_2020(self, sut):
        result = compute_price_layer_rates(sut, ["transaction", "category"])
        row = _get_row(result, trans="3110", brch="HH", year=2020)
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

    def test_unknown_role_raises(self, sut):
        with pytest.raises(ValueError, match="unknown role"):
            compute_price_layer_rates(sut, "industry")

    def test_unknown_role_in_list_raises(self, sut):
        with pytest.raises(ValueError, match="unknown role"):
            compute_price_layer_rates(sut, ["product", "industry"])

    def test_none_mapped_role_raises(self, sut):
        """A role that is a valid SUTColumns field but maps to None raises."""
        # wholesale_margins is mapped in the fixture, but vat is also mapped.
        # Use a fresh sut where retail_margins is None (default).
        with pytest.raises(ValueError, match="not mapped"):
            compute_price_layer_rates(sut, "retail_margins")

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


# ===========================================================================
# Tests: compute_totals
# ===========================================================================
#
# Fixture data recap:
#
#   Supply (2 rows):
#     year  nrnr  trans   brch  bas
#     2020  A     0100    IND   100.0
#     2021  A     0100    IND   110.0
#
#   Use (6 rows):
#     year  nrnr  trans   brch  bas   ava   moms  koeb
#     2020  A     2000    X     20.0  2.0   NaN   22.0
#     2020  A     3110    HH    40.0  4.0   8.0   52.0
#     2020  A     6001    ""    20.0  NaN   NaN   20.0
#     2021  A     2000    X     22.0  3.0   NaN   25.0
#     2021  A     3110    HH    44.0  5.0   9.0   58.0
#     2021  A     6001    ""    22.0  NaN   NaN   22.0
#
# compute_totals(sut, "product") groups by (year, nrnr), summing over
# trans+brch. Supply rows contribute to bas only (NaN → 0 for ava/moms/koeb).
#
#   2020, A:
#     bas  = 100 + 20 + 40 + 20 = 180
#     ava  = 0   + 2  + 4  + 0  = 6
#     moms = 0   + 0  + 8  + 0  = 8
#     koeb = 0   + 22 + 52 + 20 = 94
#
#   2021, A:
#     bas  = 110 + 22 + 44 + 22 = 198
#     ava  = 0   + 3  + 5  + 0  = 8
#     moms = 0   + 0  + 9  + 0  = 9
#     koeb = 0   + 25 + 58 + 22 = 105
#
# compute_totals(sut, ["transaction", "category"]) groups by (year, trans,
# brch), summing over product. Supply rows form their own groups (trans=0100).
# Supply-only groups have ava=moms=koeb=0 (NaN → 0).


class TestComputeTotalsOutputStructure:

    def test_product_dimension_columns(self, sut):
        result = compute_totals(sut, "product")
        assert list(result.columns) == ["year", "nrnr", "bas", "ava", "moms", "koeb"]

    def test_transaction_category_dimensions_columns(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        assert list(result.columns) == ["year", "trans", "brch", "bas", "ava", "moms", "koeb"]

    def test_product_dimension_excludes_transaction_and_category(self, sut):
        result = compute_totals(sut, "product")
        assert "trans" not in result.columns
        assert "brch" not in result.columns

    def test_id_is_always_first_column(self, sut):
        for dims in ("product", ["transaction", "category"], ["product", "transaction"]):
            result = compute_totals(sut, dims)
            assert result.columns[0] == "year"

    def test_product_dimension_row_count(self, sut):
        # One row per (year, nrnr): 1 product × 2 years = 2 rows
        result = compute_totals(sut, "product")
        assert len(result) == 2

    def test_transaction_category_row_count(self, sut):
        # Groups: (0100, IND), (2000, X), (3110, HH), (6001, "") × 2 years = 8 rows
        result = compute_totals(sut, ["transaction", "category"])
        assert len(result) == 8

    def test_string_shorthand_equals_single_element_list(self, sut):
        result_str = compute_totals(sut, "product")
        result_list = compute_totals(sut, ["product"])
        pd.testing.assert_frame_equal(result_str, result_list)

    def test_sorted_by_group_keys(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        years = result["year"].tolist()
        assert years == sorted(years)


class TestComputeTotalsProductDimension:
    """Aggregate over transaction and category, keeping product."""

    def test_bas_2020(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2020, nrnr="A")
        assert row["bas"] == pytest.approx(180.0)

    def test_ava_2020(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2020, nrnr="A")
        assert row["ava"] == pytest.approx(6.0)

    def test_moms_2020(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2020, nrnr="A")
        assert row["moms"] == pytest.approx(8.0)

    def test_koeb_2020(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2020, nrnr="A")
        assert row["koeb"] == pytest.approx(94.0)

    def test_bas_2021(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2021, nrnr="A")
        assert row["bas"] == pytest.approx(198.0)

    def test_ava_2021(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2021, nrnr="A")
        assert row["ava"] == pytest.approx(8.0)

    def test_moms_2021(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2021, nrnr="A")
        assert row["moms"] == pytest.approx(9.0)

    def test_koeb_2021(self, sut):
        result = compute_totals(sut, "product")
        row = _get_row(result, year=2021, nrnr="A")
        assert row["koeb"] == pytest.approx(105.0)


class TestComputeTotalsTransactionCategoryDimensions:
    """Aggregate over product, keeping transaction and category.

    Supply rows form their own groups (trans=0100, brch=IND) and have
    NaN for ava/moms/koeb, which sum() treats as 0.
    """

    def test_supply_row_bas_2020(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        row = _get_row(result, year=2020, trans="0100", brch="IND")
        assert row["bas"] == pytest.approx(100.0)

    def test_supply_row_ava_is_nan_2020(self, sut):
        """Supply has no ava column — all-NaN group stays NaN (min_count=1)."""
        import math
        result = compute_totals(sut, ["transaction", "category"])
        row = _get_row(result, year=2020, trans="0100", brch="IND")
        assert math.isnan(row["ava"])

    def test_use_row_bas_3110_2020(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        row = _get_row(result, year=2020, trans="3110", brch="HH")
        assert row["bas"] == pytest.approx(40.0)

    def test_use_row_ava_3110_2020(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        row = _get_row(result, year=2020, trans="3110", brch="HH")
        assert row["ava"] == pytest.approx(4.0)

    def test_use_row_moms_3110_2020(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        row = _get_row(result, year=2020, trans="3110", brch="HH")
        assert row["moms"] == pytest.approx(8.0)

    def test_use_row_koeb_3110_2020(self, sut):
        result = compute_totals(sut, ["transaction", "category"])
        row = _get_row(result, year=2020, trans="3110", brch="HH")
        assert row["koeb"] == pytest.approx(52.0)


class TestComputeTotalsErrors:

    def test_no_metadata_raises(self, supply_df, use_df):
        sut_no_meta = SUT(
            price_basis="current_year",
            supply=supply_df,
            use=use_df,
        )
        with pytest.raises(ValueError, match="sut.metadata is required"):
            compute_totals(sut_no_meta, "product")

    def test_unknown_role_raises(self, sut):
        with pytest.raises(ValueError, match="unknown role"):
            compute_totals(sut, "industry")

    def test_unknown_role_in_list_raises(self, sut):
        with pytest.raises(ValueError, match="unknown role"):
            compute_totals(sut, ["product", "industry"])

    def test_none_mapped_role_raises(self, sut):
        """retail_margins is None in the fixture columns."""
        with pytest.raises(ValueError, match="not mapped"):
            compute_totals(sut, "retail_margins")


class TestComputeTotalsSUTMethod:

    def test_method_equals_free_function(self, sut):
        result_free = compute_totals(sut, "product")
        result_method = sut.compute_totals("product")
        pd.testing.assert_frame_equal(result_free, result_method)

    def test_method_list_dimensions(self, sut):
        result_free = compute_totals(sut, ["transaction", "category"])
        result_method = sut.compute_totals(["transaction", "category"])
        pd.testing.assert_frame_equal(result_free, result_method)


class TestComputeTotalsUsePriceColumns:
    """use_price_columns nulls non-specified price columns for use rows only.

    Fixture recap:
      Supply 2020 A: bas=100 (ava/moms/koeb absent)
      Use 2020 A: bas=80, ava=6, moms=8, koeb=94  (summed over trans+brch)

    With use_price_columns="koeb" and dimensions="product":
      bas = 100  (supply unaffected; use bas nulled → all-supply group → 100)
      ava = NaN  (use ava nulled; supply has no ava → all-NaN)
      moms= NaN  (same)
      koeb= 94   (only use koeb kept)
    """

    def test_single_column_string_keeps_only_that_column_for_use(self, sut):
        import math
        result = compute_totals(sut, "product", use_price_columns="koeb")
        row = _get_row(result, year=2020, nrnr="A")
        assert row["koeb"] == pytest.approx(94.0)
        assert math.isnan(row["ava"])
        assert math.isnan(row["moms"])

    def test_single_column_supply_bas_unaffected(self, sut):
        # Supply basic prices must not be nulled even though "bas" is not in use_price_columns.
        result = compute_totals(sut, "product", use_price_columns="koeb")
        row = _get_row(result, year=2020, nrnr="A")
        assert row["bas"] == pytest.approx(100.0)

    def test_list_form_equals_string_form(self, sut):
        result_str = compute_totals(sut, "product", use_price_columns="koeb")
        result_list = compute_totals(sut, "product", use_price_columns=["koeb"])
        pd.testing.assert_frame_equal(result_str, result_list)

    def test_multiple_columns(self, sut):
        import math
        result = compute_totals(sut, "product", use_price_columns=["ava", "moms"])
        row = _get_row(result, year=2020, nrnr="A")
        assert row["ava"] == pytest.approx(6.0)
        assert row["moms"] == pytest.approx(8.0)
        assert math.isnan(row["koeb"])
        # Supply bas still present
        assert row["bas"] == pytest.approx(100.0)

    def test_transaction_category_dimensions_use_rows_nulled(self, sut):
        import math
        result = compute_totals(sut, ["transaction", "category"], use_price_columns="koeb")
        # Use group (3110, HH): only koeb kept
        row = _get_row(result, year=2020, trans="3110", brch="HH")
        assert row["koeb"] == pytest.approx(52.0)
        assert math.isnan(row["bas"])
        assert math.isnan(row["ava"])
        assert math.isnan(row["moms"])

    def test_transaction_category_dimensions_supply_bas_unaffected(self, sut):
        # Supply-only group (0100, IND): bas comes from supply, unaffected
        result = compute_totals(sut, ["transaction", "category"], use_price_columns="koeb")
        row = _get_row(result, year=2020, trans="0100", brch="IND")
        assert row["bas"] == pytest.approx(100.0)

    def test_none_is_default_behaviour(self, sut):
        result_none = compute_totals(sut, "product", use_price_columns=None)
        result_default = compute_totals(sut, "product")
        pd.testing.assert_frame_equal(result_none, result_default)

    def test_unknown_column_raises(self, sut):
        with pytest.raises(ValueError, match="unknown column"):
            compute_totals(sut, "product", use_price_columns="nonexistent")

    def test_method_delegate_passes_use_price_columns(self, sut):
        result_free = compute_totals(sut, "product", use_price_columns="koeb")
        result_method = sut.compute_totals("product", use_price_columns="koeb")
        pd.testing.assert_frame_equal(result_free, result_method)
