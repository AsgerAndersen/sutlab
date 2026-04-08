## Problem

Users balance SUT tables year by year using Jupyter notebooks, iterating between experimenting with balancing operations and inspecting results. The balancing process is exploratory — users try things, backtrack, and refine — so the workflow must not interfere with experimentation.

The end goal is a balanced time series, not just a single year. The typical workflow is:

1. Balance the latest year, then cascade that sequence backwards across the full revision period
2. Inspect the time series, identify where it breaks down
3. Either fix a single idiosyncratic year, or fix a year and cascade backwards again from that point
4. Repeat until the full time series is clean

This creates a piecewise structure: the time series ends up covered by a small number of anchor sequences, each applying to a contiguous range of years. A balancing sequence is a fixed ordered list of function calls — only the input data (the SUT for each year) varies.

## Solution

Three folders:

- **`explore_balancing`**: free experimentation; nothing here is canonical
- **`balancing_anchors`**: one notebook per anchor year, named `balance_YYYY.ipynb`, copied from `explore_balancing` when a sequence is finalised; also contains a required Excel file mapping each anchor year to the years it covers
- **`run_balancing`**: populated by a program that reads the Excel mapping, copies each anchor notebook for every year it covers (renaming to `balance_YYYY.ipynb` for the target year), sets `BALANCING_YEAR = YYYY` at the top of each notebook, and executes them

When a year looks strange, the user copies `balance_YYYY.ipynb` from `run_balancing` back into `explore_balancing`, experiments, and when satisfied moves the updated notebook to `balancing_anchors` (updating the Excel mapping if the anchor structure changes). Then reruns the program for the affected years.

## Open question: inspection context

Balancing operates on a single year, but inspection is most meaningful in a time series context. When experimenting with a sequence for year *t*, users want to see how *t* looks relative to other years in the revision period — but those other years may be in various states of balancing.

This raises the question of how to make the current best state of other years easily loadable into an exploration notebook. Some rough directions to explore with users:

- **Checkpoint flag**: an anchor notebook could optionally mark a point up to which it is executed for context purposes; results would be saved and loadable into exploration notebooks
- **Full run as context**: simply run all current anchors across all years and persist the results, so any exploration notebook can load a complete time series in its current best-balanced state
- **No special mechanism**: users manually load whichever years they need as context, accepting some friction