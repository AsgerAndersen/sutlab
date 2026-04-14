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
    "balance":       ("#f5f5f5", "#fafafa"),
    # GVA and Input coefficient rows in the industry balance table.
    "derived":       ("#fce8d0", "#fef3e8"),
}
_INDEX_COLORS = {
    "supply":        ("#d8eedb", "#e3f3e5"),
    "supply_total":  "#b8d8ba",
    "use":           ("#d0e8f8", "#dbedfa"),
    "use_total":     "#a5cff4",
    "balance":       ("#e5e5e5", "#ebebeb"),
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
                bg = colors["balance"][0]
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


def _style_imbalances_table(
    df: pd.DataFrame,
    supply_cols: list[str],
    use_cols: list[str],
    rel_col: str,
) -> Styler:
    """Apply column-group colours and formatting to the imbalances table.

    Columns are coloured by role:

    - Supply columns (``supply_*``) → green (``supply`` palette), alternating
      row shading.
    - Use columns (``use_*``) → blue (``use`` palette), alternating row
      shading.
    - Diff and rel columns → neutral grey (``balance`` palette), alternating
      row shading.

    The index (product code, and label if present) uses the neutral grey
    index palette (``_INDEX_COLORS["balance"]``), alternating per row.

    ``rel_col`` is formatted with :func:`_format_percentage`; all other
    columns use :func:`_format_number`.

    Parameters
    ----------
    df : pd.DataFrame
        The imbalances DataFrame from ``UnbalancedProductsData.imbalances``.
    supply_cols : list of str
        Column names that belong to the supply group (green).
    use_cols : list of str
        Column names that belong to the use group (blue), including price
        layers and purchasers' prices.
    rel_col : str
        Name of the relative-difference column, formatted as a percentage.
    """
    styler = df.style
    non_rel_cols = [c for c in df.columns if c != rel_col]
    if non_rel_cols:
        styler = styler.format(_format_number, na_rep="", subset=non_rel_cols)
    if rel_col in df.columns:
        styler = styler.format(_format_percentage, na_rep="", subset=[rel_col])

    if df.empty:
        return styler

    n = len(df)
    supply_col_set = set(supply_cols)
    use_col_set = set(use_cols)

    # Build per-cell CSS: column group determines the colour palette,
    # row position determines which alternating shade to use.
    css_data = {}
    for col in df.columns:
        col_css = []
        for i in range(n):
            shade = i % 2
            if col in supply_col_set:
                bg = _DATA_COLORS["supply"][shade]
            elif col in use_col_set:
                bg = _DATA_COLORS["use"][shade]
            else:
                bg = _DATA_COLORS["balance"][shade]
            col_css.append(f"background-color: {bg}")
        css_data[col] = col_css

    css_df = pd.DataFrame(css_data, index=df.index)
    styler = styler.apply(lambda d: css_df, axis=None)

    # Index: alternating neutral grey, slightly more saturated than data cells.
    index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}" for i in range(n)
    ]

    if isinstance(df.index, pd.MultiIndex):
        for level in df.index.names:
            styler = styler.apply_index(
                lambda s, css=index_css: css, level=level, axis=0
            )
    else:
        styler = styler.apply_index(lambda s, css=index_css: css, axis=0)

    return styler


