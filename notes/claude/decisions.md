# Decisions log

Append-only. Each entry: date, decision, brief rationale.

---

- **2026-03-18**: SUT is a collection (multi-member long-format DataFrames) with a
  `balancing_id` field. Inspection spans the full collection; balancing operates on the
  marked member only. Rationale: inspection is naturally multi-year; balancing is
  single-year; the collection avoids forcing year arguments into every balancing call.

- **2026-03-18**: `PriceSpec` eliminated. `SUTColumns` restructured with explicit named
  fields per price-layer role. `SUTClassifications` added as a nested dataclass inside
  `SUTMetadata`, replacing five flat classification fields.

- **2026-03-18**: `set_active` renamed to `mark_for_balancing` — more concrete, reflects
  tagging rather than starting a process.

- **2026-03-18**: Current and previous year's prices kept as separate `SUT` objects.
  Same metadata object can be reused for both.

- **2026-03-18**: `price_basis` stays as `Literal["current_year", "previous_year"]`.
  `'fixed'` and `'chained'` not added — out of scope and easy to extend when needed.

- **2026-03-19**: Classification table text-name column renamed `description` → `name`.
  `description` implied prose; `name` reflects intent: the official standard text name.

- **2026-03-19**: Excel metadata file formats settled — see `metadata_format.md`
  (user-facing) and `notes/claude/data_representation.md` (internal reference).

- **2026-03-19**: `gdp_component` removed from `SUTClassifications.transactions`.
  GDP decomposition mapping is analysis-time input, not SUT metadata. Rationale: chaining
  and aggregation do not commute — GDP must be computed at the right aggregation level
  before chaining. Full design deferred to inspection function design. Valid
  `gdp_component` values settled for future use: `output`, `imports`, `intermediate`,
  `private_consumption`, `government_consumption`, `exports`, `investment`,
  `gross_fixed_capital_formation`, `inventory_changes`,
  `acquisitions_less_disposals_of_valuables`. The last three are sub-components of
  `investment` — use instead of it, not alongside.

- **2026-03-18**: Balancing functions will filter `sut.supply` and `sut.use` to the
  rows matching `balancing_id`, operate on those, and return a new SUT with updated
  DataFrames. The rest of the collection is carried along untouched.

- **2026-03-19**: Notes structure reorganised. Decisions log moved to this file.
  `data_representation.md` rewritten as a clean current-state reference. CLAUDE.md
  no longer requires reading all notes at session start — consult proactively when
  relevant.

- **2026-03-19**: I/O module placed at `sutlab/io.py` (flat, not a subpackage). Public
  API function names: `load_metadata_from_excel`, `load_metadata_columns_from_excel`,
  `load_metadata_classifications_from_excel`, `load_sut_from_parquet`. Naming convention:
  `load_<noun>_from_<source>`, hierarchically structured so related functions group in
  autocomplete. Internal helpers can be abstract; this principle applies to the public API only.

- **2026-03-19**: Excel metadata loading standardises data on read: leading/trailing
  whitespace stripped from all string columns in all sheets. No other normalisation
  (no case folding). All columns in all metadata sheets read as strings (`dtype=str`)
  to prevent integer inference on values like `2021`.

- **2026-03-19**: `transactions` classification sheet gains a required `table` column
  (`"supply"` or `"use"`). Validated when loading metadata — error raised immediately
  if column is absent or contains invalid values. Supply/use transaction lists are
  derived on the fly from `classifications.transactions` where needed (not stored
  redundantly on `SUTMetadata`).

- **2026-03-19**: Raw SUT parquet files contain both supply and use rows in a single
  file. `ta_l_YEAR` = current year prices; `ta_d_YEAR` = previous year prices.
  `load_sut_from_parquet` loads one price basis at a time. Paths supplied as
  `dict[id_value, path]` for supply and use; id column name always explicit via
  `id_col` parameter.

- **2026-03-19**: Fixture data redesigned. Combined supply+use format (single parquet
  file per year, matching real data). One year (2021, current prices). Four products
  (A, B, C, T), three industries (X, Y, Z). Transactions: 0100, 0700, 2000, 3110,
  3200, 5139, 5200, 6001. Price layers: `ava` (trade_margins) and `moms` (vat) only.
  Product T is trade services produced by industry Z; its output equals the sum of all
  ava values across use rows. T has no explicit use rows — its use is distributed
  implicitly via the ava column. ava rates vary at the cell level (product × brch).

