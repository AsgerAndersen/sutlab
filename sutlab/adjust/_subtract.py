# sutlab/adjust/_subtract.py — adjust_subtract_sut

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import BalancingTargets, SUT
from sutlab.adjust._add import _add_long_tables


def _negate_price_columns(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    price_cols = [c for c in df.columns if c not in set(key_cols)]
    result = df.copy()
    result[price_cols] = -result[price_cols]
    return result


def adjust_subtract_sut(sut: SUT, adjustments: SUT) -> SUT:
    """Return a new SUT with the values from ``adjustments`` subtracted from ``sut``.

    For rows with matching keys (id, product, transaction, category) the price
    column values in ``adjustments`` are subtracted from those in ``sut``. NaN is
    treated as 0 — subtracting NaN from a value leaves the value unchanged;
    NaN − NaN stays NaN. Rows in ``adjustments`` with no matching key in ``sut``
    are appended as negated values (i.e. 0 − adjustment).

    Both supply and use DataFrames are processed. If ``adjustments`` carries
    balancing targets, they are subtracted from ``sut``'s balancing targets with
    the same semantics. All other fields — metadata, balancing_id,
    balancing_config — are taken from ``sut``.

    Parameters
    ----------
    sut : SUT
        The SUT collection to subtract from. Must have ``metadata`` set.
    adjustments : SUT
        The SUT whose values are subtracted from ``sut``. Metadata is optional;
        if present and ``sut`` also has metadata, their ``SUTColumns`` must match.

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
            "sut.metadata is required to call adjust_subtract_sut. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.price_basis != adjustments.price_basis:
        raise ValueError(
            f"Cannot subtract SUTs with different price bases: "
            f"sut.price_basis={sut.price_basis!r}, "
            f"adjustments.price_basis={adjustments.price_basis!r}."
        )
    if adjustments.metadata is not None:
        if sut.metadata.columns != adjustments.metadata.columns:
            raise ValueError(
                "Cannot subtract SUTs with different SUTColumns. "
                "Both SUTs must use the same column name mappings."
            )

    cols = sut.metadata.columns
    key_cols = [cols.id, cols.product, cols.transaction, cols.category]
    target_key_cols = [cols.id, cols.transaction, cols.category]

    neg_supply = _negate_price_columns(adjustments.supply, key_cols)
    neg_use = _negate_price_columns(adjustments.use, key_cols)

    new_supply = _add_long_tables(sut.supply, neg_supply, key_cols)
    new_use = _add_long_tables(sut.use, neg_use, key_cols)

    if adjustments.balancing_targets is not None:
        neg_supply_targets = _negate_price_columns(
            adjustments.balancing_targets.supply, target_key_cols
        )
        neg_use_targets = _negate_price_columns(
            adjustments.balancing_targets.use, target_key_cols
        )
        if sut.balancing_targets is None:
            new_targets = BalancingTargets(
                supply=neg_supply_targets,
                use=neg_use_targets,
            )
        else:
            new_targets = BalancingTargets(
                supply=_add_long_tables(
                    sut.balancing_targets.supply, neg_supply_targets, target_key_cols
                ),
                use=_add_long_tables(
                    sut.balancing_targets.use, neg_use_targets, target_key_cols
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