def _style_balancing_targets_table(
    df: pd.DataFrame,
    price_col: str,
    rel_col: str,
    palette: str,
) -> Styler:
    """Apply column-group colours and formatting to a balancing targets table.

    Columns are coloured by role:

    - Actual value (``{price_col}``) and target (``target_{price_col}``) →
      supply green or use blue, depending on ``palette``.
    - All other columns (diff, rel, tol, violation) → neutral grey
      (``balance`` palette), alternating row shading.

    The rel column is formatted with :func:`_format_percentage`; all other
    columns use :func:`_format_number`.

    Parameters
    ----------
    df : pd.DataFrame
        The supply or use targets DataFrame.
    price_col : str
        Name of the price column (e.g. ``"bas"`` or ``"koeb"``).
    rel_col : str
        Name of the relative-deviation column, formatted as a percentage.
    palette : str
        Colour palette for the price and target columns. Either
        ``"supply"`` (green) or ``"use"`` (blue).
    """
    styler = df.style
    non_rel_cols = [c for c in df.columns if c != rel_col]
    if non_rel_cols:
        styler = styler.format(_format_number, na_rep="", subset=non_rel_cols)
    if rel_col in df.columns:
        styler = styler.format(_format_percentage, na_rep="", subset=[rel_col])

    if df.empty:
        return styler

    n = len(df)
    target_col = f"target_{price_col}"
    value_cols = {price_col, target_col}

    # Identify transaction block boundaries (transaction code is always index
    # level 0). The separator border goes on different rows depending on the
    # element being styled:
    #
    # - Data columns and category index levels: border on the LAST row of each
    #   block, so it appears at the bottom of the block.
    # - Transaction index levels (trans, trans_txt): border on the FIRST row
    #   of each block, because pandas Styler merges repeated outer-level values
    #   into a single spanning cell and takes CSS from the first row of that
    #   span. Placing the border there causes it to appear at the bottom of the
    #   merged cell, i.e. at the block boundary.
    #
    # No border is placed after the final block in either case.
    trans_vals = df.index.get_level_values(0)
    block_end_rows = {
        i for i in range(n - 1)
        if trans_vals[i] != trans_vals[i + 1]
    }
    # For transaction index levels, pandas Styler merges repeated values into
    # a single spanning cell and takes CSS from the FIRST row of that span.
    # The border must therefore be placed on the first row of each non-last
    # block so it appears at the bottom edge of the merged cell.
    all_block_starts = {0} | {i + 1 for i in block_end_rows}
    last_block_start = max(all_block_starts)
    trans_border_rows = all_block_starts - {last_block_start}

    css_data = {}
    for col in df.columns:
        col_css = []
        for i in range(n):
            shade = i % 2
            if col in value_cols:
                bg = _DATA_COLORS[palette][shade]
            else:
                bg = _DATA_COLORS["balance"][shade]
            sep = "; border-bottom: 2px solid #999" if i in block_end_rows else ""
            col_css.append(f"background-color: {bg}{sep}")
        css_data[col] = col_css

    css_df = pd.DataFrame(css_data, index=df.index)
    styler = styler.apply(lambda d: css_df, axis=None)

    # Index CSS: transaction levels use block_start_rows; category levels use
    # block_end_rows. For a 2-level index (trans, cat) level 0 is transaction
    # and level 1 is category. For a 4-level index (trans, trans_txt, cat,
    # cat_txt) levels 0-1 are transaction and levels 2-3 are category.
    index_nlevels = df.index.nlevels
    trans_level_names = df.index.names[:2] if index_nlevels == 4 else df.index.names[:1]
    cat_level_names = df.index.names[2:] if index_nlevels == 4 else df.index.names[1:]

    # CSS for transaction index levels: border on first row of each non-last block.
    trans_index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        + ("; border-bottom: 2px solid #999" if i in trans_border_rows else "")
        for i in range(n)
    ]
    # CSS for category index levels: border on last row of each block.
    cat_index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        + ("; border-bottom: 2px solid #999" if i in block_end_rows else "")
        for i in range(n)
    ]

    if isinstance(df.index, pd.MultiIndex):
        for level in trans_level_names:
            styler = styler.apply_index(
                lambda s, css=trans_index_css: css, level=level, axis=0
            )
        for level in cat_level_names:
            styler = styler.apply_index(
                lambda s, css=cat_index_css: css, level=level, axis=0
            )
    else:
        styler = styler.apply_index(lambda s, css=trans_index_css: css, axis=0)

    return styler


