# sutlab/adjust/_substitute.py — adjust_substitute_sut

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import BalancingTargets, SUT


def _substitute_long_tables(
    base_df: pd.DataFrame,
    values_df: pd.DataFrame,
    key_cols: list[str],
) -> pd.DataFrame:
    """Substitute rows from ``values_df`` into ``base_df``.

    For rows with matching ``key_cols``, all price column values from
    ``values_df`` replace those from ``base_df`` — including NaN (NaN in
    ``values_df`` means "set to NaN", not "leave unchanged"). Rows present
    only in ``values_df`` are appended. Rows present only in ``base_df``
    are carried through unchanged.

    Parameters
    ----------
    base_df : DataFrame
        The DataFrame being substituted into.
    values_df : DataFrame
        The DataFrame whose values replace matching rows.
    key_cols : list of str
        Columns that together uniquely identify a row.

    Returns
    -------
    DataFrame
        Combined DataFrame. Column order follows ``base_df``; extra columns
        present only in ``values_df`` are appended at the end.
    """
    key_set = set(key_cols)
    base_price_cols = [c for c in base_df.columns if c not in key_set]
    values_price_cols = [c for c in values_df.columns if c not in key_set]

    shared_price_cols = set(base_price_cols) & set(values_price_cols)
    only_base_price_cols = [c for c in base_price_cols if c not in shared_price_cols]
    only_values_price_cols = [c for c in values_price_cols if c not in shared_price_cols]

    merged = base_df.merge(
        values_df,
        on=key_cols,
        how="outer",
        suffixes=("_base", "_values"),
        indicator=True,
    )

    is_left_only = merged["_merge"] == "left_only"

    result = merged[key_cols].copy()

    # Shared columns: use values_df value for matching and right_only rows;
    # keep base value for left_only rows.
    for col in base_price_cols:
        if col in shared_price_cols:
            result[col] = merged[f"{col}_values"].where(~is_left_only, merged[f"{col}_base"])
        else:
            result[col] = merged[col]

    # Columns only in values_df: NaN for left_only rows (base had no value),
    # values_df value for all others. The outer merge already produces this.
    for col in only_values_price_cols:
        result[col] = merged[col]

    return result


def adjust_substitute_sut(sut: SUT, adjustments: SUT) -> SUT:
    """Return a new SUT with rows from ``adjustments`` substituted into ``sut``.

    For rows with matching keys (id, product, transaction, category) all price
    column values from ``adjustments`` replace those in ``sut`` — including NaN
    (NaN in ``adjustments`` means "set to NaN", not "leave unchanged"). Rows in
    ``adjustments`` with no matching key in ``sut`` are appended as new rows.
    Rows in ``sut`` with no matching key in ``adjustments`` are unchanged.

    Both supply and use DataFrames are processed. If ``adjustments`` carries
    balancing targets, they are substituted into ``sut``'s balancing targets
    with the same semantics. All other fields — metadata, balancing_id,
    balancing_config — are taken from ``sut``.

    Parameters
    ----------
    sut : SUT
        The SUT collection to substitute into. Must have ``metadata`` set.
    adjustments : SUT
        The SUT whose rows replace matching rows in ``sut``. Metadata is
        optional; if present and ``sut`` also has metadata, their
        ``SUTColumns`` must match.

    Returns
    -------
    SUT
        New SUT with updated supply and use DataFrames. The original SUT is
        not modified.

    Raises
    ------
    TypeError
        If ``sut`` or ``adjustments`` is not a ``SUT`` instance.
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.price_basis`` and ``adjustments.price_basis`` differ.
    ValueError
        If both ``sut`` and ``adjustments`` have metadata but their
        ``SUTColumns`` differ.
    """
    if not isinstance(sut, SUT):
        raise TypeError(
            f"sut must be a SUT instance, got {type(sut).__name__}."
        )
    if not isinstance(adjustments, SUT):
        raise TypeError(
            f"adjustments must be a SUT instance, got {type(adjustments).__name__}."
        )

    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call adjust_substitute_sut. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.price_basis != adjustments.price_basis:
        raise ValueError(
            f"Cannot substitute SUTs with different price bases: "
            f"sut.price_basis={sut.price_basis!r}, "
            f"adjustments.price_basis={adjustments.price_basis!r}."
        )
    if adjustments.metadata is not None:
        if sut.metadata.columns != adjustments.metadata.columns:
            raise ValueError(
                "Cannot substitute SUTs with different SUTColumns. "
                "Both SUTs must use the same column name mappings."
            )

    cols = sut.metadata.columns
    key_cols = [cols.id, cols.product, cols.transaction, cols.category]
    target_key_cols = [cols.id, cols.transaction, cols.category]

    new_supply = _substitute_long_tables(sut.supply, adjustments.supply, key_cols)
    new_use = _substitute_long_tables(sut.use, adjustments.use, key_cols)

    if adjustments.balancing_targets is not None:
        if sut.balancing_targets is None:
            new_targets = adjustments.balancing_targets
        else:
            new_targets = BalancingTargets(
                supply=_substitute_long_tables(
                    sut.balancing_targets.supply,
                    adjustments.balancing_targets.supply,
                    target_key_cols,
                ),
                use=_substitute_long_tables(
                    sut.balancing_targets.use,
                    adjustments.balancing_targets.use,
                    target_key_cols,
                ),
            )
    else:
        new_targets = sut.balancing_targets

    return replace(
        sut,
        supply=new_supply,
        use=new_use,
        balancing_targets=new_targets,
    )
