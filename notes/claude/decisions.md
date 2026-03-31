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

- **2026-03-24**: `mark_for_balancing` renamed to `set_balancing_id` — consistent with
  the `set_*` naming convention established for functions that return a new SUT with one
  field updated (e.g. `set_balancing_targets`).

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

- **2026-03-24**: `price_layers_shares` added to `ProductInspection`. Same structure as
  `price_layers`. Each value divided by total use at purchasers' prices for that product
  and year (sum of `price_purchasers` across all use rows). Styled and formatted as
  percentages, same as the other price layer tables.

- **2026-03-24**: `price_layers` Styler: cycling palette (amber, purple, teal, rose)
  with light data shades. Within each block: `price_layer` index uses `index_total`
  shade (block header); `transaction`/`transaction_txt` index alternates between the
  two lighter index shades (matching the row color, like the balance table); Total row
  is bold with more saturated shade throughout. Separators: `1px solid #ccc` between
  layer blocks, `2px solid #999` between product blocks.

- **2026-03-25**: Balance table updated to show both sides at purchasers' prices (user
  feedback after showing the functionality). Supply transactions remain at basic prices;
  a new "Price layers" row is inserted between supply transactions and "Total supply",
  showing the total of all intermediate price layers from the use side (sum of
  `price_purchasers - price_basic` across all use rows for that product and year).
  "Total supply" = supply basic total + price layers. Use transaction rows and "Total
  use" are now at purchasers' prices. "Total use" styled bold with `supply_total` green
  shade. "Price layers" row uses the regular alternating supply colour (not bold, not
  the total shade).

- **2026-03-25**: `inspect_products` gains an optional `ids` argument (single value,
  list, or range) to restrict which collection members appear as columns in all 13
  tables. Default `None` = all ids. Unknown ids raise a `ValueError` with available
  ids listed. Ordering follows the original collection order, not the request order.

- **2026-03-25**: `use_detail` values are now at purchasers' prices (previously basic
  prices). `_build_detail_df` takes a `price_col` parameter; supply_detail passes
  `price_basic`, use_detail passes `price_purchasers`.

- **2026-03-25**: Detail tables (`supply_detail`, `use_detail`) gain a per-product
  summary row at the bottom of each product block: "Total supply" and "Total use"
  respectively. MultiIndex: `(product, product_txt, "", total_label, "", "")`. Summary
  rows are appended after `sort_index()` so they always appear last. Styled bold with
  the total colour; excluded from distribution denominators.

- **2026-03-25**: Uncategorized transactions (empty category column) are included in
  detail tables. Per-transaction logic: if a transaction has any categorized rows, only
  those are shown; if a transaction has no categorized rows (e.g. exports), it appears
  as a single row with `category=""`. Aggregated across all rows for that transaction
  when the category is empty.

- **2026-03-26**: `price_layers_shares` renamed to `price_layers_rates`. Computation
  changed from "share of total purchasers' price" to step-wise rate: each layer value
  divided by the cumulative price just before it is added (basic + all preceding layers).
  Rates are computed per transaction row (not product-level). Total rows removed from
  `price_layers_rates` — they are not meaningful as rates. Renamed on `ProductInspection`,
  `ProductInspectionData`, and in all tests and docs.

- **2026-03-26**: `compute_price_layer_rates(sut, aggregation_level)` added in new
  module `sutlab/compute.py`. General-purpose function for use both in inspection and
  post-balancing validation. Returns long-format wide-per-layer DataFrame with `id` first
  and sorted by key columns. `aggregation_level`: `"product"`, `"transaction"`, or
  `"category"`. Hardcoded Danish default denominators (`_DEFAULT_DENOMINATORS` dict):
  `wholesale_margins→[basic]`, `retail_margins→[basic, wholesale]`,
  `product_taxes_less_subsidies→[basic, wholesale, retail]`,
  `vat→[basic, wholesale, retail, ptls]`. Raises `ValueError` for layers present in data
  but not in `_DEFAULT_DENOMINATORS` — non-Danish layer structures not yet supported.
  Filtering to specific products should be done via `get_rows` before calling (performance).
  Product-specific denominator overrides deferred to future metadata design.

- **2026-03-26**: `price_layers_detailed`, `price_layers_detailed_distribution`,
  `price_layers_detailed_growth`, `price_layers_detailed_rates` added to
  `ProductInspection` / `ProductInspectionData`. 7-level MultiIndex:
  `(product, product_txt, price_layer, transaction, transaction_txt, category, category_txt)`.
  `price_layers_detailed` totals match the corresponding `price_layers` totals exactly.
  `price_layers_detailed_rates` has no Total rows; rates computed at `(transaction, category)`
  level via `compute_price_layer_rates(..., "category")`.
  Distribution/growth builders reused unchanged (operate only on levels present in both
  5- and 7-level indexed tables).

- **2026-03-26**: Removed hardcoded `overflow-y: auto; max-height: 600px` from all four
  styling functions (`_style_balance_table`, `_style_detail_table`,
  `_style_price_layers_table`, `_style_price_layers_detailed_table`). These constraints
  were causing unwanted inner scrollbars in all styled output tables. Tables now render
  at full height; scrolling is handled by the notebook environment only.