def _style_comparison_table(
    df: pd.DataFrame,
    palette: str,
    rel_col: str,
) -> Styler:
    """Apply colours and formatting to a scalar comparison table.

    Used for ``supply``, ``use_basic``, ``use_purchasers`` and the
    corresponding balancing-targets tables.

    Colour scheme:

    - ``before_*`` columns → shade 0 of ``palette`` (supply green or use
      blue), fixed across all rows.
    - ``after_*`` columns → shade 1 of ``palette``, fixed across all rows.
      The two shades make before/after visually distinguishable by column.
    - ``diff_*`` and ``rel_*`` columns → neutral grey (``balance`` palette),
      alternating by row position.

    The ``id`` index level (outermost, always merged) gets a thick
    ``2px solid #999`` border at the bottom of each non-last id block,
    placed on the **first** row of the block (pandas takes CSS from the
    first row of a merged span). All inner index levels and data cells get
    the border on the **last** row of each block.

    Parameters
    ----------
    df : pd.DataFrame
        Comparison table with a MultiIndex whose first level is the id
        column. Columns: ``before_{col}``, ``after_{col}``, ``diff_{col}``,
        ``rel_{col}``.
    palette : str
        ``"supply"`` (green) or ``"use"`` (blue).
    rel_col : str
        Name of the relative-difference column, formatted as a percentage.
        Pass an empty string when no rel column is present.
    """
    non_rel_cols = [c for c in df.columns if c != rel_col]
    styler = df.style
    if non_rel_cols:
        styler = styler.format(_format_number, na_rep="", subset=non_rel_cols)
    if rel_col and rel_col in df.columns:
        styler = styler.format(_format_percentage, na_rep="", subset=[rel_col])

    if df.empty:
        return styler

    n = len(df)
    id_vals = df.index.get_level_values(0)

    # Identify id block boundaries.
    block_end_rows = {i for i in range(n - 1) if id_vals[i] != id_vals[i + 1]}
    all_block_starts = {0} | {i + 1 for i in block_end_rows}
    last_block_start = max(all_block_starts)
    id_border_rows = all_block_starts - {last_block_start}

    # Data CSS: column role determines shade; row position selects alternating
    # grey for diff/rel; id-block separator on the last row of each block.
    css_data = {}
    for col in df.columns:
        col_css = []
        for i in range(n):
            sep = "; border-bottom: 2px solid #999" if i in block_end_rows else ""
            if col.startswith("before_"):
                bg = _DATA_COLORS[palette][0]
            elif col.startswith("after_"):
                bg = _DATA_COLORS[palette][1]
            else:
                bg = _DATA_COLORS["balance"][i % 2]
            col_css.append(f"background-color: {bg}{sep}")
        css_data[col] = col_css

    css_df = pd.DataFrame(css_data, index=df.index)
    styler = styler.apply(lambda d: css_df, axis=None)

    # id index level (level 0): merged cell — border on first row of each
    # non-last block so it aligns with the full block height.
    id_index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        + ("; border-bottom: 2px solid #999" if i in id_border_rows else "")
        for i in range(n)
    ]
    # All other index levels: border on last row of each id block.
    inner_index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        + ("; border-bottom: 2px solid #999" if i in block_end_rows else "")
        for i in range(n)
    ]

    if isinstance(df.index, pd.MultiIndex):
        styler = styler.apply_index(lambda s, css=id_index_css: css, level=0, axis=0)
        for level_name in df.index.names[1:]:
            styler = styler.apply_index(
                lambda s, css=inner_index_css: css, level=level_name, axis=0
            )
    else:
        styler = styler.apply_index(lambda s, css=id_index_css: css, axis=0)

    return styler


