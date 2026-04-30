# sutlab/aggregate/_individual_consumption.py — aggregate_classification_individual_consumption

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, SUTClassifications, BalancingTargets
from sutlab.aggregate._shared import (
    _aggregate_with_esa_filter,
    _build_classification,
    _get_matching_trans,
    _require_transactions_classification,
    _update_classification_names,
    _validate_from_in_classification,
    _validate_full_coverage,
    _validate_mapping,
    _validate_metadata_columns_simple,
    _validate_no_passthrough_collision,
)

_ESA_CODES = ["P31"]


def aggregate_classification_individual_consumption(
    sut: SUT,
    mapping: pd.DataFrame,
    *,
    metadata: pd.DataFrame | None = None,
    full_coverage: bool = True,
    classification_name: str | None = None,
) -> SUT:
    """Return a new SUT with individual consumption codes aggregated according to ``mapping``.

    Maps category codes on individual consumption (P31) rows from
    ``mapping['from']`` to ``mapping['to']``, then sums all price columns
    within each resulting group. Only rows whose transaction has ESA code P31
    are affected; all other rows pass through unchanged.

    ``balancing_config`` is cleared. ``balancing_targets`` is aggregated with
    the same mapping on the same ESA-filtered rows. ``balancing_id`` is
    preserved.

    Parameters
    ----------
    sut : SUT
        The SUT collection to aggregate. Must have ``metadata`` set with a
        transactions classification including an ``esa_code`` column.
    mapping : DataFrame
        Two-column DataFrame with ``'from'`` (original individual consumption
        codes) and ``'to'`` (aggregated codes). Many-to-one is allowed;
        ``'from'`` must not contain duplicates or NaN.
    metadata : DataFrame or None, optional
        New individual consumption classification table. Columns must be the
        actual category column name (e.g. ``'brch'``) and optionally that name
        with a ``'_txt'`` suffix. When ``full_coverage=True`` this replaces the
        existing classification entirely. When ``full_coverage=False`` it is
        merged with existing rows for unmapped pass-through codes.
        ``None`` clears the classification.
    full_coverage : bool, default True
        If ``True``, every individual consumption code (category code on P31
        rows) in supply, use, and (if present) balancing targets must appear
        in ``mapping['from']``; raises if any code is missing.
    classification_name : str or None, default None
        New classification system name for the category dimension. Has no
        effect if ``classification_names`` is absent or has no row for the
        category dimension.

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
        If ``sut.metadata.classifications.transactions`` is ``None``
        (required for ESA-based row filtering).
    ValueError
        If ``mapping`` is missing ``'from'`` or ``'to'`` columns, or either
        contains NaN.
    ValueError
        If ``mapping['from']`` contains duplicate values.
    ValueError
        If ``full_coverage=True`` and any individual consumption code in the
        data is absent from ``mapping['from']``.
    ValueError
        If the SUT already has an individual consumption classification and any
        code in ``mapping['from']`` is absent from it.
    ValueError
        If ``metadata`` has incorrect columns.
    ValueError
        If ``full_coverage=False`` and any ``mapping['to']`` value is also
        a pass-through (unmapped) code in the data.
    """
    if not isinstance(sut, SUT):
        raise TypeError(f"sut must be a SUT instance, got {type(sut).__name__}.")
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call "
            "aggregate_classification_individual_consumption. "
            "Provide a SUTMetadata with column name mappings."
        )
    _require_transactions_classification(
        sut, "aggregate_classification_individual_consumption"
    )

    cols = sut.metadata.columns
    cat_col = cols.category
    trans_col = cols.transaction
    trans_cls = sut.metadata.classifications.transactions
    matching_trans = _get_matching_trans(trans_cls, trans_col, _ESA_CODES)

    _validate_mapping(mapping)

    esa_supply = sut.supply[sut.supply[trans_col].isin(matching_trans)]
    esa_use = sut.use[sut.use[trans_col].isin(matching_trans)]
    dfs_for_validation = [esa_supply, esa_use]
    if sut.balancing_targets is not None:
        dfs_for_validation.append(
            sut.balancing_targets.supply[
                sut.balancing_targets.supply[trans_col].isin(matching_trans)
            ]
        )
        dfs_for_validation.append(
            sut.balancing_targets.use[
                sut.balancing_targets.use[trans_col].isin(matching_trans)
            ]
        )

    if full_coverage:
        _validate_full_coverage(mapping, dfs_for_validation, cat_col)

    old_cls = sut.metadata.classifications
    if old_cls is not None and old_cls.individual_consumption is not None:
        _validate_from_in_classification(
            mapping, old_cls.individual_consumption, cat_col, "individual_consumption"
        )

    if metadata is not None:
        _validate_metadata_columns_simple(metadata, cat_col)

    if not full_coverage:
        _validate_no_passthrough_collision(mapping, dfs_for_validation, cat_col)

    key_cols = [cols.id, cols.product, trans_col, cat_col]
    new_supply = _aggregate_with_esa_filter(
        sut.supply, mapping, key_cols, cat_col, trans_col, matching_trans
    )
    new_use = _aggregate_with_esa_filter(
        sut.use, mapping, key_cols, cat_col, trans_col, matching_trans
    )

    new_targets: BalancingTargets | None = None
    if sut.balancing_targets is not None:
        tgt_key_cols = [cols.id, trans_col, cat_col]
        new_tgt_supply = _aggregate_with_esa_filter(
            sut.balancing_targets.supply,
            mapping,
            tgt_key_cols,
            cat_col,
            trans_col,
            matching_trans,
        )
        new_tgt_use = _aggregate_with_esa_filter(
            sut.balancing_targets.use,
            mapping,
            tgt_key_cols,
            cat_col,
            trans_col,
            matching_trans,
        )
        new_targets = replace(
            sut.balancing_targets, supply=new_tgt_supply, use=new_tgt_use
        )

    old_ind_cls = (
        old_cls.individual_consumption if old_cls is not None else None
    )
    new_ind_cls = _build_classification(
        old_ind_cls, mapping, metadata, full_coverage, cat_col
    )

    if old_cls is None:
        new_cls: SUTClassifications | None = (
            SUTClassifications(individual_consumption=new_ind_cls)
            if new_ind_cls is not None
            else None
        )
    else:
        new_cls_names = _update_classification_names(
            old_cls.classification_names, cat_col, classification_name
        )
        new_cls = replace(
            old_cls,
            individual_consumption=new_ind_cls,
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
