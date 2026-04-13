"""
filter_free_cells: remove locked rows from supply and use tables.
"""

from __future__ import annotations

from dataclasses import replace

from sutlab.sut import SUT
from sutlab.balancing._shared import _evaluate_locks


def filter_free_cells(sut: SUT, *, table: str | None = None) -> SUT:
    """Return a new SUT with locked rows removed from supply and/or use.

    Uses the lock specification in ``sut.balancing_config.locks`` to identify
    locked rows (same OR logic as the balancing functions: products,
    transactions, categories, and cells levels). Locked rows are dropped from
    the selected table(s); all other fields — including
    ``balancing_targets`` — are left intact.

    ``price_layers`` locks (which restrict column scaling rather than rows)
    are ignored by this function.

    Parameters
    ----------
    sut : SUT
        The SUT to filter. Must have ``metadata``, ``balancing_config``, and
        ``balancing_config.locks`` set.
    table : str or None, optional
        Which table to filter. ``"supply"`` filters only ``sut.supply``;
        ``"use"`` filters only ``sut.use``; ``None`` (default) filters both.

    Returns
    -------
    SUT
        New SUT with locked rows removed from the selected table(s). The
        original is not modified.

    Raises
    ------
    ValueError
        If ``table`` is not ``None``, ``"supply"``, or ``"use"``.
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.balancing_config`` is ``None``.
    ValueError
        If ``sut.balancing_config.locks`` is ``None``.
    """
    if table is not None and table not in ("supply", "use"):
        raise ValueError(
            f"table must be 'supply', 'use', or None. Got: {repr(table)}"
        )
    if sut.metadata is None:
        raise ValueError("sut.metadata is None — cannot evaluate locks without column metadata.")
    if sut.balancing_config is None:
        raise ValueError("sut.balancing_config is None — no lock specification available.")
    if sut.balancing_config.locks is None:
        raise ValueError("sut.balancing_config.locks is None — no lock specification available.")

    cols = sut.metadata.columns
    locks = sut.balancing_config.locks

    if table == "supply":
        supply_locked = _evaluate_locks(sut.supply, locks, cols)
        new_supply = sut.supply[~supply_locked].reset_index(drop=True)
        new_use = sut.use
    elif table == "use":
        use_locked = _evaluate_locks(sut.use, locks, cols)
        new_supply = sut.supply
        new_use = sut.use[~use_locked].reset_index(drop=True)
    else:
        supply_locked = _evaluate_locks(sut.supply, locks, cols)
        use_locked = _evaluate_locks(sut.use, locks, cols)
        new_supply = sut.supply[~supply_locked].reset_index(drop=True)
        new_use = sut.use[~use_locked].reset_index(drop=True)

    return replace(sut, supply=new_supply, use=new_use)
