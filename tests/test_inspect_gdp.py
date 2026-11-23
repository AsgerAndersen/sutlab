"""
Tests for inspect_gdp.
"""

import pytest
import pandas as pd
import numpy as np

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import (
    inspect_gdp,
    GdpInspection,
    GdpData,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
#
# Transactions:
#   0100  P1  supply  Market output
#   0130  P1  supply  Non-market output
#   D221  D2121 supply  (import duties, identified by ESA code only)
#   0700  P7  supply  Imports
#   2000  P2  use     Intermediate consumption
#   3110  P31 use     Private consumption
#   5139  P51g use    Fixed investment
#   6001  P6  use     Exports
#
# Years: 2021, 2022
#
# Price layers: ava (wholesale margins), moms (vat)
# ---------------------------------------------------------------------------


@pytest.fixture
def cols():
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
def transactions_df():
    return pd.DataFrame({
        "trans":     ["0100",          "0130",             "D221",         "0700",    "2000",                    "3110",              "5139",                       "6001"],
        "trans_txt": ["Market output", "Non-market output","Import duties","Imports", "Intermediate consumption","Private cons.",     "Fixed investment",           "Exports"],
        "table":     ["supply",        "supply",           "supply",       "supply",  "use",                     "use",               "use",                        "use"],
        "esa_code":  ["P1",            "P1",               "D2121",        "P7",      "P2",                      "P31",               "P51g",                       "P6"],
        "gdp_decomp":["Market output", "Non-market output",None,           "Imports", "Intermediate consumption","Private consumption","Gross fixed capital formation","Exports"],
    })


@pytest.fixture
def supply():
    # 2 years, multiple products per transaction
    return pd.DataFrame({
        "year":  [2021,   2021,   2021,   2021,   2021,   2022,   2022,   2022,   2022,   2022],
        "nrnr":  ["A",    "B",    "A",    "A",    "A",    "A",    "B",    "A",    "A",    "A"],
        "trans": ["0100", "0100", "0130", "D221", "0700", "0100", "0100", "0130", "D221", "0700"],
        "brch":  ["X",    "Y",    "X",    "",     "",     "X",    "Y",    "X",    "",     ""],
        "bas":   [100.0,  50.0,   30.0,   10.0,   60.0,   110.0,  55.0,   33.0,   11.0,   65.0],
        "koeb":  [100.0,  50.0,   30.0,   10.0,   60.0,   110.0,  55.0,   33.0,   11.0,   65.0],
    })


@pytest.fixture
def use():
    return pd.DataFrame({
        "year":  [2021,   2021,   2021,   2022,   2022,   2022],
        "nrnr":  ["A",    "A",    "A",    "A",    "A",    "A"],
        "trans": ["2000", "3110", "5139", "2000", "3110", "5139"],
        "brch":  ["X",    "HH",   "",     "X",    "HH",   ""],
        "bas":   [80.0,   40.0,   20.0,   88.0,   44.0,   22.0],
        "ava":   [5.0,    2.0,    1.0,    5.5,    2.2,    1.1],
        "moms":  [8.0,    4.0,    2.0,    8.8,    4.4,    2.2],
        "koeb":  [93.0,   46.0,   23.0,   102.3,  50.6,   25.3],
    })


@pytest.fixture
def sut(supply, use, cols, transactions_df):
    classifications = SUTClassifications(transactions=transactions_df)
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    return SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------


def test_returns_inspection_object(sut):
    result = inspect_gdp(sut)
    assert isinstance(result, GdpInspection)
    assert isinstance(result.data, GdpData)
    assert isinstance(result.data.gdp, pd.DataFrame)


def test_columns_are_sorted_id_values(sut):
    result = inspect_gdp(sut)
    assert list(result.data.gdp.columns) == [2021, 2022]


def test_index_is_two_level_multiindex(sut):
    result = inspect_gdp(sut)
    assert isinstance(result.data.gdp.index, pd.MultiIndex)
    assert result.data.gdp.index.nlevels == 2


def test_production_block_present(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp.index.get_level_values(0).unique().tolist()
    assert "Production" in blocks


def test_expenditure_block_present(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp.index.get_level_values(0).unique().tolist()
    assert "Expenditure" in blocks


# ---------------------------------------------------------------------------
# Production block row labels
# ---------------------------------------------------------------------------


def test_production_block_row_labels(sut):
    # ava is wholesale_margins (margin role) → excluded
    # moms is vat (tax role) → included, first letter capitalised
    result = inspect_gdp(sut)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    expected = [
        "Market output",
        "Non-market output",
        "Intermediate consumption",
        "Gross Value Added",
        "Moms",         # vat column, capitalised; ava (margin) excluded
        "Import duties",
        "Total product taxes, netto",
        "GDP",
    ]
    assert prod_labels == expected


# ---------------------------------------------------------------------------
# Expenditure block row labels
# ---------------------------------------------------------------------------


def test_expenditure_block_row_labels(sut):
    result = inspect_gdp(sut)
    exp_labels = result.data.gdp.loc["Expenditure"].index.tolist()
    expected = [
        "Private consumption",
        "Gross fixed capital formation",
        "Domestic final expenditure",
        "Exports",
        "Imports",
        "Export, netto",
        "GDP",
    ]
    assert exp_labels == expected


# ---------------------------------------------------------------------------
# Production block values
# ---------------------------------------------------------------------------


def test_production_p1_market_output(sut):
    # supply trans=0100: 2021: 100+50=150, 2022: 110+55=165
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Market output")]
    assert row[2021] == pytest.approx(150.0)
    assert row[2022] == pytest.approx(165.0)


def test_production_p1_nonmarket_output(sut):
    # supply trans=0130: 2021: 30, 2022: 33
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Non-market output")]
    assert row[2021] == pytest.approx(30.0)
    assert row[2022] == pytest.approx(33.0)


def test_production_p2_intermediate_consumption(sut):
    # use trans=2000, koeb: 2021: 93, 2022: 102.3 → negated
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Intermediate consumption")]
    assert row[2021] == pytest.approx(-93.0)
    assert row[2022] == pytest.approx(-102.3)


def test_production_gva_derived(sut):
    # GVA = Market output + Non-market output + Intermediate consumption
    # 2021: 150 + 30 + (-93) = 87
    # 2022: 165 + 33 + (-102.3) = 95.7
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Gross Value Added")]
    assert row[2021] == pytest.approx(87.0)
    assert row[2022] == pytest.approx(95.7)


def test_production_margin_column_excluded(sut):
    # ava is wholesale_margins (margin role) → must not appear in Production block
    result = inspect_gdp(sut)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    assert "ava" not in prod_labels
    assert "Ava" not in prod_labels


def test_production_vat_column_capitalised(sut):
    # moms is vat role → included as "Moms"
    # use moms: 2021: 8+4+2=14, 2022: 8.8+4.4+2.2=15.4
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Moms")]
    assert row[2021] == pytest.approx(14.0)
    assert row[2022] == pytest.approx(15.4)


def test_production_import_duties(sut):
    # supply trans=D221, bas: 2021: 10, 2022: 11
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Import duties")]
    assert row[2021] == pytest.approx(10.0)
    assert row[2022] == pytest.approx(11.0)


def test_production_total_product_taxes(sut):
    # moms (vat) + import duties only; ava (margin) excluded
    # 2021: 14+10=24, 2022: 15.4+11=26.4
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "Total product taxes, netto")]
    assert row[2021] == pytest.approx(24.0)
    assert row[2022] == pytest.approx(26.4)


def test_production_gdp(sut):
    # GDP = GVA + Total taxes: 2021: 87+24=111, 2022: 95.7+26.4=122.1
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Production", "GDP")]
    assert row[2021] == pytest.approx(111.0)
    assert row[2022] == pytest.approx(122.1)


# ---------------------------------------------------------------------------
# Expenditure block values
# ---------------------------------------------------------------------------


def test_expenditure_private_consumption(sut):
    # use trans=3110, koeb: 2021: 46, 2022: 50.6
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "Private consumption")]
    assert row[2021] == pytest.approx(46.0)
    assert row[2022] == pytest.approx(50.6)


