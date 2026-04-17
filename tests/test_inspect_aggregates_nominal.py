"""
Tests for inspect_aggregates_nominal.
"""

import pytest
import pandas as pd
import numpy as np

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata
from sutlab.inspect import (
    inspect_aggregates_nominal,
    AggregatesNominalInspection,
    AggregatesNominalData,
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
    result = inspect_aggregates_nominal(sut)
    assert isinstance(result, AggregatesNominalInspection)
    assert isinstance(result.data, AggregatesNominalData)
    assert isinstance(result.data.gdp, pd.DataFrame)


def test_columns_are_sorted_id_values(sut):
    result = inspect_aggregates_nominal(sut)
    assert list(result.data.gdp.columns) == [2021, 2022]


def test_index_is_two_level_multiindex(sut):
    result = inspect_aggregates_nominal(sut)
    assert isinstance(result.data.gdp.index, pd.MultiIndex)
    assert result.data.gdp.index.nlevels == 2


def test_production_block_present(sut):
    result = inspect_aggregates_nominal(sut)
    blocks = result.data.gdp.index.get_level_values(0).unique().tolist()
    assert "Production" in blocks


def test_expenditure_block_present(sut):
    result = inspect_aggregates_nominal(sut)
    blocks = result.data.gdp.index.get_level_values(0).unique().tolist()
    assert "Expenditure" in blocks


# ---------------------------------------------------------------------------
# Production block row labels
# ---------------------------------------------------------------------------


def test_production_block_row_labels(sut):
    # ava is wholesale_margins (margin role) → excluded
    # moms is vat (tax role) → included, first letter capitalised
    result = inspect_aggregates_nominal(sut)
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
    result = inspect_aggregates_nominal(sut)
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
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Market output")]
    assert row[2021] == pytest.approx(150.0)
    assert row[2022] == pytest.approx(165.0)


def test_production_p1_nonmarket_output(sut):
    # supply trans=0130: 2021: 30, 2022: 33
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Non-market output")]
    assert row[2021] == pytest.approx(30.0)
    assert row[2022] == pytest.approx(33.0)


def test_production_p2_intermediate_consumption(sut):
    # use trans=2000, koeb: 2021: 93, 2022: 102.3 → negated
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Intermediate consumption")]
    assert row[2021] == pytest.approx(-93.0)
    assert row[2022] == pytest.approx(-102.3)


def test_production_gva_derived(sut):
    # GVA = Market output + Non-market output + Intermediate consumption
    # 2021: 150 + 30 + (-93) = 87
    # 2022: 165 + 33 + (-102.3) = 95.7
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Gross Value Added")]
    assert row[2021] == pytest.approx(87.0)
    assert row[2022] == pytest.approx(95.7)


def test_production_margin_column_excluded(sut):
    # ava is wholesale_margins (margin role) → must not appear in Production block
    result = inspect_aggregates_nominal(sut)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    assert "ava" not in prod_labels
    assert "Ava" not in prod_labels


def test_production_vat_column_capitalised(sut):
    # moms is vat role → included as "Moms"
    # use moms: 2021: 8+4+2=14, 2022: 8.8+4.4+2.2=15.4
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Moms")]
    assert row[2021] == pytest.approx(14.0)
    assert row[2022] == pytest.approx(15.4)


def test_production_import_duties(sut):
    # supply trans=D221, bas: 2021: 10, 2022: 11
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Import duties")]
    assert row[2021] == pytest.approx(10.0)
    assert row[2022] == pytest.approx(11.0)


def test_production_total_product_taxes(sut):
    # moms (vat) + import duties only; ava (margin) excluded
    # 2021: 14+10=24, 2022: 15.4+11=26.4
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "Total product taxes, netto")]
    assert row[2021] == pytest.approx(24.0)
    assert row[2022] == pytest.approx(26.4)


def test_production_gdp(sut):
    # GDP = GVA + Total taxes: 2021: 87+24=111, 2022: 95.7+26.4=122.1
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Production", "GDP")]
    assert row[2021] == pytest.approx(111.0)
    assert row[2022] == pytest.approx(122.1)


# ---------------------------------------------------------------------------
# Expenditure block values
# ---------------------------------------------------------------------------


def test_expenditure_private_consumption(sut):
    # use trans=3110, koeb: 2021: 46, 2022: 50.6
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "Private consumption")]
    assert row[2021] == pytest.approx(46.0)
    assert row[2022] == pytest.approx(50.6)


def test_expenditure_fixed_investment(sut):
    # use trans=5139, koeb: 2021: 23, 2022: 25.3
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "Gross fixed capital formation")]
    assert row[2021] == pytest.approx(23.0)
    assert row[2022] == pytest.approx(25.3)


def test_expenditure_domestic_final_expenditure(sut):
    # DFE = Private consumption + GFCF: 2021: 46+23=69, 2022: 50.6+25.3=75.9
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "Domestic final expenditure")]
    assert row[2021] == pytest.approx(69.0)
    assert row[2022] == pytest.approx(75.9)


