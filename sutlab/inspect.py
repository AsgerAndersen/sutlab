"""
Inspection functions for supply and use tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes, _natural_sort_key


def _format_number(value: float) -> str:
    """Format a raw value with European thousands separator and one decimal.

    Example: 1234567.8 → "1.234.567,8"
    """
    if pd.isna(value):
        return ""
    formatted = f"{value:,.1f}"
    return formatted.replace(",", "§").replace(".", ",").replace("§", ".")


def _format_percentage(value: float) -> str:
    """Format a fraction as a European-style percentage string with two decimals.

    Example: 0.05 → "5,0%"
    """
    if pd.isna(value):
        return ""
    return f"{value * 100:.1f}".replace(".", ",") + "%"


# Cycling colour palettes for price layer blocks.
# Each palette has two alternating light shades for transaction rows,
# a more saturated shade for Total data cells, and a more saturated shade
# for index cells (used on price_layer, transaction, and transaction_txt).
_LAYER_PALETTES = [
    {  # amber
        "data":        ("#fffde7", "#fffef5"),
        "data_total":  "#fff3c4",
        "index":       ("#fff8cc", "#fffbe0"),
        "index_total": "#ffecaa",
    },
    {  # purple
        "data":        ("#f8f0ff", "#fbf6ff"),
        "data_total":  "#ecd8f8",
        "index":       ("#f2e4ff", "#f6eeff"),
        "index_total": "#e0c5f5",
    },
    {  # teal
        "data":        ("#e8faf8", "#f2fcfb"),
        "data_total":  "#b8ece8",
        "index":       ("#d8f5f2", "#e5f8f6"),
        "index_total": "#a8e0dc",
    },
    {  # rose
        "data":        ("#fff0f4", "#fff8fa"),
        "data_total":  "#fcd4e4",
        "index":       ("#ffe4ee", "#ffecf4"),
        "index_total": "#f8bbce",
    },
]

# Balance table row colours.
# Data cells use lighter shades; index cells use slightly darker shades of the
# same hue to match the visual convention in default Jupyter DataFrame display.
_DATA_COLORS = {
    "supply":        ("#e8f5e9", "#f1faf2"),
    "supply_total":  "#c8e6c9",
    "use":           ("#e3f2fd", "#ecf6fe"),
    "use_total":     "#bbdefb",
    "balance":       "#f5f5f5",
}
_INDEX_COLORS = {
    "supply":        ("#d8eedb", "#e3f3e5"),
    "supply_total":  "#b8d8ba",
    "use":           ("#d0e8f8", "#dbedfa"),
    "use_total":     "#a5cff4",
    "balance":       "#e5e5e5",
}


def _build_balance_row_css(df: pd.DataFrame, colors: dict) -> list[str]:
    """Return a list of CSS strings, one per row of the balance table.

    Determines each row's type (supply transaction, Total supply, use
    transaction, Total use, Balance) and returns the corresponding
    background-color and font-weight CSS, using the provided ``colors`` dict.
    Pass ``_DATA_COLORS`` for data cells and ``_INDEX_COLORS`` for index cells.
    """
    trans_txt_vals = df.index.get_level_values("transaction_txt")
    product_vals = df.index.get_level_values("product")
    row_css = [""] * len(df)

    for product in product_vals.unique():
        abs_positions = [i for i, v in enumerate(product_vals) if v == product]
        block_txts = [trans_txt_vals[i] for i in abs_positions]

        total_supply_pos = block_txts.index("Total supply")
        supply_counter = 0
        use_counter = 0

        for j, (i_abs, txt) in enumerate(zip(abs_positions, block_txts)):
            if txt == "Total supply":
                bg = colors["supply_total"]
                bold = True
            elif txt == "Total use":
                bg = colors["use_total"]
                bold = True
            elif txt == "Balance":
                bg = colors["balance"]
                bold = False
            elif j < total_supply_pos:
                bg = colors["supply"][supply_counter % 2]
                supply_counter += 1
                bold = False
            else:
                bg = colors["use"][use_counter % 2]
                use_counter += 1
                bold = False

            weight = "bold" if bold else "normal"
            row_css[i_abs] = f"background-color: {bg}; font-weight: {weight}"

    # Add a separator line after the Balance row of every product block except
    # the last, so multi-product tables have a clear visual boundary.
    products_list = list(product_vals.unique())
    for product in products_list[:-1]:
        abs_positions = [i for i, v in enumerate(product_vals) if v == product]
        block_txts = [trans_txt_vals[i] for i in abs_positions]
        row_css[abs_positions[-1]] += "; border-bottom: 2px solid #999"

    return row_css


def _style_balance_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply colours, bold, and product separators to a balance-shaped table.

    Used by the ``balance``, ``balance_distribution``, and ``balance_growth``
    properties. ``format_func`` is applied to all data cells.
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    index_css = _build_balance_row_css(df, _INDEX_COLORS)

    trans_vals = df.index.get_level_values("transaction")
    trans_txt_vals = df.index.get_level_values("transaction_txt")
    product_vals = df.index.get_level_values("product")
    products_list = list(product_vals.unique())
    n = len(df)

    # transaction level: colour non-"" cells; for non-last products, put the
    # separator border on the Total use row (first of the merged "" span).
    transaction_css = [
        css if t != "" else "" for css, t in zip(index_css, trans_vals)
    ]

    # product and product_txt levels: pandas merges each product block into one
    # <th>, using CSS from the first row. Put the separator on the first row of
    # each non-last product block so the border appears after the last row.
    product_css = [""] * n
    product_txt_css = [""] * n

    for product in products_list[:-1]:
        abs_positions = [i for i, v in enumerate(product_vals) if v == product]
        block_txts = [trans_txt_vals[i] for i in abs_positions]

        product_css[abs_positions[0]] = "border-bottom: 2px solid #999"
        product_txt_css[abs_positions[0]] = "border-bottom: 2px solid #999"

        total_use_abs = abs_positions[block_txts.index("Total use")]
        transaction_css[total_use_abs] = "border-bottom: 2px solid #999"

    styler = styler.apply(_apply_balance_style, axis=None)
    styler = styler.apply_index(
        lambda s, css=transaction_css: css, level="transaction", axis=0
    )
    styler = styler.apply_index(
        lambda s, css=index_css: css, level="transaction_txt", axis=0
    )
    styler = styler.apply_index(
        lambda s, css=product_css: css, level="product", axis=0
    )
    styler = styler.apply_index(
        lambda s, css=product_txt_css: css, level="product_txt", axis=0
    )
    styler = styler.set_table_styles(
        [{"selector": "", "props": [("display", "block"), ("overflow-y", "auto"), ("max-height", "600px")]}],
        overwrite=False,
    )
    return styler


def _style_detail_table(df: pd.DataFrame, format_func, color_key: str) -> Styler:
    """Apply row colours and separators to a detail table (supply_detail or use_detail).

    Parameters
    ----------
    df : pd.DataFrame
        A supply_detail or use_detail DataFrame.
    format_func : callable
        Applied to all data cells (e.g. ``_format_number``).
    color_key : str
        ``"supply"`` or ``"use"`` — selects the colour set from
        ``_DATA_COLORS`` / ``_INDEX_COLORS``.
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    data_row_colors = _DATA_COLORS[color_key]
    idx_row_colors = _INDEX_COLORS[color_key]
    idx_hdr_color = _INDEX_COLORS[f"{color_key}_total"]

    product_vals = df.index.get_level_values("product")
    trans_vals = df.index.get_level_values("transaction")
    products = list(product_vals.unique())
    n = len(df)

    data_css = [""] * n
    cat_css = [""] * n
    cat_txt_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n
    prod_css = [""] * n
    prod_txt_css = [""] * n

    for p_idx, product in enumerate(products):
        is_last_product = (p_idx == len(products) - 1)
        prod_positions = [i for i, v in enumerate(product_vals) if v == product]
        # Ordered unique transactions for this product
        prod_trans = list(dict.fromkeys(trans_vals[i] for i in prod_positions))

        if not is_last_product:
            prod_css[prod_positions[0]] = "border-bottom: 2px solid #999"
            prod_txt_css[prod_positions[0]] = "border-bottom: 2px solid #999"

        for t_idx, trans in enumerate(prod_trans):
            is_last_trans = (t_idx == len(prod_trans) - 1)
            trans_positions = [i for i in prod_positions if trans_vals[i] == trans]

            if not is_last_trans:
                sep = "; border-bottom: 1px solid #ccc"
            elif not is_last_product:
                sep = "; border-bottom: 2px solid #999"
            else:
                sep = ""

            # transaction / transaction_txt: one merged cell per block → CSS on first row
            trans_css[trans_positions[0]] = f"background-color: {idx_hdr_color}{sep}"
            trans_txt_css[trans_positions[0]] = f"background-color: {idx_hdr_color}{sep}"

            for i, i_abs in enumerate(trans_positions):
                is_last_row = (i == len(trans_positions) - 1)
                row_sep = sep if is_last_row else ""
                bg_data = data_row_colors[i % 2]
                bg_idx = idx_row_colors[i % 2]
                data_css[i_abs] = f"background-color: {bg_data}{row_sep}"
                cat_css[i_abs] = f"background-color: {bg_idx}{row_sep}"
                cat_txt_css[i_abs] = f"background-color: {bg_idx}{row_sep}"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=cat_css: css, level="category", axis=0)
    styler = styler.apply_index(lambda s, css=cat_txt_css: css, level="category_txt", axis=0)
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    styler = styler.apply_index(lambda s, css=prod_css: css, level="product", axis=0)
    styler = styler.apply_index(lambda s, css=prod_txt_css: css, level="product_txt", axis=0)
    styler = styler.set_table_styles(
        [{"selector": "", "props": [("display", "block"), ("overflow-y", "auto"), ("max-height", "600px")]}],
        overwrite=False,
    )
    return styler


