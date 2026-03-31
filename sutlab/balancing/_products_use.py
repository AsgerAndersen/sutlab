"""
balance_products_use: scale use rows to match supply totals per product.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, Locks, SUTColumns, _match_codes
from sutlab.balancing._shared import _evaluate_locks, _get_use_price_columns


def _balance_rows_table(
    member_df: pd.DataFrame,
    product_targets: pd.Series,
    locks: Locks | None,
    adjust_transactions: list,
    adjust_categories: list,
    cols: SUTColumns,
    target_price_col: str,
    scale_price_cols: list[str],
) -> pd.DataFrame:
    """Scale adjustable rows to hit per-product use totals.

    For each product group in ``member_df``, computes a scale factor from the
    ratio of the required adjustment to the current adjustable total, and
    applies it to all columns in ``scale_price_cols`` on adjustable rows.
    Fixed rows (locked or (transaction, category) not in the adjust sets) are
    left unchanged.

    Parameters
    ----------
    member_df : DataFrame
        Use rows from the balancing member, filtered to the selected products.
    product_targets : pd.Series
        Target ``target_price_col`` total per product. Index must be product
        code values; values are the target totals (from supply).
    locks : Locks or None
        Cells that must not be modified.
    adjust_transactions : list
        Transaction codes whose rows may be scaled.
    adjust_categories : list
        Category codes whose rows may be scaled. A row is adjustable only if
        its transaction is in ``adjust_transactions`` AND its category is in
        ``adjust_categories``.
    cols : SUTColumns
        Column name mapping.
    target_price_col : str
        Column whose group total must match the target (``cols.price_basic``).
    scale_price_cols : list of str
        All price columns to apply the scale factor to (all price columns in
        chain order, to preserve price layer rate ratios).

    Returns
    -------
    DataFrame
        Copy of ``member_df`` with price columns updated on adjustable rows.
        Index matches the input.

    Raises
    ------
    ValueError
        If any product group has adjustable rows summing to zero in
        ``target_price_col`` but a non-zero deficit to the target, and is not
        covered by a product lock.
    """
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category

    df = member_df.copy()

    # Map the per-product target onto each row.
    df["_target"] = df[prod_col].map(product_targets)

    # Classify rows: adjustable = transaction in adjust set AND category in
    # adjust set AND not locked.
    df["_locked"] = _evaluate_locks(df, locks, cols)
    df["_adjustable"] = (
        df[trans_col].isin(set(adjust_transactions))
        & df[cat_col].isin(set(adjust_categories))
        & ~df["_locked"]
    )

    # Compute the group-level sum of the target price column for adjustable
    # and fixed rows separately. transform("sum") broadcasts back to each row.
    df["_adj_price"] = df[target_price_col].where(df["_adjustable"])
    df["_fix_price"] = df[target_price_col].where(~df["_adjustable"])
    df["_sum_adj"] = df.groupby(prod_col, dropna=False)["_adj_price"].transform("sum")
    df["_sum_fix"] = df.groupby(prod_col, dropna=False)["_fix_price"].transform("sum")

    # Validate feasibility. Products locked via locks.products are silently
    # skipped — users knowingly declare them off-limits for row balancing.
    # Transaction, category, or cell locks that happen to cover all adjustable
    # rows raise an error — the user likely does not realise the implication.
    deficit = df["_target"] - df["_sum_fix"]
    unbalanceable = df[(df["_sum_adj"] == 0) & (deficit.abs() > 1e-10)]
    if not unbalanceable.empty:
        prod_locked_set = set()
        if locks is not None and locks.products is not None:
            prod_locked_set = set(locks.products[cols.product].tolist())

        truly_unbalanceable = unbalanceable[[prod_col]].drop_duplicates()
        truly_unbalanceable = truly_unbalanceable[
            ~truly_unbalanceable[prod_col].isin(prod_locked_set)
        ]
        if not truly_unbalanceable.empty:
            products_str = ", ".join(
                repr(p) for p in truly_unbalanceable[prod_col].tolist()
            )
            raise ValueError(
                f"Cannot balance product(s) {products_str}: adjustable rows sum "
                f"to zero in the target price column, but the target differs from "
                f"the fixed sum. Extend adjust_transactions, adjust_categories, or "
                f"unlock rows to make balancing possible."
            )

    # Compute the scale factor per product (constant within each product group).
    # Three cases for sum_adj == 0:
    #   deficit == 0  → already balanced → 0/0 = NaN → fillna(1.0)
    #   deficit != 0, product-locked → silently skipped → n/0 = inf → 1.0
    #   deficit != 0, not product-locked → raised above
    df["_scale"] = deficit / df["_sum_adj"]
    df["_scale"] = (
        df["_scale"]
        .replace([float("inf"), float("-inf")], float("nan"))
        .fillna(1.0)
    )

    # Exclude locked price layer columns from scaling.
    if locks is not None and locks.price_layers is not None:
        locked_layer_cols = set(locks.price_layers["price_layer"].tolist())
        scale_price_cols = [c for c in scale_price_cols if c not in locked_layer_cols]

    # Apply the scale factor to all price columns on adjustable rows.
    adj_mask = df["_adjustable"]
    df.loc[adj_mask, scale_price_cols] = (
        df.loc[adj_mask, scale_price_cols]
        .multiply(df.loc[adj_mask, "_scale"], axis=0)
    )

    # Drop helper columns before returning.
    helper_cols = [
        "_target", "_locked", "_adjustable",
        "_adj_price", "_fix_price", "_sum_adj", "_sum_fix", "_scale",
    ]
    df = df.drop(columns=helper_cols)

    return df


def balance_products_use(
    sut: SUT,
    products: str | list[str] | None = None,
    adjust_transactions: str | list[str] | None = None,
    adjust_categories: str | list[str] | None = None,
) -> SUT:
    """Scale use rows so each product's total use in basic prices matches its supply.

    For each selected product, computes a scale factor from the ratio of the
    supply total (basic prices) to the current adjustable use total (basic
    prices), and applies it to **all** price columns on adjustable rows. This
    preserves price layer rate ratios. Fixed rows — locked rows and rows whose
    (transaction, category) is not in the adjust sets — are left unchanged.

    The target is derived internally from ``sut.supply``; ``sut.balancing_targets``
    is not required.

    Parameters
    ----------
    sut : SUT
        The SUT collection. Must have ``balancing_id`` and ``metadata`` set.
    products : str, list of str, or None
        Product codes to balance. Each entry supports the same pattern syntax
        as :func:`~sutlab.sut.get_rows`: exact (``"A"``), wildcard (``"A*"``),
        range (``"A:C"``), or negation (``"~T"``). Only products present in
        both supply and use for the balancing member are eligible. If ``None``,
        all such products are included, excluding any covered by a product lock.
    adjust_transactions : str, list of str, or None
        Transaction codes whose rows may be scaled. Same pattern syntax as
        ``products``. Rows for other transactions are treated as fixed. If
        ``None``, all transactions present in the filtered use are included.
    adjust_categories : str, list of str, or None
        Category codes whose rows may be scaled. Same pattern syntax as
        ``products``. Combined with ``adjust_transactions`` via AND logic: a
        row is adjustable only if its transaction matches ``adjust_transactions``
        AND its category matches ``adjust_categories``. If ``None``, all
        categories for the selected transactions are included.

    Returns
    -------
    SUT
        New SUT with an updated use DataFrame for the balancing member. Supply
        and all other collection members are unchanged. The original SUT is not
        modified.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.balancing_id`` is ``None``.
    ValueError
        If the products filter matches no products present in both supply and
        use for the balancing member.
    ValueError
        If any product group has adjustable rows summing to zero in basic prices
        but a non-zero deficit to the supply target, and is not covered by a
        product lock.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call balance_products_use. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.balancing_id is None:
        raise ValueError(
            "sut.balancing_id is not set. Call set_balancing_id first to "
            "designate which collection member to balance."
        )

    cols = sut.metadata.columns
    id_col = cols.id
    trans_col = cols.transaction
    cat_col = cols.category
    prod_col = cols.product
    balancing_id = sut.balancing_id
    locks = sut.balancing_config.locks if sut.balancing_config is not None else None

    # Extract balancing member rows.
    member_supply = sut.supply[sut.supply[id_col] == balancing_id]
    member_use = sut.use[sut.use[id_col] == balancing_id]

    # Products must appear in both supply and use: the target comes from supply,
    # and there must be use rows to scale.
    supply_products = set(member_supply[prod_col].tolist())
    use_products = set(member_use[prod_col].tolist())
    intersection_products = sorted(supply_products & use_products)

    # Resolve products. When None: all intersection products not covered by a
    # product lock. Product locks declare a product off-limits for row balancing
    # and are silently excluded here (not an error).
    if products is None:
        prod_locked_set = set()
        if locks is not None and locks.products is not None:
            prod_locked_set = set(locks.products[prod_col].tolist())
        products_list = [p for p in intersection_products if p not in prod_locked_set]
    else:
        if isinstance(products, str):
            products = [products]
        products_list = _match_codes(intersection_products, products)

    if not products_list:
        raise ValueError(
            f"The products filter matched no products present in both supply and "
            f"use for balancing_id={balancing_id!r}. "
            f"Available products (intersection of supply and use): "
            f"{intersection_products}."
        )

    # Filter use to selected products.
    member_use_filtered = member_use[member_use[prod_col].isin(set(products_list))]

    # Resolve adjust_transactions: if None, all transactions in the filtered use.
    if adjust_transactions is None:
        adjust_trans_list = sorted(set(member_use_filtered[trans_col].tolist()))
    else:
        if isinstance(adjust_transactions, str):
            adjust_transactions = [adjust_transactions]
        all_use_trans = sorted(set(member_use_filtered[trans_col].tolist()))
        adjust_trans_list = _match_codes(all_use_trans, adjust_transactions)

    # Resolve adjust_categories: if None, all categories for the selected
    # transactions in the filtered use.
    if adjust_categories is None:
        trans_filtered_use = member_use_filtered[
            member_use_filtered[trans_col].isin(set(adjust_trans_list))
        ]
        adjust_cats_list = sorted(set(trans_filtered_use[cat_col].tolist()))
    else:
        if isinstance(adjust_categories, str):
            adjust_categories = [adjust_categories]
        all_use_cats = sorted(set(member_use_filtered[cat_col].tolist()))
        adjust_cats_list = _match_codes(all_use_cats, adjust_categories)

    # Compute the per-product supply total (target for use basic prices).
    product_targets = (
        member_supply[member_supply[prod_col].isin(set(products_list))]
        .groupby(prod_col, dropna=False)[cols.price_basic]
        .sum()
    )

    use_price_cols = _get_use_price_columns(sut.use, cols)

    # Balance use rows. Scale factor computed from basic prices (matching supply);
    # applied to all price columns to preserve price layer rate ratios.
    balanced_use_rows = _balance_rows_table(
        member_df=member_use_filtered,
        product_targets=product_targets,
        locks=locks,
        adjust_transactions=adjust_trans_list,
        adjust_categories=adjust_cats_list,
        cols=cols,
        target_price_col=cols.price_basic,
        scale_price_cols=use_price_cols,
    )

    # Write updated price columns back into a full-collection copy.
    new_use = sut.use.copy()
    new_use.loc[balanced_use_rows.index, use_price_cols] = (
        balanced_use_rows[use_price_cols]
    )

    return replace(sut, use=new_use)
