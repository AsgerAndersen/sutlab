"""
Generate minimal fixture SUT data for testing.

Run from the project root:
    uv run python data/fixtures/generate.py

Writes:
    data/fixtures/ta_l_2021.parquet   supply table, year 2021
    data/fixtures/ta_d_2021.parquet   use table, year 2021
    data/fixtures/ta_l_2022.parquet   supply table, year 2022
    data/fixtures/ta_d_2022.parquet   use table, year 2022
    data/fixtures/metadata/ta_classifications.xlsx
    data/fixtures/metadata/karakteristiske_brancher.xlsx

The fixture is small (3 products, 2 industries, 7 transaction codes, 2 years)
but covers the full SUT structure: output, imports, intermediate use, household
consumption, collective government consumption, investment, and exports.

Supply equals use for each product in each year. The GDP identity holds in
both years. Both are verified on generation — an AssertionError means the
fixture data is inconsistent.

Manual verification (basic prices):

  Year 2021
    Supply totals:      A=240,  B=180,  C=180
    Use totals:         A=240,  B=180,  C=180
    GDP (production):   output(480) - intermediate(220) = 260
    GDP (expenditure):  final_demand(380) - imports(120) = 260

  Year 2022
    Supply totals:      A=270,  B=200,  C=200
    Use totals:         A=270,  B=200,  C=200
    GDP (production):   output(540) - intermediate(240) = 300
    GDP (expenditure):  final_demand(430) - imports(130) = 300

Price layers are applied to intermediate use (2000) and household consumption
(3110) only. All basic-price values for those rows are multiples of 20, so
all layer values are exact integers:

    eng  = 10% of bas   (wholesale trade margin)
    det  =  5% of bas   (retail trade margin)
    afg  =  5% of bas   (excise taxes)
    moms = 20% of bas   (VAT)
    koeb = 1.40 x bas   (purchasers' prices)

All other transaction types have NaN for eng/det/afg/moms and koeb = bas.

Design rationale: see notes/claude/data_representation.md.
"""

import math
from pathlib import Path

import pandas as pd


FIXTURES = Path(__file__).parent
METADATA = FIXTURES / "metadata"
METADATA.mkdir(parents=True, exist_ok=True)

# Column order matches production data column names.
COLS = ["nrnr", "trans", "brch", "bas", "eng", "det", "afg", "moms", "koeb"]

NAN = float("nan")

# Price layer shares applied to intermediate use and household consumption.
ENG_SHARE  = 0.10   # wholesale trade margin
DET_SHARE  = 0.05   # retail trade margin
AFG_SHARE  = 0.05   # excise taxes
MOMS_SHARE = 0.20   # VAT


def with_layers(bas: float) -> list:
    """Return [bas, eng, det, afg, moms, koeb] with price layers applied.

    Uses standard rounding (0.5 rounds up). All bas values in the fixture
    are multiples of 20, so all results are exact integers.
    """
    eng  = math.floor(bas * ENG_SHARE  + 0.5)
    det  = math.floor(bas * DET_SHARE  + 0.5)
    afg  = math.floor(bas * AFG_SHARE  + 0.5)
    moms = math.floor(bas * MOMS_SHARE + 0.5)
    koeb = bas + eng + det + afg + moms
    return [bas, eng, det, afg, moms, koeb]


def without_layers(bas: float) -> list:
    """Return [bas, NaN, NaN, NaN, NaN, koeb=bas]. No price layers applicable."""
    return [bas, NAN, NAN, NAN, NAN, bas]


# ---------------------------------------------------------------------------
# Supply tables (ta_l)
# Only output (0100) and imports (0700). No price layers.
# Supply totals (basic prices): 2021: A=240, B=180, C=180
#                               2022: A=270, B=200, C=200
# ---------------------------------------------------------------------------

def make_supply(year: int) -> pd.DataFrame:
    """Return the supply table for the given year."""
    if year == 2021:
        rows = [
            # nrnr   trans   brch
            ["A",   "0100", "X",   *without_layers(200)],
            ["B",   "0100", "X",   *without_layers(100)],
            ["B",   "0100", "Y",   *without_layers(60)],
            ["C",   "0100", "Y",   *without_layers(120)],
            ["A",   "0700", "",    *without_layers(40)],
            ["B",   "0700", "",    *without_layers(20)],
            ["C",   "0700", "",    *without_layers(60)],
        ]
    elif year == 2022:
        rows = [
            ["A",   "0100", "X",   *without_layers(220)],
            ["B",   "0100", "X",   *without_layers(110)],
            ["B",   "0100", "Y",   *without_layers(70)],
            ["C",   "0100", "Y",   *without_layers(140)],
            ["A",   "0700", "",    *without_layers(50)],
            ["B",   "0700", "",    *without_layers(20)],
            ["C",   "0700", "",    *without_layers(60)],
        ]
    else:
        raise ValueError(f"No fixture data for year {year}.")

    return pd.DataFrame(rows, columns=COLS)


