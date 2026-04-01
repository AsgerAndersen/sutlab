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
    # GVA and Input coefficient rows in the industry balance table.
    "derived":       ("#fce8d0", "#fef3e8"),
}
_INDEX_COLORS = {
    "supply":        ("#d8eedb", "#e3f3e5"),
    "supply_total":  "#b8d8ba",
    "use":           ("#d0e8f8", "#dbedfa"),
    "use_total":     "#a5cff4",
    "balance":       "#e5e5e5",
    # GVA and Input coefficient rows in the industry balance table.
    "derived":       ("#f5d5b2", "#fbe9cc"),
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


def _style_detail_table(
    df: pd.DataFrame,
    format_func,
    color_key: str,
    *,
    outer_level: str = "product",
    outer_txt_level: str = "product_txt",
    inner_level: str = "category",
    inner_txt_level: str = "category_txt",
) -> Styler:
    """Apply row colours and separators to a detail table.

    Handles any detail table whose MultiIndex has the shape:
    ``(outer, outer_txt, transaction, transaction_txt, inner, inner_txt)``.
    For ``inspect_products`` detail tables the outer group is ``product`` and
    the inner dimension is ``category``. For ``inspect_industries`` detail
    tables the outer group is ``industry`` and the inner dimension is
    ``product``.

    Parameters
    ----------
    df : pd.DataFrame
        A detail DataFrame (supply_detail or use_detail).
    format_func : callable
        Applied to all data cells (e.g. ``_format_number``).
    color_key : str
        ``"supply"`` or ``"use"`` — selects the colour set from
        ``_DATA_COLORS`` / ``_INDEX_COLORS``.
    outer_level : str
        Index level name for the outermost grouping dimension. Default
        ``"product"`` (for ``inspect_products``).
    outer_txt_level : str
        Index level name for the outer label column. Default
        ``"product_txt"``.
    inner_level : str
        Index level name for the innermost dimension (rows within a
        transaction). Default ``"category"``.
    inner_txt_level : str
        Index level name for the inner label column. Default
        ``"category_txt"``.
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    data_row_colors = _DATA_COLORS[color_key]
    data_total_color = _DATA_COLORS[f"{color_key}_total"]
    idx_row_colors = _INDEX_COLORS[color_key]
    idx_hdr_color = _INDEX_COLORS[f"{color_key}_total"]

    outer_vals = df.index.get_level_values(outer_level)
    trans_vals = df.index.get_level_values("transaction")
    outers = list(outer_vals.unique())
    n = len(df)

    data_css = [""] * n
    inner_css = [""] * n
    inner_txt_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n
    outer_css = [""] * n
    outer_txt_css = [""] * n

    for p_idx, outer in enumerate(outers):
        is_last_outer = (p_idx == len(outers) - 1)
        outer_positions = [i for i, v in enumerate(outer_vals) if v == outer]

        if not is_last_outer:
            outer_css[outer_positions[0]] = "border-bottom: 2px solid #999"
            outer_txt_css[outer_positions[0]] = "border-bottom: 2px solid #999"

        # trans_row_counter: rows seen per transaction so far (within this outer),
        # used to alternate inner-dimension colours within each transaction.
        trans_row_counter = {}
        # Track the start of the current contiguous run of the same transaction so
        # that trans_css can be placed on the first row of the run. Merged cells in
        # the rendered HTML take CSS from the first row of their rowspan, so the
        # border must go there rather than on the last row.
        run_start_i_abs = None
        prev_trans = None

        for pos_idx, i_abs in enumerate(outer_positions):
            trans = trans_vals[i_abs]
            is_last_pos = (pos_idx == len(outer_positions) - 1)
            next_trans = trans_vals[outer_positions[pos_idx + 1]] if not is_last_pos else None

            # Separator on the bottom of this row:
            #   thick  → end of outer block
            #   thin   → end of transaction block (next row belongs to a different transaction)
            #   none   → mid-block (next row has the same transaction)
            if is_last_pos:
                sep = "; border-bottom: 2px solid #999" if not is_last_outer else ""
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

            # Data and inner cells are styled individually on every row.
            if trans == "":
                data_css[i_abs] = (
                    f"background-color: {data_total_color}; font-weight: bold{sep}"
                )
                inner_css[i_abs] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
                inner_txt_css[i_abs] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
            else:
                row_pos = trans_row_counter.get(trans, 0)
                trans_row_counter[trans] = row_pos + 1
                data_css[i_abs] = f"background-color: {data_row_colors[row_pos % 2]}{sep}"
                inner_css[i_abs] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"
                inner_txt_css[i_abs] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=inner_css: css, level=inner_level, axis=0)
    styler = styler.apply_index(lambda s, css=inner_txt_css: css, level=inner_txt_level, axis=0)
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    styler = styler.apply_index(lambda s, css=outer_css: css, level=outer_level, axis=0)
    styler = styler.apply_index(lambda s, css=outer_txt_css: css, level=outer_txt_level, axis=0)
    return styler


def _style_price_layers_table(
    df: pd.DataFrame,
    format_func,
    *,
    outer_level: str = "product",
    outer_txt_level: str = "product_txt",
) -> Styler:
    """Apply colours, bold, and separators to a price_layers-shaped table.

    Each distinct ``price_layer`` value gets a colour from ``_LAYER_PALETTES``
    (cycling if there are more layers than palette entries). Within each
    ``(outer_level, price_layer)`` block:

    - Transaction rows alternate between the two light shades of that layer's
      palette; their ``transaction`` and ``transaction_txt`` index cells use
      the more saturated shade.
    - The Total row uses the more saturated data shade and is bold throughout
      (data cells and ``transaction``/``transaction_txt`` index cells).
    - The ``price_layer`` index cell (one merged cell per block) uses the
      more saturated shade; the separator border is placed on it so the
      border-bottom aligns with the block boundary.

    Separators: ``1px solid #ccc`` between layer blocks within an outer group,
    ``2px solid #999`` between outer group blocks.

    Parameters
    ----------
    df : pd.DataFrame
        Price layers table with a MultiIndex whose levels include
        ``outer_level``, ``outer_txt_level``, ``price_layer``,
        ``transaction``, and ``transaction_txt``.
    format_func : callable
        Number formatter passed to ``Styler.format``.
    outer_level : str, optional
        Name of the outermost MultiIndex level. Default ``"product"``.
    outer_txt_level : str, optional
        Name of the label level for the outer dimension. Default ``"product_txt"``.
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    outer_vals = df.index.get_level_values(outer_level)
    layer_vals = df.index.get_level_values("price_layer")
    trans_txt_vals = df.index.get_level_values("transaction_txt")
    n = len(df)

    data_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n
    layer_css = [""] * n
    outer_css = [""] * n
    outer_txt_css = [""] * n

    outers = list(dict.fromkeys(outer_vals))

    for p_idx, outer in enumerate(outers):
        is_last_outer = (p_idx == len(outers) - 1)
        outer_positions = [i for i, v in enumerate(outer_vals) if v == outer]
        outer_layers = list(dict.fromkeys(layer_vals[i] for i in outer_positions))

        # outer/outer_txt: one merged cell per outer group — separator on first row
        if not is_last_outer:
            outer_css[outer_positions[0]] = "border-bottom: 2px solid #999"
            outer_txt_css[outer_positions[0]] = "border-bottom: 2px solid #999"

        for l_idx, layer in enumerate(outer_layers):
            is_last_layer = (l_idx == len(outer_layers) - 1)
            palette = _LAYER_PALETTES[l_idx % len(_LAYER_PALETTES)]

            block_positions = [i for i in outer_positions if layer_vals[i] == layer]
            block_txts = [trans_txt_vals[i] for i in block_positions]

            if not is_last_layer:
                sep = "; border-bottom: 1px solid #ccc"
            elif not is_last_outer:
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
    styler = styler.apply_index(lambda s, css=outer_css: css, level=outer_level, axis=0)
    styler = styler.apply_index(lambda s, css=outer_txt_css: css, level=outer_txt_level, axis=0)
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


def _style_industry_balance_table(
    df: pd.DataFrame,
    p1_trans: frozenset,
    format_func=None,
) -> Styler:
    """Apply colours, bold, and industry separators to the industry balance table.

    Colour scheme:

    - P1 (output) transaction rows: alternating green (``supply`` palette).
    - ``Total output`` row (bold): saturated green (``supply_total``).
    - P2 (input) transaction rows: alternating blue (``use`` palette).
    - ``Total input`` row (bold): saturated blue (``use_total``).
    - ``Gross value added`` and ``Input coefficient`` rows: alternating
      brown-orange (``derived`` palette).

    Industry blocks are separated by a thick border (``2px solid #999``).
    The ``transaction`` index level is coloured for non-``""`` codes only,
    following the same convention as :func:`_style_balance_table`.

    Parameters
    ----------
    df : pd.DataFrame
        Industry balance table from :func:`inspect_industries`, with a
        four-level MultiIndex ``(industry, industry_txt, transaction,
        transaction_txt)``.
    p1_trans : frozenset
        Set of P1 transaction codes. Used to distinguish output rows from
        input rows when no ``Total output`` / ``Total input`` anchor is
        present (single-transaction case).
    format_func : callable or None
        When provided, applied uniformly to all cells (e.g.
        ``_format_percentage`` for growth tables). When ``None`` (default),
        mixed formatting is used: ``_format_number`` for most rows and
        ``_format_percentage`` for the Input coefficient row.
    """
    # Format: uniform when format_func is given; mixed otherwise.
    styler = df.style
    if format_func is not None:
        styler = styler.format(format_func, na_rep="")
    else:
        # Mixed: Input coefficient → percentage, everything else → number.
        coeff_mask = df.index.get_level_values("transaction_txt") == "Input coefficient"
        non_coeff_idx = df.index[~coeff_mask]
        coeff_idx = df.index[coeff_mask]
        if len(non_coeff_idx) > 0:
            styler = styler.format(
                _format_number, na_rep="", subset=pd.IndexSlice[non_coeff_idx, :]
            )
        if len(coeff_idx) > 0:
            styler = styler.format(
                _format_percentage, na_rep="", subset=pd.IndexSlice[coeff_idx, :]
            )

    if df.empty:
        return styler

    industry_vals = df.index.get_level_values("industry")
    trans_vals = df.index.get_level_values("transaction")
    trans_txt_vals = df.index.get_level_values("transaction_txt")
    industries_list = list(dict.fromkeys(industry_vals))
    n = len(df)

    data_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n
    industry_css = [""] * n
    industry_txt_css = [""] * n

    for ind_idx, industry in enumerate(industries_list):
        is_last_industry = (ind_idx == len(industries_list) - 1)
        ind_positions = [i for i, v in enumerate(industry_vals) if v == industry]

        # industry / industry_txt: one merged cell per block. Separator goes on
        # the first row so the border-bottom aligns with the full block height.
        if not is_last_industry:
            industry_css[ind_positions[0]] = "border-bottom: 2px solid #999"
            industry_txt_css[ind_positions[0]] = "border-bottom: 2px solid #999"

        output_counter = 0
        input_counter = 0
        derived_counter = 0

        for j, i_abs in enumerate(ind_positions):
            trans = trans_vals[i_abs]
            txt = trans_txt_vals[i_abs]
            is_last_row = (j == len(ind_positions) - 1)

            # Thick separator on the last row of each non-last industry block.
            sep = "; border-bottom: 2px solid #999" if (is_last_row and not is_last_industry) else ""

            if txt == "Total output":
                bg_data = _DATA_COLORS["supply_total"]
                bg_idx = _INDEX_COLORS["supply_total"]
                bold = True
            elif txt == "Total input":
                bg_data = _DATA_COLORS["use_total"]
                bg_idx = _INDEX_COLORS["use_total"]
                bold = True
            elif txt in ("Gross value added", "Input coefficient"):
                bg_data = _DATA_COLORS["derived"][derived_counter % 2]
                bg_idx = _INDEX_COLORS["derived"][derived_counter % 2]
                bold = False
                derived_counter += 1
            elif trans in p1_trans:
                bg_data = _DATA_COLORS["supply"][output_counter % 2]
                bg_idx = _INDEX_COLORS["supply"][output_counter % 2]
                bold = False
                output_counter += 1
            else:
                # P2 (input) transaction row.
                bg_data = _DATA_COLORS["use"][input_counter % 2]
                bg_idx = _INDEX_COLORS["use"][input_counter % 2]
                bold = False
                input_counter += 1

            weight = "bold" if bold else "normal"
            data_css[i_abs] = f"background-color: {bg_data}; font-weight: {weight}{sep}"
            trans_txt_css[i_abs] = f"background-color: {bg_idx}; font-weight: {weight}{sep}"

            # transaction level: colour non-"" cells only.
            # "" cells get no background; if the separator is needed, put just the border.
            if trans != "":
                trans_css[i_abs] = f"background-color: {bg_idx}; font-weight: {weight}{sep}"
            elif sep:
                trans_css[i_abs] = "border-bottom: 2px solid #999"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    styler = styler.apply_index(lambda s, css=industry_css: css, level="industry", axis=0)
    styler = styler.apply_index(lambda s, css=industry_txt_css: css, level="industry_txt", axis=0)
    return styler


def _style_final_use_use_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply row colours to a final-use transaction-level use table.

    The table has a two-level MultiIndex ``(transaction, transaction_txt)``.
    Each non-total row alternates between the two light use-blue shades for
    both index and data cells.  The ``"Total use"`` row (``transaction == ""``)
    is bold with the total use-blue shade throughout.  A thin
    ``1px solid #ccc`` separator is placed at the bottom of the last
    non-total row.

    Parameters
    ----------
    df : pd.DataFrame
        Use table from :func:`inspect_final_uses`.
    format_func : callable
        Applied to all data cells (e.g. ``_format_number``).
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    data_row_colors = _DATA_COLORS["use"]
    data_total_color = _DATA_COLORS["use_total"]
    idx_row_colors = _INDEX_COLORS["use"]
    idx_total_color = _INDEX_COLORS["use_total"]

    trans_vals = df.index.get_level_values("transaction")
    n = len(df)

    data_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n

    row_pos = 0

    for i in range(n):
        trans = trans_vals[i]
        is_last_row = (i == n - 1)
        next_trans = trans_vals[i + 1] if not is_last_row else None

        # Thin separator before the "Total use" row.
        if not is_last_row and next_trans == "" and trans != "":
            sep = "; border-bottom: 1px solid #ccc"
        else:
            sep = ""

        if trans == "":
            data_css[i] = f"background-color: {data_total_color}; font-weight: bold"
            trans_css[i] = f"background-color: {idx_total_color}; font-weight: bold"
            trans_txt_css[i] = f"background-color: {idx_total_color}; font-weight: bold"
        else:
            shade = data_row_colors[row_pos % 2]
            idx_shade = idx_row_colors[row_pos % 2]
            data_css[i] = f"background-color: {shade}{sep}"
            trans_css[i] = f"background-color: {idx_shade}{sep}"
            trans_txt_css[i] = f"background-color: {idx_shade}{sep}"
            row_pos += 1

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(
        lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0
    )
    return styler


def _style_final_use_use_categories_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply row colours and separators to a final-use use table.

    The table has a four-level MultiIndex
    ``(transaction, transaction_txt, category, category_txt)``.
    ``transaction`` acts as the block grouping dimension (equivalent to
    ``transaction`` within a product block in ``_style_detail_table``).
    ``category`` is the row-level detail dimension.

    - Within each transaction block, category rows alternate between the two
      light use-blue shades. The ``transaction`` and ``transaction_txt``
      index cells have no background colour (only a separator border).
    - The ``"Total use"`` row (``transaction == ""``) is bold with the total
      use-blue shade throughout.
    - A thin ``1px solid #ccc`` separator is placed between transaction
      blocks. No separator at the very bottom.
    - Handles non-contiguous transaction blocks (produced when ``sort_id`` is
      applied), identical to the behaviour of ``_style_detail_table``.

    Parameters
    ----------
    df : pd.DataFrame
        Use table from :func:`inspect_final_uses`.
    format_func : callable
        Applied to all data cells (e.g. ``_format_number``).
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    data_row_colors = _DATA_COLORS["use"]
    data_total_color = _DATA_COLORS["use_total"]
    idx_row_colors = _INDEX_COLORS["use"]
    idx_hdr_color = _INDEX_COLORS["use_total"]

    trans_vals = df.index.get_level_values("transaction")
    n = len(df)

    data_css = [""] * n
    cat_css = [""] * n
    cat_txt_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n

    # trans_row_counter: rows seen per transaction so far, used to alternate
    # category colours within each transaction across all its occurrences.
    trans_row_counter: dict = {}
    # Track the start of the current contiguous run so that trans_css is
    # placed on the first row of the run (merged cells take CSS from there).
    run_start_i = None
    prev_trans = None

    for i in range(n):
        trans = trans_vals[i]
        is_last_row = (i == n - 1)
        next_trans = trans_vals[i + 1] if not is_last_row else None

        # Separator: thin border between transaction blocks; none at the end.
        if is_last_row or next_trans == trans:
            sep = ""
        else:
            sep = "; border-bottom: 1px solid #ccc"

        # Detect start of a new contiguous run of the same transaction.
        if trans != prev_trans:
            run_start_i = i
            prev_trans = trans

        # At the end of a contiguous run, write trans CSS on the run's first
        # row so the border aligns with the merged cell's bottom edge.
        if next_trans != trans:
            if trans == "":
                trans_css[run_start_i] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
                trans_txt_css[run_start_i] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
            else:
                border_css = "border-bottom: 1px solid #ccc" if sep else ""
                trans_css[run_start_i] = border_css
                trans_txt_css[run_start_i] = border_css

        # Data and category cells are styled individually on every row.
        if trans == "":
            data_css[i] = f"background-color: {data_total_color}; font-weight: bold{sep}"
            cat_css[i] = f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
            cat_txt_css[i] = f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
        else:
            row_pos = trans_row_counter.get(trans, 0)
            trans_row_counter[trans] = row_pos + 1
            data_css[i] = f"background-color: {data_row_colors[row_pos % 2]}{sep}"
            cat_css[i] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"
            cat_txt_css[i] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=cat_css: css, level="category", axis=0)
    styler = styler.apply_index(lambda s, css=cat_txt_css: css, level="category_txt", axis=0)
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    return styler


