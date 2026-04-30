# sutlab/aggregate/_transactions.py — aggregate_classification_transactions

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, SUTClassifications, BalancingTargets
from sutlab.aggregate._shared import (
    _aggregate_long_table,
    _build_classification,
    _update_classification_names,
    _validate_from_in_classification,
    _validate_full_coverage,
    _validate_mapping,
    _validate_no_passthrough_collision,
    _validate_transactions_metadata_columns,
)


def aggregate_classification_transactions(
    sut: SUT,
    mapping: pd.DataFrame,
    *,
    metadata: pd.DataFrame | None = None,
    full_coverage: bool = True,
    classification_name: str | None = None,
) -> SUT:
    """Return a new SUT with transactions aggregated according to ``mapping``.

    Maps transaction codes in supply, use, and balancing targets from
    ``mapping['from']`` to ``mapping['to']``, then sums all price columns
    within each resulting group. Many-to-one mappings aggregate multiple
    transactions into one; one-to-one mappings rename.

    The transactions classification is rebuilt from ``metadata``. All rows are
    in scope — no ESA filtering. ``balancing_config`` is cleared.
    ``balancing_targets`` is aggregated with the same mapping.
    ``balancing_id`` is preserved.

    Parameters
    ----------
    sut : SUT
        The SUT collection to aggregate. Must have ``metadata`` set.
    mapping : DataFrame
        Two-column DataFrame with ``'from'`` (original transaction codes) and
        ``'to'`` (aggregated transaction codes). Many-to-one is allowed;
        ``'from'`` must not contain duplicates or NaN.
    metadata : DataFrame or None, optional
        New transactions classification table. Required columns: transaction
        column name (e.g. ``'trans'``), ``'table'``, ``'esa_code'``.
        Optional column: ``'{trans_col}_txt'``. When ``full_coverage=True``
        this replaces the existing classification entirely. When
        ``full_coverage=False`` it is merged with existing rows for unmapped
        pass-through codes. ``None`` clears the classification.
    full_coverage : bool, default True
        If ``True``, every transaction code in supply, use, and (if present)
        balancing targets must appear in ``mapping['from']``; raises if any
        code is missing. If ``False``, codes absent from ``mapping['from']``
        pass through unchanged.
    classification_name : str or None, default None
        New classification system name for the transaction dimension. Has no
        effect if ``classification_names`` is absent or has no row for the
        transaction dimension.

    Returns
    -------
    SUT
        New SUT with aggregated supply, use, and balancing targets.
        ``balancing_config`` is set to ``None``. ``balancing_id`` and
        ``price_basis`` are preserved.

    Raises
    ------
    TypeError
        If ``sut`` is not a ``SUT`` instance or ``mapping`` is not a DataFrame.
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``mapping`` is missing ``'from'`` or ``'to'`` columns, or either
        contains NaN.
    ValueError
        If ``mapping['from']`` contains duplicate values.
    ValueError
        If ``full_coverage=True`` and any transaction code in the data is
        absent from ``mapping['from']``.
    ValueError
        If the SUT already has a transactions classification and any code in
        ``mapping['from']`` is absent from it.
    ValueError
        If ``metadata`` is provided and is missing required columns
        (transaction column, ``'table'``, ``'esa_code'``).
    ValueError
        If ``full_coverage=False`` and any ``mapping['to']`` value is also
        a pass-through (unmapped) transaction code in the data.
    """
    if not isinstance(sut, SUT):
        raise TypeError(f"sut must be a SUT instance, got {type(sut).__name__}.")
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call aggregate_classification_transactions. "
            "Provide a SUTMetadata with column name mappings."
        )

    cols = sut.metadata.columns
    trans_col = cols.transaction

    _validate_mapping(mapping)

    dfs_for_validation = [sut.supply, sut.use]
    if sut.balancing_targets is not None:
        dfs_for_validation.extend([
            sut.balancing_targets.supply,
            sut.balancing_targets.use,
        ])

    if full_coverage:
        _validate_full_coverage(mapping, dfs_for_validation, trans_col)

    old_cls = sut.metadata.classifications
    if old_cls is not None and old_cls.transactions is not None:
        _validate_from_in_classification(
            mapping, old_cls.transactions, trans_col, "transactions"
        )

    if metadata is not None:
        _validate_transactions_metadata_columns(metadata, trans_col)

    if not full_coverage:
        _validate_no_passthrough_collision(mapping, dfs_for_validation, trans_col)

    key_cols = [cols.id, cols.product, trans_col, cols.category]
    new_supply = _aggregate_long_table(sut.supply, mapping, key_cols, trans_col)
    new_use = _aggregate_long_table(sut.use, mapping, key_cols, trans_col)

    new_targets: BalancingTargets | None = None
    if sut.balancing_targets is not None:
        tgt_key_cols = [cols.id, trans_col, cols.category]
        new_tgt_supply = _aggregate_long_table(
            sut.balancing_targets.supply, mapping, tgt_key_cols, trans_col
        )
        new_tgt_use = _aggregate_long_table(
            sut.balancing_targets.use, mapping, tgt_key_cols, trans_col
        )
        new_targets = replace(
            sut.balancing_targets, supply=new_tgt_supply, use=new_tgt_use
        )

    old_trans_cls = old_cls.transactions if old_cls is not None else None
    new_trans_cls = _build_classification(
        old_trans_cls, mapping, metadata, full_coverage, trans_col
    )

    if old_cls is None:
        new_cls: SUTClassifications | None = (
            SUTClassifications(transactions=new_trans_cls)
            if new_trans_cls is not None
            else None
        )
    else:
        new_cls_names = _update_classification_names(
            old_cls.classification_names, trans_col, classification_name
        )
        new_cls = replace(
            old_cls,
            transactions=new_trans_cls,
            classification_names=new_cls_names,
        )

    new_metadata = replace(sut.metadata, classifications=new_cls)

    return replace(
        sut,
        supply=new_supply,
        use=new_use,
        metadata=new_metadata,
        balancing_targets=new_targets,
        balancing_config=None,
    )
