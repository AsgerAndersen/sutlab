# Data representation

## Session: 2026-03-18 — Core SUT dataclass

### Decisions made

**Structure:** Four dataclasses in `sutlab/sut.py`:
- `PriceSpec` — column names for price values (basic, purchasers, layers list)
- `SUTColumns` — maps conceptual dimensions to actual DataFrame column names
- `SUTMetadata` — column spec + optional classification tables
- `SUT` — top-level object: year, price_basis, supply, use, optional metadata

**Key design choices:**
- Column names are not hardcoded. `SUTColumns` holds the actual column names from the
  source data. Code accesses e.g. `df[sut.metadata.columns.product]`.
- Supply DataFrame holds only the basic-prices column (plus product/transaction/category).
  Price layers are a use-side concept.
- Use DataFrame holds all price columns: basic, layers (eng/det/afg/moms etc.), purchasers.
  The layer columns are configurable via `PriceSpec.layers` — not hardcoded to Danish names.
- `price_basis` field: `"current_year"` or `"previous_year"`. These are the only two price
  bases in which SUTs are balanced. Chain-linking (deriving volume indices) is out of scope
  for now but this field sets up the distinction correctly.
- The `brch`-equivalent dimension is called `category` conceptually (the column-dimension
  of the traditional SUT matrix — industry for production/intermediate use, consumption
  function for final demand, empty for imports/exports/investment).
- `metadata` is optional on `SUT`. Functions requiring specific metadata raise informative
  errors if it is absent.
- `characteristic_industries` (product → primary industry mapping) intentionally excluded
  from `SUTMetadata` for now.

### What was deferred
- Validation logic (separate function, not yet written)
- I/O functions (loading from parquet/Excel)
- Chain-linking / volume index calculation

---

## Session: 2026-03-18 — SUT as collection, set_active

### Decisions made

**SUT is a collection, not a single-year object.** `supply` and `use` are long-format
DataFrames spanning multiple members (typically years). An extra id column (name specified
in `SUTColumns.id`) identifies which rows belong to which member.

**Rationale:** Inspection is naturally multi-year (comparing a year being balanced against
historical context). Balancing is single-year. A collection keeps both workflows in one
object.

**`balancing_id` field on `SUT`.** Marks which member is the active balancing target.
`None` if no member is active.

**`set_active(sut, balancing_id) -> SUT`.** Returns a new SUT with `balancing_id` set.
Immutable — original is unchanged. Raises informative `ValueError` if the id is not found
or if `metadata` is None.

**`year` field removed.** The id column subsumes it. The id is not required to be temporal
(could be a quarter string, a scenario name, etc.).

**`SUTColumns.id` added.** Column name for the identifier dimension.

**Column order convention.** Supply and use DataFrames should follow the order: id,
product, transaction, category, price columns. Not enforced by the dataclass — I/O
functions are responsible for establishing this order. Documented in the `SUT` docstring.

### Alternatives considered

- **Two types: SUT (single) + SUTSeries (collection)** — rejected because inspection
  functions would need the user to inject the work-in-progress SUT into the series before
  each call, or inspection would miss the latest balancing changes.
- **Collection with mutable `balancing_id`** — rejected in favour of immutable `set_active`
  to avoid accidental mutation and to allow two active years to coexist (e.g. for comparison).

### Implementation status

Implemented and tested. 8 tests in `tests/test_sut.py`, all passing.

### Verification
Confirmed working:
```python
from sutlab.sut import SUT, SUTMetadata, SUTColumns, PriceSpec
# SUT constructed from 2019 example parquet files
# supply shape (45793, 4), use shape (45780, 9)
```
