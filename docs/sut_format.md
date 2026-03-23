# SUT data format

A `SUT` object holds a collection of supply and use tables — typically a series of years — in two long-format DataFrames: `sut.supply` and `sut.use`.

## Supply and use DataFrames

Each row represents one cell: a (id, product, transaction, category) combination and its values. Column names in your data are mapped to their roles via the columns metadata file.

**Supply** holds output and import rows at basic prices only. **Use** holds intermediate and final use rows at all price levels.

Some use rows have no category — imports, exports, and investment rows. These have a missing value in the category column.

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