- **2026-03-26**: Output cell height control investigated and abandoned for now. Attempted:
  (1) CSS injection via `IPython.display.HTML` — sandboxed in JupyterLab, no effect;
  (2) JavaScript injection via `IPython.display.Javascript` with multiple CSS selectors —
  no effect (likely VS Code Jupyter renders differently from JupyterLab);
  (3) `output_height` parameter on `inspect_products` wrapping Styler HTML in a scrollable
  div — not working well. All three approaches removed. User will configure output height
  via VS Code notebook settings if needed.

- **2026-03-26**: `BalancingTargets` format changed. Supply and use DataFrames now mirror
  the SUT long-format without the product dimension: same column names (via `SUTColumns`),
  same price columns. Supply column order: `id, transaction, category, price_basic`. Use
  column order: `id, transaction, category, price_basic, [price layers], price_purchasers`.
  NaN in a price column means no target for that combination. Currently only `price_basic`
  (supply) and `price_purchasers` (use) carry non-NaN values. The `target` role removed
  from `SUTColumns`.

- **2026-03-26**: `set_balancing_targets` simplified — validates required columns only,
  no longer checks (transaction, category) coverage. Coverage validation is the
  balancing function's responsibility.

- **2026-03-26**: Tolerances removed from `BalancingTargets`. New `BalancingConfig`
  dataclass added to `SUT` (field `balancing_config`, set via `set_balancing_config`).
  `BalancingConfig` has two fields: `target_tolerances: TargetTolerances | None` and
  `locks: Locks | None`.

- **2026-03-26**: `TargetTolerances` dataclass: `transactions` (transaction-level
  tolerances; columns: transaction col name, `rel`, `abs`) and `categories` (overrides
  for specific transaction-category pairs; columns: transaction col name, category col
  name, `rel`, `abs`). No id column — applies across all years.

- **2026-03-26**: `Locks` dataclass: `products`, `transactions`, `categories`, `cells` —
  all `DataFrame | None`. A cell is locked if it matches any level (OR logic). Column
  names match actual data column names. Excel file sheet names: `products`,
  `transactions`, `categories`, `cells`.

- **2026-03-26**: `load_balancing_config_from_excel(metadata, *, tolerances_path,
  locks_path)` added to `sutlab/io.py`. Sub-loaders are private. Same decision applied
  retrospectively to metadata sub-loaders: `load_metadata_columns_from_excel` and
  `load_metadata_classifications_from_excel` are now private (`_` prefix). Only
  `load_metadata_from_excel` is public.

- **2026-03-26**: All metadata loaders select only their specified columns from each
  sheet. Extra columns added by users (notes, scratch work) are silently ignored.

- **2026-03-26**: Fixture fix: supply rows (`0100`, `0700`) now correctly have
  `koeb = NaN`. Supply is valued at basic prices only; purchasers' price is a
  use-side concept. `generate.py` updated with a separate `supply_row` helper.

- **2026-03-26**: `balance_columns` function signature settled:
  `balance_columns(sut, transactions, categories, adjust_products) -> SUT`.
  `transactions` and `categories` identify which column totals to balance (AND logic —
  each (transaction, category) combination is balanced independently against its target).
  `adjust_products` is the set of products whose rows may be scaled to hit the target;
  all other products in those columns are treated as fixed. Operates on the member
  identified by `sut.balancing_id`. Returns a new SUT with updated supply/use DataFrames;
  the rest of the collection is carried along untouched.

- **2026-03-26**: `balance_columns` scaling logic settled. For each (transaction,
  category) column: fixed rows = locked rows (any match across the four `Locks` levels
  via OR logic) + rows whose product is not in `adjust_products`. Adjustable rows =
  `adjust_products` rows that are not locked. Scale factor =
  `(target - sum_fixed) / sum_adjustable`. Each adjustable row is multiplied by this
  factor. Locks are evaluated before scaling; a product in `adjust_products` that is
  also locked is treated as fixed.

- **2026-03-27**: `balance_columns` remaining design decisions settled:
  - Tolerances: deferred — not used actively in this iteration.
  - Zero adjustable total: raise an informative error if `sum_adjustable == 0` and
    `target - sum_fixed != 0`. If both are zero the column is already balanced — no-op,
    no error.
  - Diagnostics: none. Post-balancing validation is handled by separate inspect functions.
  - Price layer scaling (use side): targets are in purchasers' prices; scale factor is
    computed from purchasers' prices. The same factor is then applied to ALL price columns
    (`price_basic`, all intermediate layers, `price_purchasers`) on adjustable rows.
    Rationale: preserves the ratio between price layers. Supply side: only `price_basic`,
    scale factor computed from basic prices.

