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
  `load_metadata_classifications_from_excel`, `load_sut_from_separated_parquet`. Naming convention:
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
  `load_sut_from_separated_parquet` loads one price basis at a time. Paths supplied as
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
  - `supply_products` / `use_products` — category breakdown for transactions with non-empty
    category column. 6-level MultiIndex `(product, product_txt, transaction,
    transaction_txt, category, category_txt)`. Sorted MultiIndex. Supply/use split from
    `sut.supply` / `sut.use` directly.
  - `balance_distribution` — same structure as `balance` minus the Balance row. Supply
    rows normalised by Total supply per year; use rows by Total use per year.
  - `supply_products_distribution` / `use_products_distribution` — same structure as detail
    tables. Each value divided by the product's total across all transactions/categories
    per year (column-wise normalisation within each product block).
  - `balance_growth` / `supply_products_growth` / `use_products_growth` — year-on-year
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

- **2026-03-24**: Detail table Styler: supply_products all green, use_products all blue.
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

- **2026-03-25**: `use_products` values are now at purchasers' prices (previously basic
  prices). `_build_detail_df` takes a `price_col` parameter; supply_products passes
  `price_basic`, use_products passes `price_purchasers`.

- **2026-03-25**: Detail tables (`supply_products`, `use_products`) gain a per-product
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

- **2026-03-31**: `balancing.py` refactored into a package. Structure:
  `__init__.py` (re-exports public API), `_shared.py` (`_evaluate_locks`,
  `_get_use_price_columns`), `_columns.py` (`_balance_table` + `balance_columns`),
  `_products_use.py` (`_balance_rows_table` + `balance_products_use`). Future
  balancing functions (`_ras.py`, `_price_layers.py`) follow the same pattern.
  Private helpers imported directly from submodules in tests.

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

- **2026-03-30**: `sort_id` optional argument added to `inspect_products`. When set to
  an id value (e.g. a year), all non-total rows are sorted descending by that column's
  value within their group. Groups: `["product"]` for detail tables,
  `["product", "price_layer"]` for price layer tables. Total rows (transaction == "")
  remain fixed at the end. Sorting is a flat sort: all rows within a group are sorted
  independently by value (transactions and categories intermixed). `balance`,
  `balance_distribution`, and `balance_growth` are not sorted. `price_layers_rates` and
  `price_layers_detailed_rates` are sorted independently by their own rate values (not
  inherited from their parent tables). Distribution/growth variants inherit the sorted
  order of their parent tables.

- **2026-03-30**: `_style_detail_table` and `_style_price_layers_detailed_table`
  rewritten to handle non-contiguous transaction blocks (which arise when `sort_id`
  scatters rows of the same transaction). Key changes: (1) iterate rows in order rather
  than grouping by transaction; (2) separators placed between adjacent rows where the
  transaction changes; (3) `trans_css` placed on the first row of each *contiguous run*
  of the same transaction (not the first global occurrence), because merged cells in
  pandas HTML rendering take CSS from the first row of their rowspan. A
  `trans_row_counter` dict tracks within-transaction row position for alternating
  category colours.

