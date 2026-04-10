# sutlab/adjust/_add.py — adjust_add_sut

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import BalancingTargets, SUT


def _add_long_tables(
    base_df: pd.DataFrame,
    values_df: pd.DataFrame,
    key_cols: list[str],
) -> pd.DataFrame:
    """Add two long-format DataFrames by summing matching rows and appending new ones.

    For rows with matching ``key_cols``, price columns are summed. NaN in a
    price column is treated as 0 — adding NaN to a value leaves the value
    unchanged — but NaN + NaN remains NaN (i.e. if both DataFrames have no
    value for a cell, the result also has no value).

    For rows present only in one DataFrame those rows are carried through
    unchanged (the absent DataFrame contributes zero for all price columns).

    Parameters
    ----------
    base_df : DataFrame
        The DataFrame being added to.
    values_df : DataFrame
        The DataFrame whose values are added.
    key_cols : list of str
        Columns that together uniquely identify a row. Used as groupby keys.

    Returns
    -------
    DataFrame
        Combined DataFrame with one row per unique key combination.
        Column order follows ``base_df``; any extra columns present only in
        ``values_df`` are appended at the end.
    """
    combined = pd.concat([base_df, values_df], ignore_index=True)
    price_cols = [c for c in combined.columns if c not in set(key_cols)]
    result = (
        combined
        .groupby(key_cols, dropna=False)[price_cols]
        .sum(min_count=1)
        .reset_index()
    )
    return result


def adjust_add_sut(sut: SUT, adjustments: SUT) -> SUT:
    """Return a new SUT with the values from ``adjustments`` added to ``sut``.

    For rows with matching keys (id, product, transaction, category) the price
    column values are summed. NaN is treated as 0 — adding NaN to a value
    leaves the value unchanged; NaN + NaN stays NaN. Rows in ``adjustments``
    with no matching key in ``sut`` are appended as new rows.

    Both supply and use DataFrames are processed. If ``adjustments`` carries
    balancing targets, they are added to ``sut``'s balancing targets with the
    same semantics (numerical addition on matching keys, append on new keys,
    NaN = 0). All other fields — metadata, balancing_id, balancing_config —
    are taken from ``sut``.

    A typical use case is applying a batch of benchmark revision adjustments:
    ``adjustments`` holds the adjustment amounts and ``sut`` holds the current
    estimates.

    Parameters
    ----------
    sut : SUT
        The SUT collection to add to. Must have ``metadata`` set.
    adjustments : SUT
        The SUT whose values are added to ``sut``. Metadata is optional;
        if present and ``sut`` also has metadata, their ``SUTColumns`` must
        match.

    Returns
    -------
    SUT
        New SUT with updated supply and use DataFrames. The original SUT is
        not modified.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.price_basis`` and ``adjustments.price_basis`` differ.
    ValueError
        If both ``sut`` and ``adjustments`` have metadata but their
        ``SUTColumns`` differ.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call adjust_add_sut. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.price_basis != adjustments.price_basis:
        raise ValueError(
            f"Cannot add SUTs with different price bases: "
            f"sut.price_basis={sut.price_basis!r}, "
            f"adjustments.price_basis={adjustments.price_basis!r}."
        )
    if adjustments.metadata is not None:
        if sut.metadata.columns != adjustments.metadata.columns:
            raise ValueError(
                "Cannot add SUTs with different SUTColumns. "
                "Both SUTs must use the same column name mappings."
            )

    cols = sut.metadata.columns
    key_cols = [cols.id, cols.product, cols.transaction, cols.category]
    target_key_cols = [cols.id, cols.transaction, cols.category]

    new_supply = _add_long_tables(sut.supply, adjustments.supply, key_cols)
    new_use = _add_long_tables(sut.use, adjustments.use, key_cols)

    # Add balancing targets if adjustments carries them.
    if adjustments.balancing_targets is not None:
        if sut.balancing_targets is None:
            new_targets = adjustments.balancing_targets
        else:
            new_supply_targets = _add_long_tables(
                sut.balancing_targets.supply,
                adjustments.balancing_targets.supply,
                target_key_cols,
            )
            new_use_targets = _add_long_tables(
                sut.balancing_targets.use,
                adjustments.balancing_targets.use,
                target_key_cols,
            )
            new_targets = BalancingTargets(
                supply=new_supply_targets,
                use=new_use_targets,
            )
    else:
        new_targets = sut.balancing_targets

    return replace(
        sut,
        supply=new_supply,
        use=new_use,
        balancing_targets=new_targets,
    )
