"""
Generate fixture SUT data for testing.

Run from the project root:
    uv run python data/fixtures/generate.py

Writes:
    data/fixtures/ta_l_2021.parquet          combined supply+use, year 2021, current prices
    data/fixtures/ta_targets_2021.xlsx       balancing targets for 2021
    data/fixtures/ta_tolerances.xlsx         balancing tolerances (all years)
    data/fixtures/metadata/columns.xlsx
    data/fixtures/metadata/ta_classifications.xlsx
    data/fixtures/metadata/karakteristiske_brancher.xlsx

The fixture covers four products (A, B, C, T), three industries (X, Y, Z),
and the following transactions:

    Supply: 0100 (output), 0700 (imports)
    Use:    2000 (intermediate consumption), 3110 (household consumption),
            3200 (government collective consumption), 5139 (GFCF — other),
            5200 (changes in inventories), 6001 (exports)

Product T is produced by the trade industry (Z). Its output equals the total
trade margins (ava) distributed across all use rows. T has no explicit use
rows — its use is recorded implicitly via the ava column.

Price layers:
    ava (trade_margins):  applied to 2000, 3110, and 3200; rate varies by cell
    moms (vat):           applied to 3110 only, fixed at 20% of bas
    koeb = bas + ava + moms (NaN layers treated as zero)

Supply equals use in basic prices for each product. GDP identity holds.
Verified on generation — an AssertionError means the fixture is inconsistent.

Manual verification (basic prices):
    Supply totals:  A=140, B=140, C=140, T=32
    Use totals:     A=140, B=140, C=140
    T use is implicit: sum of all ava values = 2+3+2+4+1+2 + 4+6+2 + 2+3+1 = 32

GDP at market prices:
    Expenditure:  final demand (purchasers') - imports = 342 - 60 = 282
    Production:   output - IC (purchasers') + VAT = 392 - 134 + 24 = 282
"""

from pathlib import Path

import pandas as pd


FIXTURES = Path(__file__).parent
METADATA = FIXTURES / "metadata"
METADATA.mkdir(parents=True, exist_ok=True)

NAN = float("nan")

COLS = ["nrnr", "trans", "brch", "bas", "ava", "moms", "koeb"]


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def no_layers(nrnr: str, trans: str, brch: str, bas: float) -> list:
    """Row with no price layers: ava=NaN, moms=NaN, koeb=bas."""
    return [nrnr, trans, brch, bas, NAN, NAN, bas]


def ava_only(nrnr: str, trans: str, brch: str, bas: float, ava: float) -> list:
    """Row with trade margin only: moms=NaN, koeb=bas+ava."""
    return [nrnr, trans, brch, bas, ava, NAN, bas + ava]


def ava_and_moms(
    nrnr: str, trans: str, brch: str, bas: float, ava: float, moms: float
) -> list:
    """Row with trade margin and VAT: koeb=bas+ava+moms."""
    return [nrnr, trans, brch, bas, ava, moms, bas + ava + moms]


# ---------------------------------------------------------------------------
# SUT data
# ---------------------------------------------------------------------------

def make_sut_2021() -> pd.DataFrame:
    """Return the combined supply+use table for 2021 at current prices.

    Product T (trade services) appears only on the supply side. Its output
    equals the total trade margins distributed across use rows via the ava
    column (32 = 14 on intermediate + 12 on household + 6 on government).
    """
    rows = [
        # --- Supply: output (0100) ---
        no_layers("A", "0100", "X",  120),
        no_layers("B", "0100", "X",   80),
        no_layers("B", "0100", "Y",   40),
        no_layers("C", "0100", "Y",  120),
        no_layers("T", "0100", "Z",   32),  # trade industry output = sum of all ava

        # --- Supply: imports (0700) ---
        no_layers("A", "0700", "",    20),
        no_layers("B", "0700", "",    20),
        no_layers("C", "0700", "",    20),

        # --- Use: intermediate consumption (2000) --- ava rate varies by cell ---
        ava_only("A", "2000", "X",    20,  2),  # ava = 10%
        ava_only("A", "2000", "Y",    20,  3),  # ava = 15%
        ava_only("B", "2000", "X",    20,  2),  # ava = 10%
        ava_only("B", "2000", "Y",    20,  4),  # ava = 20%
        ava_only("C", "2000", "X",    20,  1),  # ava =  5%
        ava_only("C", "2000", "Y",    20,  2),  # ava = 10%

        # --- Use: household consumption (3110) --- ava varies by product, moms = 20% ---
        ava_and_moms("A", "3110", "HH",   40,  4,  8),  # ava = 10%, moms = 20%
        ava_and_moms("B", "3110", "HH",   40,  6,  8),  # ava = 15%, moms = 20%
        ava_and_moms("C", "3110", "HH",   40,  2,  8),  # ava =  5%, moms = 20%

        # --- Use: government collective consumption (3200) --- ava varies by product ---
        ava_only("A", "3200", "GOV",  20,  2),  # ava = 10%
        ava_only("B", "3200", "GOV",  20,  3),  # ava = 15%
        ava_only("C", "3200", "GOV",  20,  1),  # ava =  5%

        # --- Use: gross fixed capital formation --- other (5139) ---
        no_layers("A", "5139", "",    10),
        no_layers("B", "5139", "",    10),
        no_layers("C", "5139", "",    10),

        # --- Use: changes in inventories (5200) ---
        no_layers("A", "5200", "",    10),
        no_layers("B", "5200", "",    10),
        no_layers("C", "5200", "",    10),

        # --- Use: exports (6001) ---
        no_layers("A", "6001", "",    20),
        no_layers("B", "6001", "",    20),
        no_layers("C", "6001", "",    20),
    ]
    return pd.DataFrame(rows, columns=COLS)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