- **2026-03-27**: `balance_columns` arguments made optional. `transactions`, `categories`,
  and `adjust_products` all default to `None`. `None` semantics: `transactions=None` →
  all transactions with a non-NaN target value in `balancing_targets`; `categories=None`
  → all categories from those target rows for the selected transactions;
  `adjust_products=None` → all products in the balancing member (locks still apply).
  All three arguments support the same pattern syntax as `get_rows` (exact, wildcard,
  range, negation) via `_match_codes` imported from `sutlab.sut`.

- **2026-03-27**: `balance_columns` implemented in `sutlab/balancing.py`. Private helpers:
  `_evaluate_locks(df, locks, cols)` → boolean Series (OR across four lock levels);
  `_get_use_price_columns(use_df, cols)` → list of price column names in chain order.
  Core logic: vectorized groupby + transform("sum") to broadcast group-level fixed/adjustable
  sums to each row; scale factor computed and applied in one `.multiply()` call. No row loops.
  Tests in `tests/test_balancing.py` (31 tests, all passing). `balance_columns` exported
  from `sutlab/__init__.py`.

- **2026-03-27**: `balance_products_use(sut, products=None, adjust_transactions=None, adjust_categories=None)`
  added to `sutlab/balancing.py`. Scales use rows so each product's total use in basic prices
  equals its supply total (derived internally from `sut.supply` — `balancing_targets` not
  required). Scale factor computed from basic prices and applied to all price columns (same
  principle as `balance_columns` use side: preserve price layer rate ratios). Only products
  present in both supply and use are eligible (intersection). Product locks silently skip a
  product; transaction/category/cell locks covering all rows of a product raise an error.
  Private helper `_balance_rows_table` mirrors `_balance_table` but groups by product.
  19 new tests, 58 total passing.

- **2026-03-27**: `balance_columns` zero-adjustable error refined. Transaction/category
  locks represent a deliberate decision to exclude an entire column from balancing — such
  columns are silently skipped even if `sum_adjustable == 0` and `deficit != 0`. Product
  locks or cell locks that happen to cover all adjustable rows are NOT silently skipped:
  the user likely does not realise the implication, so an informative error is raised.
  Distinguishing rule: check whether the (transaction, category) pair is covered by
  `locks.transactions` or `locks.categories`; if yes, skip; otherwise raise.

- **2026-03-30**: `Locks.price_layers` added — a new optional `DataFrame | None` field with
  a single `price_layer` column. Values are use-side price layer column names (intermediate
  layers only — not `price_basic` or `price_purchasers`). When a layer is listed, both
  `balance_columns` and `balance_products_use` leave it untouched: the scale factor is still
  computed from the target price column, but the locked layer columns are excluded from the
  set of columns to which the factor is applied. Consequence: implied rates for locked layers
  change, which is intended (e.g. Danish `afg` is never adjusted in balancing). Validated on
  load: each value must be a known price layer column name from metadata. Loaded from an
  optional `price_layers` sheet in the locks Excel file; silently absent if the sheet does
  not exist.

- **2026-03-30**: Performance optimisations to `inspect_products` (`sutlab/inspect.py`):
  replaced `iterrows` with `dict(zip(...))` for name lookups; moved groupby calls outside
  product loops (N→1); replaced per-(product, transaction) `pivot_table` calls with a
  single pivot + dict-of-groups for O(1) lookup; vectorised `_build_detail_distribution`
  via groupby + numpy division; computed `compute_price_layer_rates` once per call (not
  once per table); replaced per-group `set_index`+`reindex` in rate lookup building with
  a single `pivot_table` + single `reindex` + numpy extraction. Total wall time on 12-year
  example SUT dropped from ~1.12s to ~0.60s (~46% reduction).

- **2026-03-30**: `_match_codes` (`sutlab/sut.py`) pre-computes natural sort keys once
  when any range pattern is present. Avoids O(N_codes × N_range_patterns) `re.split`
  calls — relevant at ~2400 product codes.

- **2026-03-31**: `compute.py` renamed to `derive.py`. Settled scope: analytical functions
  that compute derived quantities from a SUT or SUT collection — e.g. price layer rates,
  chain-linked volume indices, GDP components, input-output multipliers. Distinct from
  `balancing.py` (modifies the SUT) and `inspect/` (produces display tables). Kept flat
  for now; will be converted to a package if it grows crowded, following the same
  threshold as `io.py` (i.e. not until the file becomes difficult to navigate).

- **2026-03-30**: `SUTClassifications` column naming changed. Classification DataFrames
  no longer use generic `code`/`name` column names. Instead they use the actual data
  column name (from `SUTColumns`) as the key column, and `{col}_txt` as the label column.
  For example, if the product column is `nrnr`, the products classification has `nrnr` and
  `nrnr_txt` columns. The `transactions` classification adds `table` and `esa_code` as
  before. The `industries`, `individual_consumption`, and `collective_consumption`
  classifications all use the category column name and `{col}_txt` (since industry codes
  and consumption function codes all live in the `category` column, disambiguated by
  transaction code). `_load_metadata_classifications_from_excel` now requires a `columns`
  argument; `load_metadata_from_excel` handles this internally (loads columns first, passes
  them along). Rationale: direct merge-on without renaming; consistent with the principle
  that column names are never hardcoded.
