# SUT balancing system

## Purpose

We have an Excel-based system for balancing supply and use tables (SUTs). The system is built around a set of well-defined operations — proportional adjustments and RAS variants — which the user applies in sequence to bring a SUT into balance. It works well, but is slow on large tables and balancing sequences cannot be saved and rerun.

This system reimplements the operations as Python functions. This makes it possible to express a balancing procedure as an explicit, rerunnable sequence of calls, which can be applied automatically across a time series of SUTs.

## Input and output

**Input:**
- A SUT in purchasers' prices and basic prices, including intermediate price layers (margins and taxes)
- A configuration specifying locks and tolerances (see below)

**Output:**
- A balanced SUT satisfying product balances and target totals within the specified tolerances

## Price layer logic

The system balances in purchasers' prices. For each use cell $(i,j)$, fixed price layer shares are computed from the input SUT:

$$
\alpha_{ij} = \frac{\text{margin}_{ij}}{\text{purchasers}_{ij}}, \qquad \beta_{ij} = \frac{\text{tax}_{ij}}{\text{purchasers}_{ij}}
$$

These are held constant during balancing and used to convert between purchasers' prices and basic prices:

$$
\text{basic}_{ij} = (1 - \alpha_{ij} - \beta_{ij})\,\text{purchasers}_{ij}
$$

A product's total supply in purchasers' prices equals its supply in basic prices plus the *bridge value* — the sum of margins and taxes across all use cells for that product. The bridge value therefore depends on the use distribution.

## Configuration

The configuration specifies which cells are locked (unchanged during balancing) and which tolerances target totals must satisfy.

**Locks** can be specified at product, transaction, or cell level and are combined: a cell is locked if it is locked according to at least one criterion.

**Tolerances** are specified per transaction code as a relative and/or absolute bound:

$$
\text{tol} = \begin{cases} \text{rel} \cdot |\text{target}| & \text{rel only} \\ \text{abs} & \text{abs only} \\ \min(\text{rel} \cdot |\text{target}|,\; \text{abs}) & \text{both} \end{cases}
$$

After balancing, each target total must lie in $[\text{target} - \text{tol},\; \text{target} + \text{tol}]$. Tolerances can be overridden at the transaction–industry level.

## Operations

A balancing procedure is expressed as a sequence of calls to the functions below. Locked cells are never modified.

**`column_balance(columns, adjust_rows=None)`**  
Proportionally scales the specified columns in purchasers' prices to their target totals. If `adjust_rows` is given, only those rows absorb the adjustment. Underlying price layers are derived via the fixed shares.

**`row_balance(rows, adjust_columns=None)`**  
Proportionally scales use of the specified products so that total use equals total supply in purchasers' prices. Because the bridge value depends on the use distribution, this can be solved directly: the scaling factor is computed in basic prices as

$$
\frac{\text{total supply in basic prices}}{\text{total use in basic prices}}
$$

and then applied in purchasers' prices. (This is equivalent to the iterative method in the existing Excel system under the assumption of linear price layer formulas — this should be verified.)

**`ras(rows, columns, adjust_rows=None, adjust_columns=None, type)`**  
RAS balancing of the use matrix so that rows match product supplies and columns match target totals. `type` is either `RAS-area` (supply totals in purchasers' prices are held fixed) or `RAS-total` (supply totals are updated continuously via `RAS-SUT`, see below).

**`shift(from_, to, level, share=1.0)`**  
Moves a given share of values from one cell/row/column to another.

**`lock(x, level)`** / **`unlock(x, level)`**  
Locks or unlocks cells dynamically within a balancing sequence.

## RAS-SUT

`RAS-SUT` is a RAS variant that handles the case where row totals are given in basic prices and column totals in purchasers' prices. The algorithm iterates:

1. **Column step:** Proportionally scale columns in purchasers' prices to their target totals.
2. **Row step:** Compute row totals in basic prices; proportionally scale rows in purchasers' prices using the resulting factors.

Repeat until column totals are within their column-specific tolerances and row totals in basic prices are satisfied within numerical tolerance. Consistency between the row and column constraints cannot be verified analytically before balancing, since the transformation between basic and purchasers' prices depends on the use distribution.

## Inspection

Users need to be able to look up values in the tables, check imbalances, and inspect aggregates throughout the balancing process — both to understand the current state before choosing an action and to evaluate the consequences afterwards.

A set of inspection functions supports this. For now, each returns a dataclass containing one or more DataFrames and optionally figures.