def _style_final_use_use_products_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply row colours and separators to a final-use use-detail table.

    The table has a six-level MultiIndex
    ``(transaction, transaction_txt, category, category_txt, product, product_txt)``.

    - ``transaction`` is the outer block grouping dimension: thick
      ``2px solid #999`` separator between transaction blocks, no background
      colour. Handles non-contiguous transaction blocks from ``sort_id``.
    - ``category`` is the middle grouping dimension: header use-blue colour with
      thin ``1px solid #ccc`` separator between category blocks within the same
      transaction. Handles non-contiguous category blocks from ``sort_id``.
    - ``product`` rows alternate between the two light use-blue shades.
    - The ``"Total use"`` row (``transaction == ""``) is bold with the total
      use-blue shade throughout.

    Parameters
    ----------
    df : pd.DataFrame
        Use-detail table from :func:`inspect_final_uses`.
    format_func : callable
        Applied to all data cells (e.g. ``_format_number``).
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    data_row_colors = _DATA_COLORS["use"]
    data_total_color = _DATA_COLORS["use_total"]
    idx_row_colors = _INDEX_COLORS["use"]
    idx_hdr_color = _INDEX_COLORS["use_total"]

    trans_vals = df.index.get_level_values("transaction")
    cat_vals = df.index.get_level_values("category")
    n = len(df)

    data_css = [""] * n
    prod_css = [""] * n
    prod_txt_css = [""] * n
    cat_css = [""] * n
    cat_txt_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n

    # cat_row_counter: rows seen per (transaction, category) pair, used to
    # alternate product colours within each group across non-contiguous runs.
    cat_row_counter: dict = {}
    # Track starts of contiguous runs for merged-cell CSS placement.
    trans_run_start_i = None
    cat_run_start_i = None
    prev_trans = None
    prev_cat_pair = None

    for i in range(n):
        trans = trans_vals[i]
        cat = cat_vals[i]
        cat_pair = (trans, cat)
        is_last_row = (i == n - 1)
        next_trans = trans_vals[i + 1] if not is_last_row else None
        next_cat = cat_vals[i + 1] if not is_last_row else None
        next_cat_pair = (next_trans, next_cat) if not is_last_row else None

        # Separator at the bottom of the current row:
        #   thick  → transaction block changes
        #   thin   → same transaction, category block changes
        #   none   → same (transaction, category), or last row
        if is_last_row:
            sep = ""
        elif next_trans != trans:
            sep = "; border-bottom: 2px solid #999"
        elif next_cat_pair != cat_pair:
            sep = "; border-bottom: 1px solid #ccc"
        else:
            sep = ""

        # Detect start of new contiguous runs.
        if trans != prev_trans:
            trans_run_start_i = i
            prev_trans = trans
        if cat_pair != prev_cat_pair:
            cat_run_start_i = i
            prev_cat_pair = cat_pair

        # At the end of a transaction run, write trans/trans_txt CSS on the
        # run's first row (merged cells take CSS from the first row of their span).
        if next_trans != trans:
            if trans == "":
                trans_css[trans_run_start_i] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold"
                )
                trans_txt_css[trans_run_start_i] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold"
                )
            else:
                # Non-total transaction outer: no background, just the border.
                trans_css[trans_run_start_i] = "border-bottom: 2px solid #999"
                trans_txt_css[trans_run_start_i] = "border-bottom: 2px solid #999"

        # At the end of a (transaction, category) run, write cat/cat_txt CSS
        # on the run's first row.
        if next_cat_pair != cat_pair:
            if trans == "":
                cat_css[cat_run_start_i] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
                cat_txt_css[cat_run_start_i] = (
                    f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
                )
            else:
                cat_css[cat_run_start_i] = f"background-color: {idx_hdr_color}{sep}"
                cat_txt_css[cat_run_start_i] = f"background-color: {idx_hdr_color}{sep}"

        # Data and product cells are styled individually on every row.
        if trans == "":
            data_css[i] = f"background-color: {data_total_color}; font-weight: bold{sep}"
            prod_css[i] = f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
            prod_txt_css[i] = f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
        else:
            row_pos = cat_row_counter.get(cat_pair, 0)
            cat_row_counter[cat_pair] = row_pos + 1
            data_css[i] = f"background-color: {data_row_colors[row_pos % 2]}{sep}"
            prod_css[i] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"
            prod_txt_css[i] = f"background-color: {idx_row_colors[row_pos % 2]}{sep}"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=prod_css: css, level="product", axis=0)
    styler = styler.apply_index(lambda s, css=prod_txt_css: css, level="product_txt", axis=0)
    styler = styler.apply_index(lambda s, css=cat_css: css, level="category", axis=0)
    styler = styler.apply_index(lambda s, css=cat_txt_css: css, level="category_txt", axis=0)
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    return styler