_SUPPLY_TRANS = {"0100", "0700"}


def verify_balance(df: pd.DataFrame) -> None:
    """Raise AssertionError if supply != use for any product (basic prices).

    For A, B, C: checks that output+imports == sum of all use rows.
    For T: checks that output == sum of all ava values (implicit use).
    """
    supply_df = df[df["trans"].isin(_SUPPLY_TRANS)]
    use_df = df[~df["trans"].isin(_SUPPLY_TRANS)]

    supply_by_product = supply_df.groupby("nrnr")["bas"].sum()
    use_by_product = use_df.groupby("nrnr")["bas"].sum()

    for product in ["A", "B", "C"]:
        s = supply_by_product[product]
        u = use_by_product[product]
        assert s == u, f"Product '{product}': supply ({s}) != use ({u})"

    t_supply = supply_by_product["T"]
    total_ava = use_df["ava"].sum()  # NaN skipped by default
    assert t_supply == total_ava, (
        f"Product 'T': supply ({t_supply}) != sum of ava ({total_ava})"
    )


def verify_gdp(df: pd.DataFrame) -> None:
    """Raise AssertionError if GDP expenditure != GDP production at market prices.

    Expenditure: final demand at purchasers' prices minus imports at basic prices.
    Production:  domestic output at basic prices minus IC at purchasers' prices
                 plus VAT. Trade margins cancel (included in both output of T
                 and IC at purchasers' prices), so only VAT on final demand
                 remains as the wedge between basic and market prices.
    """
    supply_df = df[df["trans"].isin(_SUPPLY_TRANS)]
    use_df = df[~df["trans"].isin(_SUPPLY_TRANS)]

    # Expenditure approach
    final_demand_trans = {"3110", "3200", "5139", "5200", "6001"}
    final_demand = use_df[use_df["trans"].isin(final_demand_trans)]["koeb"].sum()
    imports = supply_df[supply_df["trans"] == "0700"]["bas"].sum()
    gdp_expenditure = final_demand - imports

    # Production approach
    output = supply_df[supply_df["trans"] == "0100"]["bas"].sum()
    ic_basic = use_df[use_df["trans"] == "2000"]["bas"].sum()
    ic_ava = use_df[use_df["trans"] == "2000"]["ava"].sum()  # NaN skipped
    ic_purchasers = ic_basic + ic_ava
    vat = use_df["moms"].sum()  # NaN skipped
    gdp_production = output - ic_purchasers + vat

    assert gdp_expenditure == gdp_production, (
        f"GDP expenditure ({gdp_expenditure}) != GDP production ({gdp_production})"
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
        "nrnr":     ["A",         "B",         "C",         "T"],
        "nrnr_txt": ["Product A", "Product B", "Product C", "Trade services"],
    })
    transactions = pd.DataFrame({
        "trans": ["0100", "0700", "2000", "3110", "3200", "5139", "5200", "6001"],
        "trans_txt": [
            "Output at basic prices",
            "Imports",
            "Intermediate consumption",
            "Household consumption",
            "Government collective consumption",
            "Gross fixed capital formation - other",
            "Changes in inventories",
            "Exports of domestic production",
        ],
        "table":    ["supply", "supply", "use",  "use",  "use",  "use",   "use",  "use"],
        "esa_code": ["P1",     "P7",     "P2",   "P31",  "P32",  "P51g",  "P52",  "P6"],
    })
    industries = pd.DataFrame({
        "brch":     ["X",          "Y",          "Z"],
        "brch_txt": ["Industry X", "Industry Y", "Trade industry"],
    })
    individual_consumption = pd.DataFrame({
        "brch":     ["HH"],
        "brch_txt": ["Households"],
    })
    collective_consumption = pd.DataFrame({
        "brch":     ["GOV"],
        "brch_txt": ["Government"],
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
    conceptual role. The year column is added by the I/O loading function
    (not present in the raw parquet files, which are single-year).
    """
    return pd.DataFrame({
        "column": ["year", "nrnr",    "trans",        "brch",
                   "bas",           "koeb",
                   "ava",           "moms"],
        "role":   ["id",  "product", "transaction",   "category",
                   "price_basic",   "price_purchasers",
                   "trade_margins", "vat"],
    })


def make_targets_2021() -> pd.DataFrame:
    """Return balancing targets for 2021.

    One row per (trans, brch) combination. No id column — the loader adds
    the year when loading. Mirrors the combined SUT long format without the
    product dimension: columns are trans, brch, bas, ava, moms, koeb.

    Supply rows have a non-NaN value in bas (basic prices) only.
    Use rows have a non-NaN value in koeb (purchasers' prices) only.
    All other price cells are NaN.

    Values are deliberately slightly different from the actual column totals
    in the fixture data to simulate a realistic balancing scenario.

    Actual totals for reference:
        supply: 0100/X=200, 0100/Y=160, 0100/Z=32, 0700/""=60
        use:    2000/X=65,  2000/Y=69,  3110/HH=156, 3200/GOV=66,
                5139/""=30, 5200/""=30, 6001/""=60
    """
    NAN = float("nan")
    #            trans     brch    bas   ava   moms   koeb
    rows = [
        # supply targets — only bas is non-NaN
        ["0100", "X",   202,  NAN,  NAN,  NAN],
        ["0100", "Y",   158,  NAN,  NAN,  NAN],
        ["0100", "Z",    33,  NAN,  NAN,  NAN],
        ["0700", "",     62,  NAN,  NAN,  NAN],
        # use targets — only koeb is non-NaN
        ["2000", "X",   NAN,  NAN,  NAN,   64],
        ["2000", "Y",   NAN,  NAN,  NAN,   71],
        ["3110", "HH",  NAN,  NAN,  NAN,  160],
        ["3200", "GOV", NAN,  NAN,  NAN,   65],
        ["5139", "",    NAN,  NAN,  NAN,   28],
        ["5200", "",    NAN,  NAN,  NAN,   32],
        ["6001", "",    NAN,  NAN,  NAN,   58],
    ]
    return pd.DataFrame(rows, columns=["trans", "brch", "bas", "ava", "moms", "koeb"])


def make_tolerances() -> dict[str, pd.DataFrame]:
    """Return tolerance tables for ta_tolerances.xlsx.

    tolerances_trans: one row per transaction, covering all 8 transactions.
    tolerances_trans_cat: a few (trans, brch) overrides — only 0100/X, 2000/Y,
    and 3110/HH, to show that not all combinations need to be listed.
    """
    transactions = pd.DataFrame({
        "trans": ["0100", "0700", "2000", "3110", "3200", "5139", "5200", "6001"],
        "rel":   [0.02,   0.02,   0.02,   0.02,   0.02,   0.02,   0.02,   0.02],
        "abs":   [5.0,    3.0,    5.0,    5.0,    3.0,    2.0,    2.0,    3.0],
    })
    categories = pd.DataFrame({
        "trans": ["0100", "2000", "3110"],
        "brch":  ["X",    "Y",    "HH"],
        "rel":   [0.01,   0.03,   0.02],
        "abs":   [3.0,    7.0,    10.0],
    })
    return {"transactions": transactions, "categories": categories}


def make_locks() -> dict[str, pd.DataFrame]:
    """Return lock tables for balancing_locks.xlsx.

    Locks product C (all transactions/categories) and transactions 3200 and
    6001 (all products/categories). trans_cat and cells sheets are absent.
    """
    products = pd.DataFrame({"nrnr": ["C"]})
    transactions = pd.DataFrame({"trans": ["3200", "6001"]})
    return {"products": products, "transactions": transactions}


def make_karakteristiske_brancher() -> pd.DataFrame:
    """Return characteristic industry table (primary producer per product)."""
    return pd.DataFrame({
        "nrnr": ["A", "B", "C", "T"],
        "brch": ["X", "X", "Y", "Z"],
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sut = make_sut_2021()
    verify_balance(sut)
    verify_gdp(sut)
    sut.to_parquet(FIXTURES / "ta_l_2021.parquet", index=False)
    print(f"ta_l_2021.parquet: {len(sut)} rows -- balanced OK")

    targets = make_targets_2021()
    targets.to_excel(FIXTURES / "ta_targets_2021.xlsx", index=False)
    print(f"ta_targets_2021.xlsx: {len(targets)} rows")

    tolerances = make_tolerances()
    with pd.ExcelWriter(FIXTURES / "ta_tolerances.xlsx") as writer:
        for sheet_name, df in tolerances.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print("ta_tolerances.xlsx OK")

    locks = make_locks()
    with pd.ExcelWriter(FIXTURES / "balancing_locks.xlsx") as writer:
        for sheet_name, df in locks.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print("balancing_locks.xlsx OK")

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
