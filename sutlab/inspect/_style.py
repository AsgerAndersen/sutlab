"""
Formatting helpers and Styler factories for inspection tables.

All functions are private — they are used by the inspection modules and by
the styled properties on the result dataclasses.
"""

from __future__ import annotations

import pandas as pd
from pandas.io.formats.style import Styler


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


def _apply_balance_style(df: pd.DataFrame) -> pd.DataFrame:
    """Return a same-shape DataFrame of CSS strings for the balance table data cells."""
    row_css = _build_balance_row_css(df, _DATA_COLORS)
    return pd.DataFrame(
        {col: row_css for col in df.columns},
        index=df.index,
    )


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
    data_total_color = _DATA_COLORS[f"{color_key}_total"]
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

        if not is_last_product:
            prod_css[prod_positions[0]] = "border-bottom: 2px solid #999"
            prod_txt_css[prod_positions[0]] = "border-bottom: 2px solid #999"

        # trans_row_counter: rows seen per transaction so far (within this product),
        # used to alternate category colours within each transaction.
        trans_row_counter = {}
        # Track the start of the current contiguous run of the same transaction so
        # that trans_css can be placed on the first row of the run. Merged cells in
        # the rendered HTML take CSS from the first row of their rowspan, so the
        # border must go there rather than on the last row.
        run_start_i_abs = None
        prev_trans = None

        for pos_idx, i_abs in enumerate(prod_positions):
            trans = trans_vals[i_abs]
            is_last_pos = (pos_idx == len(prod_positions) - 1)
            next_trans = trans_vals[prod_positions[pos_idx + 1]] if not is_last_pos else None

            # Separator on the bottom of this row:
            #   thick  → end of product block
            #   thin   → end of transaction block (next row belongs to a different transaction)
            #   none   → mid-block (next row has the same transaction)
            if is_last_pos:
                sep = "; border-bottom: 2px solid #999" if not is_last_product else ""
            elif next_trans != trans:
                sep = "; border-bottom: 1px solid #ccc"
            else:
                sep = ""

            # Detect start of a new contiguous run of this transaction.
            if trans != prev_trans:
                run_start_i_abs = i_abs
                prev_trans = trans

            # At the end of a contiguous run, write trans/trans_txt CSS on the run's
            # first row so that the border appears on the merged cell's bottom edge.
            if next_trans != trans:  # end of run (also covers is_last_pos)
                if trans == "":
                    trans_css[run_start_i_abs] = (
                        f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                    )
                    trans_txt_css[run_start_i_abs] = (
                        f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                    )
                else:
                    trans_css[run_start_i_abs] = f"background-color: {idx_hdr_color}{sep}"
                    trans_txt_css[run_start_i_abs] = f"background-color: {idx_hdr_color}{sep}"

            # Data and category cells are styled individually on every row.
            if trans == "":
                data_css[i_abs] = (
                    f"background-color: {data_total_color}; font-weight: bold{sep}"
                )
                cat_css[i_abs] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
                cat_txt_css[i_abs] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
            else:
                row_pos = trans_row_counter.get(trans, 0)
                trans_row_counter[trans] = row_pos + 1
                data_css[i_abs] = f"background-color: {data_row_colors[row_pos % 2]}{sep}"
                cat_css[i_abs] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"
                cat_txt_css[i_abs] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"

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
    return styler


