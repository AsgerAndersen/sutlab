"""
Computation functions for supply and use tables.
"""

from __future__ import annotations

import dataclasses

import pandas as pd

from sutlab.sut import SUT


# Default denominator specification for Danish SUT price layers.
#
# Maps each price layer role to the roles whose column values are summed to
# form the denominator when computing the rate for that layer. The rate
# expresses the proportional price increase at that step in the price chain:
#
#   rate = layer_value / denominator
#
# Price chain sequence:
#   basic → wholesale_margins → retail_margins
#        → product_taxes_less_subsidies → vat
#
# NOTE: Only covers price layers present in Danish national accounts data.
# Non-Danish data with different price layer structures will need
# metadata-specified denominators (not yet implemented). The structure of
# this dict is intentional: it is the natural place to plug in a
# metadata-driven override once that is implemented.
_DEFAULT_DENOMINATORS: dict[str, list[str]] = {
    "wholesale_margins": [
        "price_basic",
    ],
    "retail_margins": [
        "price_basic",
        "wholesale_margins",
    ],
    "product_taxes_less_subsidies": [
        "price_basic",
        "wholesale_margins",
        "retail_margins",
    ],
    "vat": [
        "price_basic",
        "wholesale_margins",
        "retail_margins",
        "product_taxes_less_subsidies",
    ],
}

# All optional price layer roles defined on SUTColumns.
# Used to detect mapped columns that have no default denominator specification.
_ALL_LAYER_ROLES: list[str] = [
    "trade_margins",
    "wholesale_margins",
    "retail_margins",
    "transport_margins",
    "product_taxes",
    "product_subsidies",
    "product_taxes_less_subsidies",
    "vat",
]


