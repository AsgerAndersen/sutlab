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
| `balancing_targets` | `BalancingTargets \| None` | Target column totals for the current balancing round |
| `balancing_config` | `BalancingConfig \| None` | Tolerances and locked cells; applies across all ids |
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
and `name` columns. Extra columns in Excel sheets are silently ignored on load.

| Field | Sheet name in Excel | Columns | Notes |
|---|---|---|---|
| `classification_names` | `classifications` | `dimension`, `classification` | Maps dimension names to classification system names |
| `products` | `products` | `code`, `name` | |
| `transactions` | `transactions` | `code`, `name`, `table`, `esa_code` | `table` is `"supply"` or `"use"` — required, validated on load |
| `industries` | `industries` | `code`, `name` | |
| `individual_consumption` | `individual_consumption` | `code`, `name` | |
| `collective_consumption` | `collective_consumption` | `code`, `name` | |

GDP decomposition mapping is **not** stored here — it is passed as an argument to
inspection functions (design deferred to inspection function design).

### BalancingTargets

Target column totals for one balancing round, split into supply and use. Mirrors the SUT
long-format **without the product dimension**. Column names match the actual column names
in the SUT DataFrames (via `SUTColumns`).

| Field | Type | Column order |
|---|---|---|
| `supply` | `pd.DataFrame` | `id, transaction, category, price_basic` |
| `use` | `pd.DataFrame` | `id, transaction, category, price_basic, [price layers], price_purchasers` |

A NaN in a price column means no target for that combination. Currently only
`price_basic` (supply) and `price_purchasers` (use) carry non-NaN values, but the
structure is ready for layer-level targets.

`set_balancing_targets` validates required columns only. Coverage validation is the
balancing function's responsibility.

### BalancingConfig

Configuration for balancing functions. Applies across all ids — not tied to a specific
`balancing_id`. Set via `set_balancing_config`.

| Field | Type | Description |
|---|---|---|
| `target_tolerances` | `TargetTolerances \| None` | Tolerances for target deviations |
| `locks` | `Locks \| None` | Cells that balancing functions must never modify |

### TargetTolerances

| Field | Type | Columns | Notes |
|---|---|---|---|
| `transactions` | `DataFrame \| None` | transaction col name, `rel`, `abs` | One row per transaction code; no id column |
| `categories` | `DataFrame \| None` | transaction col name, category col name, `rel`, `abs` | Overrides for specific (transaction, category) pairs; partial coverage |

Excel file: two optional sheets named `transactions` and `categories`.

### Locks

A cell (product, transaction, category) is locked if it matches **any** level — OR logic.

| Field | Type | Columns | Locks |
|---|---|---|---|
| `products` | `DataFrame \| None` | product col name | All cells for listed products |
| `transactions` | `DataFrame \| None` | transaction col name | All cells for listed transactions |
| `categories` | `DataFrame \| None` | transaction col name, category col name | All cells for listed (transaction, category) pairs |
| `cells` | `DataFrame \| None` | product col name, transaction col name, category col name | Specific (product, transaction, category) combinations |

Excel file: four optional sheets named `products`, `transactions`, `categories`, `cells`.
Column names in all sheets must match the actual data column names (from `SUTColumns`).
Extra columns are silently ignored on load.

### set_balancing_id / set_balancing_targets / set_balancing_config

```python
set_balancing_id(sut: SUT, balancing_id: str | int) -> SUT
set_balancing_targets(sut: SUT, targets: BalancingTargets) -> SUT
set_balancing_config(sut: SUT, config: BalancingConfig) -> SUT
```

All return a new SUT with one field updated. Do not mutate the original.

---

## DataFrame column conventions

Established by I/O functions; not enforced by the dataclass.

- **Supply**: `id, product, transaction, category, price_basic`
- **Use**: `id, product, transaction, category, price_basic, [price layers], price_purchasers`

Supply rows have `NaN` in all price layer columns and `price_purchasers`. Purchasers'
price is a use-side concept.

---

## Excel metadata file formats

### Columns file

Two columns, one row per column present in the SUT DataFrames:

| `column` | `role` |
|---|---|
| actual column name | role from the fixed list in SUTColumns |

Required roles must be present; optional roles can be absent (field set to `None`).
Extra columns in the file are silently ignored.

### Classifications file (multi-sheet)

The file as a whole is optional. Each sheet is individually optional. Extra columns in
any sheet are silently ignored — users may add notes without breaking the loader.

**`classifications` sheet**: `dimension` and `classification` columns.

**`transactions` sheet**: `code`, `name`, `table`, and `esa_code` columns. `table` must
be `"supply"` or `"use"`; `esa_code` must be a valid ESA code — both validated on load.

**All other sheets** (`products`, `industries`, `individual_consumption`,
`collective_consumption`): `code` and `name` columns.

Sheet names must match exactly (used as keys when loading).

### Balancing targets file

One file per id value (year). Same format as the SUT long-format without the product
dimension. Required columns: transaction col name, category col name, and all price
columns defined in `SUTColumns`. No id column in the file — added by the loader.

### Tolerances file (multi-sheet)

Two optional sheets:

- `transactions`: transaction col name, `rel`, `abs`
- `categories`: transaction col name, category col name, `rel`, `abs`

### Locks file (multi-sheet)

Four optional sheets: `products`, `transactions`, `categories`, `cells`. Column names
must match the actual data column names. Extra columns are silently ignored.

---

## I/O public API

- `load_metadata_from_excel(columns_path, classifications_path)` → `SUTMetadata`
- `load_sut_from_parquet(id_values, paths, metadata, price_basis)` → `SUT`
- `load_balancing_targets_from_excel(id_values, paths, metadata)` → `BalancingTargets`
- `load_balancing_config_from_excel(metadata, *, tolerances_path, locks_path)` → `BalancingConfig`

Sub-loaders are private helpers (`_` prefix). Users call only the top-level functions.

---

## Deferred design

**GDP decomposition argument** — valid `gdp_component` values are settled:
`output`, `imports`, `intermediate`, `private_consumption`, `government_consumption`,
`exports`, `investment` (total capital formation), `gross_fixed_capital_formation`,
`inventory_changes`, `acquisitions_less_disposals_of_valuables`. The last three are
sub-components of `investment` — use instead of it, not alongside. The exact interface
(DataFrame, dict, or other) is deferred to inspection function design.