- **2026-03-31**: `SUT` dataclass gains methods that delegate to all public non-loader
  free functions (`set_balancing_id`, `set_balancing_targets`, `set_balancing_config`,
  `get_rows`, `get_ids`, `get_product_codes`, `get_transaction_codes`,
  `get_industry_codes`, `get_individual_consumption_codes`,
  `get_collective_consumption_codes`, `compute_price_layer_rates`, `inspect_products`,
  `balance_columns`, `balance_products_use`). Loader functions remain module-level only
  (they produce a SUT; they don't operate on one). `@dataclass` retained — methods work
  identically in a dataclass. Circular imports avoided with lazy imports inside method
  bodies for external modules (`derive`, `inspect`, `balancing`); same-module functions
  called directly by name (global lookup at call time, not recursive). Free-function
  docstrings assigned to methods after definition (`SUT.method.__doc__ = fn.__doc__`)
  so `?sut.method` in Jupyter shows the full documentation: same-module assignments at
  the bottom of `sut.py`, external-module assignments in `sutlab/__init__.py`.

- **2026-03-31**: `sutlab/inspect.py` refactored into a package `sutlab/inspect/` in
  preparation for multiple inspection functions. Structure: `__init__.py` re-exports the
  public API (`inspect_products`, `ProductInspection`, `ProductInspectionData`) and private
  names used in tests; `_style.py` holds all formatting helpers, colour constants, and Styler
  factories; `_products.py` holds `inspect_products`, its result dataclasses, and all
  `_build_*` helpers. New inspection functions should be added as `_<name>.py` alongside
  `_products.py`, with their public names re-exported in `__init__.py`. All existing imports
  continue to work unchanged.

- **2026-04-01**: `inspect_industries(sut, industries, ids=None, sort_id=None)` implemented
  in `sutlab/inspect/_industries.py`. Returns `IndustryInspection` with 12 tables (data +
  styled): `balance`, `balance_growth`, `supply_products`, `supply_products_distribution`,
  `supply_products_growth`, `use_products`, `use_products_distribution`,
  `use_products_coefficients`, `use_products_growth`, `price_layers`, `price_layers_rates`,
  `price_layers_distribution`, `price_layers_growth`.

- **2026-04-01**: `inspect_industries` balance table structure: MultiIndex
  `(industry, industry_txt, transaction, transaction_txt)`. Within each industry: P1 rows
  at basic prices, "Total output" (only when ≥ 2 P1 in metadata), P2 rows at purchasers'
  prices, "Total input" (only when ≥ 2 P2 in metadata), GVA `(B1g, "Gross value added")`,
  input coefficient `("", "Input coefficient")`. Total rows determined from
  `classifications.transactions` metadata, not from data.

- **2026-04-01**: `inspect_industries` supply_products / use_products: MultiIndex
  `(industry, industry_txt, transaction, transaction_txt, product, product_txt)`. One
  "Total supply" / "Total use" row per industry block (summed across all transactions).
  P1 (supply) from `sut.supply` at basic prices; P2 (use) from `sut.use` at purchasers'
  prices. Zero-supply or zero-use products excluded. `sort_id` sorts non-total rows
  descending within `["industry"]` groups.

- **2026-04-01**: `use_products_coefficients`: same structure as `use_products`. Each value
  divided by the industry's total P1 output at basic prices (recomputed from `sut.supply`).
  Expresses each product's contribution to the input coefficient. Total use row equals the
  overall input coefficient.

- **2026-04-01**: `inspect_industries` price layer tables: MultiIndex
  `(industry, industry_txt, price_layer, transaction, transaction_txt)`. One block per
  `(industry, price_layer)`. Total row only when ≥ 2 P2 transactions in metadata.
  `price_layers_distribution` is empty (not computed) when only 1 P2 transaction — would
  be 1.0 everywhere. `price_layers_rates` has no Total rows. Rates computed via
  `compute_price_layer_rates(filtered_sut, ["transaction", "category"])` on a SUT whose
  use is pre-filtered to P2 transactions and matched industries.

- **2026-04-01**: `compute_price_layer_rates` generalised: `aggregation_level` now accepts
  `str | list[str]` of column role names. A string is normalised to a single-element list
  internally. Existing calls with `"product"`, `"transaction"`, or `"category"` are unchanged.
  New `["transaction", "category"]` grouping enables industry-level rate computation.

- **2026-04-01**: `_style_price_layers_table` generalised with `outer_level="product"` /
  `outer_txt_level="product_txt"` keyword params. Industry variant passes `"industry"` /
  `"industry_txt"`. All existing call sites unchanged.

- **2026-04-01**: `_sort_by_id_value` moved from `_products.py` to new `_shared.py`
  (shared helpers for the inspect package). Used by both `_products.py` and
  `_industries.py`. The `group_levels` argument is a list of MultiIndex level names
  (e.g. `["product"]`, `["industry"]`, `["product", "price_layer"]`).

- **2026-04-02**: `inspect_final_uses` added. Final use transaction codes are
  use-side transactions with ESA codes other than P2. Three levels of detail:
  `use` (transaction-level, 2-level MultiIndex), `use_categories`
  (transaction+category, 4-level), `use_products` (transaction+category+product,
  6-level). Each has `_distribution` and `_growth` variants. `sort_id` applies a
  flat global sort to `use`, `use_categories`, and `use_products` but NOT to
  price layer tables.

- **2026-04-02**: `inspect_final_uses` price layer tables: intermediate layers
  only (no `price_basic`), no Total rows. Distribution denominator is the sum of
  all layer rows in the (transaction, category) block. `sort_id` does not affect
  price layer block ordering.

- **2026-04-02**: `_style_final_use_use_categories_table` — `transaction`/
  `transaction_txt` index cells have no background colour (only a separator
  border), consistent with the outermost-level convention in other inspection
  tables. `_style_final_use_use_table` (transaction-level) uses alternating row
  colours on all cells including index, since each transaction IS a leaf row.

- **2026-04-06**: Removed the four `price_layers_detailed` tables
  (`price_layers_detailed`, `price_layers_detailed_distribution`,
  `price_layers_detailed_growth`, `price_layers_detailed_rates`) from
  `inspect_products`. `ProductInspection` now returns 13 tables. Rationale:
  user decision — the category-level price layer breakdown is not needed.

- **2026-04-06**: `get_product_codes`, `get_transaction_codes`,
  `get_industry_codes`, `get_individual_consumption_codes`, and
  `get_collective_consumption_codes` now include a `_txt` label column when
  the corresponding classification table is present in
  `sut.metadata.classifications`. Silently omitted when absent.

- **2026-04-06**: The five `get_*_codes` functions (excluding `get_ids`) now
  accept an optional filter argument (`products`, `transactions`, `industries`,
  or `categories`) using the same pattern syntax as `get_rows` (exact,
  wildcard `*`, range `:`, negation `~`). Default `None` returns all codes.

- **2026-04-07**: Added `inspect_unbalanced_products(sut, products=None, sort=False,
  tolerance=1)` in `sutlab/inspect/_product_imbalances.py`. Returns
  `UnbalancedProductsInspection` with `.data.imbalances` (DataFrame) and a styled
  `.imbalances` property. Only includes products where `abs(diff) > tolerance`.
  Raises if `balancing_id` is None. Column order: `diff_*`, `rel_*`, `supply_*`,
  `use_*`, price layers, `use_{purchasers}`. All column names prefixed with
  `supply_`/`use_`/`diff_`/`rel_` + actual data column name. Index is product code
  (MultiIndex with label when classifications present). Excluded from the public
  products argument: margin products (see below).

- **2026-04-07**: `_DATA_COLORS["balance"]` and `_INDEX_COLORS["balance"]` changed
  from single strings to 2-tuples to support alternating row shading in the
  imbalances table. `_build_balance_row_css` updated to use `[0]` for the Balance
  row (no behaviour change). Styling: supply columns green, use columns blue,
  diff/rel columns neutral grey — all alternating per row. Index alternates in
  neutral grey.

- **2026-04-07**: Added `SUTClassifications.margin_products` — optional DataFrame
  with columns `{product_col}`, optionally `{product_col}_txt`, and `price_layer`
  (actual data column name mapping the product to the price layer it supplies into).
  Loaded from optional `margin_products` sheet in the classifications Excel file;
  `price_layer` values validated against known price layer columns from `SUTColumns`.
  `inspect_unbalanced_products` always excludes margin products when the table is
  present.

- **2026-04-07**: Added `resolve_target_tolerances(sut) -> SUT` in
  `sutlab/balancing/_tolerances.py`. Attaches `tol_{price_basic}` to
  `balancing_targets.supply` and `tol_{price_purchasers}` to
  `balancing_targets.use`. Tolerance per row = `min(abs(rel*target), abs_tol)`.
  Supports partial tolerances (rel-only or abs-only; raises only when both are
  absent for a non-NaN target). NaN target → NaN tolerance. Categories override
  transactions. Also callable as `sut.resolve_target_tolerances()`.

- **2026-04-07**: Added `inspect_unbalanced_targets(sut, transactions=None,
  categories=None, sort=False) -> UnbalancedTargetsInspection` in
  `sutlab/inspect/_balancing_targets.py`. Returns `.data.supply` and `.data.use`
  DataFrames with columns `{price}`, `target_{price}`, `diff_{price}`,
  `rel_{price}`, `tol_{price}`, `violation_{price}`. Violation = signed distance
  outside tolerance band (positive if above, negative if below, 0 if within).
  Supply uses basic prices; use uses purchasers' prices. Also returns
  `.data.supply_violations` and `.data.use_violations`: DataFrames of violating
  rows (empty if none), or None if no target_tolerances configured.
  `resolve_target_tolerances` is called silently if tol columns are absent.
  Styled properties (`.supply`, `.use`, `.supply_violations`, `.use_violations`)
  return Styler objects: actual+target columns in supply green / use blue,
  analytical columns in neutral grey, rel as percentage. Transaction blocks
  separated by `2px solid #999` borders; transaction index levels get border on
  first row of merged span, category levels on last row. Also callable as
  `sut.inspect_unbalanced_targets()`.

- **2026-04-07**: Column naming convention settled for balancing-related columns:
  `tol_{price}` and `violation_{price}` (not `{price}_tol` or `tol_violation`).
  `compute_*` naming reserved for functions in `derive.py` that compute analytical
  quantities from SUT data. `resolve_*` used in `balancing/` for functions that
  resolve configuration into usable form.

- **2026-04-07**: `add_sut(sut, adjustments)` added to `sut.py`. Semantics: numerical
  addition on matching keys (id, product, transaction, category); new keys appended;
  NaN treated as 0 (NaN + value = value, NaN + NaN = NaN). Both supply and use processed.
  Balancing targets combined with same semantics when `adjustments` carries them; otherwise
  base SUT's targets preserved. Metadata, balancing_id, balancing_config always from base.
  `price_basis` must match (raise otherwise); `SUTColumns` must match if both have metadata.
  Primary use case: benchmark revision adjustments. Parameter named `adjustments` (not
  `sut_values` or `other`) to reflect domain intent.

- **2026-04-08**: `load_sut_from_parquet` renamed to `load_sut_from_separated_parquet`.
  New function `load_sut_from_combined_parquet(path, metadata, price_basis)` added for the
  case where all collection members live in a single parquet file with the id column already
  present. "Separated" = one file per member, id supplied by caller; "combined" = one file
  for all members, id already in the file. Both functions sort supply and use rows by
  (id, product, transaction, category) and reset the index. Same transaction code validation
  in both.

- **2026-04-08**: Four new SUT loaders added: `load_sut_from_separated_csv`,
  `load_sut_from_combined_csv`, `load_sut_from_separated_excel`,
  `load_sut_from_combined_excel`. CSV loaders expose `sep` and `encoding` as
  keyword-only arguments (pandas defaults). All CSV/Excel loaders read product,
  transaction, and category columns as str; price columns converted to numeric
  via `pd.to_numeric`. For combined loaders the id column type is inferred by
  pandas. Private helper `_assemble_sut(df, metadata, price_basis)` extracted
  and shared by all six SUT loaders to eliminate duplicated validation, split,
  sort, and assembly logic.

- **2026-04-08**: Six SUT write functions added to `io.py` (symmetric to the six loaders):
  `write_sut_to_separated_parquet/csv/excel` and `write_sut_to_combined_parquet/csv/excel`.
  All take `(sut, folder, prefix, *, price_basis_code=None)`. CSV writers add `sep` and
  `encoding` keyword args. File naming: `{prefix}_{code}_{id_value}.ext` (separated) or
  `{prefix}_{code}.ext` (combined). Default codes: `"l"` for current year, `"d"` for
  previous year; overridable via `price_basis_code`. Id values extracted from the SUT data,
  not supplied by the caller. Supply and use concatenated on write; supply rows have NaN in
  price layer and purchasers' price columns (integer price columns become float after
  write-read cycle). Private helpers `_combine_supply_use` and `_resolve_price_basis_code`
  shared across all six writers.

