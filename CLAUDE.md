# Project: sutlab

## What this project does
Python library for compiling, balancing, and analysing supply and use tables (SUTs) in the Danish national accounts. Primary users are ~10 colleagues at Statistics Denmark with mixed Python experience, most with SAS backgrounds.

## Technology stack
- Language: Python 3.12
- Environment: UV — run Python with `uv run python` from the project root. No activation needed.
- Package install policy: always ask before adding new dependencies; use `uv add`
- Key dependencies: pandas, openpyxl (Excel for metadata/configuration), pyarrow (parquet support) — others to be decided

## Current status
- **Phase**: Implementation
- **What exists**: Core SUT dataclasses, `set_balancing_id`, and `get_rows` (`sutlab/sut.py`) + tests (`tests/test_sut.py`) + metadata I/O functions and `load_sut_from_parquet` (`sutlab/io.py`) + tests (`tests/test_io.py`) + `inspect_products` (`sutlab/inspect/`) returning 13 tables (balance, supply/use detail, price layers, price layer rates, and distribution/growth variants for all groups) + optional `sort_id` argument (sorts non-total rows descending by a chosen id value, within product or product+price_layer groups) + tests (`tests/test_inspect.py`, `tests/test_derive.py`) + `compute_price_layer_rates` (`sutlab/derive.py`) + `BalancingTargets`, `BalancingConfig`, `TargetTolerances`, `Locks` dataclasses + `set_balancing_targets`, `set_balancing_config` + `load_balancing_targets_from_excel`, `load_balancing_config_from_excel` + fixture data (`data/fixtures/`) + user documentation (`docs/`) + `balance_columns`, `balance_products_use` (`sutlab/balancing.py`) + tests (`tests/test_balancing.py`) + pandas-style methods on `SUT` delegating to all public non-loader free functions + `inspect_industries` (`sutlab/inspect/_industries.py`) returning 12 tables (balance, balance_growth, supply/use detail + distribution/coefficients/growth variants, price layers + rates/distribution/growth) + tests (`tests/test_inspect_industries.py`, `tests/test_price_layers_industries.py`) + `inspect_final_uses` (`sutlab/inspect/_final_uses.py`) returning 13 tables (`use` transaction-level, `use_categories` by transaction+category, `use_products` by transaction+category+product, each with `_distribution` and `_growth` variants, plus `price_layers`, `price_layers_rates`, `price_layers_distribution`, `price_layers_growth` — intermediate layers only, no basic prices, no total rows) + tests (`tests/test_inspect_final_uses.py`) + `get_product_codes`, `get_transaction_codes`, `get_industry_codes`, `get_individual_consumption_codes`, `get_collective_consumption_codes` each return a `_txt` label column when the corresponding classification table is present, and accept an optional filter argument (`products`, `transactions`, `industries`, or `categories`) using the same pattern syntax as `get_rows` + `inspect_unbalanced_products(sut, products=None, sort=False, tolerance=1)` (`sutlab/inspect/_product_imbalances.py`) returning `UnbalancedProductsInspection` with `.data.imbalances` and styled `.imbalances` property — one row per product where `abs(diff) > tolerance` in the active balancing member; margin products always excluded; columns `diff_*`, `rel_*`, `supply_*`, `use_*`, price layers, `use_{purchasers}` + tests (`tests/test_inspect_product_imbalances.py`) + `SUTClassifications.margin_products` — optional DataFrame mapping margin-supply products to their price layer column; loaded from optional `margin_products` sheet in the classifications Excel file + `resolve_target_tolerances` (`sutlab/balancing/_tolerances.py`) attaching `tol_{price_basic}` / `tol_{price_purchasers}` columns to balancing targets + `inspect_balancing_targets(sut, transactions=None, categories=None, sort=False)` (`sutlab/inspect/_balancing_targets.py`) returning `BalancingTargetsInspection` with `.data.supply`, `.data.use`, `.data.supply_violations`, `.data.use_violations` + tests (`tests/test_inspect_balancing_targets.py`) + `add_sut(sut, adjustments)` (`sutlab/sut.py`) — adds values from one SUT to another; matching keys summed, new keys appended, NaN treated as 0; balancing targets combined with same semantics when present; primary use case: benchmark revision adjustments + tests (`tests/test_sut.py`) + `load_sut_from_dataframe`, `load_balancing_targets_from_dataframe` (`sutlab/io.py`) — accept combined in-memory DataFrames (id column present, all years stacked); price columns must already be numeric + tests (`tests/test_io.py`)
- **What's next**: Further balancing/inspection functions