def test_expenditure_fixed_investment(sut):
    # use trans=5139, koeb: 2021: 23, 2022: 25.3
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "Gross fixed capital formation")]
    assert row[2021] == pytest.approx(23.0)
    assert row[2022] == pytest.approx(25.3)


def test_expenditure_domestic_final_expenditure(sut):
    # DFE = Private consumption + GFCF: 2021: 46+23=69, 2022: 50.6+25.3=75.9
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "Domestic final expenditure")]
    assert row[2021] == pytest.approx(69.0)
    assert row[2022] == pytest.approx(75.9)


def test_expenditure_exports(sut):
    # use trans=6001: no rows in fixture → exports not present in use
    # Actually 6001 is not in the use fixture — check it's NaN
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "Exports")]
    assert pd.isna(row[2021])
    assert pd.isna(row[2022])


def test_expenditure_imports(sut):
    # supply trans=0700, bas: 2021: 60, 2022: 65 → negated
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "Imports")]
    assert row[2021] == pytest.approx(-60.0)
    assert row[2022] == pytest.approx(-65.0)


def test_expenditure_export_netto(sut):
    # Export netto = Exports (NaN) + Imports (-60/-65)
    # NaN + (-60) → min_count=1 → -60
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "Export, netto")]
    assert row[2021] == pytest.approx(-60.0)
    assert row[2022] == pytest.approx(-65.0)


def test_expenditure_gdp(sut):
    # GDP = DFE + Export netto: 2021: 69+(-60)=9, 2022: 75.9+(-65)=10.9
    result = inspect_gdp(sut)
    row = result.data.gdp.loc[("Expenditure", "GDP")]
    assert row[2021] == pytest.approx(9.0)
    assert row[2022] == pytest.approx(10.9)


# ---------------------------------------------------------------------------
# GDP approaches can diverge (unbalanced SUT)
# ---------------------------------------------------------------------------


def test_gdp_production_and_expenditure_can_differ(sut):
    result = inspect_gdp(sut)
    prod_gdp = result.data.gdp.loc[("Production", "GDP"), 2021]
    exp_gdp = result.data.gdp.loc[("Expenditure", "GDP"), 2021]
    # With our fixture data they should differ — just confirm both are returned
    assert not pd.isna(prod_gdp)
    assert not pd.isna(exp_gdp)


# ---------------------------------------------------------------------------
# Balance block
# ---------------------------------------------------------------------------