def _style_price_layers_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply colours, bold, and separators to a price_layers-shaped table.

    Each distinct ``price_layer`` value gets a colour from ``_LAYER_PALETTES``
    (cycling if there are more layers than palette entries). Within each
    ``(product, price_layer)`` block:

    - Transaction rows alternate between the two light shades of that layer's
      palette; their ``transaction`` and ``transaction_txt`` index cells use
      the more saturated shade.
    - The Total row uses the more saturated data shade and is bold throughout
      (data cells and ``transaction``/``transaction_txt`` index cells).
    - The ``price_layer`` index cell (one merged cell per block) uses the
      more saturated shade; the separator border is placed on it so the
      border-bottom aligns with the block boundary.

    Separators: ``1px solid #ccc`` between layer blocks within a product,
    ``2px solid #999`` between product blocks.
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    product_vals = df.index.get_level_values("product")
    layer_vals = df.index.get_level_values("price_layer")
    trans_txt_vals = df.index.get_level_values("transaction_txt")
    n = len(df)

    data_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n
    layer_css = [""] * n
    prod_css = [""] * n
    prod_txt_css = [""] * n

    products = list(dict.fromkeys(product_vals))

    for p_idx, product in enumerate(products):
        is_last_product = (p_idx == len(products) - 1)
        prod_positions = [i for i, v in enumerate(product_vals) if v == product]
        prod_layers = list(dict.fromkeys(layer_vals[i] for i in prod_positions))

        # product/product_txt: one merged cell per product — separator on first row
        if not is_last_product:
            prod_css[prod_positions[0]] = "border-bottom: 2px solid #999"
            prod_txt_css[prod_positions[0]] = "border-bottom: 2px solid #999"

        for l_idx, layer in enumerate(prod_layers):
            is_last_layer = (l_idx == len(prod_layers) - 1)
            palette = _LAYER_PALETTES[l_idx % len(_LAYER_PALETTES)]

            block_positions = [i for i in prod_positions if layer_vals[i] == layer]
            block_txts = [trans_txt_vals[i] for i in block_positions]

            if not is_last_layer:
                sep = "; border-bottom: 1px solid #ccc"
            elif not is_last_product:
                sep = "; border-bottom: 2px solid #999"
            else:
                sep = ""

            # price_layer index: one merged cell per block — CSS (+ separator) on first row
            layer_css[block_positions[0]] = f"background-color: {palette['index_total']}{sep}"

            counter = 0
            for i, i_abs in enumerate(block_positions):
                is_last_row = (i == len(block_positions) - 1)
                is_total = (block_txts[i] == "Total")
                row_sep = sep if is_last_row else ""

                if is_total:
                    bg_data = palette["data_total"]
                    bg_index = palette["index_total"]
                    bold = True
                else:
                    bg_data = palette["data"][counter % 2]
                    bg_index = palette["index"][counter % 2]
                    bold = False
                    counter += 1

                weight = "bold" if bold else "normal"
                data_css[i_abs] = f"background-color: {bg_data}; font-weight: {weight}{row_sep}"
                trans_css[i_abs] = (
                    f"background-color: {bg_index}; font-weight: {weight}{row_sep}"
                )
                trans_txt_css[i_abs] = (
                    f"background-color: {bg_index}; font-weight: {weight}{row_sep}"
                )

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    styler = styler.apply_index(lambda s, css=layer_css: css, level="price_layer", axis=0)
    styler = styler.apply_index(lambda s, css=prod_css: css, level="product", axis=0)
    styler = styler.apply_index(lambda s, css=prod_txt_css: css, level="product_txt", axis=0)
    styler = styler.set_table_styles(
        [{"selector": "", "props": [("display", "block"), ("overflow-y", "auto"), ("max-height", "600px")]}],
        overwrite=False,
    )
    return styler


