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
- **What exists**: Project skeleton + core SUT dataclasses and `mark_for_balancing` (`sutlab/sut.py`) + tests (`tests/test_sut.py`) + fixture data (`data/fixtures/`) + metadata format documentation (`metadata_format.md`)
- **What's next**: I/O functions (loading SUT collection from parquet, metadata from Excel) — formats fully settled, see `metadata_format.md` and `notes/claude/data_representation.md`

## Architecture
<!-- Canonical record of settled decisions. Update when decisions are made, never delete. -->

### Module structure
- `sutlab/sut.py` — Core dataclasses: `SUT`, `SUTMetadata`, `SUTColumns`, `SUTClassifications`; and `mark_for_balancing`

### Core data representation
Four dataclasses and one function in `sutlab/sut.py`:

- **`SUTColumns`** — maps conceptual roles to actual DataFrame column names. Required
  roles: `id` (the identifier column, e.g. `'year'`), `product`, `transaction`, `category`
  (industry for production/intermediate use, consumption function for final demand),
  `price_basic`, `price_purchasers`. Optional price-layer roles (all `str | None`):
  `trade_margins`, `wholesale_margins`, `retail_margins`, `transport_margins`,
  `product_taxes`, `product_subsidies`, `product_taxes_less_subsidies`, `vat`. Loaded
  from a two-column Excel table (`column`, `role`); the dataclass is the internal Python
  representation.
- **`SUTClassifications`** — optional classification tables: `classification_names`
  (dimension → classification system mapping), `products`, `transactions`, `industries`,
  `individual_consumption`, `collective_consumption`. All classification tables have `code`
  and `name` columns. The `transactions` table has an optional `gdp_component` column
  mapping each transaction code to one of: `output`, `imports`, `intermediate`,
  `private_consumption`, `government_consumption`, `exports`, `investment` (total capital
  formation), `gross_fixed_capital_formation`, `inventory_changes`,
  `acquisitions_less_disposals_of_valuables`. The last three are sub-components of
  investment (not alongside it). GDP functions sum all components present and display each as a separate line.
- **`SUTMetadata`** — holds a `SUTColumns` and an optional `SUTClassifications`. Functions
  that need a specific classification table raise an informative error if it is absent.
- **`SUT`** — top-level object holding a **collection** of SUTs: `price_basis`
  (`"current_year"` or `"previous_year"`), `supply` DataFrame (long format, all members,
  basic prices only), `use` DataFrame (long format, all members, all price columns),
  `balancing_id` (the id of the member currently being balanced, or `None`), `metadata`
  (optional `SUTMetadata`).
- **`mark_for_balancing(sut, balancing_id)`** — returns a new `SUT` with `balancing_id` set.
  Does not mutate the original. Raises an informative error if the id is not found.

Column names are never hardcoded — all are specified via `SUTColumns`. Supply holds only
the basic-prices column; price layers are a use-side concept.

The collection design separates two workflows: **balancing** operates on the single member
identified by `balancing_id`; **inspection** spans the full collection. This means a
multi-year series is always available as context during single-year balancing.

### Design principles
<!-- Permanent, load-bearing decisions about how the system works. Record when/why in Decisions log. -->
- The code is agnostic to classification systems and transaction codes — never hardcode product codes, industry codes, or transaction codes. All are user-supplied metadata.
- Classification metadata is user-specified and can be loaded from any source (Excel, database, etc.). The internal representation does not assume a source format.

### Scope exclusions (current)
- Value added is not decomposed — GVA is derivable as output minus intermediate use, but no breakdown by wages, operating surplus, etc.
- No supplementary data (hours worked, employment, capital stock, etc.)
These will be added to the data structure when needed — do not anticipate them.

### Conventions
- Prioritise readability over elegance or performance. The target reader is a colleague with limited Python experience.
- Prefer explicit over concise — avoid abstractions that obscure what the code is doing
- Break multi-step operations into named intermediate variables rather than chaining methods or nesting calls
- Prefer a functional style — operations as plain functions that take data and return data. Avoid class hierarchies and inheritance unless there is a clear and specific reason.
- Exception: dataclasses are fine as simple data containers (e.g. for the SUT object itself).
- Error messages should be informative for non-experts — e.g. `"Product 'CPA_A01' not found. Available products: ..."` rather than a bare KeyError
- Supply and use DataFrames follow column order: id, product, transaction, category, price columns. Established by I/O functions; not enforced by the dataclass.
- Type hints on all public functions
- Docstrings on all public functions, NumPy style

## Domain glossary
<!-- Add as needed. Be precise where domain meaning differs from plain English. -->
- **SUT**: Supply and use table — a matrix framework balancing the production and use of goods and services in the economy
- **Product**: A category of good or service (rows in the use table, columns in the supply table)
- **Industry**: A category of producer (columns in the use table, rows in the supply table)
- **Intermediate use**: Use of goods and services as inputs to production. The main body of the use table, distinct from final demand.
- **Final demand**: The final expenditure components of the use table — household consumption, government consumption, gross fixed capital formation, and exports. Distinct from intermediate use by industries.
- **Value added**: Output minus intermediate use. Includes compensation of employees, taxes less subsidies on production, and operating surplus.
- **Basic prices / purchasers' prices**: The two main price bases in a SUT. The difference is accounted for by price layers: wholesale trade margins, retail trade margins, taxes minus subsidies on products (excluding VAT), and VAT. These are Danish-specific price layers — do not assume the simpler SNA treatment.
- **Transaction codes**: Standardised SNA codes identifying types of economic flows (e.g. P1 output, P2 intermediate consumption, P51G gross fixed capital formation). In a SUT they identify value added components and final demand categories. Never hardcoded — always user-supplied.
- **Current prices**: SUT values expressed in the prices of the current year t. The monetary tables as compiled.
- **Previous year's prices**: SUT values for year t revalued at the prices of year t-1. Used as the basis for volume calculations.
- **Chain-linked volume indices**: Volume time series constructed by linking year-to-year Laspeyres volume indices. Derived from the current and previous year's prices tables — not directly observable in the SUT.
- **Supplementary data**: Physical or volume measures outside the monetary accounting framework (e.g. hours worked, employment, capital stock). Used for e.g. productivity analysis but not part of the SUT itself.

