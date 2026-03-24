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

**Requirements:** `sut.metadata.classifications.transactions` must be loaded and must include a `name` column and an `esa_code` column. Product labels are optional — if no product classification is loaded, the `product_txt` index level is empty throughout.

### Accessing results

Each table is available in two forms:

```python
result.balance          # styled — renders directly in Jupyter
result.data.balance     # raw DataFrame — use for further calculations
```

All styled properties use European number formatting (`1.234.567,8`). Distribution and growth tables are formatted as percentages (`5,0%`).

### Tables

The result contains 12 tables, grouped below by topic.

---

#### Balance

`balance` — one row per transaction, columns are years. Supply transactions appear first, then *Total supply*, then use transactions, then *Total use*, then *Balance* (supply minus use). Values are at basic prices.

`balance_distribution` — same structure, without the Balance row. Supply rows are expressed as a share of Total supply; use rows as a share of Total use.

`balance_growth` — same structure, without the Balance row. Each value is the year-on-year change: `(current − previous) / previous`.

---

#### Supply and use detail

`supply_detail` / `use_detail` — category breakdown (by industry or consumption function) for transactions that have categories. Rows have a six-level index: product, product label, transaction, transaction label, category, category label. Values are at basic prices.

`supply_detail_distribution` / `use_detail_distribution` — each value expressed as a share of the product's total supply (or use) in that year.

`supply_detail_growth` / `use_detail_growth` — year-on-year change within each category row.

---

#### Price layers

`price_layers` — shows how the gap between basic prices and purchasers' prices is distributed across transactions, for each intermediate price layer (trade margins, VAT, etc.). One block per `(product, layer)` combination, ending with a *Total* row. Only layers present in the data and only transactions with non-zero values for that layer are shown.

`price_layers_distribution` — each transaction row expressed as a share of the Total for that `(product, layer)` block in each year.

`price_layers_growth` — year-on-year change within each row.

---

### Row MultiIndex levels

| Table group | Index levels |
|---|---|
| Balance | `product`, `product_txt`, `transaction`, `transaction_txt` |
| Detail | `product`, `product_txt`, `transaction`, `transaction_txt`, `category`, `category_txt` |
| Price layers | `product`, `product_txt`, `price_layer`, `transaction`, `transaction_txt` |

The `*_txt` levels contain labels from the classifications file, or an empty string if the relevant classification is not loaded. `price_layer` contains the actual column name from the use DataFrame (e.g. `ava`, `moms`).