def _apply_balance_style(df: pd.DataFrame) -> pd.DataFrame:
    """Return a same-shape DataFrame of CSS strings for the balance table data cells."""
    row_css = _build_balance_row_css(df, _DATA_COLORS)
    return pd.DataFrame(
        {col: row_css for col in df.columns},
        index=df.index,
    )


# ESA code → attribute name on SUTClassifications for category label lookup.
# Transactions with ESA codes outside this mapping (P6, P7, P51g, P52, ...)
# are not expected to have category breakdowns.
_ESA_TO_CLASSIFICATION_ATTR: dict[str, str] = {
    "P1":  "industries",
    "P2":  "industries",
    "P31": "individual_consumption",
    "P32": "collective_consumption",
}


@dataclass
class ProductInspectionData:
    """Raw DataFrames underlying a :class:`ProductInspection`.

    Use these directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding properties on :class:`ProductInspection`,
    which return styled versions.
    """

    balance: pd.DataFrame
    supply_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_detail_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_detail_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_shares: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class ProductInspection:
    """
    Result of :func:`inspect_products`.

    Raw DataFrames are available under ``result.data``. The properties on
    this class return :class:`~pandas.io.formats.style.Styler` objects that
    render with European number formatting in Jupyter notebooks.

    Attributes
    ----------
    balance : pd.DataFrame
        Wide-format balance table. Rows have a four-level MultiIndex with
        names ``product``, ``product_txt``, ``transaction``,
        ``transaction_txt``:

        - ``product``: product code (e.g. ``"V10100"``).
        - ``product_txt``: product name from classifications, or ``""`` if
          no product classification is loaded.
        - ``transaction``: transaction code for data rows (e.g. ``"0100"``),
          or ``""`` for summary rows.
        - ``transaction_txt``: transaction name for data rows
          (e.g. ``"Output at basic prices"``), or ``"Total supply"``,
          ``"Total use"``, ``"Balance"`` for summary rows.

        Supply transactions appear first, then ``"Total supply"``, then use
        transactions, then ``"Total use"``, then ``"Balance"`` (Total supply
        minus Total use). Columns are the collection ids (e.g. years). Values
        are at basic prices. Missing cells are filled with ``0``.

    supply_detail : pd.DataFrame
        Wide-format category breakdown for supply transactions. Rows have a
        six-level MultiIndex with names ``product``, ``product_txt``,
        ``transaction``, ``transaction_txt``, ``category``, ``category_txt``:

        - ``product``: product code.
        - ``product_txt``: product name from classifications, or ``""`` if
          no product classification is loaded.
        - ``transaction``: transaction code (e.g. ``"0100"``).
        - ``transaction_txt``: transaction name (e.g. ``"Output at basic
          prices"``).
        - ``category``: category code (e.g. industry code).
        - ``category_txt``: category name from the matching classification
          (``industries``, ``individual_consumption``, or
          ``collective_consumption``), determined via the ``esa_code`` column
          in the transaction classification. ``""`` if the classification is
          not loaded or the ESA code is not in the mapping.

        Only transactions where at least one selected product has non-empty
        categories are included. Products with no rows for a given transaction
        are omitted. Columns are the collection ids (e.g. years). Values are
        at basic prices. Missing cells are filled with ``0``.

    use_detail : pd.DataFrame
        Same structure as ``supply_detail``, for use-side transactions.

    balance_distribution : pd.DataFrame
        Same structure as ``balance``. Supply-side rows (up to and including
        ``"Total supply"``) are divided by ``"Total supply"`` for each year.
        Use-side rows (up to and including ``"Total use"``) are divided by
        ``"Total use"`` for each year. The ``"Balance"`` row is divided by
        ``"Total supply"``. Where the denominator is zero the result is
        ``NaN``.

    supply_detail_distribution : pd.DataFrame
        Same structure as ``supply_detail``. For each product and year, every
        value is divided by the sum across all transactions and categories for
        that product in that year. Values therefore express each category's
        share of total supply for the product in each year.

    use_detail_distribution : pd.DataFrame
        Same structure as ``use_detail``, with the same normalization as
        ``supply_detail_distribution`` but relative to total use.

    balance_growth : pd.DataFrame
        Same structure as ``balance``. Each value is the change relative to
        the previous year: ``(current - previous) / previous``, so 5% growth
        is stored as ``0.05``. The first year column is ``NaN`` throughout.
        Division by zero also yields ``NaN``.

    supply_detail_growth : pd.DataFrame
        Same structure as ``supply_detail``, with the same year-on-year
        growth calculation as ``balance_growth``.

    use_detail_growth : pd.DataFrame
        Same structure as ``use_detail``, with the same year-on-year
        growth calculation as ``balance_growth``.

    price_layers : pd.DataFrame
        Wide-format price layer breakdown for use-side transactions. Rows
        have a five-level MultiIndex with names ``product``, ``product_txt``,
        ``price_layer``, ``transaction``, ``transaction_txt``:

        - ``product``: product code.
        - ``product_txt``: product name from classifications, or ``""`` if
          no product classification is loaded.
        - ``price_layer``: the actual column name of the price layer in the
          use DataFrame (e.g. ``"ava"``, ``"moms"``), in the order the
          columns appear in ``sut.use``. Only layers mapped to a non-``None``
          role in ``SUTColumns`` and present in ``sut.use`` are included.
        - ``transaction``: transaction code for data rows, or ``""`` for
          the Total row.
        - ``transaction_txt``: transaction name for data rows, or
          ``"Total"`` for the summary row.

        One block per ``(product, price_layer)`` combination. Within each
        block, only use transactions with at least one non-zero value for
        that layer are included, followed by a Total row summing across
        them. Columns are the collection ids. Empty DataFrame if no price
        layer columns are present.

    price_layers_distribution : pd.DataFrame
        Same structure as ``price_layers``. Within each
        ``(product, price_layer)`` block, every row is divided by the
        Total row for that year. The Total row itself becomes ``1.0``.
        Division by zero yields ``NaN``.

    price_layers_growth : pd.DataFrame
        Same structure as ``price_layers``, with the same year-on-year
        growth calculation as ``balance_growth``.

    price_layers_shares : pd.DataFrame
        Same structure as ``price_layers``. Every value is divided by the
        total use at purchasers' prices for that product and year (sum of
        the purchasers' price column across all use rows for that product).
        Expresses each price layer row as a share of the product's total
        purchasers' price use. Division by zero yields ``NaN``.
    """

    data: ProductInspectionData

    @property
    def balance(self) -> Styler:
        return _style_balance_table(self.data.balance, _format_number)

    @property
    def supply_detail(self) -> Styler:
        return _style_detail_table(self.data.supply_detail, _format_number, "supply")

    @property
    def use_detail(self) -> Styler:
        return _style_detail_table(self.data.use_detail, _format_number, "use")

    @property
    def balance_distribution(self) -> Styler:
        return _style_balance_table(self.data.balance_distribution, _format_percentage)

    @property
    def supply_detail_distribution(self) -> Styler:
        return _style_detail_table(self.data.supply_detail_distribution, _format_percentage, "supply")

    @property
    def use_detail_distribution(self) -> Styler:
        return _style_detail_table(self.data.use_detail_distribution, _format_percentage, "use")

    @property
    def balance_growth(self) -> Styler:
        return _style_balance_table(self.data.balance_growth, _format_percentage)

    @property
    def supply_detail_growth(self) -> Styler:
        return _style_detail_table(self.data.supply_detail_growth, _format_percentage, "supply")

    @property
    def use_detail_growth(self) -> Styler:
        return _style_detail_table(self.data.use_detail_growth, _format_percentage, "use")

    @property
    def price_layers(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers, _format_number)

    @property
    def price_layers_distribution(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers_distribution, _format_percentage)

    @property
    def price_layers_growth(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers_growth, _format_percentage)

    @property
    def price_layers_shares(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers_shares, _format_percentage)


