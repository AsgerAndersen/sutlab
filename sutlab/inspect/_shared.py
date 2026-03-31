"""
Shared helpers used by multiple inspect modules.
"""

from __future__ import annotations

import pandas as pd


def _sort_by_id_value(
    df: pd.DataFrame,
    group_levels: list[str],
    sort_id,
) -> pd.DataFrame:
    """Sort non-total rows within groups by sort_id column value, descending.

    Within each group (defined by ``group_levels``), rows where
    ``transaction == ""`` are treated as total/summary rows and kept at the
    end. All other rows are sorted by the value in the ``sort_id`` column,
    largest first. Row order between groups is preserved.

    Parameters
    ----------
    df : pd.DataFrame
        Wide-format inspection table with a MultiIndex containing a
        ``"transaction"`` level and id values as columns.
    group_levels : list of str
        Index level names defining the groups within which rows are sorted.
        Use ``["product"]`` for product detail tables,
        ``["industry"]`` for industry detail tables, and
        ``["product", "price_layer"]`` for price layer tables.
    sort_id : hashable
        Column name (id value, e.g. ``2021``) to sort by.

    Returns
    -------
    pd.DataFrame
        Same DataFrame with rows reordered within each group.
    """
    if df.empty:
        return df

    trans_vals = df.index.get_level_values("transaction")
    total_mask = trans_vals == ""

    level_arrays = {level: df.index.get_level_values(level) for level in group_levels}
    group_tuples = list(dict.fromkeys(
        zip(*[level_arrays[level] for level in group_levels])
    ))

    blocks = []
    for group_key in group_tuples:
        group_mask = level_arrays[group_levels[0]] == group_key[0]
        for level, key in zip(group_levels[1:], group_key[1:]):
            group_mask = group_mask & (level_arrays[level] == key)

        data_rows = df[group_mask & ~total_mask]
        total_rows = df[group_mask & total_mask]

        sorted_data = data_rows.sort_values(by=sort_id, ascending=False)
        blocks.append(pd.concat([sorted_data, total_rows]))

    return pd.concat(blocks)