## Data
- `data/examples/` → Example SUT data from Statistics Denmark. Parquet files for SUT tables (pandas DataFrames saved with `to_parquet`).
- `data/examples/metadata/` → Metadata for example data (e.g. classifications). Excel files.
- `data/fixtures/` → Small synthetic data for tests. Two levels: minimal (2-3 products, 2 industries, hand-crafted round numbers) and small (aggregated from real data, more realistic). Not yet created.

## Decisions log
<!-- Append when a decision is made. Never delete entries. -->
- 2026-03-18: Core data representation settled — see Architecture section and `notes/claude/data_representation.md`
- 2026-03-18: SUT is a collection (multi-member long-format DataFrames) with a `balancing_id` field marking the active member. `mark_for_balancing` returns a new SUT immutably. Rationale: inspection is naturally multi-year; balancing is single-year; the collection keeps both in one object without forcing the user to pass year arguments to every balancing call or inject a work-in-progress SUT into every inspection call.
- 2026-03-18: `PriceSpec` eliminated. `SUTColumns` restructured with explicit named fields per price-layer role (fixed list: `trade_margins`, `wholesale_margins`, `retail_margins`, `transport_margins`, `product_taxes`, `product_subsidies`, `product_taxes_less_subsidies`, `vat`). Loaded from two-column Excel table (`column`, `role`). `SUTClassifications` added as a nested dataclass inside `SUTMetadata`, replacing the five flat classification fields. Transactions classification table includes a `gdp_component` column with a fixed GDP decomposition.
- 2026-03-18: `set_active` renamed to `mark_for_balancing` — more concrete, reflects tagging rather than starting a process.
- 2026-03-18: Current and previous year's prices are kept as separate `SUT` objects (not combined in one dataclass). Same metadata object can be reused across both.
- 2026-03-18: `price_basis` stays as `Literal["current_year", "previous_year"]`. `'fixed'` and `'chained'` not added — out of scope for now and easy to extend when needed.
- 2026-03-19: Classification table text-name column renamed `description` → `name` across all classification tables. `description` implied prose; `name` reflects the intent: the official standard text name of a code.
- 2026-03-19: `gdp_component` expanded with investment sub-components: `gross_fixed_capital_formation`, `inventory_changes`, `acquisitions_less_disposals_of_valuables`. These are alternatives to the `investment` catch-all for users with granular transaction tables — use instead of `investment`, not alongside it. GDP functions display each component as a separate line.
- 2026-03-19: `gdp_component` is optional on the transactions classification table (not required). Functions that need it raise an informative error if absent.
- 2026-03-19: Excel metadata file formats fully settled — see `metadata_format.md` (user-facing) and `notes/claude/data_representation.md` (full spec).

## Open design questions
- What is the full module structure beyond `sut.py`?
- How are locks/cells referenced in balancing operations? (product/transaction/category keys, or index-based?)
- Are price-layer share tables (α, β) stored on the SUT object or computed on the fly when needed?

## Project structure

CLAUDE.md is the authoritative record of decisions. Notes are working material — if notes contradict CLAUDE.md, CLAUDE.md wins.

Version control: git, remote on GitHub. Commit logical units of work with descriptive messages.

Claude can read and write:
- `sutlab/` → source code
- `tests/` → tests
- `notes/claude/` → session notes, organised by topic (append, don't rewrite)

Claude should NOT read or write:
- `notes/mine/` → your personal notes

Claude should NOT:
- Make architectural or structural decisions unilaterally — propose, then wait for approval
- Reorganise modules without discussion
- Add dependencies without asking
- Write implementation code during planning sessions (small illustrative sketches are fine)
- Push to GitHub without asking

## Session instructions

### Start of every session:
1. Read this CLAUDE.md in full
2. Read all files in `notes/claude/`
3. State briefly: current phase, what was last worked on, what's next

### End of every session:
1. Append a summary to `notes/claude/` (organised by topic, not by session)
2. Update the Decisions log with anything settled this session
3. Update Open design questions — add newly surfaced ones, remove resolved ones
4. Update Current status
5. Suggest any CLAUDE.md edits for approval — do not edit directly

### Planning sessions:
- Propose options with explicit tradeoffs; do not advocate unless asked
- End with a clear statement of what has and hasn't been settled

### Implementation sessions:
- Check that relevant architecture decisions are settled before writing code
- Write tests alongside implementation, not after
- If a decision turns out to be ambiguous mid-implementation, stop and flag it rather than resolving silently
- Flag code that feels fragile, surprising, or assumption-laden, even if not asked

### General behaviour:
- When uncertain, say so explicitly rather than inferring silently
- Prefer proposing over doing for anything structural
- Prefer targeted edits over rewrites