def inspect_products(sut: SUT, products: str | list[str]) -> ProductInspection:
    """
    Return inspection tables for one or more products.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    products : str or list of str
        Product codes to include. Accepts the same pattern syntax as
        :func:`get_rows`: exact codes, wildcards (``*``), ranges (``:``),
        and negation (``~``).

    Returns
    -------
    ProductInspection
        A dataclass with 12 inspection tables. Raw DataFrames are available
        under ``result.data``; the same-named properties on the returned
        object give styled versions for Jupyter display. See
        :class:`ProductInspection` for field descriptions.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.metadata.classifications`` or
        ``sut.metadata.classifications.transactions`` is ``None`` — required
        to look up transaction names.
    ValueError
        If ``sut.metadata.classifications.transactions`` does not have a
        ``name`` column.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call inspect_products. "
            "Provide a SUTMetadata with column name mappings."
        )
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            "sut.metadata.classifications.transactions is required to call "
            "inspect_products. Load a classifications file with a "
            "'transactions' sheet."
        )

    trans_df = sut.metadata.classifications.transactions
    if "name" not in trans_df.columns:
        raise ValueError(
            "sut.metadata.classifications.transactions must have a 'name' column."
        )

    cols = sut.metadata.columns

    # Resolve product patterns to concrete codes
    if isinstance(products, str):
        patterns = [products]
    else:
        patterns = list(products)

    supply_codes = sut.supply[cols.product].dropna().unique().tolist()
    use_codes = sut.use[cols.product].dropna().unique().tolist()
    all_codes = sorted(set(supply_codes) | set(use_codes), key=_natural_sort_key)
    matched_products = _match_codes(all_codes, patterns)

    # All ids, sorted — shared by all table builders so tables have consistent columns
    supply_ids = sut.supply[cols.id].unique().tolist()
    use_ids = sut.use[cols.id].unique().tolist()
    all_ids = sorted(set(supply_ids) | set(use_ids))

    # Transaction name lookup: code → name
    trans_names = {
        str(row["code"]): str(row["name"])
        for _, row in trans_df.iterrows()
    }

    # Product name lookup: code → name, empty string if not available
    products_df = sut.metadata.classifications.products
    if products_df is not None:
        product_names = {
            str(row["code"]): str(row["name"])
            for _, row in products_df.iterrows()
        }
    else:
        product_names = {}

    # Category name lookup per transaction: {trans_code: {cat_code: cat_name}}
    # Uses esa_code on each transaction to find the right classification table.
    category_names_by_trans = _build_category_names_by_trans(
        trans_df, sut.metadata.classifications
    )

    balance = _build_balance_table(
        sut, matched_products, trans_names, product_names, all_ids
    )
    supply_detail = _build_detail_df(
        sut.supply, matched_products, product_names,
        trans_names, category_names_by_trans, cols, all_ids,
    ).sort_index()
    use_detail = _build_detail_df(
        sut.use, matched_products, product_names,
        trans_names, category_names_by_trans, cols, all_ids,
    ).sort_index()
    balance_distribution = _build_balance_distribution(balance)
    supply_detail_distribution = _build_detail_distribution(supply_detail)
    use_detail_distribution = _build_detail_distribution(use_detail)
    balance_growth = _build_growth_table(balance)
    supply_detail_growth = _build_growth_table(supply_detail)
    use_detail_growth = _build_growth_table(use_detail)
    price_layers = _build_price_layers_table(
        sut, matched_products, trans_names, product_names, all_ids
    )
    price_layers_distribution = _build_price_layers_distribution(price_layers)
    price_layers_growth = _build_growth_table(price_layers)
    price_layers_shares = _build_price_layers_shares(
        price_layers, sut, matched_products, all_ids
    )

    data = ProductInspectionData(
        balance=balance,
        supply_detail=supply_detail,
        use_detail=use_detail,
        balance_distribution=balance_distribution,
        supply_detail_distribution=supply_detail_distribution,
        use_detail_distribution=use_detail_distribution,
        balance_growth=balance_growth,
        supply_detail_growth=supply_detail_growth,
        use_detail_growth=use_detail_growth,
        price_layers=price_layers,
        price_layers_distribution=price_layers_distribution,
        price_layers_growth=price_layers_growth,
        price_layers_shares=price_layers_shares,
    )
    return ProductInspection(data=data)


def _build_category_names_by_trans(
    trans_df: pd.DataFrame,
    classifications,
) -> dict[str, dict[str, str]]:
    """Return {trans_code: {cat_code: cat_name}} for category label lookup.

    Uses the ``esa_code`` column in ``trans_df`` to determine which
    classification table provides category names for each transaction.
    Returns an empty inner dict for transactions whose ESA code is not in
    ``_ESA_TO_CLASSIFICATION_ATTR``, or whose matching classification table
    is not loaded or has no ``name`` column.
    """
    if classifications is None or "esa_code" not in trans_df.columns:
        return {}

    result: dict[str, dict[str, str]] = {}

    for _, row in trans_df.iterrows():
        trans_code = str(row["code"])
        esa_code = str(row["esa_code"])

        cls_attr = _ESA_TO_CLASSIFICATION_ATTR.get(esa_code)
        if cls_attr is None:
            result[trans_code] = {}
            continue

        cls_df = getattr(classifications, cls_attr, None)
        if cls_df is None or "name" not in cls_df.columns:
            result[trans_code] = {}
            continue

        result[trans_code] = {
            str(r["code"]): str(r["name"])
            for _, r in cls_df.iterrows()
        }

    return result


def _build_balance_table(
    sut: SUT,
    matched_products: list[str],
    trans_names: dict[str, str],
    product_names: dict[str, str],
    all_ids: list,
) -> pd.DataFrame:
    """Build the wide-format balance table for the given products."""
    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    bas_col = cols.price_basic

    # Aggregate to (product, transaction, id) → sum of price_basic
    supply_agg = (
        sut.supply
        .groupby([prod_col, trans_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
    )
    use_agg = (
        sut.use
        .groupby([prod_col, trans_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
    )

    blocks = []

    for product in matched_products:
        product_txt = product_names.get(product, "")

        # --- Supply side for this product ---
        prod_supply_agg = supply_agg[supply_agg[prod_col] == product]

        if not prod_supply_agg.empty:
            prod_supply_wide = prod_supply_agg.pivot_table(
                index=trans_col,
                columns=id_col,
                values=bas_col,
                aggfunc="sum",
                fill_value=0,
            )
            prod_supply_wide.columns.name = None
            for id_val in all_ids:
                if id_val not in prod_supply_wide.columns:
                    prod_supply_wide[id_val] = 0
            prod_supply_wide = prod_supply_wide[all_ids]
            supply_trans = sorted(prod_supply_wide.index.tolist(), key=_natural_sort_key)
        else:
            prod_supply_wide = pd.DataFrame(columns=all_ids)
            supply_trans = []

        # --- Use side for this product ---
        prod_use_agg = use_agg[use_agg[prod_col] == product]

        if not prod_use_agg.empty:
            prod_use_wide = prod_use_agg.pivot_table(
                index=trans_col,
                columns=id_col,
                values=bas_col,
                aggfunc="sum",
                fill_value=0,
            )
            prod_use_wide.columns.name = None
            for id_val in all_ids:
                if id_val not in prod_use_wide.columns:
                    prod_use_wide[id_val] = 0
            prod_use_wide = prod_use_wide[all_ids]
            use_trans = sorted(prod_use_wide.index.tolist(), key=_natural_sort_key)
        else:
            prod_use_wide = pd.DataFrame(columns=all_ids)
            use_trans = []

        # --- Assemble rows for this product ---
        # Each row label is a 4-tuple: (product, product_txt, transaction, transaction_txt)
        # Summary rows use "" for transaction and the summary label for transaction_txt.
        row_labels = []
        row_data = []

        for trans in supply_trans:
            trans_txt = trans_names.get(trans, trans)
            row_labels.append((product, product_txt, trans, trans_txt))
            row_data.append(prod_supply_wide.loc[trans, all_ids].tolist())

        row_labels.append((product, product_txt, "", "Total supply"))
        if supply_trans:
            total_supply = prod_supply_wide.loc[supply_trans, all_ids].sum()
        else:
            total_supply = pd.Series(0.0, index=all_ids)
        row_data.append(total_supply.tolist())

        for trans in use_trans:
            trans_txt = trans_names.get(trans, trans)
            row_labels.append((product, product_txt, trans, trans_txt))
            row_data.append(prod_use_wide.loc[trans, all_ids].tolist())

        row_labels.append((product, product_txt, "", "Total use"))
        if use_trans:
            total_use = prod_use_wide.loc[use_trans, all_ids].sum()
        else:
            total_use = pd.Series(0.0, index=all_ids)
        row_data.append(total_use.tolist())

        row_labels.append((product, product_txt, "", "Balance"))
        row_data.append((total_supply - total_use).tolist())

        block = pd.DataFrame(
            row_data,
            index=pd.MultiIndex.from_tuples(
                row_labels,
                names=["product", "product_txt", "transaction", "transaction_txt"],
            ),
            columns=all_ids,
        )
        blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)


def _build_detail_df(
    df: pd.DataFrame,
    matched_products: list[str],
    product_names: dict[str, str],
    trans_names: dict[str, str],
    category_names_by_trans: dict[str, dict[str, str]],
    cols,
    all_ids: list,
) -> pd.DataFrame:
    """Build a category-breakdown DataFrame for one side (supply or use).

    Returns a single DataFrame with a six-level MultiIndex:
    (product, product_txt, transaction, transaction_txt, category, category_txt).
    Only transactions where at least one selected product has non-empty
    categories are included. Products with no rows for a given transaction
    are omitted.
    """
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category
    bas_col = cols.price_basic

    # Restrict to selected products with non-empty categories
    df_selected = df[df[prod_col].isin(matched_products)]
    df_with_cats = df_selected[
        df_selected[cat_col].notna() & (df_selected[cat_col] != "")
    ]

    if df_with_cats.empty:
        return pd.DataFrame()

    trans_codes = sorted(
        df_with_cats[trans_col].unique().tolist(), key=_natural_sort_key
    )

    row_labels = []
    row_data = []

    for trans_code in trans_codes:
        trans_txt = trans_names.get(trans_code, trans_code)
        trans_data = df_with_cats[df_with_cats[trans_col] == trans_code]
        cat_name_lookup = category_names_by_trans.get(trans_code, {})

        # Aggregate to (product, category, id) → sum of price_basic
        agg = (
            trans_data
            .groupby([prod_col, cat_col, id_col], as_index=False, dropna=False)[bas_col]
            .sum()
        )

        for product in matched_products:
            prod_agg = agg[agg[prod_col] == product]
            if prod_agg.empty:
                continue

            product_txt = product_names.get(product, "")

            wide = prod_agg.pivot_table(
                index=cat_col,
                columns=id_col,
                values=bas_col,
                aggfunc="sum",
                fill_value=0,
            )
            wide.columns.name = None
            for id_val in all_ids:
                if id_val not in wide.columns:
                    wide[id_val] = 0
            wide = wide[all_ids]

            categories = sorted(wide.index.tolist(), key=_natural_sort_key)

            for cat in categories:
                cat_txt = cat_name_lookup.get(cat, "")
                row_labels.append((product, product_txt, trans_code, trans_txt, cat, cat_txt))
                row_data.append(wide.loc[cat, all_ids].tolist())

    if not row_labels:
        return pd.DataFrame()

    return pd.DataFrame(
        row_data,
        index=pd.MultiIndex.from_tuples(
            row_labels,
            names=["product", "product_txt", "transaction", "transaction_txt",
                   "category", "category_txt"],
        ),
        columns=all_ids,
    )


def _build_balance_distribution(balance: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalized version of the balance table.

    Within each product block, supply-side rows (up to and including
    "Total supply") are divided by "Total supply" per year. Use-side rows
    (up to and including "Total use") are divided by "Total use" per year.
    The "Balance" row is excluded — it is not meaningful as a share.
    Division by zero yields NaN.
    """
    if balance.empty:
        return pd.DataFrame()

    dist = balance.copy().astype(float)
    product_vals = balance.index.get_level_values("product")
    trans_txt_vals = balance.index.get_level_values("transaction_txt")

    for product in product_vals.unique():
        abs_positions = [i for i, v in enumerate(product_vals) if v == product]
        block_txts = [trans_txt_vals[i] for i in abs_positions]

        total_supply_pos = block_txts.index("Total supply")
        total_use_pos = block_txts.index("Total use")

        total_supply = balance.iloc[abs_positions[total_supply_pos]].astype(float)
        total_use = balance.iloc[abs_positions[total_use_pos]].astype(float)

        # Supply rows + "Total supply"
        for i_block in range(total_supply_pos + 1):
            i_abs = abs_positions[i_block]
            dist.iloc[i_abs] = balance.iloc[i_abs].astype(float).div(total_supply).values

        # Use rows + "Total use"
        for i_block in range(total_supply_pos + 1, total_use_pos + 1):
            i_abs = abs_positions[i_block]
            dist.iloc[i_abs] = balance.iloc[i_abs].astype(float).div(total_use).values

    balance_mask = trans_txt_vals == "Balance"
    return dist[~balance_mask]