- **2026-04-08**: Writer sorting: separated writers sort each member by (product, transaction,
  category) before writing; combined writers sort by (id, product, transaction, category).
  Combined writers now also require `sut.metadata` (previously only separated did) — needed
  to identify sort column names. `index=False` on all writers (no DataFrame index written).

- **2026-04-08**: `load_balancing_targets_from_excel` renamed to
  `load_balancing_targets_from_separated_excel`. New function
  `load_balancing_targets_from_combined_excel(path, metadata)` added — reads a single file
  with id column already present. Transaction and category columns read as str; id column
  type inferred by pandas (not forced to str). Same transaction code validation as the
  separated function.

- **2026-04-08**: Added `load_sut_from_dataframe` and `load_balancing_targets_from_dataframe`
  as in-memory equivalents of the file-based combined loaders. Accept a combined DataFrame
  (id column present, all years stacked) — same format as the combined file loaders.
  Price columns must already be numeric (no `pd.to_numeric` coercion, unlike Excel loaders).
  Extracted `_assemble_balancing_targets` private helper, eliminating duplicated logic from
  both existing balancing targets loaders. No `to_dataframe` functions added — users can
  construct the combined DataFrame themselves (`pd.concat([sut.supply, sut.use])`).

- **2026-04-08**: `compute_totals(sut, dimensions)` added to `derive.py`. `dimensions`
  specifies which of `{product, transaction, category}` to **keep** in the groupby; `id`
  is always kept. Returns a single stacked DataFrame (combined format: supply + use, NaN
  in price layer and purchasers' price columns for supply rows). All-NaN groups remain NaN
  (`min_count=1`). String or list accepted. Callable as `sut.compute_totals(dimensions)`.
  Placed in `derive.py` rather than a new `aggregate.py` module, which is reserved for
  classification aggregation (different concept).

- **2026-04-08**: Six SUT write methods added to `SUT` class as pandas-style delegates:
  `write_to_separated_parquet`, `write_to_combined_parquet`, `write_to_separated_csv`,
  `write_to_combined_csv`, `write_to_separated_excel`, `write_to_combined_excel`. Named
  without `_sut_` since it is redundant on an instance. Docstrings attached in
  `__init__.py` following established pattern.

- **2026-04-09**: `print_paths: bool = False` (keyword-only) added to all loader and
  writer functions in `io.py` (and the six `SUT` write delegate methods). When `True`,
  prints a brief message with the paths being read or written before the I/O operation.
  Format: combined functions print a single line; separated functions print a header with
  member count and an indented `id: path` list. Writers compute all output paths up-front
  before printing (consistent "before" timing across all functions). Price basis included
  in SUT messages; omitted from metadata and balancing config messages; omitted from
  balancing targets messages (always current prices). Argument name chosen over `verbose`
  (too abstract) for clarity. `_format_price_basis` private helper added to convert
  `"current_year"` → `"current year"` for display.

- **2026-04-09**: `use_price_columns: str | list[str] | None = None` (keyword-only)
  added to `compute_totals`. When specified, only the listed price columns (actual column
  names, not role names) are summed for use rows; all other price columns are set to NaN
  before aggregation. Supply rows are unaffected. Column names used (not role names)
  because price column names are user-defined and data-specific — users know their column
  names, not the abstract role names. Unknown column names raise ValueError with available
  columns listed. `SUT.compute_totals` delegate updated to pass the argument through.

- **2026-04-10**: `add_sut` renamed `adjust_add_sut` and moved to a new `sutlab/adjust/`
  package. The adjust module is intended to hold functions that directly adjust SUT values
  (e.g. `adjust_multiply`, `adjust_move` — not yet designed). Full scope of the adjust
  module is unsettled pending user discussions; the module was created now to give
  `adjust_add_sut` a home. `_add_long_tables` private helper moved alongside it.
  Tests moved to `tests/test_adjust.py`. `SUT.add_sut` method renamed `SUT.adjust_add_sut`
  with a local import to avoid circular imports (same pattern as inspect/balancing methods).

- **2026-04-10**: `sheet_name: str | int = 0` (keyword-only) added to all four Excel
  loaders: `load_sut_from_separated_excel`, `load_sut_from_combined_excel`,
  `load_balancing_targets_from_separated_excel`, `load_balancing_targets_from_combined_excel`.
  Passed directly to `pd.read_excel`. In the separated loaders the same sheet name applies
  to every file. Default `0` preserves existing behaviour (first sheet). `None` not used as
  default because `pd.read_excel(..., sheet_name=None)` returns a dict of DataFrames rather
  than a single DataFrame.

- **2026-04-10**: `inspect_sut_comparison(before, after, ...)` added in `sutlab/inspect/_sut_comparison.py`.
  Returns `SUTComparisonInspection` with `data: SUTComparisonData` (8 table fields + `summary`).
  Compares two SUTs row-level across all price columns using a single outer merge per side
  (supply: 1 merge, use: 1 merge reused for all three use tables). Key design decisions:
  - Outer join: rows present in only one SUT always included.
  - 4 SUT tables: `supply` (basic prices), `use_basic`, `use_purchasers`, `use_price_layers`
    (long-format, one row per key+price_layer).
  - 4 nullable balancing targets tables: same structure, no product dimension. All four are
    `None` when either SUT lacks `balancing_targets`.
  - `summary` DataFrame: index=table name, column=`n_differences`. Row order: supply,
    use_basic, use_price_layers, use_purchasers in each block. Targets block omitted when absent.
  - Filtering arguments: `ids`, `products`, `transactions`, `categories` (same pattern syntax
    as `get_rows`). Products filter not applied to targets tables (no product dimension).
  - `diff_tolerance` / `rel_tolerance`: rows excluded when both `abs(diff) <= diff_tolerance`
    and `abs(rel) <= rel_tolerance`. One-sided rows (present in only one SUT) always included
    unless `filter_nan_as_zero=True` suppresses NaN-vs-zero cases.
  - `filter_nan_as_zero: bool = False`: post-filter mask `(before.isna() & after.eq(0)) |
    (before.eq(0) & after.isna())` applied after the main keep filter; applies to all tables.
  - `sort: bool = False`: sorts within id (or id+price_layer for layers table) by abs(diff)
    descending.
  - Index: `(id, product, transaction, category)` with optional `_txt` companions from
    classifications. Layers table adds `price_layer` as final level (no txt companion).
    Targets tables: `(id, transaction, category)`, no product.
  - Delegate: `after_sut.inspect_sut_comparison(before_sut)` (self=after, arg=before).
  - Styled properties on `SUTComparisonInspection`: `supply` (green), `use_basic`/
    `use_purchasers` (blue), `use_price_layers` (cycling layer palettes), `summary`
    (supply rows green, use rows alternating blue, block separator between SUT and targets
    blocks), and the four nullable `balancing_targets_*` properties. `before_*` columns get
    palette shade 0, `after_*` get shade 1; `diff_*`/`rel_*` get alternating grey.
    Id-block separators follow the merged-cell convention (border on first row for merged
    id level, last row for data and inner index levels).

- **2026-04-13**: Add `isinstance` type validation (raising `TypeError`) for custom-class
  inputs across six functions: `set_balancing_targets` (targets: BalancingTargets),
  `set_balancing_config` (config: BalancingConfig), `adjust_add_sut` (both sut and
  adjustments: SUT), `inspect_sut_comparison` (before: SUT), `load_sut_from_dataframe`
  (df: pd.DataFrame), `load_balancing_targets_from_dataframe` (df: pd.DataFrame).
  Scope rule: validate user-supplied custom-class arguments only; skip the `sut` parameter
  when the function is also callable as a SUT method (sut is guaranteed to be SUT via self).

- **2026-04-13**: `write_sut_to_separated_parquet/csv/excel` (and their `SUT` delegate
  methods) changed to take `id_values: list[str | int]` and `paths: list[str | Path]`
  instead of `folder`, `prefix`, `price_basis_code`. Caller now controls exact output
  paths; auto-naming logic removed. Validates that all provided id values are present in
  the SUT (informative error listing available ids); also validates equal lengths of
  `id_values` and `paths`. `Path` import added to `sut.py`.

- **2026-04-13**: Added balancing targets loaders for parquet and CSV:
  `load_balancing_targets_from_separated_parquet`, `load_balancing_targets_from_combined_parquet`,
  `load_balancing_targets_from_separated_csv`, `load_balancing_targets_from_combined_csv`.
  All delegate to `_assemble_balancing_targets`; parquet stores price columns as numeric
  so no conversion needed; CSV reads transaction/category as str and converts price columns.

- **2026-04-13**: Added six balancing targets writer functions:
  `write_balancing_targets_to_separated/combined_parquet/csv/excel`. Take
  `columns_metadata: SUTColumns` (not full `SUTMetadata` — no classifications needed for
  writing). Private `_combine_balancing_targets(targets, columns_metadata)` helper
  concatenates supply+use and sorts by id/transaction/category. `BalancingTargets` exposes
  matching `write_to_*` delegate methods. Combined writers take a single `path` argument
  (same pattern established for SUT combined writers this session).

- **2026-04-13**: `write_sut_to_combined_parquet/csv/excel` changed to take a single
  `path: str | Path` argument instead of `folder + prefix + price_basis_code`. Caller
  controls the full output path. `_resolve_price_basis_code` and `_DEFAULT_PRICE_BASIS_CODES`
  removed as dead code.

- **2026-04-13**: Rule added to CLAUDE.md: never rely on column or row ordering — always
  identify columns by name via `SUTColumns` and select rows by value, not position.

- **2026-04-13**: Added `set_metadata(sut, metadata) -> SUT` free function and
  `sut.set_metadata(metadata)` delegate method. Same immutable pattern as
  `set_balancing_id/targets/config`. Raises `TypeError` if argument is not `SUTMetadata`.

- **2026-04-13**: Added `write_to_excel(path)` method to all six inspection result
  classes (ProductInspection, IndustryInspection, FinalUseInspection,
  UnbalancedProductsInspection, BalancingTargetsInspection, SUTComparisonInspection).
  Implemented via shared generic helper `_write_inspection_to_excel` in
  `sutlab/inspect/_shared.py` using `dataclasses.fields(obj.data)`.
  Design decisions:
  - Skip None fields; write empty DataFrames as empty sheets.
  - Use `Styler.to_excel()` where a styled property exists (carries colours etc.);
    silent fallback to raw `df.to_excel()` if styling raises (e.g. mismatched columns).
  - Post-processing via openpyxl: bold headers (copy(cell.font) to preserve existing
    properties), index column widths fit to content, value column widths fixed at 13,
    number formats (#,##0.0 for monetary; 0.0% for _distribution/_rates/_growth tables
    and rel_* columns in mixed tables).
  - Sheet name truncation: if field name >31 chars, truncate each _-separated segment
    to 3 chars. Currently only two field names exceed the limit
    (balancing_targets_use_purchasers, balancing_targets_use_price_layers).


- **2026-04-13**: Renamed `get_rows` → `filter_rows` and `remove_locked_cells` →
  `filter_free_cells`. Rationale: "filter" is consistent with pandas conventions (keep
  matching rows); "free" is accurate — the function retains unlocked (free) rows, not
  locked ones. Both functions gained a `table: str | None = None` keyword argument:
  `"supply"` or `"use"` limits filtering to that table; `None` (default) filters both.
  `_remove_locked.py` renamed to `_filter_free.py`.

- **2026-04-14**: Renamed all `*_detail_*` fields/properties in `ProductInspection` and
  `IndustryInspection` to `*_products_*` (e.g. `supply_detail` → `supply_products`,
  `use_detail_coefficients` → `use_products_coefficients`). Rationale: "products" is more
  explicit and consistent with the dimension being broken down.

- **2026-04-14**: Added `supply_products_summary` and `use_products_summary` tables to
  `IndustryInspection`. Per-transaction statistics over the product dimension: `total_supply`/
  `total_use`, `n_products`, coverage counts (`n_products_p{N}`, always using numeric suffix —
  no min/median/max aliases for coverage rows), value percentiles (`value_{label}`), share
  percentiles (`share_{label}`). Row order: total, n_products, coverage (asc), value (desc),
  share (desc). `inspect_industries` gains `percentiles=[0.5, 1.0]` and
  `coverage_thresholds=[0.5, 0.8, 0.95]` keyword-only arguments. Formatting: total/value →
  number, n_products/n_products_* → integer, share_* → percentage. No special bold or colour
  on the total row — uniform alternating colours throughout.

- **2026-04-14**: Added `display_products_n_largest(n, id)`,
  `display_products_threshold_value(threshold, id)`, and
  `display_products_threshold_share(threshold, id)` to `IndustryInspection`. Each returns a
  new `IndustryInspection` with products tables filtered for display; derived tables and rows
  (transaction == "") always preserved; summary/balance/price_layer tables copied unchanged.
  Supply and use filtered independently. All filtering vectorised (groupby().rank(),
  boolean indexing, index.isin()). `id` is required (no default).

- **2026-04-14**: `compare_dimensions: str | list[str] | None = None` added to
  `inspect_sut_comparison` (and the SUT delegate method). Accepted values: `"product"`,
  `"transaction"`, `"category"` — one or more. When set, both SUTs are aggregated via
  groupby+sum (min_count=1) over the dimensions not listed, after filtering and before
  comparing. Canonical column order (product → transaction → category) is preserved
  regardless of the order the user specifies. For balancing targets (no product dimension),
  `"product"` has no effect; transaction/category dimensions are aggregated as expected.
  `_set_key_index` and `_set_layers_index` refactored to be fully dynamic: they now take
  a `names_by_col: dict[str, dict[str, str]]` argument instead of separate col/names
  arguments, and add `_txt` companions only for columns present in the dict. This allowed
  `_set_targets_index` and `_set_targets_layers_index` to be removed (targets now use the
  same generic helpers).

- **2026-04-15**: `compare_dimensions` removed from `inspect_sut_comparison` — not useful in
  practice. `_resolve_dimension_cols` and `_aggregate_to_dimensions` helpers deleted.

- **2026-04-15**: `diff_tolerance` and `rel_tolerance` in `inspect_sut_comparison` now use AND
  logic: a row is kept only when `abs(diff) > diff_tolerance` AND `abs(rel) > rel_tolerance`.
  When `rel_tolerance` is left at its default `inf`, behaviour is unchanged (only diff applies).

- **2026-04-15**: Four new summary tables added to `SUTComparisonData`: `supply_products_summary`,
  `supply_columns_summary`, `use_products_summary`, `use_columns_summary`. Derived from the
  already-filtered `data.supply` and `data.use_purchasers` tables respectively. Columns:
  `n_changes`, `diff_norm` (Euclidean norm of diffs), diff percentile columns, rel percentile
  columns (NaN rel values excluded). Configurable via `percentiles` argument (default
  `[0.0, 0.5, 1.0]`). When `sort=True`, sorted descending by `diff_norm`. Index: code columns
  with interleaved `_txt` companions where available. Styled properties added (green/blue).

- **2026-04-15**: `inspect_sut_comparison` `.summary` table updated: column renamed from
  `n_differences` to `n_changes`; four new rows added for the summary tables. Block order:
  base comparison tables → products summaries → columns summaries → balancing targets (optional).
  Block separators in `_style_summary_table` updated to handle four blocks.

- **2026-04-16**: `inspect_aggregates_nominal` designed (not yet implemented). See
  `notes/claude/inspect_aggregates.md` for full design reference. Key decisions:
  - Function renamed `inspect_aggregates_nominal` (not `inspect_gdp_nominal`) to leave room
    for additional aggregate tables in the same inspection object later.
  - `gdp_decomp` column added to `SUTClassifications.transactions` as an optional extra
    column. Optional override `gdp_decomp: pd.DataFrame | None` argument (columns:
    actual transaction col name + `"gdp_decomp"`) overrides the metadata column.
    Raises informative error if absent from both metadata and argument.
  - ESA codes drive classification: P1 (output, supply), P2 (intermediate consumption, use,
    negated), P6 (exports, use), P7 (imports, use, negated), D2121 (import duties, supply).
    D2121 is supply-side so it cannot appear in the expenditure block's domestic final use.
  - Product tax rows come from summing price layer columns across all products/use rows
    (not from transaction rows). Import duties come from D2121 supply rows.
  - Sign convention: P2 and P7 rows multiplied by −1 explicitly; all others taken as-is.
  - GDP from production and expenditure will not necessarily agree (SUT may be unbalanced).
  - Multiple transactions sharing the same `gdp_decomp` value are summed into one row.
  - Output: `AggregatesNominalInspection` with `.data` holding the GDP DataFrame.
    Styling deferred. Columns = id values; rows = 2-level MultiIndex (approach, component).
  - Future `inspect_aggregates_real` will chain-link rows independently (chain-linking is
    not additive). A shared private helper will define row structure separately from value
    computation, reused by both nominal and real functions.

- **2026-04-17**: Added `display_unit: float | None = None` to all 7 inspect functions
  and their result classes. When set, number-formatted values (not percentages, not
  integers) are divided by `display_unit` at display time — both in Jupyter Styler
  properties and `write_to_excel`. Raw `.data` DataFrames are always unchanged. Default
  `None` disables division. Implemented via `_make_number_formatter(display_unit)` in
  `_style.py` and in-place cell value division in `_apply_number_formats` in `_shared.py`.
  `IndustryInspection._apply_products_filter` preserves `display_unit` on the returned
  object.

- **2026-04-17**: Moved `display_unit` from inspect function argument to a mutable field
  on result classes. Set via `set_display_unit(value)` which returns a new copy (immutable
  pattern, consistent with SUT). Inspect functions no longer accept `display_unit`.
  `set_display_unit` validates that the value is a positive power of 10 (or `None`).

- **2026-04-17**: Added `rel_base: int = 100` field to all 7 inspection result classes,
  with `set_rel_base(value)` returning a new copy. Validates value is in `{100, 1000,
  10000}` and maps to symbols `%`, `‰`, `‱` respectively. `_make_percentage_formatter(
  rel_base)` in `_style.py` replaces hardcoded `_format_percentage` calls throughout.
  Excel output uses the standard `%` format for `rel_base=100`; for 1000/10000 it
  multiplies cell values and applies a custom format string with the symbol.

- **2026-04-20**: Added `gdp_growth` and `gdp_distribution` to `AggregatesNominalInspection`.
  `gdp_growth`: year-on-year growth rates; Balance block excluded (growth of a discrepancy
  is not meaningful). `gdp_distribution`: shares of GDP per block — Production rows divided
  by Production GDP, Expenditure rows divided by Expenditure GDP; Balance block excluded.
  Both have styled properties using `_make_percentage_formatter(rel_base)` and are written
  to Excel with percentage formatting automatically via the `_distribution`/`_growth` suffix
  detection in `_shared.py`.

- **2026-04-20**: Consolidated `_build_growth_table` into `_shared.py`. Previously
  duplicated identically in `_products.py`, `_industries.py`, and `_final_uses.py`. The
  shared version is pure math only (no row filtering). The Balance-row exclusion that was
  baked into the `_products.py` copy is now done inline at the call site. New callers
  (aggregates nominal) filter rows before calling the shared function.

- **2026-04-20**: Refactored `_style_aggregates_nominal_table` to accept a `formatter`
  callable instead of `display_unit`, consistent with the pattern of other style functions
  (`_style_balance_table`, `_style_detail_table`, etc.). The `.gdp` property now passes
  `_make_number_formatter(display_unit)`; `.gdp_growth` and `.gdp_distribution` pass
  `_make_percentage_formatter(rel_base)`.

- **2026-04-20**: Added `inspect_tables_comparison(other)` to all 7 inspection result
  classes. Returns a generic `TablesComparison` dataclass (in `sutlab/inspect/_tables_comparison.py`)
  with `.diff` and `.rel` fields, each an instance of the same inspection class as the
  caller. `.diff` holds element-wise differences (self − other); `.rel` holds relative
  changes ((self − other) / other). Key design decisions:
  - Reuses existing inspection dataclasses for `.diff` and `.rel` — no new result types.
  - `.rel` has `_all_rel=True` (internal flag on each inspection class) which switches all
    number-formatted styled properties to percentage format. `_style.py` functions that
    previously used `display_unit` directly gain an `all_rel` parameter; `_shared.py`
    `_apply_number_formats` also gains `all_rel` for Excel output.
  - Index alignment uses outer join; division by zero → NaN (inf replaced).
  - None fields (e.g. optional violations tables) propagate as None in both diff and rel.
  - `TablesComparison.set_display_unit`/`set_rel_base` propagate to both inner objects.
  - `display_unit` and `rel_base` copied from the calling object at construction time.
  - `TablesComparison` exported from `sutlab/inspect/__init__.py`.

- **2026-04-20**: Fixed stale references: `inspect_balancing_targets` / `BalancingTargetsInspection`
  renamed to `inspect_unbalanced_targets` / `UnbalancedTargetsInspection` in CLAUDE.md and
  decisions.md (code was already correct).

- **2026-04-20**: Added `ids: str | int | list[str | int] | None = None` to both
  `inspect_unbalanced_products` and `inspect_unbalanced_targets`.
  - `ids=None` computes across all ids in the SUT (union of supply and use ids, sorted).
  - `ids=...` restricts to the matched subset using the same `_match_codes`-based
    pattern API as `filter_rows` (convert to strings for matching, keep original types).
  - `balancing_id` requirement removed from both functions.
  - All non-summary tables have the id column as the outermost index level (always
    a MultiIndex, even when one id selected). Categories tables: (id, trans, cat) or
    (id, trans, trans_txt, cat, cat_txt) with labels. Transactions tables: (id, trans)
    or (id, trans, trans_txt) with labels. Imbalances table: (id, product) or
    (id, product, label) with labels.
  - Summary collapses across all selected ids: `n_unbalanced` = total count,
    `largest_diff` = max-abs across all ids.
  - Diff filter (`abs(diff) > 1` for targets, `abs(diff) > tolerance` for products)
    applied independently per id.
  - Empty ids or ids with no data/targets produce empty tables silently (no error).
  - `_build_imbalances_for_id` extracted as private helper in `_product_imbalances.py`.
  - `_build_categories_table` and `_build_transactions_table` now take `id_value`
    explicitly instead of using `sut.balancing_id`.
  - `_resolve_ids` and `_prepend_id_level` defined as private helpers in each module.
  - SUT delegate methods updated to accept and pass through `ids`.
  - `_style_imbalances_table` draws `border-bottom: 2px solid #999` between id blocks:
    outermost level (merged cells) gets border on first row of block; data cells and
    inner index levels get border on last row of block. Consistent with other separator
    patterns in the codebase.

- **2026-04-20**: Added `set_decimals(n: int)` to all 7 inspection classes and `TablesComparison`. Controls decimal places in both number and percentage formatting (Jupyter display and Excel). Validates: non-negative int. Default 1 (existing behaviour preserved). Threads through all `_style.py` formatter factories and `_apply_number_formats` in `_shared.py`. Propagates via `inspect_tables_comparison` and `TablesComparison.set_decimals` the same way as `set_display_unit`/`set_rel_base`.

- **2026-04-21** (session 2): Added `display_index(values, level)` to all 7 inspection result classes. Filters every DataFrame field whose index contains a level named `level` to rows matching `values`; tables without that level are unchanged; `None` fields pass through. Accepts the same pattern syntax as `filter_rows` (exact, wildcard `*`, range `:`, negation `~`); non-string values stringified for matching. Shared helper `_display_index` in `_shared.py`; `_match_codes` imported there from `sutlab.sut`. Method name deliberate choice (shorter than `display_index_values`). A potential styling issue was noted: after filtering, some border lines may show partial gaps in the filtered index level's column. Root cause not identified from static analysis; deferred pending a concrete reproduction case.

- **2026-04-21** (session 3): Added `tables_description` to all 7 inspection result classes. Final design: `result.data.tables_description` is a raw DataFrame (`name` as index, single `description` column) as a `@property` on each `*Data` class; `result.tables_description` is a `Styler` using alternating neutral grey (balance palette, `_DATA_COLORS["balance"]`) with saturated index colours (`_INDEX_COLORS["balance"]`), via new `_style_tables_description` in `_style.py`. Descriptions are hardcoded strings. `.columns` (per-table column descriptions) was considered and rejected: too much maintenance burden for marginal gain.

- **2026-04-21**: Attached missing free-function docstrings to delegate methods so that `?obj.method` in Jupyter shows the full documentation. The pattern (`Class.method.__doc__ = free_fn.__doc__`) was already established in `sutlab/__init__.py` and `sutlab/sut.py`; this session identified and filled the gaps: `SUT.set_metadata` (added to `sut.py` block), and `SUT.compute_totals`, `SUT.inspect_unbalanced_products`, `SUT.inspect_unbalanced_targets`, `SUT.inspect_sut_comparison`, `SUT.inspect_aggregates_nominal`, `SUT.filter_free_cells`, `SUT.resolve_target_tolerances`, plus all six `BalancingTargets.write_to_*` methods (added to `__init__.py` block). No other classes had the problem.

- **2026-04-21** (sessions 4–5): Major refactor — unified `DisplayConfiguration` across all 7 inspection classes and `TablesComparison`.
  - New `DisplayConfiguration` dataclass in `sutlab/inspect/_display_config.py`. Two categories of fields:
    - User-settable: `display_unit`, `rel_base`, `decimals`, `display_index` (dict[str, list]), `sort_column`, `sort_ascending`, `display_values_n_largest` (dict: column→n).
    - Hard-coded per class (preserved by reset): `protected_tables: frozenset`, `protected_index_values: dict[str, list]`, `index_grouping: dict[str, list | None]`.
  - `_apply_display_config(df, table_name, config)` in `_shared.py`: applies display_index filter → n_largest filter → sort; returns df unchanged if `table_name in config.protected_tables` or df is empty.
  - All 7 inspection classes: replaced `display_unit`, `rel_base`, `decimals` fields with `display_configuration: DisplayConfiguration`; old setters renamed to `set_display_unit`, `set_display_rel_base`, `set_display_decimals`; `display_index(values, level)` replaced by `set_display_index(level, values)` (argument order swapped, additive union); added `set_display_sort_column(column, ascending=False)`, `set_display_values_n_largest(n, column)`, `set_display_configuration_to_defaults()`.
  - All styled properties now call `_apply_display_config` before styling; `.data` always returns full unfiltered data.
  - `TablesComparison`: replaced `display_unit/rel_base/decimals` with `display_configuration: DisplayConfiguration`; setters propagate to inner objects via their `set_display_*` methods (not via `dataclasses.replace`).
  - `sort_id` removed from `inspect_products`, `inspect_industries`, `inspect_final_uses` (and SUT delegates). `sort` removed from `inspect_unbalanced_products`, `inspect_unbalanced_targets`, `inspect_sut_comparison` (and SUT delegates). `display_products_n_largest`, `display_products_threshold_value`, `display_products_threshold_share` removed from `IndustryInspection`.
  - Sorting/filtering now done via `set_display_sort_column`, `set_display_index`, `set_display_values_n_largest` on the result object.
  - `index_grouping`: per-table list of index levels defining groups for sort/n_largest; `None` = global. Hard-coded at construction in inspect functions (where `id_col` is known). Default factories use empty `index_grouping={}` (overridden at construction).
  - `protected_index_values`: rows always shown, pinned to end (e.g. `{"transaction": [""]}` for Total rows).
  - `DisplayConfiguration` exported from `sutlab/inspect/__init__.py`.
  - All tests updated accordingly; 1554 tests pass.