## Architecture

### Module structure
- `sutlab/sut.py` — Core dataclasses: `SUT`, `SUTMetadata`, `SUTColumns`, `SUTClassifications`, `BalancingTargets`, `BalancingConfig`, `TargetTolerances`, `Locks`; and `set_balancing_id`, `set_balancing_targets`, `set_balancing_config`, `get_rows`, `get_product_codes`, `get_transaction_codes`, `get_ids`, `get_industry_codes`, `get_individual_consumption_codes`, `get_collective_consumption_codes`, `add_sut`; pandas-style methods on `SUT` delegating to all public non-loader free functions including `write_to_separated_parquet`, `write_to_combined_parquet`, `write_to_separated_csv`, `write_to_combined_csv`, `write_to_separated_excel`, `write_to_combined_excel`
- `sutlab/io.py` — I/O functions (public): `load_metadata_from_excel`, six SUT loaders (all sort supply and use rows by id, product, transaction, category): `load_sut_from_separated_parquet(id_values, paths, metadata, price_basis)`, `load_sut_from_combined_parquet(path, metadata, price_basis)`, `load_sut_from_separated_csv(id_values, paths, metadata, price_basis, *, sep, encoding)`, `load_sut_from_combined_csv(path, metadata, price_basis, *, sep, encoding)`, `load_sut_from_separated_excel(id_values, paths, metadata, price_basis)`, `load_sut_from_combined_excel(path, metadata, price_basis)`. Six SUT writers: `write_sut_to_separated_parquet(sut, folder, prefix, *, price_basis_code)`, `write_sut_to_combined_parquet`, `write_sut_to_separated_csv(…, *, sep, encoding)`, `write_sut_to_combined_csv`, `write_sut_to_separated_excel`, `write_sut_to_combined_excel`. Writers name files `{prefix}_{code}_{id}.ext` (separated) or `{prefix}_{code}.ext` (combined); default codes: `"l"` = current year, `"d"` = previous year. Supply and use are concatenated on write; supply rows have NaN in price layer and purchasers' price columns. "Separated" = one file per member, id column absent; "combined" = one file for all members, id column present. CSV/Excel loaders read product/transaction/category as str and convert price columns to numeric. `load_sut_from_dataframe(df, metadata, price_basis)`, `load_balancing_targets_from_separated_excel(id_values, paths, metadata)`, `load_balancing_targets_from_combined_excel(path, metadata)`, `load_balancing_targets_from_dataframe(df, metadata)`, `load_balancing_config_from_excel(metadata, *, tolerances_path, locks_path)`. Sub-loaders, `_assemble_sut`, `_assemble_balancing_targets`, `_combine_supply_use`, and `_resolve_price_basis_code` are private helpers.
- `sutlab/derive.py` — Derived analytical quantities: `compute_price_layer_rates(sut, aggregation_level)` — computes step-wise price layer rates; `aggregation_level` accepts a role string or list of role strings (e.g. `"product"`, `["transaction", "category"]`); uses hardcoded Danish default denominators; raises on unsupported layers. Future: chain-linked volume indices, GDP components.
- `sutlab/inspect/` — Package. `__init__.py` re-exports the public API. `_style.py` holds all formatting helpers, colour constants, and Styler factories. `_shared.py` holds shared helpers (currently `_sort_by_id_value`). `_products.py` holds `inspect_products(sut, products, ids=None, sort_id=None)` → `ProductInspection` (13 tables: balance, supply_detail, use_detail, price_layers, price_layers_rates, and distribution/growth variants for all groups). Balance and use_detail at purchasers' prices; detail tables include uncategorized transactions and per-product Total rows. `sort_id` sorts non-total rows descending by the given id value (balance tables unaffected; rates tables sorted independently). `_industries.py` holds `inspect_industries(sut, industries, ids=None, sort_id=None)` → `IndustryInspection` (12 tables: balance, balance_growth, supply_detail, supply_detail_distribution, supply_detail_growth, use_detail, use_detail_distribution, use_detail_coefficients, use_detail_growth, price_layers, price_layers_rates, price_layers_distribution, price_layers_growth). Balance table rows: P1 transactions (basic prices), optional Total output (if ≥2 P1 in metadata), P2 transactions (purchasers' prices), optional Total input (if ≥2 P2 in metadata), GVA, input coefficient. `price_layers_distribution` empty when only 1 P2 transaction. `_final_uses.py` holds `inspect_final_uses(sut, transactions, *, categories=None, ids=None, sort_id=None)` → `FinalUseInspection` (13 tables: `use`, `use_categories`, `use_products`, each with `_distribution`/`_growth` variants, plus 4 price layer tables). Candidate transactions: use-side rows with ESA codes excluding P2. `sort_id` applies flat global sort to `use`/`use_categories`/`use_products`; price layer tables unaffected. `_NON_FINAL_USE_ESA_CODES = {"P2"}`. `_product_imbalances.py` holds `inspect_unbalanced_products(sut, products=None, sort=False, tolerance=1)` → `UnbalancedProductsInspection` (1 table: `imbalances`). Requires `balancing_id` set; raises otherwise. Columns: `diff_{basic}`, `rel_{basic}`, `supply_{basic}`, `use_{basic}`, `use_{layer}` per price layer, `use_{purchasers}`. Index: product code, MultiIndex with label when classifications present. Margin products always excluded. `_balancing_targets.py` holds `inspect_balancing_targets(sut, transactions=None, categories=None, sort=False)` → `BalancingTargetsInspection` (2 main tables + 2 optional violations tables). Columns: `{price}`, `target_{price}`, `diff_{price}`, `rel_{price}`, `tol_{price}`, `violation_{price}`. Supply uses basic prices; use uses purchasers' prices. Tolerances resolved silently if `tol_` columns absent; `None` violations tables when no `target_tolerances` configured. Styled with transaction block separators. New inspection functions get their own `_<name>.py` with public names re-exported in `__init__.py`.
- `sutlab/balancing/` — Package. `__init__.py` re-exports the public API. `_shared.py` holds `_evaluate_locks`, `_get_use_price_columns`. `_columns.py` holds `balance_columns(sut, transactions=None, categories=None, adjust_products=None)` → `SUT` — scales adjustable rows to hit column targets; transaction/category locks skip silently; product/cell locks covering all adjustable rows raise an informative error. `_products_use.py` holds `balance_products_use(sut, products=None, adjust_transactions=None, adjust_categories=None)` → `SUT` — scales use rows so each product's total use in basic prices matches its supply total; target derived from supply; all price columns scaled to preserve price layer rate ratios. `_tolerances.py` holds `resolve_target_tolerances(sut) → SUT` — attaches `tol_{price_basic}` / `tol_{price_purchasers}` columns to balancing targets; tolerance = `min(abs(rel*target), abs_tol)` with partial tolerance support (rel-only or abs-only); raises only when both are absent for a non-NaN target. New balancing functions (RAS, price layer balancing, VAT threshold) get their own `_<name>.py`.

