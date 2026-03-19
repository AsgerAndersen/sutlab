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

- **2026-03-19**: Notes structure reorganised. Decisions log moved to this file.
  `data_representation.md` rewritten as a clean current-state reference. CLAUDE.md
  no longer requires reading all notes at session start — consult proactively when
  relevant.