# ---------------------------------------------------------------------------
# Use tables (ta_d)
# Intermediate (2000) and household (3110) have price layers.
# All other transaction types have NaN layers and koeb = bas.
# Use totals (basic prices): 2021: A=240, B=180, C=180
#                            2022: A=270, B=200, C=200
# ---------------------------------------------------------------------------

def make_use(year: int) -> pd.DataFrame:
    """Return the use table for the given year."""
    if year == 2021:
        rows = [
            # --- Intermediate consumption (price layers applied) ---
            ["A",   "2000", "X",   *with_layers(60)],
            ["A",   "2000", "Y",   *with_layers(40)],
            ["B",   "2000", "X",   *with_layers(40)],
            ["B",   "2000", "Y",   *with_layers(20)],
            ["C",   "2000", "X",   *with_layers(40)],
            ["C",   "2000", "Y",   *with_layers(20)],
            # --- Household consumption (price layers applied) ---
            ["A",   "3110", "HH",  *with_layers(80)],
            ["B",   "3110", "HH",  *with_layers(60)],
            ["C",   "3110", "HH",  *with_layers(40)],
            # --- Government collective consumption ---
            ["A",   "3200", "GOV", *without_layers(10)],
            ["B",   "3200", "GOV", *without_layers(20)],
            ["C",   "3200", "GOV", *without_layers(20)],
            # --- Gross fixed capital formation ---
            ["A",   "5110", "",    *without_layers(10)],
            ["B",   "5110", "",    *without_layers(10)],
            ["C",   "5110", "",    *without_layers(20)],
            # --- Exports ---
            ["A",   "6001", "",    *without_layers(40)],
            ["B",   "6001", "",    *without_layers(30)],
            ["C",   "6001", "",    *without_layers(40)],
        ]
    elif year == 2022:
        rows = [
            # --- Intermediate consumption (price layers applied) ---
            ["A",   "2000", "X",   *with_layers(80)],
            ["A",   "2000", "Y",   *with_layers(40)],
            ["B",   "2000", "X",   *with_layers(40)],
            ["B",   "2000", "Y",   *with_layers(20)],
            ["C",   "2000", "X",   *with_layers(40)],
            ["C",   "2000", "Y",   *with_layers(20)],
            # --- Household consumption (price layers applied) ---
            ["A",   "3110", "HH",  *with_layers(100)],
            ["B",   "3110", "HH",  *with_layers(60)],
            ["C",   "3110", "HH",  *with_layers(60)],
            # --- Government collective consumption ---
            ["A",   "3200", "GOV", *without_layers(10)],
            ["B",   "3200", "GOV", *without_layers(20)],
            ["C",   "3200", "GOV", *without_layers(20)],
            # --- Gross fixed capital formation ---
            ["A",   "5110", "",    *without_layers(10)],
            ["B",   "5110", "",    *without_layers(10)],
            ["C",   "5110", "",    *without_layers(20)],
            # --- Exports ---
            ["A",   "6001", "",    *without_layers(30)],
            ["B",   "6001", "",    *without_layers(50)],
            ["C",   "6001", "",    *without_layers(40)],
        ]
    else:
        raise ValueError(f"No fixture data for year {year}.")

    return pd.DataFrame(rows, columns=COLS)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_balance(supply: pd.DataFrame, use: pd.DataFrame, year: int) -> None:
    """Raise AssertionError if supply != use for any product (basic prices)."""
    supply_totals = supply.groupby("nrnr")["bas"].sum()
    use_totals    = use.groupby("nrnr")["bas"].sum()
    for product in supply_totals.index:
        s = supply_totals[product]
        u = use_totals[product]
        assert s == u, (
            f"Year {year}: supply ({s}) != use ({u}) for product '{product}'"
        )


