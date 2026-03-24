"""
Core data structures for supply and use tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable, Literal

import pandas as pd


@dataclass
class SUTColumns:
    """
    Mapping from conceptual roles to actual column names in the DataFrames.

    The DataFrames in a :class:`SUT` keep whatever column names they were
    loaded with. This dataclass tells the library which column holds which
    piece of information.

    Each field holds the actual column name string (e.g. ``'nrnr'``) for
    that conceptual role, or ``None`` if that price layer is not present in
    the data. Required roles have no default; optional roles default to
    ``None``.

    This dataclass is typically loaded from a two-column Excel table with
    columns ``column`` (the actual column name) and ``role`` (the conceptual
    role from the fixed list below) via the I/O module.

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
    price_basic : str
        Column name for values at basic prices (e.g. ``'bas'``).
    price_purchasers : str
        Column name for values at purchasers' prices (e.g. ``'koeb'``).
        Purchasers' prices equal basic prices plus all price layers.
    trade_margins : str or None
        Column name for total trade margins, when not decomposed into
        wholesale and retail (e.g. ``'mar'``).
    wholesale_margins : str or None
        Column name for wholesale trade margins (e.g. ``'eng'``).
    retail_margins : str or None
        Column name for retail trade margins (e.g. ``'det'``).
    transport_margins : str or None
        Column name for transport margins, if present.
    product_taxes : str or None
        Column name for taxes on products excluding VAT (e.g. ``'afg'``).
    product_subsidies : str or None
        Column name for subsidies on products, if recorded separately.
    product_taxes_less_subsidies : str or None
        Column name for taxes less subsidies on products, if recorded net
        rather than split into taxes and subsidies.
    vat : str or None
        Column name for VAT (e.g. ``'moms'``).
    """

    id: str
    product: str
    transaction: str
    category: str
    price_basic: str
    price_purchasers: str
    trade_margins: str | None = None
    wholesale_margins: str | None = None
    retail_margins: str | None = None
    transport_margins: str | None = None
    product_taxes: str | None = None
    product_subsidies: str | None = None
    product_taxes_less_subsidies: str | None = None
    vat: str | None = None


@dataclass
class SUTClassifications:
    """
    Classification tables for the dimensions of a SUT.

    All fields are optional. Functions that require a specific table will
    raise an informative error if it is not supplied.

    Parameters
    ----------
    classification_names : DataFrame or None
        Maps each dimension name to its classification system
        (e.g. products → ``'NRNR07'``, industries → ``'NBR117A3'``).
        Corresponds to the ``classifications`` sheet in the Excel metadata
        file.
    products : DataFrame or None
        Classification table for products: ``code`` and ``name`` columns.
    transactions : DataFrame or None
        Classification table for transaction codes: ``code``, ``name``, and
        ``table`` columns. ``table`` must be ``"supply"`` or ``"use"`` for
        every row and is validated when loading from Excel. Used to split
        combined long-format SUT data into separate supply and use tables.
    industries : DataFrame or None
        Classification table for industries: ``code`` and ``name`` columns.
    individual_consumption : DataFrame or None
        Classification table for individual consumption functions
        (e.g. NCP76): ``code`` and ``name`` columns.
    collective_consumption : DataFrame or None
        Classification table for collective consumption functions
        (e.g. NCO10): ``code`` and ``name`` columns.
    """

    classification_names: pd.DataFrame | None = None
    products: pd.DataFrame | None = None
    transactions: pd.DataFrame | None = None
    industries: pd.DataFrame | None = None
    individual_consumption: pd.DataFrame | None = None
    collective_consumption: pd.DataFrame | None = None


@dataclass
class SUTMetadata:
    """
    Column specifications and optional classification tables for a SUT.

    Parameters
    ----------
    columns : SUTColumns
        Mapping from conceptual roles to actual column names.
    classifications : SUTClassifications or None
        Classification tables for products, transactions, industries, and
        consumption functions. ``None`` if no classifications are supplied.
        Functions that require a specific table will raise an informative
        error if it is absent.
    """

    columns: SUTColumns
    classifications: SUTClassifications | None = None


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
    target via :func:`set_balancing_id`. Balancing functions operate on that member
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
        ``metadata.columns.price_basic``. Supply is valued at basic prices
        only — price layers are a use-side concept. Columns should be
        ordered: id, product, transaction, category, then price columns.
        This is not enforced but recommended for readability.
    use : DataFrame
        Use table in long format. Contains an id column, product, transaction,
        category, and all price columns specified in ``metadata.columns``
        (basic, price layers, purchasers). Columns should be ordered: id,
        product, transaction, category, then price columns. This is not
        enforced but recommended for readability.
    balancing_id : str, int, or None
        The id value of the member currently being balanced. Set via
        :func:`mark_for_balancing`. ``None`` if no member is designated as active.
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


def set_balancing_id(sut: SUT, balancing_id: str | int) -> SUT:
    """
    Return a new SUT with ``balancing_id`` set to the given id value.

    The original SUT is not modified. Balancing functions will operate only
    on rows where the id column matches ``balancing_id``; inspection functions
    span the full collection.

    Parameters
    ----------
    sut : SUT
        The SUT collection to update.
    balancing_id : str or int
        The id value to set as the active balancing target. Must exist in
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
            "sut.metadata is required to call mark_for_balancing. "
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


