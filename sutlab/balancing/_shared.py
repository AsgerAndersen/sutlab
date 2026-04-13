"""
Shared helpers used across balancing functions.
"""

from __future__ import annotations

import pandas as pd

from sutlab.sut import Locks, SUTColumns


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
        lock_df = locks.categories[[cols.transaction, cols.category]].drop_duplicates()
        matched = df[[cols.transaction, cols.category]].merge(lock_df, how="left", indicator=True)
        locked |= (matched["_merge"] == "both").to_numpy()

    if locks.cells is not None:
        lock_df = locks.cells[[cols.product, cols.transaction, cols.category]].drop_duplicates()
        matched = df[[cols.product, cols.transaction, cols.category]].merge(lock_df, how="left", indicator=True)
        locked |= (matched["_merge"] == "both").to_numpy()

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
