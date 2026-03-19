# SUT data representation — current state reference

This is a live current-state document. It is more detailed than CLAUDE.md but covers the
same settled decisions. Update when decisions change; do not append session logs here.

---

## Python dataclasses (`sutlab/sut.py`)

### SUT

Top-level object. Holds a **collection** of supply and use tables (typically a time
series) sharing the same structure and metadata.

| Field | Type | Description |
|---|---|---|
| `price_basis` | `"current_year" \| "previous_year"` | Price basis for the whole collection |
| `supply` | `pd.DataFrame` | Long-format, all members, basic prices only |
| `use` | `pd.DataFrame` | Long-format, all members, all price columns |
| `balancing_id` | `str \| int \| None` | Id of the member currently being balanced |
| `metadata` | `SUTMetadata \| None` | Column specs and optional classifications |

Current and previous year prices are kept as **separate SUT objects**. The same metadata
object can be shared between them.

Collection design: inspection functions span the full collection; balancing functions
operate on the member identified by `balancing_id`. This keeps the multi-year series
available as context during single-year balancing.

### SUTMetadata

| Field | Type | Description |
|---|---|---|
| `columns` | `SUTColumns` | Required |
| `classifications` | `SUTClassifications \| None` | Optional |

### SUTColumns

Maps conceptual roles to actual DataFrame column names. Loaded from a two-column Excel
table (`column`, `role`); this dataclass is the internal Python representation.

**Required fields** (no default):

| Field | Role |
|---|---|
| `id` | Identifies which collection member (year/quarter) a row belongs to |
| `product` | Product dimension |
| `transaction` | Transaction code |
| `category` | Industry, consumption function, or similar — the column dimension of the SUT matrix |
| `price_basic` | Values at basic prices |
| `price_purchasers` | Values at purchasers' prices |

**Optional fields** (default `None`):

| Field | Role |
|---|---|
| `trade_margins` | Total trade margins (if not split into wholesale/retail) |
| `wholesale_margins` | Wholesale trade margins |
| `retail_margins` | Retail trade margins |
| `transport_margins` | Transport margins |
| `product_taxes` | Taxes on products (gross, excluding VAT) |
| `product_subsidies` | Subsidies on products (if recorded separately) |
| `product_taxes_less_subsidies` | Taxes less subsidies on products (net) |
| `vat` | VAT |

### SUTClassifications

All fields `pd.DataFrame | None`, default `None`. All classification tables have `code`
and `name` columns.

| Field | Sheet name in Excel | Columns | Notes |
|---|---|---|---|
| `classification_names` | `classifications` | `dimension`, `classification` | Maps dimension names to classification system names |
| `products` | `products` | `code`, `name` | |
| `transactions` | `transactions` | `code`, `name`, `table` | `table` is `"supply"` or `"use"` — required, validated on load |
| `industries` | `industries` | `code`, `name` | |
| `individual_consumption` | `individual_consumption` | `code`, `name` | |
| `collective_consumption` | `collective_consumption` | `code`, `name` | |

GDP decomposition mapping is **not** stored here — it is passed as an argument to
inspection functions (design deferred to inspection function design).

### mark_for_balancing

```python
mark_for_balancing(sut: SUT, balancing_id: str | int) -> SUT
```

Returns a new SUT with `balancing_id` set. Does not mutate the original. Raises
`ValueError` with an informative message if `balancing_id` is not found.

---

## DataFrame column conventions

Established by I/O functions; not enforced by the dataclass.

- **Supply**: `id, product, transaction, category, price_basic`
- **Use**: `id, product, transaction, category, price_basic, [price layers], price_purchasers`

---

## Excel metadata file formats

### Columns file

Two columns, one row per column present in the SUT DataFrames:

| `column` | `role` |
|---|---|
| actual column name | role from the fixed list in SUTColumns |

Required roles must be present; optional roles can be absent (field set to `None`).

### Classifications file (multi-sheet)

The file as a whole is optional. Each sheet is individually optional.

**`classifications` sheet**: `dimension` and `classification` columns.

**`transactions` sheet**: `code`, `name`, and `table` columns. `table` is required and
must be `"supply"` or `"use"` — validated when loading metadata.

**All other sheets** (`products`, `industries`, `individual_consumption`,
`collective_consumption`): `code` and `name` columns.

Sheet names must match exactly (used as keys when loading).

---

## Deferred design

**GDP decomposition argument** — valid `gdp_component` values are settled:
`output`, `imports`, `intermediate`, `private_consumption`, `government_consumption`,
`exports`, `investment` (total capital formation), `gross_fixed_capital_formation`,
`inventory_changes`, `acquisitions_less_disposals_of_valuables`. The last three are
sub-components of `investment` — use instead of it, not alongside. The exact interface
(DataFrame, dict, or other) is deferred to inspection function design.
