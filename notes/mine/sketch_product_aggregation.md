# Product Aggregation for SUT Tables

## Goal

Aggregate the product dimension of a SUT table such that IO tables derived from the aggregated SUT closely approximate the IO table derived from the full SUT.

## Why the method gives similar IO tables

Under the market shares assumption, IO derivation is linear — each product's uses are distributed to industries proportionally to its supply shares from the make matrix. Aggregation error therefore stems from heterogeneity in supply share vectors within a product group. The method controls this by only grouping products with the same dominant supplier (share criterion) or negligible total supply (size criterion), ensuring within-group share vectors are either near-identical or too small to matter.

## SUT to IO transformation (market shares assumption)

For a given product use, the transformation:

1. Splits the use into domestically produced and imported portions, using domestic/import shares from total supply
2. Allocates both portions to supplying industries using the domestic make matrix row for that product

If a product has no domestic production at all (import-only), it has no make matrix row. In that case the entire use is allocated to a single supplying industry identified by the product's **characteristic industry** from metadata. This is equivalent to a degenerate market share vector with 100% on one industry.

## Method

The user supplies a super-grouping — a dataframe mapping each product code to a super-group code. This constrains which products can ever be aggregated together. The method then produces the coarsest subdivision of each super-group that satisfies the criteria below.

All criteria are evaluated across all years simultaneously, so the resulting grouping is valid for all years for which SUTs are supplied.

For each super-group:

1. A product is **small** only if its total supply is below the size threshold in every individual year. A product that exceeds the threshold in any year is treated as large.
2. Determine each large product's dominant industry — the industry that exceeds the dominant share threshold in every year. If no single industry exceeds the threshold in all years, the product has no dominant industry. For import-only products, the characteristic industry from metadata is used directly (it trivially passes the threshold).
3. Each distinct dominant industry → one subgroup; large products with no dominant industry → each becomes a singleton.
4. Small products within a super-group form their own subgroup, separate from the large product subgroups.
5. Multiple subgroups within a super-group get numeric suffixes; the small products subgroup is suffixed `_other`.

## Inputs

| Input | Description |
|---|---|
| `sut_data` | SUT tables for all relevant years |
| `super_grouping` | Dataframe mapping each product code to a super-group code |
| `characteristic_industries` | Dataframe mapping each import-only product to its characteristic industry |

## Parameters

| Parameter | Description |
|---|---|
| `size_threshold` | Maximum total supply for a product to be considered small (must hold in all years) |
| `dominant_share_threshold` | Minimum share of one industry in a product's total supply for that industry to be considered dominant (e.g. 0.975); must hold in all years |

## Output

A dataframe mapping each original product code to its group code — the coarsest subdivision of the super-grouping satisfying the criteria. Suggested metadata columns:

- Original product code
- Super-group code
- Group code
- Total supply (per year or summarised)
- Dominant industry (if any)
- Number of products in group
- Criterion used: `share`, `characteristic_industry`, `singleton`, or `small`