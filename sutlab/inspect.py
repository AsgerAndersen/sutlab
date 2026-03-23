"""
Inspection functions for supply and use tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from sutlab.sut import SUT, _match_codes, _natural_sort_key


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
class ProductInspection:
    """
    Result of :func:`inspect_products`.

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
        Same structure as ``balance``. Each value is divided by the value in
        the previous year. The first year column is ``NaN`` throughout.
        Division by zero also yields ``NaN``.

    supply_detail_growth : pd.DataFrame
        Same structure as ``supply_detail``, with the same year-on-year
        growth calculation as ``balance_growth``.

    use_detail_growth : pd.DataFrame
        Same structure as ``use_detail``, with the same year-on-year
        growth calculation as ``balance_growth``.
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
        A dataclass with a ``balance`` table, a ``supply_detail`` dict, and
        a ``use_detail`` dict. See :class:`ProductInspection` for field
        descriptions.

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
    )
    use_detail = _build_detail_df(
        sut.use, matched_products, product_names,
        trans_names, category_names_by_trans, cols, all_ids,
    )
    balance_distribution = _build_balance_distribution(balance)
    supply_detail_distribution = _build_detail_distribution(supply_detail)
    use_detail_distribution = _build_detail_distribution(use_detail)
    balance_growth = _build_growth_table(balance)
    supply_detail_growth = _build_growth_table(supply_detail)
    use_detail_growth = _build_growth_table(use_detail)

    return ProductInspection(
        balance=balance,
        supply_detail=supply_detail,
        use_detail=use_detail,
        balance_distribution=balance_distribution,
        supply_detail_distribution=supply_detail_distribution,
        use_detail_distribution=use_detail_distribution,
        balance_growth=balance_growth,
        supply_detail_growth=supply_detail_growth,
        use_detail_growth=use_detail_growth,
    )


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
        .groupby([prod_col, trans_col, id_col], as_index=False)[bas_col]
        .sum()
    )
    use_agg = (
        sut.use
        .groupby([prod_col, trans_col, id_col], as_index=False)[bas_col]
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
            .groupby([prod_col, cat_col, id_col], as_index=False)[bas_col]
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
    "Balance" is divided by "Total supply". Division by zero yields NaN.
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

        # "Balance" row — always last, divide by total supply
        i_abs = abs_positions[-1]
        dist.iloc[i_abs] = balance.iloc[i_abs].astype(float).div(total_supply).values

    return dist


def _build_growth_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build year-on-year growth table: each value divided by the previous year's value.

    The first year column is ``NaN`` throughout. Division by zero also yields
    ``NaN``. The index and column structure are identical to the input.
    """
    if df.empty:
        return pd.DataFrame()

    floats = df.astype(float)
    growth = floats.div(floats.shift(axis=1))
    return growth.replace([float("inf"), float("-inf")], float("nan"))


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
