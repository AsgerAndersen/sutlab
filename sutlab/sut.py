"""
Core data structures for supply and use tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

import pandas as pd


@dataclass
class PriceSpec:
    """
    Column names for the price values in a use table.

    Parameters
    ----------
    basic : str
        Column name for values at basic prices (e.g. ``'bas'``).
    purchasers : str
        Column name for values at purchasers' prices (e.g. ``'koeb'``).
    layers : list of str
        Ordered list of intermediate price-layer column names — wholesale
        margins, retail margins, taxes, VAT, etc. (e.g.
        ``['eng', 'det', 'afg', 'moms']``). May be empty if only basic and
        purchasers' prices are available.
    """

    basic: str
    purchasers: str
    layers: list[str] = field(default_factory=list)


@dataclass
class SUTColumns:
    """
    Mapping from conceptual dimensions to actual column names in the DataFrames.

    The DataFrames in a :class:`SUT` keep whatever column names they were
    loaded with. This dataclass tells the library which column holds which
    piece of information.

    Parameters
    ----------
    id : str
        Column name for the identifier that distinguishes individual SUTs
        within the collection (e.g. ``'year'`` or ``'quarter'``).
    product : str
        Column name for the product dimension (e.g. ``'nrnr'``).
    transaction : str
        Column name for the transaction code (e.g. ``'trans'``).
    category : str
        Column name for the second dimension of the SUT matrix — identifies
        the industry (for production and intermediate use), the consumption
        function (for final demand), or similar. Empty for imports, exports,
        and investment rows (e.g. ``'brch'``).
    prices : PriceSpec
        Column names for all price-value columns.
    """

    id: str
    product: str
    transaction: str
    category: str
    prices: PriceSpec


@dataclass
class SUTMetadata:
    """
    Column specifications and optional classification tables for a SUT.

    All classification tables are optional. Functions that require a specific
    table will raise an informative error if it is not supplied.

    Parameters
    ----------
    columns : SUTColumns
        Mapping from conceptual dimensions to actual column names.
    products : DataFrame or None
        Classification table for products: code and label columns.
    transactions : DataFrame or None
        Classification table for transaction codes: code and label columns.
    industries : DataFrame or None
        Classification table for industries: code and label columns.
    individual_consumption : DataFrame or None
        Classification table for individual consumption functions (e.g.
        NCP76): code and label columns.
    collective_consumption : DataFrame or None
        Classification table for collective consumption functions (e.g.
        NCO10): code and label columns.
    """

    columns: SUTColumns
    products: pd.DataFrame | None = None
    transactions: pd.DataFrame | None = None
    industries: pd.DataFrame | None = None
    individual_consumption: pd.DataFrame | None = None
    collective_consumption: pd.DataFrame | None = None


@dataclass
class SUT:
    """
    A collection of supply and use tables sharing the same structure and metadata.

    The collection typically holds a time series (e.g. one SUT per year), but
    the id dimension is not required to be temporal. Supply and use are stored
    as long-format DataFrames containing all members of the collection; each
    row belongs to one member identified by the id column
    (``metadata.columns.id``).

    One member of the collection can be designated as the active balancing
    target via :func:`set_active`. Balancing functions operate on that member
    only; inspection functions span the full collection.

    Parameters
    ----------
    price_basis : {"current_year", "previous_year"}
        The price basis used for valuation across the whole collection.
        ``"current_year"`` means values are in the prices of the reference
        year itself. ``"previous_year"`` means values are revalued at the
        prices of the preceding year, as used for volume calculations.
    supply : DataFrame
        Supply table in long format. Contains an id column, product,
        transaction, category, and the basic-prices column specified in
        ``metadata.columns.prices``. Supply is valued at basic prices only —
        price layers are a use-side concept. Columns should be ordered: id,
        product, transaction, category, then price columns. This is not
        enforced but recommended for readability.
    use : DataFrame
        Use table in long format. Contains an id column, product, transaction,
        category, and all price columns specified in
        ``metadata.columns.prices`` (basic, layers, purchasers). Columns
        should be ordered: id, product, transaction, category, then price
        columns. This is not enforced but recommended for readability.
    balancing_id : str, int, or None
        The id value of the member currently being balanced. Set via
        :func:`set_active`. ``None`` if no member is designated as active.
    metadata : SUTMetadata or None
        Column specifications and optional classification tables. Required by
        functions that need to look up labels or validate codes. If ``None``,
        only functions that operate purely on the data arrays can be used.
    """

    price_basis: Literal["current_year", "previous_year"]
    supply: pd.DataFrame
    use: pd.DataFrame
    balancing_id: str | int | None = None
    metadata: SUTMetadata | None = None


def set_active(sut: SUT, balancing_id: str | int) -> SUT:
    """
    Return a new SUT with the given id set as the active balancing target.

    The original SUT is not modified. Balancing functions will operate only
    on rows where the id column matches ``balancing_id``; inspection functions
    span the full collection.

    Parameters
    ----------
    sut : SUT
        The SUT collection to update.
    balancing_id : str or int
        The id value to mark as the active balancing target. Must exist in
        the supply table's id column.

    Returns
    -------
    SUT
        A new SUT with ``balancing_id`` set. The underlying data is shared
        with the original (not copied).

    Raises
    ------
    ValueError
        If ``sut.metadata`` is None — it is needed to identify the id column.
    ValueError
        If ``balancing_id`` is not found in the supply table.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call set_active. "
            "Provide a SUTMetadata with a SUTColumns.id column name."
        )

    id_col = sut.metadata.columns.id
    available_ids = sorted(sut.supply[id_col].unique())

    if balancing_id not in available_ids:
        available_str = ", ".join(str(x) for x in available_ids)
        raise ValueError(
            f"ID '{balancing_id}' not found in supply table. "
            f"Available IDs: {available_str}"
        )

    return replace(sut, balancing_id=balancing_id)