def _style_comparison_layers_table(df: pd.DataFrame) -> Styler:
    """Apply colours and formatting to a price-layers comparison table.

    Used for ``use_price_layers`` and
    ``balancing_targets_use_price_layers``.

    Colour scheme:

    - ``before`` and ``after`` columns → cycling layer palette based on the
      ``price_layer`` index value: ``data[0]`` for ``before``,
      ``data[1]`` for ``after``.
    - ``diff`` and ``rel`` columns → neutral grey (``balance`` palette),
      alternating by row position. ``rel`` is formatted as a percentage.
    - ``price_layer`` index level → ``index_total`` shade of its palette.
    - All other inner index levels → alternating neutral grey.
    - ``id`` index level (level 0) → merged cell with thick separator on the
      first row of each non-last id block.
    - Data cells and inner index levels → thick separator on the last row of
      each id block.

    Parameters
    ----------
    df : pd.DataFrame
        Price-layers comparison table with ``price_layer`` as the last
        index level. Columns: ``before``, ``after``, ``diff``, ``rel``.
    """
    non_rel_cols = [c for c in df.columns if c != "rel"]
    styler = df.style
    if non_rel_cols:
        styler = styler.format(_format_number, na_rep="", subset=non_rel_cols)
    if "rel" in df.columns:
        styler = styler.format(_format_percentage, na_rep="", subset=["rel"])

    if df.empty:
        return styler

    n = len(df)
    id_vals = df.index.get_level_values(0)
    layer_vals = df.index.get_level_values("price_layer")

    # Assign a cycling palette to each distinct price_layer value.
    distinct_layers = list(dict.fromkeys(layer_vals))
    layer_palette = {
        layer: _LAYER_PALETTES[i % len(_LAYER_PALETTES)]
        for i, layer in enumerate(distinct_layers)
    }

    # Identify id block boundaries.
    block_end_rows = {i for i in range(n - 1) if id_vals[i] != id_vals[i + 1]}
    all_block_starts = {0} | {i + 1 for i in block_end_rows}
    last_block_start = max(all_block_starts)
    id_border_rows = all_block_starts - {last_block_start}

    # Data CSS.
    css_data = {}
    for col in df.columns:
        col_css = []
        for i in range(n):
            sep = "; border-bottom: 2px solid #999" if i in block_end_rows else ""
            if col == "before":
                palette = layer_palette.get(layer_vals[i], _LAYER_PALETTES[0])
                bg = palette["data"][0]
            elif col == "after":
                palette = layer_palette.get(layer_vals[i], _LAYER_PALETTES[0])
                bg = palette["data"][1]
            else:
                bg = _DATA_COLORS["balance"][i % 2]
            col_css.append(f"background-color: {bg}{sep}")
        css_data[col] = col_css

    css_df = pd.DataFrame(css_data, index=df.index)
    styler = styler.apply(lambda d: css_df, axis=None)

    # price_layer index level: layer palette index_total shade + id separator.
    layer_index_css = []
    for i in range(n):
        palette = layer_palette.get(layer_vals[i], _LAYER_PALETTES[0])
        sep = "; border-bottom: 2px solid #999" if i in block_end_rows else ""
        layer_index_css.append(f"background-color: {palette['index_total']}{sep}")

    # id index level (level 0): merged cell — border on first row of each non-last block.
    id_index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        + ("; border-bottom: 2px solid #999" if i in id_border_rows else "")
        for i in range(n)
    ]

    # All other inner index levels (not id, not price_layer): alternating grey + id separator.
    inner_index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        + ("; border-bottom: 2px solid #999" if i in block_end_rows else "")
        for i in range(n)
    ]

    if isinstance(df.index, pd.MultiIndex):
        styler = styler.apply_index(lambda s, css=id_index_css: css, level=0, axis=0)
        for level_name in df.index.names[1:]:
            if level_name == "price_layer":
                styler = styler.apply_index(
                    lambda s, css=layer_index_css: css, level=level_name, axis=0
                )
            else:
                styler = styler.apply_index(
                    lambda s, css=inner_index_css: css, level=level_name, axis=0
                )
    else:
        styler = styler.apply_index(lambda s, css=id_index_css: css, axis=0)

    return styler


def _style_summary_table(df: pd.DataFrame) -> Styler:
    """Apply row colours and block separators to the comparison summary table.

    Colour scheme:

    - ``supply`` and ``balancing_targets_supply`` rows → green
      (``supply`` palette, shade 0).
    - Use rows (``use_basic``, ``use_purchasers``, ``use_price_layers`` and
      their ``balancing_targets_*`` counterparts) → alternating blue
      (``use`` palette), counter resetting at the start of each block.
    - Data cells use ``_DATA_COLORS``; index cells use the more saturated
      ``_INDEX_COLORS``, matching the convention in other inspection tables.

    A ``2px solid #999`` separator is placed between the SUT block (first
    four rows) and the balancing-targets block (last four rows) when both
    are present.

    Formats ``n_differences`` as a plain integer (no decimals).

    Parameters
    ----------
    df : pd.DataFrame
        Summary DataFrame with ``table`` as the index name and
        ``n_differences`` as the sole column.
    """
    styler = df.style.format(
        lambda v: "" if pd.isna(v) else str(int(v)), na_rep=""
    )

    if df.empty:
        return styler

    n = len(df)
    table_names = df.index.tolist()

    # Determine the separator row: last SUT row, when a targets block follows.
    has_targets_block = any(name.startswith("balancing_targets_") for name in table_names)
    sut_end = next(
        (i for i in range(n - 1, -1, -1) if not table_names[i].startswith("balancing_targets_")),
        None,
    )
    separator_row = sut_end if (has_targets_block and sut_end is not None) else None

    data_css = []
    index_css = []
    use_counter = 0

    for i, name in enumerate(table_names):
        # Reset the use-row alternation counter at the start of each block.
        if name in ("supply", "balancing_targets_supply"):
            use_counter = 0

        sep = "; border-bottom: 2px solid #999" if i == separator_row else ""

        is_supply = name in ("supply", "balancing_targets_supply")
        if is_supply:
            data_bg = _DATA_COLORS["supply"][0]
            index_bg = _INDEX_COLORS["supply"][0]
        else:
            data_bg = _DATA_COLORS["use"][use_counter % 2]
            index_bg = _INDEX_COLORS["use"][use_counter % 2]
            use_counter += 1

        data_css.append(f"background-color: {data_bg}{sep}")
        index_css.append(f"background-color: {index_bg}{sep}")

    css_df = pd.DataFrame({df.columns[0]: data_css}, index=df.index)
    styler = styler.apply(lambda d: css_df, axis=None)
    styler = styler.apply_index(lambda s, css=index_css: css, axis=0)

    return styler