def test_balance_block_present(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp.index.get_level_values(0).unique().tolist()
    assert "Balance" in blocks


def test_balance_block_contains_single_gdp_row(sut):
    result = inspect_gdp(sut)
    balance_labels = result.data.gdp.loc["Balance"].index.tolist()
    assert balance_labels == ["GDP"]


def test_balance_gdp_is_production_minus_expenditure(sut):
    # Production GDP: 2021=111, 2022=122.1; Expenditure GDP: 2021=9, 2022=10.9
    # Balance: 2021=102, 2022=111.2
    result = inspect_gdp(sut)
    balance = result.data.gdp.loc[("Balance", "GDP")]
    prod_gdp = result.data.gdp.loc[("Production", "GDP")]
    exp_gdp = result.data.gdp.loc[("Expenditure", "GDP")]
    assert balance[2021] == pytest.approx(prod_gdp[2021] - exp_gdp[2021])
    assert balance[2022] == pytest.approx(prod_gdp[2022] - exp_gdp[2022])


# ---------------------------------------------------------------------------
# gdp_decomp override
# ---------------------------------------------------------------------------


def test_gdp_decomp_override_replaces_classification_column(sut, cols):
    override = pd.DataFrame({
        "trans":      ["0100",          "2000",                   "3110",    "6001"],
        "gdp_decomp": ["Market output", "Intermediate consumption","Household","Exports"],
    })
    result = inspect_gdp(sut, gdp_decomp=override)
    # Non-market output (0130) is not in override → should not appear in Production P1 rows
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    assert "Non-market output" not in prod_labels
    assert "Market output" in prod_labels
    # Private consumption label replaced with "Household"
    exp_labels = result.data.gdp.loc["Expenditure"].index.tolist()
    assert "Household" in exp_labels
    assert "Private consumption" not in exp_labels


def test_gdp_decomp_override_missing_trans_col_raises(sut):
    bad_override = pd.DataFrame({
        "wrong_col":  ["0100"],
        "gdp_decomp": ["Market output"],
    })
    with pytest.raises(ValueError, match="trans"):
        inspect_gdp(sut, gdp_decomp=bad_override)


def test_gdp_decomp_override_missing_gdp_decomp_col_raises(sut):
    bad_override = pd.DataFrame({
        "trans":      ["0100"],
        "wrong_col":  ["Market output"],
    })
    with pytest.raises(ValueError, match="gdp_decomp"):
        inspect_gdp(sut, gdp_decomp=bad_override)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_wrong_price_basis_raises(sut):
    from dataclasses import replace as dc_replace
    sut_prev = dc_replace(sut, price_basis="previous_year")
    with pytest.raises(ValueError, match="current_year"):
        inspect_gdp(sut_prev)


def test_no_metadata_raises(sut):
    from dataclasses import replace as dc_replace
    sut_no_meta = dc_replace(sut, metadata=None)
    with pytest.raises(ValueError, match="metadata"):
        inspect_gdp(sut_no_meta)


def test_no_transactions_classification_raises(supply, use, cols):
    classifications = SUTClassifications()  # no transactions
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    sut_no_trans = SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
    )
    with pytest.raises(ValueError, match="transactions classification"):
        inspect_gdp(sut_no_trans)


def test_missing_gdp_decomp_column_raises(supply, use, cols):
    transactions_no_gdp = pd.DataFrame({
        "trans":    ["0100", "2000"],
        "trans_txt":["Output", "IC"],
        "table":    ["supply", "use"],
        "esa_code": ["P1", "P2"],
        # no gdp_decomp column
    })
    classifications = SUTClassifications(transactions=transactions_no_gdp)
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    sut_no_gdp = SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
    )
    with pytest.raises(ValueError, match="gdp_decomp"):
        inspect_gdp(sut_no_gdp)


# ---------------------------------------------------------------------------
# D2121 absent
# ---------------------------------------------------------------------------


def test_no_import_duties_row_when_d2121_absent(supply, use, cols):
    transactions_no_d2121 = pd.DataFrame({
        "trans":     ["0100",          "0700",    "2000",                    "3110",              "6001"],
        "trans_txt": ["Market output", "Imports", "Intermediate consumption","Private cons.",     "Exports"],
        "table":     ["supply",        "supply",  "use",                     "use",               "use"],
        "esa_code":  ["P1",            "P7",      "P2",                      "P31",               "P6"],
        "gdp_decomp":["Market output", "Imports", "Intermediate consumption","Private consumption","Exports"],
    })
    classifications = SUTClassifications(transactions=transactions_no_d2121)
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    sut_no_d2121 = SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
    )
    result = inspect_gdp(sut_no_d2121)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    assert "Import duties" not in prod_labels


# ---------------------------------------------------------------------------
# No price layers
# ---------------------------------------------------------------------------


def test_no_price_layer_rows_when_no_layer_columns(supply, transactions_df):
    cols_no_layers = SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
        # no wholesale_margins, no vat
    )
    use_no_layers = pd.DataFrame({
        "year":  [2021,   2021,   2022,   2022],
        "nrnr":  ["A",    "A",    "A",    "A"],
        "trans": ["2000", "3110", "2000", "3110"],
        "brch":  ["X",    "HH",   "X",    "HH"],
        "bas":   [80.0,   40.0,   88.0,   44.0],
        "koeb":  [80.0,   40.0,   88.0,   44.0],
    })
    classifications = SUTClassifications(transactions=transactions_df)
    metadata = SUTMetadata(columns=cols_no_layers, classifications=classifications)
    sut_no_layers = SUT(
        price_basis="current_year",
        supply=supply,
        use=use_no_layers,
        metadata=metadata,
    )
    result = inspect_gdp(sut_no_layers)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    # No tax/subsidy columns mapped → no tax layer rows
    assert "Moms" not in prod_labels
    # Import duties still present because D2121 is in trans classification
    assert "Total product taxes, netto" in prod_labels


# ---------------------------------------------------------------------------
# Multiple transactions sharing same gdp_decomp label
# ---------------------------------------------------------------------------


