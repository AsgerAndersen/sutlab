"""
Computation functions for supply and use tables.
"""

from __future__ import annotations

from typing import Literal

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
    aggregation_level: Literal["product", "transaction", "category"],
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
    aggregation_level : {"product", "transaction", "category"}
        Level at which to aggregate before computing rates.

        - ``"product"``: one row per ``(product, id)``.
        - ``"transaction"``: one row per ``(product, transaction, id)``.
        - ``"category"``: one row per ``(product, transaction, category, id)``.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame. Groupby key columns come first, followed by
        one column per price layer present in the data. Column names match
        the actual column names from ``sut.use`` (i.e. from
        ``sut.metadata.columns``). Values are dimensionless rates; division
        by zero yields ``NaN``. Returns an empty DataFrame if no price layer
        columns are present in the data.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``aggregation_level`` is not one of the accepted values.
    ValueError
        If any mapped price layer column has no default denominator
        specification. This indicates a non-Danish price layer structure
        that requires metadata-specified denominators (not yet implemented).

    Examples
    --------
    Compute transaction-level VAT rates and flag any exceeding 25 %:

    >>> rates = compute_price_layer_rates(sut, "transaction")
    >>> vat_col = sut.metadata.columns.vat
    >>> high_vat = rates[rates[vat_col] > 0.25]
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call compute_price_layer_rates. "
            "Provide a SUTMetadata with column name mappings."
        )

    if aggregation_level not in ("product", "transaction", "category"):
        raise ValueError(
            f"aggregation_level must be 'product', 'transaction', or 'category'. "
            f"Got: {aggregation_level!r}"
        )

    cols = sut.metadata.columns

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

    # Determine groupby keys based on aggregation level.
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category

    if aggregation_level == "product":
        group_keys = [id_col, prod_col]
    elif aggregation_level == "transaction":
        group_keys = [id_col, prod_col, trans_col]
    else:  # "category"
        group_keys = [id_col, prod_col, trans_col, cat_col]

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