def _build_growth_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build year-on-year growth table: change relative to the previous year.

    Each value is ``(current - previous) / previous``, so a 5% increase gives
    ``0.05``. The first year column is ``NaN`` throughout. Division by zero
    also yields ``NaN``. For balance-shaped tables the "Balance" row is
    excluded — growth of an imbalance is not meaningful.
    """
    if df.empty:
        return pd.DataFrame()

    floats = df.astype(float)
    previous = floats.shift(axis=1)
    growth = (floats - previous).div(previous)
    growth = growth.replace([float("inf"), float("-inf")], float("nan"))

    if "transaction_txt" in growth.index.names:
        balance_mask = growth.index.get_level_values("transaction_txt") == "Balance"
        growth = growth[~balance_mask]

    return growth


def _get_price_layer_columns(cols, use_df: pd.DataFrame) -> list[str]:
    """Return intermediate price layer column names in use DataFrame column order.

    Considers only the optional roles on ``SUTColumns`` between ``price_basic``
    and ``price_purchasers`` (trade_margins, wholesale_margins, retail_margins,
    transport_margins, product_taxes, product_subsidies,
    product_taxes_less_subsidies, vat). Returns only those that are both
    mapped (not ``None``) and present as actual columns in ``use_df``.
    """
    optional_layer_cols = {
        cols.trade_margins,
        cols.wholesale_margins,
        cols.retail_margins,
        cols.transport_margins,
        cols.product_taxes,
        cols.product_subsidies,
        cols.product_taxes_less_subsidies,
        cols.vat,
    }
    layer_cols_set = {col for col in optional_layer_cols if col is not None}
    return [col for col in use_df.columns if col in layer_cols_set]


def _build_price_layers_table(
    sut,
    matched_products: list[str],
    trans_names: dict[str, str],
    product_names: dict[str, str],
    all_ids: list,
) -> pd.DataFrame:
    """Build the price layers table for the given products.

    Returns a DataFrame with a five-level MultiIndex:
    (product, product_txt, price_layer, transaction, transaction_txt).
    Columns are the collection ids. One block per (product, price_layer)
    combination: one row per use transaction that has non-zero layer values
    across any id, plus a Total row summing across those transactions.
    Price layer blocks follow the column order in ``sut.use``.
    """
    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction

    layer_cols = _get_price_layer_columns(cols, sut.use)
    if not layer_cols:
        return pd.DataFrame()

    blocks = []

    for product in matched_products:
        product_txt = product_names.get(product, "")
        prod_use = sut.use[sut.use[prod_col] == product]

        if prod_use.empty:
            continue

        for layer_col in layer_cols:
            # Only rows where this layer has a value
            prod_use_with_layer = prod_use[prod_use[layer_col].notna()]

            if prod_use_with_layer.empty:
                continue

            # Aggregate to (transaction, id) → sum of layer_col
            agg = (
                prod_use_with_layer
                .groupby([trans_col, id_col], as_index=False, dropna=False)[layer_col]
                .sum()
            )

            # Pivot to wide: transactions as rows, ids as columns
            wide = agg.pivot_table(
                index=trans_col,
                columns=id_col,
                values=layer_col,
                aggfunc="sum",
                fill_value=0,
            )
            wide.columns.name = None
            for id_val in all_ids:
                if id_val not in wide.columns:
                    wide[id_val] = 0
            wide = wide[all_ids]

            # Drop transactions that are all zero across all ids
            non_zero_mask = (wide != 0).any(axis=1)
            wide = wide[non_zero_mask]

            if wide.empty:
                continue

            use_trans = sorted(wide.index.tolist(), key=_natural_sort_key)

            row_labels = []
            row_data = []

            for trans in use_trans:
                trans_txt = trans_names.get(trans, trans)
                row_labels.append((product, product_txt, layer_col, trans, trans_txt))
                row_data.append(wide.loc[trans, all_ids].tolist())

            # Total row sums across all transactions for this (product, layer)
            total = wide.loc[use_trans].sum()
            row_labels.append((product, product_txt, layer_col, "", "Total"))
            row_data.append(total.tolist())

            block = pd.DataFrame(
                row_data,
                index=pd.MultiIndex.from_tuples(
                    row_labels,
                    names=["product", "product_txt", "price_layer",
                           "transaction", "transaction_txt"],
                ),
                columns=all_ids,
            )
            blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)


def _build_price_layers_shares(
    price_layers: pd.DataFrame,
    sut,
    matched_products: list[str],
    all_ids: list,
) -> pd.DataFrame:
    """Build price layer shares relative to total product use at purchasers' prices.

    Every value in ``price_layers`` is divided by the sum of the purchasers'
    price column across all use rows for that product and year. The denominator
    is the same for every row within a product, regardless of layer or
    transaction. Division by zero yields NaN.
    """
    if price_layers.empty:
        return pd.DataFrame()

    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    purch_col = cols.price_purchasers

    # Compute denominator: total purchasers' price use per (product, year)
    use_purch = (
        sut.use
        .groupby([prod_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )

    shares = price_layers.copy().astype(float)
    product_vals = price_layers.index.get_level_values("product")

    for product in matched_products:
        prod_rows = price_layers.index.get_level_values("product") == product
        if not prod_rows.any():
            continue

        denom = pd.Series(0.0, index=all_ids)
        prod_use_purch = use_purch[use_purch[prod_col] == product]
        for _, row in prod_use_purch.iterrows():
            denom[row[id_col]] = row[purch_col]

        abs_positions = [i for i, v in enumerate(product_vals) if v == product]
        for i_abs in abs_positions:
            shares.iloc[i_abs] = (
                price_layers.iloc[i_abs].astype(float).div(denom).values
            )

    return shares


def _build_price_layers_distribution(price_layers: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalised version of the price layers table.

    Within each (product, price_layer) block, every row is divided by the
    Total row for that year. The Total row itself becomes 1.0 (100%).
    Division by zero yields NaN.
    """
    if price_layers.empty:
        return pd.DataFrame()

    dist = price_layers.copy().astype(float)
    product_vals = price_layers.index.get_level_values("product")
    layer_vals = price_layers.index.get_level_values("price_layer")
    trans_txt_vals = price_layers.index.get_level_values("transaction_txt")

    for product in list(dict.fromkeys(product_vals)):
        prod_positions = [i for i, v in enumerate(product_vals) if v == product]
        prod_layers = list(dict.fromkeys(layer_vals[i] for i in prod_positions))

        for layer in prod_layers:
            block_positions = [
                i for i in prod_positions if layer_vals[i] == layer
            ]
            block_txts = [trans_txt_vals[i] for i in block_positions]

            total_pos = block_txts.index("Total")
            total_row = price_layers.iloc[block_positions[total_pos]].astype(float)

            for i_abs in block_positions:
                dist.iloc[i_abs] = (
                    price_layers.iloc[i_abs].astype(float).div(total_row).values
                )

    return dist


def _build_detail_distribution(detail: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalized version of a detail table.

    For each product, values in each year column are divided by the sum
    across all transactions and categories for that product in that year.
    Division by zero yields NaN.
    """
    if detail.empty:
        return pd.DataFrame()

    dist = detail.copy().astype(float)
    product_vals = detail.index.get_level_values("product")

    for product in product_vals.unique():
        product_mask = product_vals == product
        product_data = detail.loc[product_mask]
        col_totals = product_data.sum(axis=0)
        dist.loc[product_mask] = product_data.div(col_totals, axis="columns").values

    return dist
