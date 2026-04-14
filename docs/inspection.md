# Inspection functions

Inspection functions summarise a SUT collection across all years. They are designed to be called in a Jupyter notebook, where the results render as styled tables.

---

## inspect_products

Returns a set of tables describing the supply, use, and price layer structure of one or more products across the full collection.

```python
from sutlab.inspect import inspect_products

result = inspect_products(sut, "A01")              # one product
result = inspect_products(sut, ["A01", "A02"])     # list of products
result = inspect_products(sut, "A0*")              # wildcard
result = inspect_products(sut, "A01:B10")          # range
```

The product argument accepts the same pattern syntax as `get_rows` — see `sut_format.md`.

**Filtering years:** by default all years in the collection are shown. Use the `ids` argument to restrict to specific years:

```python
result = inspect_products(sut, "A01", ids=2021)              # single year
result = inspect_products(sut, "A01", ids=[2019, 2020])      # list of years
result = inspect_products(sut, "A01", ids=range(2015, 2022)) # range of years
```

**Requirements:** `sut.metadata.classifications.transactions` must be loaded and must include a `name` column and an `esa_code` column. Product labels are optional — if no product classification is loaded, the `product_txt` index level is empty throughout.

### Accessing results

Each table is available in two forms:

```python
result.balance          # styled — renders directly in Jupyter
result.data.balance     # raw DataFrame — use for further calculations
```

All styled properties use European number formatting (`1.234.567,8`). Distribution and growth tables are formatted as percentages (`5,0%`).

### Tables

The result contains 17 tables, grouped below by topic.

---

#### Balance

`balance` — one row per transaction, columns are years. Supply transactions appear first (values at basic prices), then *Price layers* (total intermediate price layers from the use side — the difference between purchasers' and basic prices, summed across all use transactions for that product), then *Total supply* (at purchasers' prices), then use transactions (at purchasers' prices), then *Total use*, then *Balance* (Total supply minus Total use).

`balance_distribution` — same structure, without the Balance row. Supply-side rows (including Price layers and Total supply) are expressed as a share of Total supply; use rows as a share of Total use.

`balance_growth` — same structure, without the Balance row. Each value is the year-on-year change: `(current − previous) / previous`.

---

#### Supply and use detail

`supply_products` / `use_products` — category breakdown (by industry or consumption function) for all transactions. Transactions with category breakdowns show one row per category; transactions with no categories appear as a single row with an empty category code. Rows have a six-level index: product, product label, transaction, transaction label, category, category label. Each product block ends with a *Total supply* (or *Total use*) row summing all transactions and categories for that product and year. Supply values are at basic prices; use values are at purchasers' prices.

`supply_products_distribution` / `use_products_distribution` — each category row expressed as a share of the product's total supply (or use) in that year. The Total supply/use row is 1.0.

`supply_products_growth` / `use_products_growth` — year-on-year change within each row.

---

#### Price layers

`price_layers` — shows how the gap between basic prices and purchasers' prices is distributed across transactions, for each intermediate price layer (trade margins, VAT, etc.). One block per `(product, layer)` combination, ending with a *Total* row. Only layers present in the data and only transactions with non-zero values for that layer are shown.

`price_layers_distribution` — each transaction row expressed as a share of the Total for that `(product, layer)` block in each year.

`price_layers_growth` — year-on-year change within each row.

`price_layers_rates` — same structure as `price_layers`, but every value is the rate at which that layer grows the cumulative price at the step it is added. Rates are computed per transaction: `ava_rate = ava / basic` and `moms_rate = moms / (basic + ava)`, where numerator and denominator are both for that specific transaction. No Total rows (Total rates are not meaningful). Division by zero yields NaN.

---

#### Price layers — detailed (by category)

`price_layers_detailed` — same concept as `price_layers`, but disaggregated one further level to category (industry or consumption function). One block per `(product, layer)` combination. Within each block, rows appear in the same transaction order as `price_layers`, with each transaction's category rows sorted naturally. Each block ends with a Total row (identical to the corresponding `price_layers` Total). 7-level MultiIndex: `(product, product_txt, price_layer, transaction, transaction_txt, category, category_txt)`. Total rows have `transaction=""` and `transaction_txt="Total"`.

`price_layers_detailed_distribution` — same structure as `price_layers_detailed`. Each row (including Total) expressed as a share of the block Total for that `(product, layer)` and year. Total row is always 1.0.

`price_layers_detailed_growth` — same structure as `price_layers_detailed`. Year-on-year change within each row. First year is NaN. Balance row excluded.

`price_layers_detailed_rates` — rates computed per `(transaction, category)` cell, using the same step-wise denominator logic as `price_layers_rates`. No Total rows. 7-level MultiIndex (same as `price_layers_detailed`).

---

### Row MultiIndex levels

| Table group | Index levels |
|---|---|
| Balance | `product`, `product_txt`, `transaction`, `transaction_txt` |
| Detail | `product`, `product_txt`, `transaction`, `transaction_txt`, `category`, `category_txt` |
| Price layers | `product`, `product_txt`, `price_layer`, `transaction`, `transaction_txt` |
| Price layers detailed | `product`, `product_txt`, `price_layer`, `transaction`, `transaction_txt`, `category`, `category_txt` |

The `*_txt` levels contain labels from the classifications file, or an empty string if the relevant classification is not loaded. `price_layer` contains the actual column name from the use DataFrame (e.g. `ava`, `moms`).