# ---------------------------------------------------------------------------
# Product selection helpers
# ---------------------------------------------------------------------------


def _natural_sort_key(s: str) -> list:
    """Split a string into alternating text and integer parts for natural ordering.

    This makes embedded digit runs compare numerically rather than
    lexically, so ``"V9100" < "V10100"`` (9 < 10) rather than
    ``"V9100" > "V10100"`` ("9" > "1").

    Examples
    --------
    >>> _natural_sort_key("V9100")
    ['V', 9100, '']
    >>> _natural_sort_key("V10100")
    ['V', 10100, '']
    """
    parts = re.split(r"(\d+)", s)
    return [int(p) if p.isdigit() else p for p in parts]


def _code_matches_pattern(code: str, pattern: str) -> bool:
    """Return True if code matches a single positive pattern (exact, wildcard, or range)."""
    if "*" in pattern:
        return code.startswith(pattern.rstrip("*"))
    elif ":" in pattern:
        lo, hi = pattern.split(":", 1)
        return _natural_sort_key(lo) <= _natural_sort_key(code) <= _natural_sort_key(hi)
    else:
        return code == pattern


def _match_codes(codes: list[str], patterns: list[str]) -> list[str]:
    """Return the subset of codes that match the given patterns.

    Each pattern is one of:

    - **Exact**: plain string, matched by equality.
    - **Wildcard**: contains ``*``, matched by the prefix before the ``*``.
    - **Range**: contains ``:``, matched if the code falls between the two
      bounds (inclusive) using natural sort order.
    - **Negation**: starts with ``~``, followed by any of the above. Codes
      matching a negation pattern are excluded from the result.

    Negation is applied after positive matching. If only negation patterns
    are given, the starting set is all codes.

    Each code appears at most once in the result. Order follows the order
    of codes in the input.

    Parameters
    ----------
    codes : list of str
        The candidate codes to test (typically the unique codes present in
        the data).
    patterns : list of str
        One or more patterns as described above.

    Returns
    -------
    list of str
        Codes from ``codes`` that survive both the positive and negative passes.
    """
    positive_patterns = [p for p in patterns if not p.startswith("~")]
    negative_patterns = [p[1:] for p in patterns if p.startswith("~")]

    # Positive pass: match any positive pattern.
    # If there are no positive patterns but there are negation patterns,
    # start from all codes (negation-only means "everything except ...").
    # If patterns is empty, return nothing.
    if positive_patterns:
        candidates = [
            code for code in codes
            if any(_code_matches_pattern(code, p) for p in positive_patterns)
        ]
    elif negative_patterns:
        candidates = list(codes)
    else:
        return []

    # Negative pass: remove codes matching any negation pattern
    if negative_patterns:
        excluded = {
            code for code in candidates
            if any(_code_matches_pattern(code, p) for p in negative_patterns)
        }
        candidates = [code for code in candidates if code not in excluded]

    return candidates


def _filter_sut_by_column(sut: SUT, column_name: str, patterns: str | list[str]) -> SUT:
    """Filter supply and use to rows where column_name matches any pattern.

    Caller is responsible for metadata validation. NaN values in the column
    are silently excluded (they match no pattern).
    """
    if isinstance(patterns, str):
        patterns = [patterns]

    supply_codes = sut.supply[column_name].dropna().unique().tolist()
    use_codes = sut.use[column_name].dropna().unique().tolist()
    all_unique_codes = list(set(supply_codes) | set(use_codes))

    matched_codes = _match_codes(all_unique_codes, patterns)

    filtered_supply = sut.supply[sut.supply[column_name].isin(matched_codes)]
    filtered_use = sut.use[sut.use[column_name].isin(matched_codes)]

    return replace(sut, supply=filtered_supply, use=filtered_use)