### Core data representation

**`SUT`** — top-level object, holds a collection of supply and use tables:
- `price_basis`: `"current_year"` or `"previous_year"`. Current and previous year prices
  are kept as **separate SUT objects**; the same metadata can be shared between them.
- `supply`: long-format DataFrame, all collection members, basic prices only
- `use`: long-format DataFrame, all collection members, all price columns
- `balancing_id`: id value of the member currently being balanced, or `None`
- `balancing_targets`: optional `BalancingTargets` — target column totals for balancing
- `balancing_config`: optional `BalancingConfig` — tolerances and locked cells
- `metadata`: optional `SUTMetadata`

The collection design separates two workflows: **inspection** spans the full collection;
**balancing** operates only on the member identified by `balancing_id`. This keeps a
multi-year series available as context during single-year balancing.

**`SUTMetadata`**
- `columns`: `SUTColumns` — required
- `classifications`: `SUTClassifications` — optional

**`SUTColumns`** — maps conceptual roles to actual DataFrame column names. Loaded from a
two-column Excel table (`column`, `role`). Required roles: `id`, `product`, `transaction`,
`category`, `price_basic`, `price_purchasers`. Optional roles (all `str | None`):
`trade_margins`, `wholesale_margins`, `retail_margins`, `transport_margins`,
`product_taxes`, `product_subsidies`, `product_taxes_less_subsidies`, `vat`.