def compute_price_layer_rates(
    sut: SUT,
    aggregation_level: str | list[str],
) -> pd.DataFrame:
    """Compute price layer rates at the given aggregation level.

    Each rate expresses how much a price layer grows the cumulative price
    at the step where it is added. The denominator for each layer is the
    sum of basic prices plus all preceding layers in the chain, as
    specified in ``_DEFAULT_DENOMINATORS``.

    Use :func:`~sutlab.sut.get_rows` to filter the SUT to specific products,
    years, or transactions before calling this function.

    Parameters
    ----------
    sut : SUT
        The SUT collection to compute rates for. Only ``sut.use`` is read.
    aggregation_level : str or list of str
        One or more column role names (as defined on ``SUTColumns``) that
        together specify the grouping dimensions. The ``id`` column is always
        included automatically.

        Examples:

        - ``"product"`` — one row per ``(id, product)``.
        - ``["product", "transaction"]`` — one row per
          ``(id, product, transaction)``.
        - ``["transaction", "category"]`` — one row per
          ``(id, transaction, category)``, useful for industry-level rates
          when the data has been pre-filtered to P2 transactions and the
          selected industries.

        A plain string is treated as a single-element list.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame. The ``id`` column comes first, followed by the
        resolved groupby columns in the order given, then one column per price
        layer present in the data. Column names match the actual column names
        from ``sut.use`` (i.e. from ``sut.metadata.columns``). Values are
        dimensionless rates; division by zero yields ``NaN``. Returns an empty
        DataFrame if no price layer columns are present in the data.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If any role in ``aggregation_level`` is not a valid ``SUTColumns``
        attribute or maps to ``None``.
    ValueError
        If any mapped price layer column has no default denominator
        specification. This indicates a non-Danish price layer structure
        that requires metadata-specified denominators (not yet implemented).

    Examples
    --------
    Compute product-by-transaction VAT rates and flag any exceeding 25 %:

    >>> rates = compute_price_layer_rates(sut, ["product", "transaction"])
    >>> vat_col = sut.metadata.columns.vat
    >>> high_vat = rates[rates[vat_col] > 0.25]
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call compute_price_layer_rates. "
            "Provide a SUTMetadata with column name mappings."
        )

    cols = sut.metadata.columns

    # Normalise string shorthand to list.
    if isinstance(aggregation_level, str):
        roles = [aggregation_level]
    else:
        roles = list(aggregation_level)

    # Validate each role: must be a known SUTColumns attribute with a non-None value.
    valid_roles = [
        attr for attr in vars(cols.__class__).keys()
        if not attr.startswith("_")
    ]
    # Use the instance attributes (dataclass fields) instead.
    valid_role_names = [f.name for f in dataclasses.fields(cols)]
    for role in roles:
        if role not in valid_role_names:
            raise ValueError(
                f"aggregation_level contains unknown role {role!r}. "
                f"Valid roles: {valid_role_names}."
            )
        if getattr(cols, role) is None:
            raise ValueError(
                f"aggregation_level role {role!r} is not mapped in SUTColumns "
                f"(its value is None)."
            )

    # Guard against mapped layer columns with no default denominator.
    # These indicate a non-Danish price layer structure not yet supported.
    # Raising an error here prevents silently computing incorrect rates.
    for role in _ALL_LAYER_ROLES:
        col_name = getattr(cols, role)
        if col_name is None:
            continue
        if col_name not in sut.use.columns:
            continue
        if role not in _DEFAULT_DENOMINATORS:
            raise ValueError(
                f"Price layer '{role}' (column '{col_name}') is present in the data "
                f"but has no default denominator specification. "
                f"Available defaults: {list(_DEFAULT_DENOMINATORS.keys())}. "
                f"Non-Danish price layer structures require metadata-specified "
                f"denominators, which are not yet implemented."
            )

    # Collect layers that are both in _DEFAULT_DENOMINATORS, mapped in
    # SUTColumns, and present as columns in sut.use. Preserves dict order,
    # which matches the price chain sequence.
    present_layers: list[tuple[str, str]] = []
    for role in _DEFAULT_DENOMINATORS:
        col_name = getattr(cols, role)
        if col_name is None:
            continue
        if col_name not in sut.use.columns:
            continue
        present_layers.append((role, col_name))

    if not present_layers:
        return pd.DataFrame()

    # Build groupby keys: id first, then the resolved role columns in order.
    id_col = cols.id
    group_keys = [id_col] + [getattr(cols, role) for role in roles]

    # Single groupby: sum basic price and all layer columns at once.
    layer_col_names = [col_name for _, col_name in present_layers]
    agg_cols = [cols.price_basic] + layer_col_names
    aggregated = (
        sut.use
        .groupby(group_keys, as_index=False, dropna=False)[agg_cols]
        .sum()
    )

    # Build role → actual column name mapping for resolving denominators.
    # Includes price_basic and all present layers.
    role_to_col: dict[str, str] = {"price_basic": cols.price_basic}
    for role, col_name in present_layers:
        role_to_col[role] = col_name

    # Compute one rate column per layer.
    # For each layer, sum the denominator columns and divide the layer into it.
    # Denominator roles that are not present in the data are skipped — the
    # denominator is built from whatever is available in the chain up to that point.
    # Division by zero yields NaN.
    result = aggregated[group_keys].copy()
    for role, col_name in present_layers:
        denom_roles = _DEFAULT_DENOMINATORS[role]
        denom_cols = [role_to_col[r] for r in denom_roles if r in role_to_col]
        denom = aggregated[denom_cols].sum(axis=1)
        safe_denom = denom.where(denom != 0, other=float("nan"))
        result[col_name] = aggregated[col_name] / safe_denom

    return result.sort_values(group_keys).reset_index(drop=True)


def compute_totals(
    sut: SUT,
    dimensions: str | list[str],
) -> pd.DataFrame:
    """Compute summed totals over one or more dimensions.

    Stacks supply and use in combined format and sums all price columns
    within each group formed by ``id`` and the requested dimensions.
    Supply rows carry ``NaN`` for price layer and purchasers' price columns.
    Groups where all values for a column are ``NaN`` (e.g. supply-only
    groups for price layer columns) remain ``NaN`` in the result.

    Parameters
    ----------
    sut : SUT
        The SUT collection to aggregate.
    dimensions : str or list of str
        One or more column role names (as defined on ``SUTColumns``) that
        specify which dimensions to **keep** in the result. The ``id``
        column is always kept automatically. All other key dimensions
        (product, transaction, category — whichever are not listed) are
        summed over.

        Examples:

        - ``"product"`` — one row per ``(id, product)``.
        - ``["transaction", "category"]`` — one row per
          ``(id, transaction, category)``.

        A plain string is treated as a single-element list.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame. The ``id`` column comes first, followed by
        the resolved groupby columns in the order given, then one column
        per price column present in the data: basic prices, price layers
        (in the order they appear in ``SUTColumns``), and purchasers'
        prices. Rows are sorted by the groupby columns.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If any role in ``dimensions`` is not a valid ``SUTColumns``
        attribute or maps to ``None``.

    Examples
    --------
    Aggregate over all products to get transaction-level totals:

    >>> totals = compute_totals(sut, ["transaction", "category"])

    Aggregate over transactions and categories to get product totals:

    >>> totals = compute_totals(sut, "product")
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call compute_totals. "
            "Provide a SUTMetadata with column name mappings."
        )

    cols = sut.metadata.columns

    # Normalise string shorthand to list.
    if isinstance(dimensions, str):
        roles = [dimensions]
    else:
        roles = list(dimensions)

    # Validate each role: must be a known SUTColumns attribute with a non-None value.
    valid_role_names = [f.name for f in dataclasses.fields(cols)]
    resolved_dims = []
    for role in roles:
        if role not in valid_role_names:
            raise ValueError(
                f"dimensions contains unknown role {role!r}. "
                f"Valid roles: {valid_role_names}."
            )
        col_name = getattr(cols, role)
        if col_name is None:
            raise ValueError(
                f"dimensions role {role!r} is not mapped in SUTColumns "
                f"(its value is None)."
            )
        resolved_dims.append(col_name)

    id_col = cols.id
    group_keys = [id_col] + resolved_dims

    # Collect price columns: price_basic, then mapped and present layer columns
    # (in _ALL_LAYER_ROLES order), then price_purchasers.
    layer_cols = [
        getattr(cols, role)
        for role in _ALL_LAYER_ROLES
        if getattr(cols, role) is not None
        and getattr(cols, role) in sut.use.columns
    ]
    all_price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    # Stack supply and use in combined format.
    # reindex selects only the needed columns, filling missing ones with NaN.
    # Supply rows will have NaN for price layer and purchasers' price columns.
    all_cols = group_keys + all_price_cols
    supply_stacked = sut.supply.reindex(columns=all_cols)
    use_stacked = sut.use.reindex(columns=all_cols)
    stacked = pd.concat([supply_stacked, use_stacked], ignore_index=True)

    # Group by id and the requested dimensions; sum all price columns.
    # NaN values are treated as zero by default (skipna=True).
    # groupby sorts by group keys by default (sort=True).
    result = (
        stacked
        .groupby(group_keys, as_index=False, dropna=False)[all_price_cols]
        .sum(min_count=1)
    )

    return result