def _filter_sut_by_ids(sut: SUT, ids: str | int | Iterable[str | int]) -> SUT:
    """Filter supply and use to rows matching the given id values or patterns.

    Handles int/str type conversion so integer id columns (e.g. years) work
    alongside string patterns. Caller is responsible for metadata validation.
    """
    if isinstance(ids, (str, int)):
        ids = [ids]
    else:
        ids = list(ids)

    id_col = sut.metadata.columns.id

    ids_as_str = [str(v) for v in ids]
    supply_codes = [str(v) for v in sut.supply[id_col].unique()]
    use_codes = [str(v) for v in sut.use[id_col].unique()]
    all_unique_codes = list(set(supply_codes) | set(use_codes))

    matched_codes = _match_codes(all_unique_codes, ids_as_str)

    filtered_supply = sut.supply[sut.supply[id_col].astype(str).isin(matched_codes)]
    filtered_use = sut.use[sut.use[id_col].astype(str).isin(matched_codes)]

    return replace(sut, supply=filtered_supply, use=filtered_use)


def get_rows(
    sut: SUT,
    *,
    ids: str | int | Iterable[str | int] | None = None,
    products: str | list[str] | None = None,
    transactions: str | list[str] | None = None,
    categories: str | list[str] | None = None,
) -> SUT:
    """Return a new SUT containing only the rows matching the given criteria.

    All arguments except ``sut`` are optional, but at least one must be
    provided. Filters are applied with AND logic — each argument narrows the
    result further.

    Parameters
    ----------
    sut : SUT
        The SUT collection to filter.
    ids : str, int, iterable of str or int, or None
        Filter by collection member id. Accepts a single value, a list, or
        any iterable including ``range``. Each entry is one of:

        - **Exact value**: e.g. ``2019`` or ``"Q1"``.
        - **Wildcard**: contains ``*``, e.g. ``"201*"``.
        - **Range**: contains ``:``, e.g. ``"2015:2019"``
          (inclusive, natural sort order).
        - **Negation**: starts with ``~``, e.g. ``"~2019"`` excludes that id.

        ``range(2015, 2020)`` is equivalent to ``[2015, 2016, 2017, 2018, 2019]``.
    products : str, list of str, or None
        Filter by product code. Each entry is one of:

        - **Exact code**: e.g. ``"V10100"``.
        - **Wildcard**: contains ``*``, e.g. ``"V10*"``.
        - **Range**: contains ``:``, e.g. ``"V10100:V20300"``
          (inclusive, natural sort order).
        - **Negation**: starts with ``~``, e.g. ``"~V10*"`` excludes all V10
          codes. If only negation patterns are given, the starting set is all
          codes in the data.

    transactions : str, list of str, or None
        Filter by transaction code. Same pattern syntax as ``products``.

        Note: each transaction code belongs to either supply or use, not
        both. Filtering by a supply transaction code will produce an empty
        use table and vice versa.
    categories : str, list of str, or None
        Filter by category code. Same pattern syntax as ``products``.

        Rows with no category (imports, exports, investment) have a NaN
        category value and are excluded when filtering by category.

    Returns
    -------
    SUT
        A new SUT with ``supply`` and ``use`` filtered to matching rows.
        ``balancing_id`` is set to ``None`` — balancing a sub-SUT is not
        supported. ``price_basis`` and ``metadata`` are carried over
        unchanged. If no rows match, the result contains empty DataFrames.

    Raises
    ------
    ValueError
        If all of ``ids``, ``products``, ``transactions``, and ``categories``
        are ``None``.
    ValueError
        If ``sut.metadata`` is ``None`` — it is needed to identify the
        relevant columns.
    """
    if ids is None and products is None and transactions is None and categories is None:
        raise ValueError(
            "At least one of ids, products, transactions, or categories must be provided."
        )

    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_rows. "
            "Provide a SUTMetadata with column name mappings."
        )

    cols = sut.metadata.columns
    result = sut

    if ids is not None:
        result = _filter_sut_by_ids(result, ids)
    if products is not None:
        result = _filter_sut_by_column(result, cols.product, products)
    if transactions is not None:
        result = _filter_sut_by_column(result, cols.transaction, transactions)
    if categories is not None:
        result = _filter_sut_by_column(result, cols.category, categories)

    return replace(result, balancing_id=None)


# ---------------------------------------------------------------------------
# Code lookup functions
# ---------------------------------------------------------------------------


