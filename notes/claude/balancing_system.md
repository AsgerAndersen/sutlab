# Balancing system

## Context

The first major project goal is to implement the SUT balancing system described in
`notes/mine/sut_balancing.md`. This is a reimplementation of an existing Excel-based tool.

## Session: 2026-03-18 — Planning started

### What was established

**Project goal confirmed:** Implement a balancing system as a sequence of operations
(column_balance, row_balance, ras, shift, lock/unlock) applied to supply and use tables.

**Long-format data structure** (from exploring example data):

Columns: `nrnr` (product), `trans` (transaction code), `brch` (industry or consumption
classification — meaning depends on `trans`), `bas` (basic prices), `eng` (wholesale
margin), `det` (retail margin), `afg` (excise taxes), `moms` (VAT), `koeb` (purchasers'
prices).

Supply and use are stored as separate files per year:
- `ta_l_YYYY.parquet` — supply table
- `ta_d_YYYY.parquet` — use table

Price layers (`eng`, `det`, `afg`, `moms`) are sparse — only populated for transactions
where they apply (mainly intermediate use and household consumption).

**Data representation preferences (user):**
- Separate supply and use DataFrames (not combined)
- Long format (same column structure as source files)

### What was deferred

- Full data representation design for the balancing system — session ended before
  completing this. Specifically not yet settled:
  - How locks/cells are referenced (product/transaction/category keys?)
  - Whether price-layer share tables (α, β) are part of the SUT object or computed on the fly
  - Full module structure for the balancing system

---

## Session: 2026-03-18 — Data representation settled

### Decisions made

The SUT data structure has been redesigned to support both balancing and inspection
naturally. See `notes/claude/data_representation.md` for full details.

Key point for balancing: balancing functions will filter `sut.supply` and `sut.use` to
`sut.balancing_id` rows, operate on those, and return a new SUT with updated DataFrames.
The rest of the collection (other years) is carried along untouched.

### Still open

- How locks/cells are referenced
- Whether α/β share tables are stored on the SUT object or computed on the fly
- Full module structure