def test_multiple_transactions_same_label_are_summed(supply, use, cols):
    # Give 0100 and 0130 the same gdp_decomp label "Total output"
    transactions_merged = pd.DataFrame({
        "trans":     ["0100",         "0130",         "D221",  "0700",   "2000",                   "3110",              "5139",                       "6001"],
        "trans_txt": ["Market",       "Non-market",   "D2121", "Imports","IC",                     "Private",           "GFCF",                       "Exports"],
        "table":     ["supply",       "supply",       "supply","supply", "use",                    "use",               "use",                        "use"],
        "esa_code":  ["P1",           "P1",           "D2121", "P7",     "P2",                     "P31",               "P51g",                       "P6"],
        "gdp_decomp":["Total output", "Total output", None,    "Imports","Intermediate consumption","Private consumption","Gross fixed capital formation","Exports"],
    })
    classifications = SUTClassifications(transactions=transactions_merged)
    metadata = SUTMetadata(columns=cols, classifications=classifications)
    sut_merged = SUT(
        price_basis="current_year",
        supply=supply,
        use=use,
        metadata=metadata,
    )
    result = inspect_gdp(sut_merged)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    # Only one "Total output" row, not two separate rows
    assert prod_labels.count("Total output") == 1
    # Value should be sum of 0100 and 0130: 2021: 150+30=180
    row = result.data.gdp.loc[("Production", "Total output")]
    assert row[2021] == pytest.approx(180.0)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------


def test_gdp_property_returns_styler(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut)
    assert isinstance(result.gdp, Styler)


def test_gdp_styler_has_correct_shape(sut):
    result = inspect_gdp(sut)
    styler = result.gdp
    assert styler.data.shape == result.data.gdp.shape


def test_gdp_styler_with_display_unit(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut).set_display_unit(1e6)
    assert isinstance(result.gdp, Styler)


# ---------------------------------------------------------------------------
# SUT delegate method
# ---------------------------------------------------------------------------


def test_sut_delegate_method(sut):
    result = sut.inspect_gdp()
    assert isinstance(result, GdpInspection)


def test_sut_delegate_method_with_override(sut, cols):
    override = pd.DataFrame({
        "trans":      ["0100",          "2000"],
        "gdp_decomp": ["Market output", "Intermediate consumption"],
    })
    result = sut.inspect_gdp(gdp_decomp=override)
    assert isinstance(result, GdpInspection)


# ---------------------------------------------------------------------------
# gdp_growth table
# ---------------------------------------------------------------------------


