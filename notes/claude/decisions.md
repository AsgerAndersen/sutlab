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
