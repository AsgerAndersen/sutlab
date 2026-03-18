"""
Core data structures for supply and use tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    A supply and use table for a single year and price basis.

    Parameters
    ----------
    year : int
        The reference year of the table (the year whose transactions are
        recorded).
    price_basis : {"current_year", "previous_year"}
        The price basis used for valuation. ``"current_year"`` means values
        are in the prices of ``year`` itself. ``"previous_year"`` means values
        are revalued at the prices of ``year - 1``, as used for volume
        calculations.
    supply : DataFrame
        Supply table in long format. Columns: product, transaction, category,
        and the basic-prices column specified in ``metadata.columns.prices``.
        Supply is valued at basic prices only — price layers are a use-side
        concept.
    use : DataFrame
        Use table in long format. Columns: product, transaction, category,
        and all price columns specified in ``metadata.columns.prices`` (basic,
        layers, purchasers).
    metadata : SUTMetadata or None
        Column specifications and optional classification tables. Required by
        functions that need to look up labels or validate codes. If ``None``,
        only functions that operate purely on the data arrays can be used.
    """

    year: int
    price_basis: Literal["current_year", "previous_year"]
    supply: pd.DataFrame
    use: pd.DataFrame
    metadata: SUTMetadata | None = None
