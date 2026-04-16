# inspect_aggregates_nominal — Design Reference

## Function signature

```python
inspect_aggregates_nominal(
    sut: SUT,
    gdp_decomp: pd.DataFrame | None = None,
) -> AggregatesNominalInspection
```

- `sut` must have `price_basis = "current_year"`
- `gdp_decomp`: optional override DataFrame with columns `{transaction_col}` (actual name from `SUTColumns`) and `"gdp_decomp"`. Mirrors the structure of `SUTClassifications.transactions` but with only those two columns. When provided, overrides the `gdp_decomp` column from `SUTClassifications.transactions`.
- Raises informative error if `gdp_decomp` column is absent from both the metadata and the override argument.

## Module location

`sutlab/inspect/_aggregates_nominal.py`, re-exported from `sutlab/inspect/__init__.py`.

## gdp_decomp column in metadata

Added as an extra column on `SUTClassifications.transactions`. Multiple transaction codes may share the same `gdp_decomp` value — they are summed into a single row. The column is optional in the metadata (function raises if absent and no override provided).

## ESA code usage

The function uses `esa_code` and `table` from `SUTClassifications.transactions` to identify which DataFrame to read from and how to use each transaction:

| ESA code | Role | DataFrame | Sign |
|---|---|---|---|
| P1 | Output | `sut.supply` | as-is |
| P2 | Intermediate consumption | `sut.use` | × −1 |
| P6 | Exports | `sut.use` | as-is |
| P7 | Imports | `sut.supply` | × −1 |
| D2121 | Import duties | `sut.supply` | as-is |

**Important**: P7 (imports) are supply-side transactions — they appear in `sut.supply`, not `sut.use`. The `table` column in `SUTClassifications.transactions` is the authoritative source for which DataFrame to read from. This also means P7 rows can never accidentally land in the expenditure block's domestic final use rows (which are read from `sut.use`).

D2121 is also supply-side and handled separately from the `gdp_decomp` mapping — identified purely by ESA code, not by `gdp_decomp` value.

## Product tax/subsidy rows

Come from summing the price layer columns (`product_taxes`, `product_subsidies`, `product_taxes_less_subsidies`, `vat`) across all products and all use rows. Only columns present in `SUTColumns` are included. D2121 (import duties) is summed from supply rows with ESA code D2121 across all products, and appears as its own row.

## Table structure

One DataFrame with columns = id values (years) and a 2-level MultiIndex on rows:

- Level 0: `"Production"`, `"Expenditure"`
- Level 1: component label

### Production block

| Level 1 | Source | Sign |
|---|---|---|
| `gdp_decomp` values for P1 transactions | `sut.supply`, basic prices | as-is |
| `gdp_decomp` values for P2 transactions | `sut.use`, purchasers' prices | × −1 |
| `"Gross Value Added"` | sum of all Production rows above | derived |
| one row per present price layer column | sum across all products/use rows | as-is |
| `"Import duties"` (if D2121 present) | sum of D2121 rows in `sut.supply` | as-is |
| `"Total product taxes, netto"` | sum of price layer + import duties rows | derived |
| `"GDP"` | GVA + Total product taxes, netto | derived |

### Expenditure block

| Level 1 | Source | Sign |
|---|---|---|
| `gdp_decomp` values for domestic final use transactions | `sut.use`, purchasers' prices | as-is |
| `"Domestic final expenditure"` | sum of domestic final use rows above | derived |
| `gdp_decomp` values for P6 transactions | `sut.use`, purchasers' prices | as-is |
| `gdp_decomp` values for P7 transactions | `sut.supply`, basic prices | × −1 |
| `"Export, netto"` | sum of P6 and P7 rows | derived |
| `"GDP"` | Domestic final expenditure + Export, netto | derived |

"Domestic final use" = all use-side ESA transactions except P2. Since P7 is supply-side, it is never in `sut.use` and cannot appear here.

## Sign convention

- P2 rows and P7 rows are multiplied by −1 explicitly.
- All other rows take whatever sign comes from the data.
- Derived rows (`Gross Value Added`, `Domestic final expenditure`, `Export, netto`, `GDP`) are simple sums of their component rows — sign is already baked in.

## Balancing note

The SUT is not necessarily balanced, so the GDP figures from Production and Expenditure approaches will not necessarily agree. This is intentional — both are shown, and the discrepancy is part of the inspection value.

## Output object

`AggregatesNominalInspection` with a `.data` attribute holding the GDP DataFrame. Styling deferred to a later session.

## Example: transaction → ESA code → gdp_decomp mapping

This is the structure of `SUTClassifications.transactions` with the optional `gdp_decomp` column added. The `table` column drives which DataFrame is read; `esa_code` drives the role in the GDP calculation.

| trans | trans_txt | table | esa_code | gdp_decomp |
|---|---|---|---|---|
| 0110 | Market output | supply | P1 | Market output |
| 0130 | Non-market output | supply | P1 | Non-market output |
| D2121 | Import duties | supply | D2121 | *(not used — identified by ESA code)* |
| 0700 | Imports | supply | P7 | Imports |
| 2000 | Intermediate consumption | use | P2 | Intermediate consumption |
| 3110 | Individual consumption | use | P31 | Private consumption |
| 3200 | Collective consumption | use | P32 | Government consumption |
| 5139 | Gross fixed capital formation | use | P51g | Gross fixed capital formation |
| 5200 | Inventory changes | use | P52 | Inventory changes |
| 6001 | Exports | use | P6 | Exports |

## Example: resulting GDP table

Values are illustrative. Note GDP differs between approaches — reflecting an unbalanced SUT.

| | | 2021 | 2022 | 2023 |
|---|---|---:|---:|---:|
| **Production** | Market output | 2,100 | 2,250 | 2,380 |
| | Non-market output | 450 | 470 | 490 |
| | Intermediate consumption | -1,200 | -1,280 | -1,340 |
| | **Gross Value Added** | **1,350** | **1,440** | **1,530** |
| | Trade margins | 80 | 85 | 89 |
| | Product taxes less subsidies | 120 | 128 | 133 |
| | VAT | 210 | 225 | 238 |
| | Import duties | 15 | 16 | 17 |
| | **Total product taxes, netto** | **425** | **454** | **477** |
| | **GDP** | **1,775** | **1,894** | **2,007** |
| **Expenditure** | Private consumption | 1,050 | 1,120 | 1,185 |
| | Government consumption | 480 | 500 | 520 |
| | Gross fixed capital formation | 380 | 410 | 435 |
| | Inventory changes | 30 | 28 | 32 |
| | **Domestic final expenditure** | **1,940** | **2,058** | **2,172** |
| | Exports | 620 | 660 | 695 |
| | Imports | -790 | -835 | -870 |
| | **Export, netto** | **-170** | **-175** | **-175** |
| | **GDP** | **1,770** | **1,883** | **1,997** |

## Relation to inspect_aggregates_real (future)

`inspect_aggregates_real(sut_current, sut_previous, ...)` will produce the same table structure but with chain-linked volume indices. Chain-linking is not additive, so derived rows (`Gross Value Added`, `GDP`, etc.) must be chain-linked independently, not computed as sums of chain-linked component rows. The two functions will share a private helper that defines the row structure (ESA code mappings, sign conventions, derived row positions) separately from value computation.
