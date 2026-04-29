# SUT data format

A `SUT` object holds a collection of supply and use tables — typically a series of years — in two long-format DataFrames: `sut.supply` and `sut.use`.

## Supply and use DataFrames

Each row represents one cell: a (id, product, transaction, category) combination and its values. Column names in your data are mapped to their roles via the columns metadata file.

**Supply** holds output and import rows at basic prices only. **Use** holds intermediate and final use rows at all price levels.

Some rows have no category — imports, exports, and investment rows. These have an empty string (`""`) in the category column.

## Collections and price bases

A single `SUT` object spans all years (or other periods). The `id` column distinguishes them. Current and previous year prices are kept as **separate** `SUT` objects — they contain different data and are never mixed:

```python
sut_current   # price_basis = "current_year"
sut_previous  # price_basis = "previous_year"
```

The same metadata object can be shared between them.

## Selecting rows

`get_rows` filters a SUT by any combination of ids, products, transactions, and categories. All arguments are optional, but at least one must be provided. Filters combine with AND logic.

```python
from sutlab.sut import get_rows

get_rows(sut, products="V10100")                      # exact
get_rows(sut, products=["V10100", "V10200"])           # list
get_rows(sut, products="V10*")                         # wildcard
get_rows(sut, products="V10100:V20300")                # range (inclusive)
get_rows(sut, products="~V*")                          # negation
get_rows(sut, products=["V10*", "~V10100"])            # combined

get_rows(sut, products="V10*", transactions="2*")      # multiple dimensions

get_rows(sut, ids=2019)                                # integer id
get_rows(sut, ids=range(2015, 2020))                   # range of ids
```

`get_rows` always returns a new SUT — the original is never modified. If no rows match, empty DataFrames are returned.

## Inspecting unique codes

These functions return the unique codes present in the data as a sorted single-column DataFrame.

```python
from sutlab.sut import (
    get_codes_products,
    get_codes_transactions,
    get_ids,
    get_codes_industries,
    get_codes_individual_consumption,
    get_codes_collective_consumption,
)

get_codes_products(sut)                  # unique product codes
get_codes_transactions(sut)              # unique transaction codes
get_ids(sut)                            # unique id values

get_codes_industries(sut)                 # category codes from output (P1) and intermediate consumption (P2) rows
get_codes_individual_consumption(sut)   # category codes from individual consumption (P31) rows
get_codes_collective_consumption(sut)   # category codes from collective consumption (P32) rows
```

The three category functions require a classifications file with a `transactions` sheet including an `esa_code` column — see `metadata_format.md`.

All functions return values from both supply and use combined. Empty-category rows (imports, exports, investment rows) are excluded from the category functions.

## Balancing

### Designating the active member

`set_balancing_id` marks one collection member as the active balancing target. Balancing functions operate on that member only; inspection functions always span the full collection.

```python
from sutlab.sut import set_balancing_id

sut = set_balancing_id(sut, 2019)   # returns a new SUT — original is unchanged
sut.balancing_id                    # 2019
```

### Loading and setting balancing targets

Balancing targets are the target column totals — one per (transaction, category) combination in the SUT matrix. Supply targets are at basic prices; use targets are at purchasers' prices.

Targets are stored in one Excel file per year. Each file has the same column structure as the SUT data (using concrete column names from the columns metadata), plus a `target` column (mapped via the `target` role in the columns file). There is no id column in the file — the year is supplied when loading.

```python
from sutlab.io import load_balancing_targets_from_excel
from sutlab.sut import set_balancing_targets

targets = load_balancing_targets_from_excel(
    id_values=[2018, 2019, 2020],
    paths=[
        "data/targets_2018.xlsx",
        "data/targets_2019.xlsx",
        "data/targets_2020.xlsx",
    ],
    metadata=metadata,
)

sut = set_balancing_targets(sut, targets)
```

`set_balancing_targets` validates that the targets cover all (transaction, category) combinations present in the SUT data for each id that appears in both. `balancing_id` does not need to be set first.

`targets.supply` and `targets.use` are DataFrames with columns: id, transaction, category, target.

### Tolerances

An optional tolerances file can be loaded alongside the targets. It specifies how far each column total may deviate from its target before balancing is considered complete. Tolerances are defined at the transaction level, with optional overrides for specific (transaction, category) combinations.

The file has two sheets:

- **`transactions`** (required): one row per transaction. Columns: transaction, `rel` (relative tolerance, 0–1), `abs` (absolute tolerance).
- **`categories`** (optional): overrides for specific (transaction, category) pairs. Columns: transaction, category, `rel`, `abs`. Only combinations that need different tolerances need to be listed.

No id column in either sheet — tolerances apply across all years.

```python
targets = load_balancing_targets_from_excel(
    id_values=[2018, 2019, 2020],
    paths=["data/targets_2018.xlsx", "data/targets_2019.xlsx", "data/targets_2020.xlsx"],
    metadata=metadata,
    tolerances_path="data/tolerances.xlsx",
)

targets.tolerances_trans        # transaction-level tolerances
targets.tolerances_trans_cat    # (transaction, category) overrides, or None
```

`set_balancing_targets` validates that `tolerances_trans` covers all transaction codes present in the SUT data. `tolerances_trans_cat` is not validated for coverage.
