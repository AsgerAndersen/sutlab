"""
remove_locked_cells: remove locked rows from supply and use tables.
"""

from __future__ import annotations

from dataclasses import replace

from sutlab.sut import SUT
from sutlab.balancing._shared import _evaluate_locks


def remove_locked_cells(sut: SUT) -> SUT:
    """Return a new SUT with locked rows removed from supply and use.

    Uses the lock specification in ``sut.balancing_config.locks`` to identify
    locked rows (same OR logic as the balancing functions: products,
    transactions, categories, and cells levels). Locked rows are dropped from
    both ``supply`` and ``use``; all other fields — including
    ``balancing_targets`` — are left intact.

    ``price_layers`` locks (which restrict column scaling rather than rows)
    are ignored by this function.

    Parameters
    ----------
    sut : SUT
        The SUT to filter. Must have ``metadata``, ``balancing_config``, and
        ``balancing_config.locks`` set.

    Returns
    -------
    SUT
        New SUT with locked rows removed. The original is not modified.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.balancing_config`` is ``None``.
    ValueError
        If ``sut.balancing_config.locks`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError("sut.metadata is None — cannot evaluate locks without column metadata.")
    if sut.balancing_config is None:
        raise ValueError("sut.balancing_config is None — no lock specification available.")
    if sut.balancing_config.locks is None:
        raise ValueError("sut.balancing_config.locks is None — no lock specification available.")

    cols = sut.metadata.columns
    locks = sut.balancing_config.locks

    supply_locked = _evaluate_locks(sut.supply, locks, cols)
    use_locked = _evaluate_locks(sut.use, locks, cols)

    new_supply = sut.supply[~supply_locked].reset_index(drop=True)
    new_use = sut.use[~use_locked].reset_index(drop=True)

    return replace(sut, supply=new_supply, use=new_use)
