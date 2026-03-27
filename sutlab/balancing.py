"""
Balancing functions for supply and use tables.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, Locks, SUTColumns, _match_codes


def _evaluate_locks(df: pd.DataFrame, locks: Locks | None, cols: SUTColumns) -> pd.Series:
    """Return a boolean Series indicating which rows are locked.

    A row is locked if it matches any of the four lock levels:

    - ``products``: the row's product is in the locked products list.
    - ``transactions``: the row's transaction is in the locked transactions list.
    - ``categories``: the (transaction, category) pair is in the locked
      categories table.
    - ``cells``: the (product, transaction, category) triple is in the locked
      cells table.

    OR logic: a row is locked if it matches **any** of the above levels.

    Parameters
    ----------
    df : DataFrame
        Rows to evaluate. Must contain the product, transaction, and
        category columns.
    locks : Locks or None
        Lock specification. If ``None``, returns all ``False`` (no rows locked).
    cols : SUTColumns
        Column name mapping.

    Returns
    -------
    pd.Series
        Boolean Series with the same index as ``df``.
    """
    locked = pd.Series(False, index=df.index)

    if locks is None:
        return locked

    if locks.products is not None:
        locked_products = set(locks.products[cols.product].tolist())
        locked |= df[cols.product].isin(locked_products)

    if locks.transactions is not None:
        locked_trans = set(locks.transactions[cols.transaction].tolist())
        locked |= df[cols.transaction].isin(locked_trans)

    if locks.categories is not None:
        lock_pairs = set(zip(
            locks.categories[cols.transaction],
            locks.categories[cols.category],
        ))
        df_pairs = list(zip(df[cols.transaction], df[cols.category]))
        locked |= pd.Series(df_pairs, index=df.index).isin(lock_pairs)

    if locks.cells is not None:
        lock_triples = set(zip(
            locks.cells[cols.product],
            locks.cells[cols.transaction],
            locks.cells[cols.category],
        ))
        df_triples = list(zip(df[cols.product], df[cols.transaction], df[cols.category]))
        locked |= pd.Series(df_triples, index=df.index).isin(lock_triples)

    return locked


def _get_use_price_columns(use_df: pd.DataFrame, cols: SUTColumns) -> list[str]:
    """Return the names of all price columns present in the use DataFrame.

    Returns columns in price-chain order: basic price first, then each
    intermediate layer in sequence, then purchasers' prices last. Only
    columns that are both mapped in ``cols`` and present in ``use_df``
    are included.

    Parameters
    ----------
    use_df : DataFrame
        The use table to inspect.
    cols : SUTColumns
        Column name mapping.

    Returns
    -------
    list of str
        Price column names in price-chain order.
    """
    all_price_roles = [
        "price_basic",
        "trade_margins",
        "wholesale_margins",
        "retail_margins",
        "transport_margins",
        "product_taxes",
        "product_subsidies",
        "product_taxes_less_subsidies",
        "vat",
        "price_purchasers",
    ]
    result = []
    for role in all_price_roles:
        col_name = getattr(cols, role)
        if col_name is not None and col_name in use_df.columns:
            result.append(col_name)
    return result


def _balance_table(
    member_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    locks: Locks | None,
    adjust_products: list,
    cols: SUTColumns,
    target_price_col: str,
    scale_price_cols: list[str],
) -> pd.DataFrame:
    """Scale adjustable rows to hit per-column targets.

    For each (transaction, category) group in ``member_df``, computes a
    scale factor from the ratio of the required adjustment to the current
    adjustable total, and applies it to all columns in ``scale_price_cols``
    on adjustable rows. Fixed rows (locked or product not in
    ``adjust_products``) are left unchanged.

    Parameters
    ----------
    member_df : DataFrame
        Rows from the balancing member, filtered to the requested
        (transaction, category) combinations.
    targets_df : DataFrame
        Targets for the balancing member. Must contain ``cols.transaction``,
        ``cols.category``, and ``target_price_col``. One row per
        (transaction, category); extra columns are ignored.
    locks : Locks or None
        Cells that must not be modified.
    adjust_products : list
        Product codes that may be scaled.
    cols : SUTColumns
        Column name mapping.
    target_price_col : str
        Column whose group total must match the target. For supply:
        ``cols.price_basic``. For use: ``cols.price_purchasers``.
    scale_price_cols : list of str
        All price columns to apply the scale factor to. For supply:
        ``[cols.price_basic]``. For use: all price columns in chain order.

    Returns
    -------
    DataFrame
        Copy of ``member_df`` with price columns updated on adjustable rows.
        Index matches the input.

    Raises
    ------
    ValueError
        If any (transaction, category) combination in ``member_df`` has no
        target in ``targets_df``.
    ValueError
        If any group has adjustable rows summing to zero in
        ``target_price_col`` but a non-zero deficit to the target.
    """
    trans_col = cols.transaction
    cat_col = cols.category
    prod_col = cols.product
    group_cols = [trans_col, cat_col]

    # Merge the target value onto each row. Select only the columns needed
    # to avoid conflicts with other columns in member_df (e.g. the id column).
    target_for_merge = (
        targets_df[[trans_col, cat_col, target_price_col]]
        .rename(columns={target_price_col: "_target"})
    )
    original_index = member_df.index
    df = member_df.merge(target_for_merge, on=group_cols, how="left")
    df.index = original_index  # merge resets index; restore the original

    # Validate that every (trans, cat) combination in the data has a target.
    missing_targets = df[df["_target"].isna()][[trans_col, cat_col]].drop_duplicates()
    if not missing_targets.empty:
        missing_str = ", ".join(
            f"({row[trans_col]!r}, {row[cat_col]!r})"
            for _, row in missing_targets.iterrows()
        )
        raise ValueError(
            f"No target found for the following (transaction, category) combinations: "
            f"{missing_str}. Add targets for these combinations or remove them from "
            f"the transactions and categories arguments."
        )

    # Classify rows: adjustable = in adjust_products AND not locked.
    df["_locked"] = _evaluate_locks(df, locks, cols)
    df["_adjustable"] = df[prod_col].isin(set(adjust_products)) & ~df["_locked"]

    # Compute the group-level sum of the target price column for adjustable
    # and fixed rows separately. transform("sum") broadcasts back to each row,
    # skipping NaN (rows of the other class) by default.
    df["_adj_price"] = df[target_price_col].where(df["_adjustable"])
    df["_fix_price"] = df[target_price_col].where(~df["_adjustable"])
    df["_sum_adj"] = df.groupby(group_cols, dropna=False)["_adj_price"].transform("sum")
    df["_sum_fix"] = df.groupby(group_cols, dropna=False)["_fix_price"].transform("sum")

    # Validate that balancing is feasible: if adjustable rows sum to zero but
    # the deficit to the target is non-zero, there is nothing to scale.
    # Exception: if the column is covered by a transaction or category lock,
    # the user has deliberately excluded it from balancing — skip silently.
    deficit = df["_target"] - df["_sum_fix"]
    unbalanceable = df[(df["_sum_adj"] == 0) & (deficit.abs() > 1e-10)]
    if not unbalanceable.empty:
        col_locked_trans = set()
        col_locked_pairs = set()
        if locks is not None:
            if locks.transactions is not None:
                col_locked_trans = set(locks.transactions[cols.transaction].tolist())
            if locks.categories is not None:
                col_locked_pairs = set(zip(
                    locks.categories[cols.transaction],
                    locks.categories[cols.category],
                ))

        truly_unbalanceable = unbalanceable[[trans_col, cat_col]].drop_duplicates()
        truly_unbalanceable = truly_unbalanceable[
            ~truly_unbalanceable.apply(
                lambda r: (
                    r[trans_col] in col_locked_trans
                    or (r[trans_col], r[cat_col]) in col_locked_pairs
                ),
                axis=1,
            )
        ]
        if not truly_unbalanceable.empty:
            pairs_str = ", ".join(
                f"({row[trans_col]!r}, {row[cat_col]!r})"
                for _, row in truly_unbalanceable.iterrows()
            )
            raise ValueError(
                f"Cannot balance (transaction, category) combinations {pairs_str}: "
                f"adjustable rows sum to zero in the target price column, but the "
                f"target differs from the fixed sum. "
                f"Extend adjust_products or unlock rows to make balancing possible."
            )

    # Compute the scale factor per group (constant within each group).
    # Three cases for sum_adj == 0:
    #   deficit == 0  → already balanced → 0/0 = NaN → fillna(1.0)
    #   deficit != 0, column-locked → silently skipped → n/0 = inf → 1.0
    #   deficit != 0, not column-locked → raised above
    df["_scale"] = deficit / df["_sum_adj"]
    df["_scale"] = (
        df["_scale"]
        .replace([float("inf"), float("-inf")], float("nan"))
        .fillna(1.0)
    )

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


def balance_columns(
    sut: SUT,
    transactions: str | list[str] | None = None,
    categories: str | list[str] | None = None,
    adjust_products: str | list[str] | None = None,
) -> SUT:
    """Scale product rows to hit per-column targets for the active balancing member.

    For each (transaction, category) combination matched by the filter,
    identifies which rows are adjustable (product in ``adjust_products`` and
    not locked) and scales them uniformly so the column total in the target
    price column matches the target from ``sut.balancing_targets``. Fixed
    rows — locked rows and rows for products not in ``adjust_products`` — are
    left unchanged.

    For use columns, targets are in purchasers' prices. The scale factor is
    computed from purchasers' prices and applied to **all** price columns
    (basic, all intermediate layers, purchasers'), keeping the ratio between
    layers constant.

    Parameters
    ----------
    sut : SUT
        The SUT collection. Must have ``balancing_id``, ``balancing_targets``,
        and ``metadata`` set.
    transactions : str, list of str, or None
        Transaction codes identifying which columns to balance. Each entry
        supports the same pattern syntax as :func:`~sutlab.sut.get_rows`:
        exact (``"0100"``), wildcard (``"01*"``), range (``"0100:0700"``),
        or negation (``"~0700"``). If ``None``, all transactions that have
        targets in ``sut.balancing_targets`` are balanced.
    categories : str, list of str, or None
        Category codes identifying which columns to balance. Same pattern
        syntax as ``transactions``. Combined with ``transactions`` via AND
        logic: a (transaction, category) combination is included if its
        transaction matches ``transactions`` AND its category matches
        ``categories``. If ``None``, all categories from the targets for
        the selected transactions are included.
    adjust_products : str, list of str, or None
        Product codes whose rows may be scaled. Same pattern syntax as
        ``transactions``. Rows for products not matched are treated as
        fixed. Locking still applies — a matched product that is also
        locked is treated as fixed. If ``None``, all products in the
        balancing member are candidates (locks still apply).

    Returns
    -------
    SUT
        New SUT with updated supply and use DataFrames for the balancing
        member. All other collection members are unchanged. The original
        SUT is not modified.

    Raises
    ------
    ValueError
        If ``sut.metadata``, ``sut.balancing_id``, or
        ``sut.balancing_targets`` is ``None``.
    ValueError
        If the (transaction, category) filter matches no rows in either
        supply or use for the balancing member.
    ValueError
        If any matched (transaction, category) combination has no target.
    ValueError
        If any (transaction, category) group has adjustable rows summing to
        zero in the target price column but a non-zero deficit to the target.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call balance_columns. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.balancing_id is None:
        raise ValueError(
            "sut.balancing_id is not set. Call set_balancing_id first to "
            "designate which collection member to balance."
        )
    if sut.balancing_targets is None:
        raise ValueError(
            "sut.balancing_targets is not set. Call set_balancing_targets "
            "first to provide column targets."
        )

    cols = sut.metadata.columns
    id_col = cols.id
    trans_col = cols.transaction
    cat_col = cols.category
    prod_col = cols.product
    balancing_id = sut.balancing_id
    locks = sut.balancing_config.locks if sut.balancing_config is not None else None

    # Extract rows and targets for the balancing member.
    member_supply = sut.supply[sut.supply[id_col] == balancing_id]
    member_use = sut.use[sut.use[id_col] == balancing_id]
    supply_targets = sut.balancing_targets.supply[
        sut.balancing_targets.supply[id_col] == balancing_id
    ]
    use_targets = sut.balancing_targets.use[
        sut.balancing_targets.use[id_col] == balancing_id
    ]

    # Resolve transactions: if None, use all transactions that have a non-NaN
    # target value. If patterns are given, match against data transaction codes.
    if transactions is None:
        supply_with_target = supply_targets[supply_targets[cols.price_basic].notna()]
        use_with_target = use_targets[use_targets[cols.price_purchasers].notna()]
        trans_set = set(
            supply_with_target[trans_col].tolist() + use_with_target[trans_col].tolist()
        )
    else:
        if isinstance(transactions, str):
            transactions = [transactions]
        all_data_trans = sorted(set(
            member_supply[trans_col].tolist() + member_use[trans_col].tolist()
        ))
        trans_set = set(_match_codes(all_data_trans, transactions))

    # Resolve categories: if None, use all categories from target rows that have
    # a non-NaN target value, for the selected transactions.
    if categories is None:
        supply_with_target = supply_targets[supply_targets[cols.price_basic].notna()]
        use_with_target = use_targets[use_targets[cols.price_purchasers].notna()]
        target_trans_cat = pd.concat([
            supply_with_target[[trans_col, cat_col]],
            use_with_target[[trans_col, cat_col]],
        ])
        cat_set = set(
            target_trans_cat[target_trans_cat[trans_col].isin(trans_set)][cat_col].tolist()
        )
    else:
        if isinstance(categories, str):
            categories = [categories]
        all_data_cats = sorted(set(
            member_supply[cat_col].tolist() + member_use[cat_col].tolist()
        ))
        cat_set = set(_match_codes(all_data_cats, categories))

    # Resolve adjust_products: if None, all products in the balancing member
    # are candidates (locks still applied inside _balance_table).
    if adjust_products is None:
        adjust_products_list = sorted(set(
            member_supply[prod_col].tolist() + member_use[prod_col].tolist()
        ))
    else:
        if isinstance(adjust_products, str):
            adjust_products = [adjust_products]
        all_data_products = sorted(set(
            member_supply[prod_col].tolist() + member_use[prod_col].tolist()
        ))
        adjust_products_list = _match_codes(all_data_products, adjust_products)

    # Filter data to the resolved (transaction, category) combinations.
    member_supply_filtered = member_supply[
        member_supply[trans_col].isin(trans_set) & member_supply[cat_col].isin(cat_set)
    ]
    member_use_filtered = member_use[
        member_use[trans_col].isin(trans_set) & member_use[cat_col].isin(cat_set)
    ]

    if member_supply_filtered.empty and member_use_filtered.empty:
        available_pairs = pd.concat([
            member_supply[[trans_col, cat_col]],
            member_use[[trans_col, cat_col]],
        ]).drop_duplicates()
        available_str = ", ".join(
            f"({row[trans_col]!r}, {row[cat_col]!r})"
            for _, row in available_pairs.iterrows()
        )
        raise ValueError(
            f"The transactions and categories filter matched no rows for "
            f"balancing_id={balancing_id!r}. "
            f"Available (transaction, category) combinations: {available_str}."
        )

    use_price_cols = _get_use_price_columns(sut.use, cols)

    # Balance supply rows (scale factor computed and applied to basic prices only).
    if not member_supply_filtered.empty:
        balanced_supply_rows = _balance_table(
            member_df=member_supply_filtered,
            targets_df=supply_targets,
            locks=locks,
            adjust_products=adjust_products_list,
            cols=cols,
            target_price_col=cols.price_basic,
            scale_price_cols=[cols.price_basic],
        )
    else:
        balanced_supply_rows = member_supply_filtered

    # Balance use rows (scale factor from purchasers' prices, applied to all price columns).
    if not member_use_filtered.empty:
        balanced_use_rows = _balance_table(
            member_df=member_use_filtered,
            targets_df=use_targets,
            locks=locks,
            adjust_products=adjust_products_list,
            cols=cols,
            target_price_col=cols.price_purchasers,
            scale_price_cols=use_price_cols,
        )
    else:
        balanced_use_rows = member_use_filtered

    # Write updated price columns back into full-collection copies.
    new_supply = sut.supply.copy()
    new_supply.loc[balanced_supply_rows.index, cols.price_basic] = (
        balanced_supply_rows[cols.price_basic]
    )

    new_use = sut.use.copy()
    new_use.loc[balanced_use_rows.index, use_price_cols] = (
        balanced_use_rows[use_price_cols]
    )

    return replace(sut, supply=new_supply, use=new_use)


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
