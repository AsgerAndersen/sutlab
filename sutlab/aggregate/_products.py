# sutlab/aggregate/_products.py — aggregate_classification_products

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, SUTClassifications
from sutlab.aggregate._shared import (
    _aggregate_long_table,
    _build_classification,
    _update_classification_names,
    _validate_from_in_classification,
    _validate_full_coverage,
    _validate_mapping,
    _validate_metadata_columns_simple,
    _validate_no_passthrough_collision,
)


def _remap_margin_products(
    margin_products: pd.DataFrame,
    mapping: pd.DataFrame,
    product_col: str,
) -> pd.DataFrame | None:
    txt_col = f"{product_col}_txt"
    has_txt = txt_col in margin_products.columns
    margin_codes = set(margin_products[product_col])

    new_rows = []
    for to_code, group in mapping.groupby("to"):
        from_codes = set(group["from"])
        margin_subset = from_codes & margin_codes
        non_margin_subset = from_codes - margin_codes

        if margin_subset and non_margin_subset:
            raise ValueError(
                f"Cannot aggregate into product '{to_code}': some source products "
                f"are margin products ({sorted(margin_subset)}) and some are not "
                f"({sorted(non_margin_subset)}). Keep margin and non-margin "
                f"products in separate mappings."
            )

        if not margin_subset:
            continue

        layers = (
            margin_products
            .loc[margin_products[product_col].isin(margin_subset), "price_layer"]
            .unique()
            .tolist()
        )
        if len(layers) > 1:
            raise ValueError(
                f"Cannot aggregate into product '{to_code}': source margin "
                f"products map to different price layers: {sorted(layers)}. "
                f"Only margin products with the same price_layer can be aggregated."
            )

        row: dict = {product_col: to_code, "price_layer": layers[0]}
        if has_txt:
            row[txt_col] = None
        new_rows.append(row)

    passthrough = margin_products[
        ~margin_products[product_col].isin(set(mapping["from"]))
    ]

    if new_rows:
        aggregated = pd.DataFrame(new_rows)
        result = pd.concat([aggregated, passthrough], ignore_index=True)
    else:
        result = passthrough.copy().reset_index(drop=True)

    if len(result) == 0:
        return None

    col_order = [product_col] + ([txt_col] if has_txt else []) + ["price_layer"]
    return result[col_order]


def aggregate_classification_products(
    sut: SUT,
    mapping: pd.DataFrame,
    *,
    metadata: pd.DataFrame | None = None,
    full_coverage: bool = True,
    classification_name: str | None = None,
) -> SUT:
    """Return a new SUT with products aggregated according to ``mapping``.

    Maps product codes in supply and use from ``mapping['from']`` to
    ``mapping['to']``, then sums all price columns within each resulting
    (id, product, transaction, category) group. Many-to-one mappings
    aggregate multiple products into one; one-to-one mappings rename.

    The products classification is rebuilt from ``metadata`` and, when
    ``full_coverage=False``, rows for unmapped pass-through codes from the
    existing classification. ``balancing_config`` is cleared — re-attach
    after aggregation if needed. ``balancing_targets`` is preserved unchanged
    (targets have no product dimension). ``balancing_id`` is preserved.

    Parameters
    ----------
    sut : SUT
        The SUT collection to aggregate. Must have ``metadata`` set.
    mapping : DataFrame
        Two-column DataFrame with ``'from'`` (original product codes) and
        ``'to'`` (aggregated product codes). Many-to-one is allowed;
        ``'from'`` must not contain duplicates or NaN.
    metadata : DataFrame or None, optional
        New products classification table. Columns must be the actual product
        column name (e.g. ``'nrnr'``) and optionally that name with a
        ``'_txt'`` suffix. When ``full_coverage=True`` this replaces the
        existing products classification entirely. When ``full_coverage=False``
        it is merged with existing rows for unmapped pass-through codes.
        ``None`` clears the products classification.
    full_coverage : bool, default True
        If ``True``, every product code in supply and use must appear in
        ``mapping['from']``; raises if any code is missing. If ``False``,
        codes absent from ``mapping['from']`` pass through unchanged.
    classification_name : str or None, default None
        New classification system name for the product dimension. Replaces
        the matching row in ``classification_names`` (e.g. ``'NRNR07'`` →
        ``'AGG2'``). ``None`` sets the entry to NaN. Has no effect if
        ``classification_names`` is absent or has no row for the product
        dimension.

    Returns
    -------
    SUT
        New SUT with aggregated supply and use and updated metadata.
        ``balancing_config`` is set to ``None``. ``balancing_targets``,
        ``balancing_id``, and ``price_basis`` are preserved.

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
        If ``full_coverage=True`` and any product code in the data is absent
        from ``mapping['from']``.
    ValueError
        If the SUT already has a products classification and any code in
        ``mapping['from']`` is absent from it.
    ValueError
        If ``metadata`` has incorrect columns.
    ValueError
        If ``full_coverage=False`` and any ``mapping['to']`` value is also
        a pass-through (unmapped) product code in the data.
    ValueError
        If ``margin_products`` contains codes that would aggregate a mix of
        margin and non-margin products, or margin products with inconsistent
        price layers, into the same ``'to'`` code.
    """
    if not isinstance(sut, SUT):
        raise TypeError(f"sut must be a SUT instance, got {type(sut).__name__}.")
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call aggregate_classification_products. "
            "Provide a SUTMetadata with column name mappings."
        )

    cols = sut.metadata.columns
    product_col = cols.product

    _validate_mapping(mapping)

    if full_coverage:
        _validate_full_coverage(mapping, [sut.supply, sut.use], product_col)

    old_cls = sut.metadata.classifications
    if old_cls is not None and old_cls.products is not None:
        _validate_from_in_classification(mapping, old_cls.products, product_col, "products")

    if metadata is not None:
        _validate_metadata_columns_simple(metadata, product_col)

    if not full_coverage:
        _validate_no_passthrough_collision(mapping, [sut.supply, sut.use], product_col)

    key_cols = [cols.id, product_col, cols.transaction, cols.category]
    new_supply = _aggregate_long_table(sut.supply, mapping, key_cols, product_col)
    new_use = _aggregate_long_table(sut.use, mapping, key_cols, product_col)

    new_products_cls = _build_classification(
        old_cls.products if old_cls is not None else None,
        mapping,
        metadata,
        full_coverage,
        product_col,
    )

    if old_cls is None:
        new_cls: SUTClassifications | None = (
            SUTClassifications(products=new_products_cls)
            if new_products_cls is not None
            else None
        )
    else:
        new_margin_products = (
            _remap_margin_products(old_cls.margin_products, mapping, product_col)
            if old_cls.margin_products is not None
            else None
        )
        new_cls_names = _update_classification_names(
            old_cls.classification_names, product_col, classification_name
        )
        new_cls = replace(
            old_cls,
            products=new_products_cls,
            classification_names=new_cls_names,
            margin_products=new_margin_products,
        )

    new_metadata = replace(sut.metadata, classifications=new_cls)

    return replace(
        sut,
        supply=new_supply,
        use=new_use,
        metadata=new_metadata,
        balancing_config=None,
    )
