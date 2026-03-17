# Project: sutlab

## What this project does
Python library for compiling, balancing, and analysing supply and use tables (SUTs) in the Danish national accounts. Primary users are ~10 colleagues at Statistics Denmark with mixed Python experience, most with SAS backgrounds.

## Technology stack
- Language: Python 3.12
- Environment: UV — run Python with `uv run python` from the project root. No activation needed.
- Package install policy: always ask before adding new dependencies; use `uv add`
- Key dependencies: pandas, openpyxl (Excel for metadata/configuration), pyarrow (parquet support) — others to be decided

## Current project goals
*(to be decided)*

## Current status
- **Phase**: Planning
- **What exists**: Project skeleton only
- **What's next**: Decide core data representation

## Architecture
<!-- Canonical record of settled decisions. Update when decisions are made, never delete. -->

### Module structure
*(to be decided)*

### Core data representation
*(to be decided — first planning priority)*

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
- **Current prices**: SUT values expressed in the prices of the current year t. The monetary tables as compiled.
- **Previous year's prices**: SUT values for year t revalued at the prices of year t-1. Used as the basis for volume calculations.
- **Chain-linked volume indices**: Volume time series constructed by linking year-to-year Laspeyres volume indices. Derived from the current and previous year's prices tables — not directly observable in the SUT.
- **Supplementary data**: Physical or volume measures outside the monetary accounting framework (e.g. hours worked, employment, capital stock). Used for e.g. productivity analysis but not part of the SUT itself.

## Reference documentation
Do NOT read proactively. Consult only when a specific question requires it, and read targeted sections only.
- `docs/reference/` → Standards documents (e.g. SNA 2008). Specific files to be added as needed.

## Data
- `data/examples/` → Example SUT data from Statistics Denmark. Parquet files for SUT tables (pandas DataFrames saved with `to_parquet`). Gitignored — do not commit.
- `data/examples/metadata/` → Metadata for example data (e.g. classifications). Excel files. Gitignored — do not commit.
- `data/fixtures/` → Small synthetic data for tests. Two levels: minimal (2-3 products, 2 industries, hand-crafted round numbers) and small (aggregated from real data, more realistic). Not yet created.

## Decisions log
<!-- Append when a decision is made. Never delete entries. -->
*(none yet)*

## Open design questions
- What is the core data representation? (first priority)
- How should classification metadata be structured? The code should be abstract with respect to classification systems — classifications are user-specified, not hardcoded. Users will typically load them from Excel, but the internal representation should not assume a source format.
- What is the module structure?

## Project structure

Always read CLAUDE.md from the main repo: `C:\Users\DstMove\Desktop\claude\projects\sutlab\CLAUDE.md` — not from any worktree copy.

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
- Commit or mention committing `data/examples/`
- Push to GitHub without asking

## Session instructions

### Start of every session:
1. Read this CLAUDE.md in full
2. Run Python with `uv run python` from the project root — no activation needed
3. Read all files in `notes/claude`
4. State briefly: current phase, what was last worked on, what's next

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

## Session history
<!-- Updated by Claude at the end of every session -->
*(none yet)*