**`SUTClassifications`** — optional classification tables, all fields `DataFrame | None`.
- `classification_names` — maps dimension names to classification system names; `dimension` and `classification` columns
- `products` — key column named after the actual product column (e.g. `nrnr`), label column named `{col}_txt` (e.g. `nrnr_txt`)
- `transactions` — key column named after the actual transaction column (e.g. `trans`), label column `trans_txt`, plus `table` and `esa_code`; `table` is `"supply"` or `"use"`, required and validated on load. Used to split the combined parquet file into supply and use tables.
- `industries`, `individual_consumption`, `collective_consumption` — key column named after the actual category column (e.g. `brch`), label column `brch_txt`. These three all live in the `category` column of the data — which classification applies depends on the transaction code (P1/P2 → industries, P31 → individual_consumption, P32 → collective_consumption).
- `margin_products` — products whose supply represents a trade margin. Columns: `{product_col}`, optionally `{product_col}_txt`, and `price_layer` (actual data column name, e.g. `handelsm`). Loaded from optional `margin_products` sheet in the classifications Excel file; `price_layer` values validated against known price layer columns from `SUTColumns`. These products are always excluded from `inspect_unbalanced_products`.

**`BalancingTargets`** — target column totals, split into supply and use. Mirrors the SUT
long-format without the product dimension. Supply: `id, transaction, category, price_basic`.
Use: `id, transaction, category, price_basic, [price layers], price_purchasers`. NaN in a
price column means no target for that combination.

**`BalancingConfig`** — balancing configuration independent of which id is being balanced:
- `target_tolerances`: optional `TargetTolerances` — `transactions` and `categories` DataFrames
  (columns: transaction/category col names, `rel`, `abs`). Loaded from Excel with sheets
  `transactions` and `categories`.
- `locks`: optional `Locks` — `products`, `transactions`, `categories`, `cells`, `price_layers`
  DataFrames. A cell is locked if it matches any of the first four levels (OR logic).
  `price_layers` has a single `price_layer` column; listed layers are excluded from scaling
  in all balancing functions (values held fixed; implied rates allowed to change). Validated
  on load against known price layer column names from metadata. Loaded from Excel; all sheets
  optional — silently absent if the sheet does not exist.

**`set_balancing_id / set_balancing_targets / set_balancing_config`** — each returns a new
SUT with one field updated. Does not mutate the original.

### Design principles
- Readability over elegance or performance — target reader has limited Python experience
- Explicit over concise — avoid abstractions that obscure what the code is doing
- Break multi-step operations into named intermediate variables rather than chaining
- Functional style — plain functions that take data and return data; no class hierarchies
- Dataclasses are fine as simple data containers
- Informative error messages: `"Product 'X' not found. Available: ..."` not bare KeyError
- API design: prefer many small public functions with few arguments over fewer abstract
  functions with many arguments. Names should be explicit and hierarchically structured
  so related functions group together in autocomplete. Users navigate the API primarily
  by name. Sub-loaders and other internal helpers are private (`_` prefix) — only
  top-level loaders are public. This principle applies to the public API only.
