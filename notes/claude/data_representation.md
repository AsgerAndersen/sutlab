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

### Verification
Confirmed working:
```python
from sutlab.sut import SUT, SUTMetadata, SUTColumns, PriceSpec
# SUT constructed from 2019 example parquet files
# supply shape (45793, 4), use shape (45780, 9)
```
