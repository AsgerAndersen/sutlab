# Metadata file format

The library reads two Excel files to understand the structure of your SUT data: a
**columns file** and a **classifications file**. You can name these files whatever you
like and store them wherever you like — you provide the paths when calling the I/O
functions. Both file structures are described below.

---

## Columns file

Tells the library which column in your data plays which role.

Two columns, one row per column in your SUT DataFrames:

| `column` | `role` |
|---|---|
| `nrnr` | `product` |
| `trans` | `transaction` |
| `brch` | `category` |
| `bas` | `price_basic` |
| `koeb` | `price_purchasers` |
| `eng` | `wholesale_margins` |
| `det` | `retail_margins` |
| `afg` | `product_taxes_less_subsidies` |
| `moms` | `vat` |
| `year` | `id` |

The `column` values must match your actual DataFrame column names exactly.
The `role` values must be chosen from the fixed list below.

**Required roles** — these must be present:

| Role | Meaning |
|---|---|
| `id` | Column that identifies which year (or other period) each row belongs to |
| `product` | Product/good/service dimension |
| `transaction` | Transaction code (output, imports, intermediate use, etc.) |
| `category` | Industry, consumption function, or similar — the column dimension of the SUT matrix |
| `price_basic` | Values at basic prices |
| `price_purchasers` | Values at purchasers' prices |

**Optional roles** — include only those present in your data:

| Role | Meaning |
|---|---|
| `trade_margins` | Total trade margins (if not split into wholesale/retail) |
| `wholesale_margins` | Wholesale trade margins |
| `retail_margins` | Retail trade margins |
| `transport_margins` | Transport margins |
| `product_taxes` | Taxes on products (excluding VAT), gross |
| `product_subsidies` | Subsidies on products, if recorded separately |
| `product_taxes_less_subsidies` | Taxes less subsidies on products, net |
| `vat` | VAT |
| `target` | Target column totals used during balancing — the value column in balancing targets files |

---

## Classifications file

Provides labels and classification information for products, transactions, industries,
and consumption functions. The file as a whole is optional. Each sheet is also optional —
omit any sheet you do not have or do not need.

### Sheet: `classifications`

Maps each dimension to its classification system name. Used for display and documentation
purposes.

| `dimension` | `classification` |
|---|---|
| `products` | `NRNR07` |
| `transactions` | `...` |
| `industries` | `...` |
| `individual_consumption` | `...` |
| `collective_consumption` | `...` |

### Sheets: `products`, `industries`, `individual_consumption`, `collective_consumption`

Each of these sheets has two columns:

| `code` | `name` |
|---|---|
| `A01` | Crop and animal production |
| ... | ... |

### Sheet: `transactions`

Four columns. All four are required:

| `code` | `name` | `table` | `esa_code` |
|---|---|---|---|
| `0100` | Output at basic prices | `supply` | `P1` |
| `0700` | Imports of goods and services | `supply` | `P7` |
| `3110` | Intermediate consumption | `use` | `P2` |
| `3200` | Household consumption | `use` | `P31` |
| `3300` | Government collective consumption | `use` | `P32` |

`table` must be exactly `"supply"` or `"use"` for every row.

`esa_code` maps each institution-specific transaction code to a standardised ESA code.
Valid values: `P1`, `P2`, `P3`, `P31`, `P32`, `P51g`, `P52`, `P53`, `P6`, `P7`.
Any other value raises an error when loading.
