# Path-finding in SUT balancing

## Problem

When balancing a SUT table, imbalances often have a known source and a known
natural absorber, but no direct product overlap between them. The adjustment
must propagate through the product-industry structure over multiple balancing
steps.

This raises the question: can we identify the propagation path in advance, and
use it to design a more targeted and efficient balancing sequence?

## Structure of the problem

The SUT defines a bipartite graph over products and industries. A balancing
"path" is a sequence of cells connecting a source imbalance to an absorbing
cell, where each hop is a nonzero flow in the table.

Given:
- A source cell with a known imbalance (e.g. intermediate use too high in industry X)
- A target absorber (e.g. investment final use with slack)

Find: an ordered sequence of cells/adjustments that moves the imbalance from
source to target.

## Possible approaches

### 1. Direct graph search

Model the SUT as a bipartite graph and run BFS/DFS from the source cell.
Edges are weighted by flow magnitude. Returns all paths to the absorber,
ranked by length and flow loss at each hop.

Simple and transparent, but ignores the systemic interdependence — treats
each hop as independent.

### 2. Backward search from absorber

Define absorbers first (cells with slack), then trace backwards through the
graph to find which upstream cells connect to them. Useful when the absorber
is known but the source is not, or for identifying which imbalances a given
absorber can resolve.

### 3. Structural Path Analysis (SPA)

Decomposes the Leontief inverse into an explicit, ranked sum of paths using
the Neumann series expansion:

    L = I + A + A² + A³ + ...

Each term Aᵏ encodes all paths of exactly k hops. For a given (source, target)
pair, SPA extracts the dominant paths and their relative contribution to the
total multiplier effect.

This gives both an actionable sequence of steps and a measure of path
efficiency — making it the most principled approach.

**Reference:** Defourny & Thorbecke (1984), *Structural Path Analysis and
Multiplier Decomposition within a Social Accounting Matrix Framework*

## Open questions

- How to translate a dominant SPA path into a concrete balancing operation sequence
- Whether paths are stable enough across iterations to be useful as a plan (vs.
  recomputing after each step)
- How to handle cycles in the graph (industries that supply each other)
- Whether to search in the full SUT or in a coefficients representation