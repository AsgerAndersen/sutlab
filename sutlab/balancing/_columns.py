"""
balance_columns: scale product rows to hit per-column targets.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, Locks, SUTColumns, _match_codes
from sutlab.balancing._shared import _evaluate_locks, _get_use_price_columns


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
        supports the same pattern syntax as :func:`~sutlab.sut.filter_rows`:
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