def test_expenditure_exports(sut):
    # use trans=6001: no rows in fixture → exports not present in use
    # Actually 6001 is not in the use fixture — check it's NaN
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "Exports")]
    assert pd.isna(row[2021])
    assert pd.isna(row[2022])


def test_expenditure_imports(sut):
    # supply trans=0700, bas: 2021: 60, 2022: 65 → negated
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "Imports")]
    assert row[2021] == pytest.approx(-60.0)
    assert row[2022] == pytest.approx(-65.0)


def test_expenditure_export_netto(sut):
    # Export netto = Exports (NaN) + Imports (-60/-65)
    # NaN + (-60) → min_count=1 → -60
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "Export, netto")]
    assert row[2021] == pytest.approx(-60.0)
    assert row[2022] == pytest.approx(-65.0)


def test_expenditure_gdp(sut):
    # GDP = DFE + Export netto: 2021: 69+(-60)=9, 2022: 75.9+(-65)=10.9
    result = inspect_aggregates_nominal(sut)
    row = result.data.gdp.loc[("Expenditure", "GDP")]
    assert row[2021] == pytest.approx(9.0)
    assert row[2022] == pytest.approx(10.9)


# ---------------------------------------------------------------------------
# GDP approaches can diverge (unbalanced SUT)
# ---------------------------------------------------------------------------


def test_gdp_production_and_expenditure_can_differ(sut):
    result = inspect_aggregates_nominal(sut)
    prod_gdp = result.data.gdp.loc[("Production", "GDP"), 2021]
    exp_gdp = result.data.gdp.loc[("Expenditure", "GDP"), 2021]
    # With our fixture data they should differ — just confirm both are returned
    assert not pd.isna(prod_gdp)
    assert not pd.isna(exp_gdp)


# ---------------------------------------------------------------------------
# Balance block
# ---------------------------------------------------------------------------


def test_balance_block_present(sut):
    result = inspect_aggregates_nominal(sut)
    blocks = result.data.gdp.index.get_level_values(0).unique().tolist()
    assert "Balance" in blocks


def test_balance_block_contains_single_gdp_row(sut):
    result = inspect_aggregates_nominal(sut)
    balance_labels = result.data.gdp.loc["Balance"].index.tolist()
    assert balance_labels == ["GDP"]


def test_balance_gdp_is_production_minus_expenditure(sut):
    # Production GDP: 2021=111, 2022=122.1; Expenditure GDP: 2021=9, 2022=10.9
    # Balance: 2021=102, 2022=111.2
    result = inspect_aggregates_nominal(sut)
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
    result = inspect_aggregates_nominal(sut, gdp_decomp=override)
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
        inspect_aggregates_nominal(sut, gdp_decomp=bad_override)


def test_gdp_decomp_override_missing_gdp_decomp_col_raises(sut):
    bad_override = pd.DataFrame({
        "trans":      ["0100"],
        "wrong_col":  ["Market output"],
    })
    with pytest.raises(ValueError, match="gdp_decomp"):
        inspect_aggregates_nominal(sut, gdp_decomp=bad_override)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_wrong_price_basis_raises(sut):
    from dataclasses import replace as dc_replace
    sut_prev = dc_replace(sut, price_basis="previous_year")
    with pytest.raises(ValueError, match="current_year"):
        inspect_aggregates_nominal(sut_prev)


def test_no_metadata_raises(sut):
    from dataclasses import replace as dc_replace
    sut_no_meta = dc_replace(sut, metadata=None)
    with pytest.raises(ValueError, match="metadata"):
        inspect_aggregates_nominal(sut_no_meta)


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
        inspect_aggregates_nominal(sut_no_trans)


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
        inspect_aggregates_nominal(sut_no_gdp)


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
    result = inspect_aggregates_nominal(sut_no_d2121)
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
    result = inspect_aggregates_nominal(sut_no_layers)
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
    result = inspect_aggregates_nominal(sut_merged)
    prod_labels = result.data.gdp.loc["Production"].index.tolist()
    # Only one "Total output" row, not two separate rows
    assert prod_labels.count("Total output") == 1
    # Value should be sum of 0100 and 0130: 2021: 150+30=180
    row = result.data.gdp.loc[("Production", "Total output")]
    assert row[2021] == pytest.approx(180.0)


# ---------------------------------------------------------------------------
# SUT delegate method
# ---------------------------------------------------------------------------


def test_sut_delegate_method(sut):
    result = sut.inspect_aggregates_nominal()
    assert isinstance(result, AggregatesNominalInspection)


def test_sut_delegate_method_with_override(sut, cols):
    override = pd.DataFrame({
        "trans":      ["0100",          "2000"],
        "gdp_decomp": ["Market output", "Intermediate consumption"],
    })
    result = sut.inspect_aggregates_nominal(gdp_decomp=override)
    assert isinstance(result, AggregatesNominalInspection)