def _unique_column_values(sut: SUT, column_name: str) -> pd.DataFrame:
    """Return a sorted single-column DataFrame of unique non-null values from supply and use."""
    supply_vals = sut.supply[column_name].dropna().unique().tolist()
    use_vals = sut.use[column_name].dropna().unique().tolist()
    all_vals = list(set(supply_vals) | set(use_vals))
    return pd.DataFrame({column_name: all_vals}).sort_values(column_name).reset_index(drop=True)


def get_product_codes(sut: SUT) -> pd.DataFrame:
    """Return the unique product codes present in the data.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the product column in ``sut``,
        containing the unique product codes from supply and use combined,
        sorted in ascending order with a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_product_codes. "
            "Provide a SUTMetadata with column name mappings."
        )
    return _unique_column_values(sut, sut.metadata.columns.product)


def get_transaction_codes(sut: SUT) -> pd.DataFrame:
    """Return the unique transaction codes present in the data.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the transaction column in ``sut``,
        containing the unique transaction codes from supply and use combined,
        sorted in ascending order with a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_transaction_codes. "
            "Provide a SUTMetadata with column name mappings."
        )
    return _unique_column_values(sut, sut.metadata.columns.transaction)


def _category_codes_for_esa(sut: SUT, esa_codes: list[str]) -> pd.DataFrame:
    """Return sorted unique category codes from rows whose transaction maps to any of the given ESA codes."""
    trans_df = sut.metadata.classifications.transactions
    matching_trans = trans_df[trans_df["esa_code"].isin(esa_codes)]["code"].tolist()

    trans_col = sut.metadata.columns.transaction
    cat_col = sut.metadata.columns.category

    supply_cats = sut.supply[sut.supply[trans_col].isin(matching_trans)][cat_col].dropna().unique().tolist()
    use_cats = sut.use[sut.use[trans_col].isin(matching_trans)][cat_col].dropna().unique().tolist()
    all_cats = list(set(supply_cats) | set(use_cats))

    return pd.DataFrame({cat_col: all_cats}).sort_values(cat_col).reset_index(drop=True)


def _require_transaction_classifications(sut: SUT, function_name: str) -> None:
    """Raise ValueError if transaction classifications with esa_code are not available."""
    if sut.metadata is None:
        raise ValueError(
            f"sut.metadata is required to call {function_name}. "
            "Provide a SUTMetadata with column name mappings."
        )
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            f"sut.metadata.classifications.transactions is required to call {function_name}. "
            "Load a classifications file with a 'transactions' sheet including an 'esa_code' column."
        )


def get_industry_codes(sut: SUT) -> pd.DataFrame:
    """Return the unique industry codes present in the data.

    Industry codes are the category codes from output (P1) and intermediate
    consumption (P2) rows.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the category column in ``sut``,
        containing the unique industry codes, sorted in ascending order with
        a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.metadata.classifications.transactions``
        is ``None``.
    """
    _require_transaction_classifications(sut, "get_industry_codes")
    return _category_codes_for_esa(sut, ["P1", "P2"])


def get_individual_consumption_codes(sut: SUT) -> pd.DataFrame:
    """Return the unique individual consumption function codes present in the data.

    Individual consumption codes are the category codes from rows with ESA
    transaction P31 (Individual consumption expenditure).

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the category column in ``sut``,
        containing the unique individual consumption codes, sorted in
        ascending order with a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.metadata.classifications.transactions``
        is ``None``.
    """
    _require_transaction_classifications(sut, "get_individual_consumption_codes")
    return _category_codes_for_esa(sut, ["P31"])


def get_collective_consumption_codes(sut: SUT) -> pd.DataFrame:
    """Return the unique collective consumption function codes present in the data.

    Collective consumption codes are the category codes from rows with ESA
    transaction P32 (Collective consumption expenditure).

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the category column in ``sut``,
        containing the unique collective consumption codes, sorted in
        ascending order with a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.metadata.classifications.transactions``
        is ``None``.
    """
    _require_transaction_classifications(sut, "get_collective_consumption_codes")
    return _category_codes_for_esa(sut, ["P32"])


def get_ids(sut: SUT) -> pd.DataFrame:
    """Return the unique id values present in the data.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the id column in ``sut``,
        containing the unique id values from supply and use combined,
        sorted in ascending order with a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_ids. "
            "Provide a SUTMetadata with column name mappings."
        )
    return _unique_column_values(sut, sut.metadata.columns.id)