def _style_final_use_price_layers_table(df: pd.DataFrame, format_func) -> Styler:
    """Apply colours and separators to a final-use price layers table.

    The table has a five-level MultiIndex
    ``(transaction, transaction_txt, category, category_txt, price_layer)``.

    - ``transaction`` is the outer block grouping dimension: thick
      ``2px solid #999`` separator between transaction blocks, no
      background colour. Handles non-contiguous transaction blocks.
    - ``category`` is the middle grouping dimension: header use-blue
      colour with ``1px solid #ccc`` separator between
      ``(transaction, category)`` blocks within the same transaction,
      and ``2px solid #999`` when the transaction changes.
    - ``price_layer`` rows each get a cycling palette colour based on
      their ordinal position among distinct layer values. The Total row
      (``price_layer == ""``) is bold with the use-total colour.

    Parameters
    ----------
    df : pd.DataFrame
        Price layers table from :func:`inspect_final_uses`.
    format_func : callable
        Applied to all data cells (e.g. ``_format_number``).
    """
    styler = df.style.format(format_func, na_rep="")
    if df.empty:
        return styler

    trans_vals = df.index.get_level_values("transaction")
    cat_vals = df.index.get_level_values("category")
    layer_vals = df.index.get_level_values("price_layer")
    n = len(df)

    # Assign each distinct non-total price_layer value a cycling palette.
    distinct_layers = list(dict.fromkeys(l for l in layer_vals if l != ""))
    layer_palette = {
        l: _LAYER_PALETTES[i % len(_LAYER_PALETTES)]
        for i, l in enumerate(distinct_layers)
    }

    data_total_color = _DATA_COLORS["use_total"]
    idx_hdr_color = _INDEX_COLORS["use_total"]

    data_css = [""] * n
    layer_css = [""] * n
    cat_css = [""] * n
    cat_txt_css = [""] * n
    trans_css = [""] * n
    trans_txt_css = [""] * n

    trans_run_start_i = None
    cat_run_start_i = None
    prev_trans = None
    prev_tc_pair = None

    for i in range(n):
        trans = trans_vals[i]
        cat = cat_vals[i]
        layer = layer_vals[i]
        tc_pair = (trans, cat)
        is_last_row = (i == n - 1)
        next_trans = trans_vals[i + 1] if not is_last_row else None
        next_cat = cat_vals[i + 1] if not is_last_row else None
        next_tc_pair = (next_trans, next_cat) if not is_last_row else None

        # Separator at the bottom of the current row:
        #   thick  → transaction block changes
        #   thin   → same transaction, (trans, cat) block changes
        #   none   → same (trans, cat) block, or last row
        if is_last_row:
            sep = ""
        elif next_trans != trans:
            sep = "; border-bottom: 2px solid #999"
        elif next_tc_pair != tc_pair:
            sep = "; border-bottom: 1px solid #ccc"
        else:
            sep = ""

        # Track starts of contiguous runs for merged-cell CSS placement.
        if trans != prev_trans:
            trans_run_start_i = i
            prev_trans = trans
        if tc_pair != prev_tc_pair:
            cat_run_start_i = i
            prev_tc_pair = tc_pair

        # At the end of a transaction run, write trans/trans_txt CSS
        # (border only, no background colour).
        if next_trans != trans:
            if not is_last_row:
                trans_css[trans_run_start_i] = "border-bottom: 2px solid #999"
                trans_txt_css[trans_run_start_i] = "border-bottom: 2px solid #999"

        # At the end of a (trans, cat) run, write cat/cat_txt CSS
        # (header colour + separator).
        if next_tc_pair != tc_pair:
            cat_css[cat_run_start_i] = f"background-color: {idx_hdr_color}{sep}"
            cat_txt_css[cat_run_start_i] = f"background-color: {idx_hdr_color}{sep}"

        # price_layer and data cells: per-row styling.
        if layer == "":
            # Total row: bold use-total colour.
            data_css[i] = f"background-color: {data_total_color}; font-weight: bold{sep}"
            layer_css[i] = f"background-color: {idx_hdr_color}; font-weight: bold{sep}"
        else:
            palette = layer_palette.get(layer, _LAYER_PALETTES[0])
            data_css[i] = f"background-color: {palette['data'][0]}{sep}"
            layer_css[i] = f"background-color: {palette['index_total']}{sep}"

    styler = styler.apply(
        lambda d: pd.DataFrame({col: data_css for col in d.columns}, index=d.index),
        axis=None,
    )
    styler = styler.apply_index(lambda s, css=layer_css: css, level="price_layer", axis=0)
    styler = styler.apply_index(lambda s, css=cat_css: css, level="category", axis=0)
    styler = styler.apply_index(lambda s, css=cat_txt_css: css, level="category_txt", axis=0)
    styler = styler.apply_index(lambda s, css=trans_css: css, level="transaction", axis=0)
    styler = styler.apply_index(lambda s, css=trans_txt_css: css, level="transaction_txt", axis=0)
    return styler
