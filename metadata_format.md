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

Two required columns plus one optional column:

| `code` | `name` | `gdp_component` |
|---|---|---|
| `P1` | Output at basic prices | `output` |
| `P7` | Imports of goods and services | `imports` |
| `P2` | Intermediate consumption | `intermediate` |
| `P31` | Individual consumption expenditure | `private_consumption` |
| `P32` | Collective consumption expenditure | `government_consumption` |
| `P51G` | Gross fixed capital formation | `investment` |
| `P6` | Exports of goods and services | `exports` |

The `gdp_component` column is optional. If it is present, it must use these exact values:

```
output
imports
intermediate
private_consumption
government_consumption
exports
investment
gross_fixed_capital_formation
inventory_changes
acquisitions_less_disposals_of_valuables
```

`investment` covers total capital formation. If your transaction table distinguishes the
sub-components, you can use `gross_fixed_capital_formation`, `inventory_changes`, and/or
`acquisitions_less_disposals_of_valuables` instead of or alongside `investment`. GDP
functions will show each component as a separate line in the output.

If `gdp_component` is absent, functions that compute or display GDP will return an error.