def verify_gdp(supply: pd.DataFrame, use: pd.DataFrame, year: int) -> None:
    """Raise AssertionError if GDP (production approach) != GDP (expenditure approach)."""
    output       = supply.loc[supply["trans"] == "0100", "bas"].sum()
    imports      = supply.loc[supply["trans"] == "0700", "bas"].sum()
    intermediate = use.loc[use["trans"] == "2000", "bas"].sum()

    final_demand_trans = ["3110", "3200", "5110", "6001"]
    final_demand = use.loc[use["trans"].isin(final_demand_trans), "bas"].sum()

    gdp_production   = output - intermediate
    gdp_expenditure  = final_demand - imports

    assert gdp_production == gdp_expenditure, (
        f"Year {year}: GDP production ({gdp_production}) "
        f"!= GDP expenditure ({gdp_expenditure})"
    )


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def make_classifications() -> dict[str, pd.DataFrame]:
    """Return classification tables for ta_classifications.xlsx."""
    classifications = pd.DataFrame({
        "dimension":      ["products", "transactions", "industries",
                           "individual_consumption", "collective_consumption"],
        "classification": ["FIXTURE_PRODUCTS", "FIXTURE_TRANS",
                           "FIXTURE_INDUSTRIES", "FIXTURE_IC", "FIXTURE_CC"],
    })
    products = pd.DataFrame({
        "code":        ["A",         "B",         "C"],
        "description": ["Product A", "Product B", "Product C"],
    })
    transactions = pd.DataFrame({
        "code": ["0100", "0700", "2000", "3110", "3200", "5110", "6001"],
        "description": [
            "Output at basic prices",
            "Imports",
            "Intermediate consumption",
            "Household consumption",
            "Government collective consumption",
            "Gross fixed capital formation - dwellings",
            "Exports of domestic production",
        ],
        "gdp_component": [
            "output",
            "imports",
            "intermediate",
            "private_consumption",
            "government_consumption",
            "investment",
            "exports",
        ],
    })
    industries = pd.DataFrame({
        "code":        ["X",          "Y"],
        "description": ["Industry X", "Industry Y"],
    })
    individual_consumption = pd.DataFrame({
        "code":        ["HH"],
        "description": ["Household"],
    })
    collective_consumption = pd.DataFrame({
        "code":        ["GOV"],
        "description": ["Government"],
    })
    return {
        "classifications":        classifications,
        "products":               products,
        "transactions":           transactions,
        "industries":             industries,
        "individual_consumption": individual_consumption,
        "collective_consumption": collective_consumption,
    }


def make_columns() -> pd.DataFrame:
    """Return the SUTColumns role mapping table for columns.xlsx.

    Maps each actual column name in the loaded SUT DataFrames to its
    conceptual role. This is the fixture equivalent of the two-column
    Excel table that I/O functions will use to construct a SUTColumns
    dataclass.

    The year column is added by the I/O loading function (not present
    in the raw parquet files, which are single-year).
    """
    return pd.DataFrame({
        "column": ["year", "nrnr", "trans", "brch",
                   "bas",         "koeb",
                   "eng",               "det",
                   "afg",               "moms"],
        "role":   ["id",  "product", "transaction", "category",
                   "price_basic",   "price_purchasers",
                   "wholesale_margins",        "retail_margins",
                   "product_taxes_less_subsidies", "vat"],
    })


def make_karakteristiske_brancher() -> pd.DataFrame:
    """Return characteristic industry table (primary producer per product)."""
    return pd.DataFrame({
        "nrnr": ["A", "B", "C"],
        "brch": ["X", "X", "Y"],
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    for year in [2021, 2022]:
        supply = make_supply(year)
        use    = make_use(year)

        verify_balance(supply, use, year)
        verify_gdp(supply, use, year)

        supply.to_parquet(FIXTURES / f"ta_l_{year}.parquet", index=False)
        use.to_parquet(FIXTURES / f"ta_d_{year}.parquet", index=False)

        print(f"Year {year}: supply ({len(supply)} rows), use ({len(use)} rows) -- balanced OK")

    sheets = make_classifications()
    with pd.ExcelWriter(METADATA / "ta_classifications.xlsx") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print("Metadata: ta_classifications.xlsx OK")

    karakteristiske = make_karakteristiske_brancher()
    karakteristiske.to_excel(
        METADATA / "karakteristiske_brancher.xlsx", index=False
    )
    print("Metadata: karakteristiske_brancher.xlsx OK")

    columns = make_columns()
    columns.to_excel(METADATA / "columns.xlsx", index=False)
    print("Metadata: columns.xlsx OK")


if __name__ == "__main__":
    main()