def _style_price_layers_detailed_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply colours, bold, and separators to a price_layers_detailed-shaped table.

    Same palette logic as :func:`_style_price_layers_table` — one palette per
    layer, cycling if there are more layers than palette entries. Within each
    ``(product, price_layer)`` block:

    - Each ``(transaction, transaction_txt)`` cell spans its category rows
      (CSS on first row only). Category rows alternate between the two light
      data shades of the layer's palette.
    - The Total row (``transaction == ""``) uses the saturated data shade and
      is bold throughout.
    - The ``price_layer`` index cell (one merged cell per block) uses the
      saturated index shade; the layer separator is placed there.

    Separators: ``1px solid #ddd`` between transaction groups within a layer,
    ``1px solid #ccc`` between layer blocks within a product,
    ``2px solid #999`` between product blocks.
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    product_vals = df.index.get_level_values("product")
    layer_vals = df.index.get_level_values("price_layer")
    trans_vals = df.index.get_level_values("transaction")
    n = len(df)

    data_css = [""] * n
    cat_css = [""] * n
    cat_txt_css = [""] * n
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

        if not is_last_product:
            prod_css[prod_positions[0]] = "border-bottom: 2px solid #999"
            prod_txt_css[prod_positions[0]] = "border-bottom: 2px solid #999"

        for l_idx, layer in enumerate(prod_layers):
            is_last_layer = (l_idx == len(prod_layers) - 1)
            palette = _LAYER_PALETTES[l_idx % len(_LAYER_PALETTES)]

            block_positions = [i for i in prod_positions if layer_vals[i] == layer]
            block_trans = list(dict.fromkeys(trans_vals[i] for i in block_positions))

            if not is_last_layer:
                layer_sep = "; border-bottom: 1px solid #ccc"
            elif not is_last_product:
                layer_sep = "; border-bottom: 2px solid #999"
            else:
                layer_sep = ""

            # price_layer index: one merged cell per block — CSS on first row
            layer_css[block_positions[0]] = (
                f"background-color: {palette['index_total']}{layer_sep}"
            )

            trans_row_counter = {}
            run_start_i_abs = None
            prev_trans = None

            for pos_idx, i_abs in enumerate(block_positions):
                trans = trans_vals[i_abs]
                is_last_pos = (pos_idx == len(block_positions) - 1)
                next_trans = trans_vals[block_positions[pos_idx + 1]] if not is_last_pos else None

                if is_last_pos:
                    sep = layer_sep
                elif next_trans != trans:
                    sep = "; border-bottom: 1px solid #ddd"
                else:
                    sep = ""

                if trans != prev_trans:
                    run_start_i_abs = i_abs
                    prev_trans = trans

                if next_trans != trans:
                    if trans == "":
                        trans_css[run_start_i_abs] = (
                            f"background-color: {palette['index_total']}; font-weight: bold{sep}"
                        )
                        trans_txt_css[run_start_i_abs] = (
                            f"background-color: {palette['index_total']}; font-weight: bold{sep}"
                        )
                    else:
                        trans_css[run_start_i_abs] = (
                            f"background-color: {palette['index_total']}{sep}"
                        )
                        trans_txt_css[run_start_i_abs] = (
                            f"background-color: {palette['index_total']}{sep}"
                        )

                if trans == "":
                    data_css[i_abs] = (
                        f"background-color: {palette['data_total']}; font-weight: bold{sep}"
                    )
                    cat_css[i_abs] = (
                        f"background-color: {palette['index_total']}; font-weight: bold{sep}"
                    )
                    cat_txt_css[i_abs] = (
                        f"background-color: {palette['index_total']}; font-weight: bold{sep}"
                    )
                else:
                    row_pos = trans_row_counter.get(trans, 0)
                    trans_row_counter[trans] = row_pos + 1
                    bg_data = palette["data"][row_pos % 2]
                    bg_index = palette["index"][row_pos % 2]
                    data_css[i_abs] = f"background-color: {bg_data}{sep}"
                    cat_css[i_abs] = f"background-color: {bg_index}{sep}"
                    cat_txt_css[i_abs] = f"background-color: {bg_index}{sep}"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=cat_css: css, level="category", axis=0)
    styler = styler.apply_index(lambda s, css=cat_txt_css: css, level="category_txt", axis=0)
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    styler = styler.apply_index(lambda s, css=layer_css: css, level="price_layer", axis=0)
    styler = styler.apply_index(lambda s, css=prod_css: css, level="product", axis=0)
    styler = styler.apply_index(lambda s, css=prod_txt_css: css, level="product_txt", axis=0)
    return styler