- **2026-03-19**: GDP identity at market prices verified in `generate.py`. Expenditure
  approach: final demand at purchasers' prices minus imports at basic prices.
  Production approach: domestic output at basic prices minus IC at purchasers' prices
  plus VAT. Trade margins cancel (included in trade industry output and subtracted
  again in IC at purchasers' prices), so only VAT on final demand remains as the wedge
  between GDP at basic and market prices.

- **2026-03-23**: `get_rows` added to `sutlab/sut.py` as the single public selection
  function. Filters supply and use by ids, products, transactions, and/or categories
  (AND logic). Pattern syntax: exact, wildcard (`*`), natural-sort range (`:`),
  negation (`~`). Individual per-dimension functions dropped — `get_rows` with keyword
  arguments is simpler for the target user base. `balancing_id` set to `None` on
  result — balancing a sub-SUT is not supported. Private helpers: `_match_codes`,
  `_code_matches_pattern`, `_natural_sort_key`, `_filter_sut_by_column`,
  `_filter_sut_by_ids`.

- **2026-03-23**: `get_product_codes`, `get_transaction_codes`, `get_ids` added — return
  unique values from the data as a sorted single-column DataFrame. `get_category_codes`
  dropped in favour of three type-specific functions: `get_industry_codes` (P1/P2),
  `get_individual_consumption_codes` (P31), `get_collective_consumption_codes` (P32).
  All three require `metadata.classifications.transactions` with an `esa_code` column.

- **2026-03-23**: `esa_code` added as a required column on the `transactions`
  classification sheet. Maps institution-specific transaction codes to standardised ESA
  codes. Valid values: P1, P2, P3, P31, P32, P51g, P52, P53, P6, P7. Validated on load.
  Enables type-specific category code lookup functions.

- **2026-03-23**: Method interface on `SUT` (pandas-style `sut.get_rows(...)`) deferred.
  Decision: if adopted, implement as thin methods delegating to free functions — no logic
  changes needed. Free functions remain the canonical implementation.

- **2026-03-24**: `inspect_products(sut, products) → ProductInspection` implemented in
  `sutlab/inspect.py`. Uses same selection API as `get_rows` for the `products` argument.
  Returns a `ProductInspection` dataclass with two layers: `result.data.<table>` for raw
  DataFrames, `result.<table>` for pandas Styler (auto-renders in Jupyter).

- **2026-03-24**: `ProductInspection` contains 9 tables:
  - `balance` — wide table, ids as columns, 4-level MultiIndex
    `(product, product_txt, transaction, transaction_txt)`. Supply transactions → Total
    supply → use transactions → Total use → Balance. Basic prices only.
  - `supply_detail` / `use_detail` — category breakdown for transactions with non-empty
    category column. 6-level MultiIndex `(product, product_txt, transaction,
    transaction_txt, category, category_txt)`. Sorted MultiIndex. Supply/use split from
    `sut.supply` / `sut.use` directly.
  - `balance_distribution` — same structure as `balance` minus the Balance row. Supply
    rows normalised by Total supply per year; use rows by Total use per year.
  - `supply_detail_distribution` / `use_detail_distribution` — same structure as detail
    tables. Each value divided by the product's total across all transactions/categories
    per year (column-wise normalisation within each product block).
  - `balance_growth` / `supply_detail_growth` / `use_detail_growth` — year-on-year
    change: `(value[t] - value[t-1]) / value[t-1]`, stored as a fraction (0.05 = 5%
    growth). First year is NaN. Division by zero yields NaN (inf replaced). Balance row
    excluded from balance_growth.

- **2026-03-24**: `product_txt` always present as a MultiIndex level (empty string when
  no product classification loaded). Consistent structure regardless of metadata.

- **2026-03-24**: Transaction classification required for `inspect_products` (needs
  `name` column for labels). Product classification optional — `product_txt` is empty
  string when absent. Category labels looked up via `esa_code` on the transactions
  classification, mapping to `industries`, `individual_consumption`, or
  `collective_consumption` classification tables.

- **2026-03-24**: Styler formatting rules: raw value tables use European number format
  (e.g. `1.234.567,8`, one decimal); distribution and growth tables use European
  percentage format (e.g. `5,0%`, one decimal). NaN displayed as empty string.

- **2026-03-24**: Balance table Styler: supply rows green, use rows blue, summary rows
  (Total supply, Total use) bold with more saturated shade. Balance row neutral grey.
  Alternating shades within supply and use blocks. Colours extend to `transaction` and
  `transaction_txt` index levels (accounting for pandas sparse MultiIndex rendering —
  borders/CSS placed on first row of merged spans). Product separator: `2px solid #999`.

- **2026-03-24**: Detail table Styler: supply_detail all green, use_detail all blue.
  Alternating shades within each `(product, transaction)` block. Transaction header
  colour (slightly more saturated) applied to `transaction`/`transaction_txt` index
  levels. Separator between transaction blocks: `1px solid #ccc`; between product
  blocks: `2px solid #999`.

- **2026-03-24**: `price_layers`, `price_layers_distribution`, `price_layers_growth`
  added to `ProductInspection` / `ProductInspectionData`. MultiIndex:
  `(product, product_txt, price_layer, transaction, transaction_txt)`. `price_layer`
  values are the actual use DataFrame column names for intermediate layers (non-`None`
  optional roles in `SUTColumns`, excluding `price_basic` and `price_purchasers`),
  in use DataFrame column order. Transactions with all-zero values for a layer are
  omitted. Each `(product, layer)` block ends with a `("", "Total")` summary row.

- **2026-03-24**: `price_layer_shares` added to `ProductInspection`. Same structure as
  `price_layers`. Each value divided by total use at purchasers' prices for that product
  and year (sum of `price_purchasers` across all use rows). Styled and formatted as
  percentages, same as the other price layer tables.

- **2026-03-24**: `price_layers` Styler: cycling palette (amber, purple, teal, rose)
  with light data shades. Within each block: `price_layer` index uses `index_total`
  shade (block header); `transaction`/`transaction_txt` index alternates between the
  two lighter index shades (matching the row color, like the balance table); Total row
  is bold with more saturated shade throughout. Separators: `1px solid #ccc` between
  layer blocks, `2px solid #999` between product blocks.