def _style_unbalanced_targets_summary(df: pd.DataFrame) -> Styler:
    """Apply row colours and block separator to the unbalanced-targets summary table.

    Colour scheme:

    - ``supply_*`` rows → alternating green (``supply`` palette, shades 0/1).
    - ``use_*`` rows → alternating blue (``use`` palette, shades 0/1).

    Shade counters reset at the start of each block. A ``2px solid #999``
    separator is placed after the last main-tables row when a violations block
    follows (i.e. when the table has 8 rows).

    Formats ``n_unbalanced`` as a plain integer and ``largest_diff`` as a
    number with one decimal place. ``NaN`` values are rendered as empty strings.

    Parameters
    ----------
    df : pd.DataFrame
        Summary DataFrame with ``table`` as the index name and columns
        ``n_unbalanced`` and ``largest_diff``.
    """
    def _format_cell(v, col):
        if pd.isna(v):
            return ""
        if col == "n_unbalanced":
            return str(int(v))
        return f"{v:,.1f}"

    styler = df.style.format(
        {col: (lambda v, c=col: _format_cell(v, c)) for col in df.columns},
        na_rep="",
    )

    if df.empty:
        return styler

    n = len(df)
    table_names = df.index.tolist()

    # Separator after the 4th row (index 3) when a violations block follows.
    separator_row = 3 if n == 8 else None

    supply_counter = 0
    use_counter = 0
    data_css_rows = []
    index_css = []

    for i, name in enumerate(table_names):
        # Reset shade counters at the start of each block.
        if i == 4:
            supply_counter = 0
            use_counter = 0

        sep = "; border-bottom: 2px solid #999" if i == separator_row else ""

        if "supply" in name:
            data_bg = _DATA_COLORS["supply"][supply_counter % 2]
            index_bg = _INDEX_COLORS["supply"][supply_counter % 2]
            supply_counter += 1
        else:
            data_bg = _DATA_COLORS["use"][use_counter % 2]
            index_bg = _INDEX_COLORS["use"][use_counter % 2]
            use_counter += 1

        data_css_rows.append(f"background-color: {data_bg}{sep}")
        index_css.append(f"background-color: {index_bg}{sep}")

    css_df = pd.DataFrame(
        {col: data_css_rows for col in df.columns},
        index=df.index,
    )
    styler = styler.apply(lambda d: css_df, axis=None)
    styler = styler.apply_index(lambda s, css=index_css: css, axis=0)

    return styler


def _style_unbalanced_products_summary(df: pd.DataFrame) -> Styler:
    """Apply neutral grey colours to the unbalanced-products summary table.

    Colour scheme:

    - All rows → alternating neutral grey (``balance`` palette, shades 0/1).

    Formats ``n_unbalanced`` as a plain integer and ``largest_diff`` as a
    number with one decimal place. ``NaN`` values are rendered as empty strings.

    Parameters
    ----------
    df : pd.DataFrame
        Summary DataFrame with ``table`` as the index name and columns
        ``n_unbalanced`` and ``largest_diff``.
    """
    def _format_cell(v, col):
        if pd.isna(v):
            return ""
        if col == "n_unbalanced":
            return str(int(v))
        return f"{v:,.1f}"

    styler = df.style.format(
        {col: (lambda v, c=col: _format_cell(v, c)) for col in df.columns},
        na_rep="",
    )

    if df.empty:
        return styler

    n = len(df)
    data_css = {
        col: [
            f"background-color: {_DATA_COLORS['balance'][i % 2]}"
            for i in range(n)
        ]
        for col in df.columns
    }
    index_css = [
        f"background-color: {_INDEX_COLORS['balance'][i % 2]}"
        for i in range(n)
    ]

    css_df = pd.DataFrame(data_css, index=df.index)
    styler = styler.apply(lambda d: css_df, axis=None)
    styler = styler.apply_index(lambda s, css=index_css: css, axis=0)

    return styler