def test_gdp_growth_excludes_balance_block(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp_growth.index.get_level_values(0).unique().tolist()
    assert "Balance" not in blocks


def test_gdp_growth_has_production_and_expenditure_blocks(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp_growth.index.get_level_values(0).unique().tolist()
    assert "Production" in blocks
    assert "Expenditure" in blocks


def test_gdp_growth_first_column_is_nan(sut):
    result = inspect_gdp(sut)
    first_col = result.data.gdp_growth.columns[0]
    assert result.data.gdp_growth[first_col].isna().all()


def test_gdp_growth_computes_year_on_year_rates(sut):
    # Production GDP: 2021=111.0, 2022=122.1 → growth = (122.1-111.0)/111.0
    result = inspect_gdp(sut)
    prod_gdp_growth = result.data.gdp_growth.loc[("Production", "GDP"), 2022]
    expected = (122.1 - 111.0) / 111.0
    assert prod_gdp_growth == pytest.approx(expected)


def test_gdp_growth_same_rows_as_gdp_without_balance(sut):
    result = inspect_gdp(sut)
    gdp_no_balance = result.data.gdp[
        result.data.gdp.index.get_level_values(0) != "Balance"
    ]
    assert result.data.gdp_growth.index.equals(gdp_no_balance.index)
    assert list(result.data.gdp_growth.columns) == list(result.data.gdp.columns)


def test_gdp_growth_property_returns_styler(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut)
    assert isinstance(result.gdp_growth, Styler)


def test_gdp_growth_styler_has_correct_shape(sut):
    result = inspect_gdp(sut)
    styler = result.gdp_growth
    assert styler.data.shape == result.data.gdp_growth.shape


def test_gdp_growth_styler_with_rel_base(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut).set_display_rel_base(1000)
    assert isinstance(result.gdp_growth, Styler)


# ---------------------------------------------------------------------------
# gdp_distribution table
# ---------------------------------------------------------------------------


def test_gdp_distribution_excludes_balance_block(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp_distribution.index.get_level_values(0).unique().tolist()
    assert "Balance" not in blocks


def test_gdp_distribution_has_production_and_expenditure_blocks(sut):
    result = inspect_gdp(sut)
    blocks = result.data.gdp_distribution.index.get_level_values(0).unique().tolist()
    assert "Production" in blocks
    assert "Expenditure" in blocks


def test_gdp_distribution_same_rows_as_gdp_without_balance(sut):
    result = inspect_gdp(sut)
    gdp_no_balance = result.data.gdp[
        result.data.gdp.index.get_level_values(0) != "Balance"
    ]
    assert result.data.gdp_distribution.index.equals(gdp_no_balance.index)
    assert list(result.data.gdp_distribution.columns) == list(result.data.gdp.columns)


def test_gdp_distribution_gdp_row_equals_one(sut):
    result = inspect_gdp(sut)
    for block in ("Production", "Expenditure"):
        gdp_row = result.data.gdp_distribution.loc[(block, "GDP")]
        for val in gdp_row:
            assert val == pytest.approx(1.0)


def test_gdp_distribution_production_shares_sum_correctly(sut):
    # Production GDP 2021=111.0; GVA=87.0 → share=87/111
    result = inspect_gdp(sut)
    gva_share = result.data.gdp_distribution.loc[("Production", "Gross Value Added"), 2021]
    expected = 87.0 / 111.0
    assert gva_share == pytest.approx(expected)


def test_gdp_distribution_expenditure_shares_sum_correctly(sut):
    # Expenditure GDP 2021=9.0; Domestic final expenditure=69.0 → share=69/9
    result = inspect_gdp(sut)
    dfe_share = result.data.gdp_distribution.loc[("Expenditure", "Domestic final expenditure"), 2021]
    expected = 69.0 / 9.0
    assert dfe_share == pytest.approx(expected)


def test_gdp_distribution_production_uses_production_gdp_not_expenditure(sut):
    # Production GDP (111) ≠ Expenditure GDP (9), so the denominator matters.
    result = inspect_gdp(sut)
    gva_share = result.data.gdp_distribution.loc[("Production", "Gross Value Added"), 2021]
    # If denominator were Expenditure GDP (9) the share would be ~9.67, not ~0.78
    assert gva_share == pytest.approx(87.0 / 111.0)
    assert gva_share != pytest.approx(87.0 / 9.0)


def test_gdp_distribution_property_returns_styler(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut)
    assert isinstance(result.gdp_distribution, Styler)


def test_gdp_distribution_styler_has_correct_shape(sut):
    result = inspect_gdp(sut)
    assert result.gdp_distribution.data.shape == result.data.gdp_distribution.shape


def test_gdp_distribution_styler_with_rel_base(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut).set_display_rel_base(1000)
    assert isinstance(result.gdp_distribution, Styler)


# ---------------------------------------------------------------------------
# set_display_decimals
# ---------------------------------------------------------------------------


def test_set_decimals_default(sut):
    result = inspect_gdp(sut)
    assert result.display_configuration.decimals == 1


def test_set_decimals_returns_new_copy(sut):
    result = inspect_gdp(sut)
    updated = result.set_display_decimals(0)
    assert updated.display_configuration.decimals == 0
    assert result.display_configuration.decimals == 1


def test_set_decimals_styled_properties_do_not_raise(sut):
    from pandas.io.formats.style import Styler
    result = inspect_gdp(sut).set_display_decimals(0)
    assert isinstance(result.gdp, Styler)
    assert isinstance(result.gdp_growth, Styler)
    assert isinstance(result.gdp_distribution, Styler)


def test_set_decimals_invalid_negative_raises(sut):
    with pytest.raises(ValueError, match="non-negative integer"):
        inspect_gdp(sut).set_display_decimals(-1)


def test_set_decimals_invalid_float_raises(sut):
    with pytest.raises(ValueError, match="non-negative integer"):
        inspect_gdp(sut).set_display_decimals(1.5)


# ---------------------------------------------------------------------------
# Industry GVA and contribution tables
# ---------------------------------------------------------------------------
#
# Hand-computed from the fixtures above:
#   2021: GVA X = 100+30-93 = 37, GVA Y = 50, total GVA 87, taxes 14+10 = 24, GDP 111
#   2022: GVA X = 110+33-102.3 = 40.7, GVA Y = 55, total GVA 95.7, taxes 15.4+11 = 26.4, GDP 122.1


@pytest.fixture
def sut_with_industries(sut):
    industries = pd.DataFrame({
        "brch": ["X", "Y"],
        "brch_txt": ["Industry X", "Industry Y"],
    })
    classifications = SUTClassifications(
        transactions=sut.metadata.classifications.transactions,
        industries=industries,
    )
    metadata = SUTMetadata(columns=sut.metadata.columns, classifications=classifications)
    return SUT(price_basis="current_year", supply=sut.supply, use=sut.use, metadata=metadata)


def test_gdp_industries_values(sut):
    df = inspect_gdp(sut).data.gdp_industries
    assert df.loc[("Production", "X"), 2021] == pytest.approx(37.0)
    assert df.loc[("Production", "Y"), 2021] == pytest.approx(50.0)
    assert df.loc[("Production", "Gross Value Added"), 2022] == pytest.approx(95.7)
    assert df.loc[("Production", "Total product taxes, netto"), 2021] == pytest.approx(24.0)
    assert df.loc[("Production", "GDP"), 2022] == pytest.approx(122.1)


def test_gdp_industries_ties_to_gdp_table(sut):
    result = inspect_gdp(sut).data
    industries_gva = result.gdp_industries.loc[("Production", "Gross Value Added")]
    production_gva = result.gdp.loc[("Production", "Gross Value Added")]
    pd.testing.assert_series_equal(industries_gva, production_gva, check_names=False)
    industries_gdp = result.gdp_industries.loc[("Production", "GDP")]
    production_gdp = result.gdp.loc[("Production", "GDP")]
    pd.testing.assert_series_equal(industries_gdp, production_gdp, check_names=False)


def test_gdp_industries_labels_use_classification(sut_with_industries):
    df = inspect_gdp(sut_with_industries).data.gdp_industries
    assert ("Production", "X Industry X") in df.index
    assert ("Production", "Y Industry Y") in df.index


def test_gdp_industries_distribution_is_share_of_gdp(sut):
    df = inspect_gdp(sut).data.gdp_industries_distribution
    assert df.loc[("Production", "X"), 2021] == pytest.approx(37.0 / 111.0)
    assert df.loc[("Production", "Gross Value Added"), 2021] == pytest.approx(87.0 / 111.0)
    assert df.loc[("Production", "GDP"), 2021] == pytest.approx(1.0)


def test_gdp_industries_growth(sut):
    df = inspect_gdp(sut).data.gdp_industries_growth
    assert np.isnan(df.loc[("Production", "X"), 2021])
    assert df.loc[("Production", "X"), 2022] == pytest.approx(40.7 / 37.0 - 1)


def test_gdp_industries_growth_contributions(sut):
    df = inspect_gdp(sut).data.gdp_industries_growth_contributions
    assert df[2021].isna().all()
    assert df.loc[("Production", "X"), 2022] == pytest.approx(3.7 / 111.0)
    assert df.loc[("Production", "Y"), 2022] == pytest.approx(5.0 / 111.0)
    assert df.loc[("Production", "GDP"), 2022] == pytest.approx(11.1 / 111.0)


def test_gdp_industries_growth_contributions_sum_to_gdp_growth(sut):
    df = inspect_gdp(sut).data.gdp_industries_growth_contributions
    industry_rows = [label for _, label in df.index if label in {"X", "Y"}]
    total = sum(df.loc[("Production", label), 2022] for label in industry_rows)
    total += df.loc[("Production", "Total product taxes, netto"), 2022]
    assert total == pytest.approx(df.loc[("Production", "GDP"), 2022])


def test_gdp_growth_contributions_structure_and_gdp_rows(sut):
    result = inspect_gdp(sut).data
    contributions = result.gdp_growth_contributions
    growth = result.gdp_growth
    assert contributions.index.equals(growth.index)
    assert "Balance" not in contributions.index.get_level_values(0)
    for block in ("Production", "Expenditure"):
        assert contributions.loc[(block, "GDP"), 2022] == pytest.approx(
            growth.loc[(block, "GDP"), 2022]
        )
    assert contributions[2021].isna().all()


def test_gdp_growth_contributions_value(sut):
    contributions = inspect_gdp(sut).data.gdp_growth_contributions
    # Gross Value Added: (95.7 - 87) / 111
    assert contributions.loc[("Production", "Gross Value Added"), 2022] == pytest.approx(8.7 / 111.0)


def test_industry_tables_in_description_and_styled(sut):
    result = inspect_gdp(sut)
    names = set(result.data.tables_description.index)
    for name in (
        "gdp_growth_contributions",
        "gdp_growth_contributions_distribution",
        "gdp_industries",
        "gdp_industries_growth",
        "gdp_industries_distribution",
        "gdp_industries_growth_contributions",
        "gdp_industries_growth_contributions_distribution",
    ):
        assert name in names
        assert getattr(result, name) is not None
        assert getattr(result, name).to_html()


def test_industry_tables_write_to_excel(sut, tmp_path):
    path = tmp_path / "gdp.xlsx"
    inspect_gdp(sut).write_to_excel(path)
    sheets = pd.ExcelFile(path).sheet_names
    assert len(sheets) == 11


def test_gdp_growth_contributions_distribution_values(sut):
    df = inspect_gdp(sut).data.gdp_growth_contributions_distribution
    assert df[2021].isna().all()
    assert df.loc[("Production", "GDP"), 2022] == pytest.approx(1.0)
    assert df.loc[("Expenditure", "GDP"), 2022] == pytest.approx(1.0)
    # Gross Value Added: 8.7 of 11.1 growth
    assert df.loc[("Production", "Gross Value Added"), 2022] == pytest.approx(8.7 / 11.1)


def test_gdp_industries_growth_contributions_distribution_values(sut):
    df = inspect_gdp(sut).data.gdp_industries_growth_contributions_distribution
    assert df.loc[("Production", "X"), 2022] == pytest.approx(3.7 / 11.1)
    assert df.loc[("Production", "GDP"), 2022] == pytest.approx(1.0)
    parts = (
        df.loc[("Production", "X"), 2022]
        + df.loc[("Production", "Y"), 2022]
        + df.loc[("Production", "Total product taxes, netto"), 2022]
    )
    assert parts == pytest.approx(1.0)


def test_contributions_distribution_zero_growth_gives_nan(sut):
    # With identical years, GDP growth is exactly zero -> shares are NaN, not inf.
    sut_same = SUT(
        price_basis="current_year",
        supply=pd.concat([sut.supply[sut.supply["year"] == 2021], sut.supply[sut.supply["year"] == 2021].assign(year=2022)]),
        use=pd.concat([sut.use[sut.use["year"] == 2021], sut.use[sut.use["year"] == 2021].assign(year=2022)]),
        metadata=sut.metadata,
    )
    df = inspect_gdp(sut_same).data.gdp_growth_contributions_distribution
    assert df[2022].isna().all()


# ---------------------------------------------------------------------------
# previous= : .previous and .real inspections
# ---------------------------------------------------------------------------
#
# The previous-price SUT is the 2022 rows of the fixture with every supply
# value x 0.9 and every use value x 0.95 (so derived rows do not simply scale).
# Hand-computed 2022 values in the previous year's (2021) prices, Production block:
#   P1: X = (110 + 33) * 0.9 = 128.7, Y = 55 * 0.9 = 49.5
#   P2: X = 102.3 * 0.95 = 97.185
#   GVA: X = 31.515, Y = 49.5, total 81.015
#   taxes: moms 15.4 * 0.95 = 14.63, import duties 11 * 0.9 = 9.9 -> 24.53
#   GDP = 105.545
# Expenditure block: final use (50.6 + 25.3) * 0.95 = 72.105, imports -65 * 0.9 = -58.5
#   GDP = 13.605
# Current-price 2021 values: Production GDP 111, X GVA 37, Expenditure GDP 9.

_ALL_TABLES = [
    "gdp", "gdp_growth", "gdp_distribution",
    "gdp_growth_contributions", "gdp_growth_contributions_distribution",
    "gdp_industries", "gdp_industries_growth", "gdp_industries_distribution",
    "gdp_industries_growth_contributions",
    "gdp_industries_growth_contributions_distribution",
]


def _make_previous_sut(sut, years=(2022,)):
    supply = sut.supply[sut.supply["year"].isin(years)].copy()
    use = sut.use[sut.use["year"].isin(years)].copy()
    supply_value_columns = ["bas", "koeb"]
    use_value_columns = ["bas", "ava", "moms", "koeb"]
    supply[supply_value_columns] = supply[supply_value_columns] * 0.9
    use[use_value_columns] = use[use_value_columns] * 0.95
    return SUT(
        price_basis="previous_year",
        supply=supply,
        use=use,
        metadata=sut.metadata,
    )


@pytest.fixture
def previous_sut(sut):
    return _make_previous_sut(sut)


def test_without_previous_no_previous_or_real(sut):
    result = inspect_gdp(sut)
    assert result.previous is None
    assert result.real is None


def test_reference_id_without_previous_raises(sut):
    with pytest.raises(ValueError, match="reference_id"):
        inspect_gdp(sut, reference_id=2021)


def test_previous_and_real_are_same_class(sut, previous_sut):
    result = inspect_gdp(sut, previous=previous_sut)
    assert isinstance(result.previous, GdpInspection)
    assert isinstance(result.real, GdpInspection)
    # current-price tables are unchanged by previous=
    pd.testing.assert_frame_equal(result.data.gdp, inspect_gdp(sut).data.gdp)


def test_previous_holds_only_levels_and_shares(sut, previous_sut):
    data = inspect_gdp(sut, previous=previous_sut).previous.data
    present = {"gdp", "gdp_distribution", "gdp_industries", "gdp_industries_distribution"}
    for name in _ALL_TABLES:
        if name in present:
            assert getattr(data, name) is not None, name
        else:
            assert getattr(data, name) is None, name


def test_real_holds_volumes_growth_and_contributions(sut, previous_sut):
    data = inspect_gdp(sut, previous=previous_sut).real.data
    absent = {"gdp_distribution", "gdp_industries_distribution"}
    for name in _ALL_TABLES:
        if name in absent:
            assert getattr(data, name) is None, name
        else:
            assert getattr(data, name) is not None, name


def test_previous_values_are_previous_price_tables(sut, previous_sut):
    previous = inspect_gdp(sut, previous=previous_sut).previous.data
    assert list(previous.gdp.columns) == [2022]
    assert previous.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(105.545)
    assert previous.gdp.loc[("Expenditure", "GDP"), 2022] == pytest.approx(13.605)
    assert previous.gdp_industries.loc[("Production", "X"), 2022] == pytest.approx(31.515)


def test_real_volumes_reference_first_year(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut).real.data
    # Reference year 2021: volumes equal current prices in 2021 ...
    assert real.gdp.loc[("Production", "GDP"), 2021] == pytest.approx(111.0)
    # ... and 2022 volumes equal the 2022 values in 2021 prices.
    assert real.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(105.545)
    assert real.gdp.loc[("Production", "Gross Value Added"), 2022] == pytest.approx(81.015)
    assert real.gdp_industries.loc[("Production", "X"), 2022] == pytest.approx(31.515)
    assert real.gdp_industries.loc[("Production", "GDP"), 2022] == pytest.approx(105.545)


def test_real_volumes_other_reference_year(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut, reference_id=2022).real.data
    # Reference year 2022: 2022 equals current prices; 2021 is scaled back.
    assert real.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(122.1)
    assert real.gdp.loc[("Production", "GDP"), 2021] == pytest.approx(122.1 * 111.0 / 105.545)


def test_real_growth_is_volume_growth(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut).real.data
    assert np.isnan(real.gdp_growth.loc[("Production", "GDP"), 2021])
    assert real.gdp_growth.loc[("Production", "GDP"), 2022] == pytest.approx(105.545 / 111.0 - 1)
    assert real.gdp_growth.loc[("Expenditure", "GDP"), 2022] == pytest.approx(13.605 / 9.0 - 1)
    assert "Balance" not in real.gdp_growth.index.get_level_values(0)


def test_real_balance_is_difference_of_chained_gdp_rows(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut).real.data
    assert real.gdp.loc[("Balance", "GDP"), 2021] == pytest.approx(111.0 - 9.0)
    assert real.gdp.loc[("Balance", "GDP"), 2022] == pytest.approx(105.545 - 13.605)


def test_real_contributions_values(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut).real.data
    contributions = real.gdp_growth_contributions
    assert contributions[2021].isna().all()
    # Gross Value Added: (81.015 - 87) / 111
    assert contributions.loc[("Production", "Gross Value Added"), 2022] == pytest.approx(
        (81.015 - 87.0) / 111.0
    )
    industries = real.gdp_industries_growth_contributions
    assert industries.loc[("Production", "X"), 2022] == pytest.approx((31.515 - 37.0) / 111.0)


def test_real_gdp_contribution_equals_real_gdp_growth(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut).real.data
    for block in ("Production", "Expenditure"):
        assert real.gdp_growth_contributions.loc[(block, "GDP"), 2022] == pytest.approx(
            real.gdp_growth.loc[(block, "GDP"), 2022]
        )
    assert real.gdp_industries_growth_contributions.loc[("Production", "GDP"), 2022] == pytest.approx(
        real.gdp_industries_growth.loc[("Production", "GDP"), 2022]
    )


def test_real_industry_contributions_sum_to_gdp_growth(sut, previous_sut):
    df = inspect_gdp(sut, previous=previous_sut).real.data.gdp_industries_growth_contributions
    total = (
        df.loc[("Production", "X"), 2022]
        + df.loc[("Production", "Y"), 2022]
        + df.loc[("Production", "Total product taxes, netto"), 2022]
    )
    assert total == pytest.approx(df.loc[("Production", "GDP"), 2022])


def test_real_contributions_distribution_gdp_row_is_one(sut, previous_sut):
    real = inspect_gdp(sut, previous=previous_sut).real.data
    assert real.gdp_growth_contributions_distribution.loc[("Production", "GDP"), 2022] == pytest.approx(1.0)
    assert real.gdp_industries_growth_contributions_distribution.loc[("Production", "GDP"), 2022] == pytest.approx(1.0)


def test_previous_may_include_first_year(sut):
    previous_sut = _make_previous_sut(sut, years=(2021, 2022))
    result = inspect_gdp(sut, previous=previous_sut)
    # 2021 in previous is ignored for the chain.
    assert result.real.data.gdp.loc[("Production", "GDP"), 2021] == pytest.approx(111.0)
    assert result.real.data.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(105.545)


def test_previous_missing_a_year_raises(sut):
    previous_sut = _make_previous_sut(sut, years=(2021,))
    with pytest.raises(ValueError, match="Missing in previous"):
        inspect_gdp(sut, previous=previous_sut)


def test_previous_wrong_price_basis_raises(sut, previous_sut):
    wrong = SUT(
        price_basis="current_year",
        supply=previous_sut.supply,
        use=previous_sut.use,
        metadata=previous_sut.metadata,
    )
    with pytest.raises(ValueError, match="previous"):
        inspect_gdp(sut, previous=wrong)


def test_previous_missing_row_gives_nan_series(sut, previous_sut):
    # Drop all supply rows of industry Y from the previous SUT: its series cannot be chained.
    supply = previous_sut.supply[previous_sut.supply["brch"] != "Y"]
    reduced = SUT(
        price_basis="previous_year",
        supply=supply,
        use=previous_sut.use,
        metadata=previous_sut.metadata,
    )
    real = inspect_gdp(sut, previous=reduced).real.data
    # 2021 is the reference year (current-price value); 2022 cannot be chained.
    assert real.gdp_industries.loc[("Production", "Y"), 2021] == pytest.approx(50.0)
    assert np.isnan(real.gdp_industries.loc[("Production", "Y"), 2022])
    assert real.gdp_industries.loc[("Production", "X"), 2022] == pytest.approx(31.515)


def test_display_setters_propagate_to_previous_and_real(sut, previous_sut):
    result = inspect_gdp(sut, previous=previous_sut).set_display_decimals(3).set_display_unit(1000)
    assert result.display_configuration.decimals == 3
    assert result.previous.display_configuration.decimals == 3
    assert result.real.display_configuration.decimals == 3
    assert result.real.display_configuration.display_unit == 1000
    reset = result.set_display_configuration_to_defaults()
    assert reset.real.display_configuration.decimals == inspect_gdp(sut).display_configuration.decimals


def test_styled_properties_none_for_absent_tables(sut, previous_sut):
    result = inspect_gdp(sut, previous=previous_sut)
    assert result.previous.gdp_growth is None
    assert result.real.gdp_distribution is None
    assert result.real.gdp.to_html()
    assert result.previous.gdp.to_html()


def test_tables_description_lists_only_present_tables(sut, previous_sut):
    result = inspect_gdp(sut, previous=previous_sut)
    assert len(result.previous.data.tables_description) == 4
    assert len(result.real.data.tables_description) == 8
    assert "gdp_distribution" not in result.real.data.tables_description.index


def test_previous_and_real_write_to_excel(sut, previous_sut, tmp_path):
    result = inspect_gdp(sut, previous=previous_sut)
    previous_path = tmp_path / "previous.xlsx"
    real_path = tmp_path / "real.xlsx"
    result.previous.write_to_excel(previous_path)
    result.real.write_to_excel(real_path)
    assert len(pd.ExcelFile(previous_path).sheet_names) == 5  # description + 4 tables
    assert len(pd.ExcelFile(real_path).sheet_names) == 9  # description + 8 tables


def test_sut_method_passes_previous_and_reference_id(sut, previous_sut):
    result = sut.inspect_gdp(previous=previous_sut, reference_id=2022)
    assert result.real.data.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(122.1)


def test_tables_comparison_includes_previous_and_real(sut, previous_sut):
    first = inspect_gdp(sut, previous=previous_sut)
    # Second version: previous-price use values scaled up by 10%.
    use = previous_sut.use.copy()
    use[["bas", "ava", "moms", "koeb"]] = use[["bas", "ava", "moms", "koeb"]] * 1.1
    changed_previous = SUT(
        price_basis="previous_year",
        supply=previous_sut.supply,
        use=use,
        metadata=previous_sut.metadata,
    )
    second = inspect_gdp(sut, previous=changed_previous)

    comparison = first.inspect_tables_comparison(second)
    assert isinstance(comparison.diff.previous, GdpInspection)
    assert isinstance(comparison.rel.real, GdpInspection)

    # Current-price tables are identical, previous-price and real tables differ.
    assert comparison.diff.data.gdp.abs().sum().sum() == 0
    expected_gdp_diff = (
        first.previous.data.gdp.loc[("Production", "GDP"), 2022]
        - second.previous.data.gdp.loc[("Production", "GDP"), 2022]
    )
    assert comparison.diff.previous.data.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(expected_gdp_diff)
    assert comparison.diff.real.data.gdp.loc[("Production", "GDP"), 2022] == pytest.approx(expected_gdp_diff)
    # None tables stay None inside the nested comparisons.
    assert comparison.diff.previous.data.gdp_growth is None
    assert comparison.diff.real.data.gdp_distribution is None
    # The rel version is flagged as relative and formatted as percentages.
    assert comparison.rel.real._all_rel is True
    assert comparison.rel.real.gdp.to_html()


def test_tables_comparison_previous_none_when_either_side_lacks_it(sut, previous_sut):
    with_previous = inspect_gdp(sut, previous=previous_sut)
    without_previous = inspect_gdp(sut)
    for comparison in (
        with_previous.inspect_tables_comparison(without_previous),
        without_previous.inspect_tables_comparison(with_previous),
    ):
        assert comparison.diff.previous is None
        assert comparison.diff.real is None
        assert comparison.rel.previous is None
        assert comparison.rel.real is None


def test_tables_comparison_display_setters_reach_nested_inspections(sut, previous_sut):
    first = inspect_gdp(sut, previous=previous_sut)
    comparison = first.inspect_tables_comparison(first).set_display_decimals(3)
    assert comparison.diff.real.display_configuration.decimals == 3
    assert comparison.rel.previous.display_configuration.decimals == 3