- Use native pandas operations (groupby, merge, vectorised column ops) over Python loops on DataFrame rows or ids — both for performance and readability
- Always use `dropna=False` in `groupby` calls — the default `dropna=True` silently drops NaN group keys (e.g. empty category values)
- Column names never hardcoded — always via `SUTColumns`
- Supply holds only basic prices; price layers are a use-side concept
- DataFrame column order (established by I/O functions, not enforced by dataclass):
  - Supply: `id, product, transaction, category, price_basic`
  - Use: `id, product, transaction, category, price_basic, [price layers], price_purchasers`
- Type hints and NumPy-style docstrings on all public functions

### Scope exclusions (current)
- Value added not decomposed — GVA is derivable as output minus intermediate use, but no
  breakdown by wages, operating surplus, etc.
- No supplementary data (hours worked, employment, capital stock)

## Domain glossary
- **SUT**: Supply and use table — matrix framework balancing production and use of goods
  and services
- **Basic prices / purchasers' prices**: The two main price bases. The difference is
  accounted for by price layers: wholesale margins, retail margins, taxes less subsidies
  on products (excluding VAT), and VAT. Danish-specific — do not assume the simpler SNA
  treatment.
- **Transaction codes**: SNA codes identifying economic flows (e.g. P1 output, P2
  intermediate consumption). Never hardcoded — always user-supplied.
- **Current / previous year's prices**: Current = prices of year t. Previous = values for
  year t revalued at prices of t−1. Used for volume calculations.
- **Chain-linked volume indices**: Derived from current and previous year's prices tables
  by linking year-to-year Laspeyres indices. Chaining and aggregation do not commute —
  aggregate first, then chain.

## Data
- `data/examples/` → Example SUT data from Statistics Denmark (parquet + Excel metadata)
- `data/fixtures/` → Small synthetic data for tests (generated by `data/fixtures/generate.py`)

## Open design questions
- What other inspection functions are needed beyond `inspect_products`?
- What is the exact interface for the GDP decomposition argument to inspection functions?
- What further balancing functions are needed beyond `balance_columns` and `balance_products_use`?
- `derive.py` scope settled (see decisions.md 2026-03-31). Convert to a package if/when the file grows crowded.

## Project structure
CLAUDE.md is the authoritative record of the current state. `notes/claude/` holds
supplementary material — consult proactively when starting work on a topic with prior
design history, or when instructed.

Version control: git, remote on GitHub. Commit logical units of work with descriptive messages.

Claude can read and write: `sutlab/`, `tests/`, `notes/claude/`
Claude should NOT read or write: `notes/mine/`

Claude should NOT:
- Make architectural or structural decisions unilaterally — propose, then wait for approval
- Reorganise modules without discussion
- Add dependencies without asking
- Write implementation code during planning sessions (small illustrative sketches are fine)
- Push to GitHub without asking

## Session instructions

### Start of every session:
1. Read this CLAUDE.md in full
2. State briefly: current phase, what was last worked on, what's next
3. Consult `notes/claude/` when starting work on a topic with prior design history

### End of every session:
1. Append decisions made this session to `notes/claude/decisions.md`
2. Update any relevant topic reference files in `notes/claude/`
3. Update **Current status** and **Open design questions** in this file
4. Suggest any other CLAUDE.md edits for approval — do not edit directly

### Planning sessions:
- Propose options with explicit tradeoffs; do not advocate unless asked
- End with a clear statement of what has and hasn't been settled

### Implementation sessions:
- Check that relevant architecture decisions are settled before writing code
- Write tests alongside implementation, not after
- If a decision turns out to be ambiguous mid-implementation, stop and flag it
- Flag code that feels fragile, surprising, or assumption-laden, even if not asked

### General behaviour:
- When uncertain, say so explicitly rather than inferring silently
- Read source before making claims about function signatures or behaviour
- Prefer proposing over doing for anything structural
- Prefer targeted edits over rewrites
