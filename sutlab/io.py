"""
I/O functions for loading SUT data and metadata from files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_ROLES: set[str] = {
    "id", "product", "transaction", "category",
    "price_basic", "price_purchasers",
}

_OPTIONAL_ROLES: set[str] = {
    "trade_margins", "wholesale_margins", "retail_margins", "transport_margins",
    "product_taxes", "product_subsidies", "product_taxes_less_subsidies", "vat",
}

_ALL_KNOWN_ROLES: set[str] = _REQUIRED_ROLES | _OPTIONAL_ROLES

_VALID_TABLE_VALUES: set[str] = {"supply", "use"}

_VALID_ESA_CODES: set[str] = {"P1", "P2", "P3", "P31", "P32", "P51g", "P52", "P53", "P6", "P7"}

# Price layer role names in the order they should appear in the use DataFrame.
# Matches the field order of SUTColumns.
_PRICE_LAYER_ROLES: list[str] = [
    "trade_margins",
    "wholesale_margins",
    "retail_margins",
    "transport_margins",
    "product_taxes",
    "product_subsidies",
    "product_taxes_less_subsidies",
    "vat",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading and trailing whitespace from all string columns in df."""
    result = df.copy()
    for col in result.columns:
        if pd.api.types.is_string_dtype(result[col]):
            result[col] = result[col].str.strip()
    return result


def _validate_required_columns(
    df: pd.DataFrame,
    required: list[str],
    source: str,
) -> None:
    """Raise ValueError if any required columns are absent from df.

    Parameters
    ----------
    df : DataFrame
        The DataFrame to check.
    required : list of str
        Column names that must be present.
    source : str
        Human-readable description of where df came from, used in the error
        message (e.g. ``"'transactions' sheet"``).
    """
    missing = [col for col in required if col not in df.columns]
    if missing:
        missing_str = ", ".join(f"'{c}'" for c in missing)
        present_str = ", ".join(f"'{c}'" for c in df.columns)
        raise ValueError(
            f"{source} is missing required columns: {missing_str}. "
            f"Found: {present_str}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_metadata_columns_from_excel(path: str | Path) -> SUTColumns:
    """
    Load column role mappings from a two-column Excel file.

    The file must have a ``column`` column (actual DataFrame column names) and
    a ``role`` column (conceptual role from the fixed list). Leading and
    trailing whitespace is stripped from all values. All values are read as
    strings, so column names that look like integers (e.g. ``2021``) are read
    correctly.

    Required roles: ``id``, ``product``, ``transaction``, ``category``,
    ``price_basic``, ``price_purchasers``.

    Optional roles: ``trade_margins``, ``wholesale_margins``,
    ``retail_margins``, ``transport_margins``, ``product_taxes``,
    ``product_subsidies``, ``product_taxes_less_subsidies``, ``vat``.

    Parameters
    ----------
    path : str or Path
        Path to the Excel file.

    Returns
    -------
    SUTColumns

    Raises
    ------
    ValueError
        If the file does not have ``column`` and ``role`` columns.
    ValueError
        If any role value is not in the list of known roles.
    ValueError
        If any required role is absent.
    ValueError
        If any role or column name value appears more than once.
    """
    df = pd.read_excel(path, dtype=str)
    df = _strip_whitespace(df)

    _validate_required_columns(df, ["column", "role"], source="Columns file")

    duplicate_roles = df["role"][df["role"].duplicated()].tolist()
    if duplicate_roles:
        dupes_str = ", ".join(f"'{r}'" for r in duplicate_roles)
        raise ValueError(
            f"Duplicate role values in columns file: {dupes_str}"
        )

    duplicate_columns = df["column"][df["column"].duplicated()].tolist()
    if duplicate_columns:
        dupes_str = ", ".join(f"'{c}'" for c in duplicate_columns)
        raise ValueError(
            f"Duplicate column name values in columns file: {dupes_str}"
        )

    unknown_roles = set(df["role"]) - _ALL_KNOWN_ROLES
    if unknown_roles:
        unknown_str = ", ".join(f"'{r}'" for r in sorted(unknown_roles))
        known_str = ", ".join(f"'{r}'" for r in sorted(_ALL_KNOWN_ROLES))
        raise ValueError(
            f"Unknown role values: {unknown_str}. "
            f"Known roles: {known_str}"
        )

    missing_roles = _REQUIRED_ROLES - set(df["role"])
    if missing_roles:
        missing_str = ", ".join(f"'{r}'" for r in sorted(missing_roles))
        raise ValueError(
            f"Missing required roles: {missing_str}"
        )

    role_to_col = dict(zip(df["role"], df["column"]))

    return SUTColumns(
        id=role_to_col["id"],
        product=role_to_col["product"],
        transaction=role_to_col["transaction"],
        category=role_to_col["category"],
        price_basic=role_to_col["price_basic"],
        price_purchasers=role_to_col["price_purchasers"],
        trade_margins=role_to_col.get("trade_margins"),
        wholesale_margins=role_to_col.get("wholesale_margins"),
        retail_margins=role_to_col.get("retail_margins"),
        transport_margins=role_to_col.get("transport_margins"),
        product_taxes=role_to_col.get("product_taxes"),
        product_subsidies=role_to_col.get("product_subsidies"),
        product_taxes_less_subsidies=role_to_col.get("product_taxes_less_subsidies"),
        vat=role_to_col.get("vat"),
    )


def load_metadata_classifications_from_excel(path: str | Path) -> SUTClassifications:
    """
    Load classification tables from a multi-sheet Excel file.

    Known sheets: ``classifications``, ``products``, ``transactions``,
    ``industries``, ``individual_consumption``, ``collective_consumption``.
    Unknown sheets are silently ignored. Each known sheet is optional; its
    corresponding field is set to ``None`` if the sheet is absent.

    If the ``transactions`` sheet is present, it must have a ``table`` column
    with values ``"supply"`` or ``"use"`` for every row, and an ``esa_code``
    column mapping each transaction to a standardised ESA code. Valid ESA
    codes: ``P1``, ``P2``, ``P3``, ``P31``, ``P32``, ``P51g``, ``P52``,
    ``P53``, ``P6``, ``P7``.

    Leading and trailing whitespace is stripped from all values in all sheets.
    All values are read as strings.

    Parameters
    ----------
    path : str or Path
        Path to the Excel file.

    Returns
    -------
    SUTClassifications

    Raises
    ------
    ValueError
        If a present sheet is missing its required columns.
    ValueError
        If the ``transactions`` sheet has missing or invalid ``table`` values.
    ValueError
        If the ``transactions`` sheet has missing or invalid ``esa_code`` values.
    """
    all_sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    all_sheets = {name: _strip_whitespace(df) for name, df in all_sheets.items()}

    classification_names = None
    if "classifications" in all_sheets:
        df = all_sheets["classifications"]
        _validate_required_columns(
            df, ["dimension", "classification"], source="'classifications' sheet"
        )
        classification_names = df

    products = None
    if "products" in all_sheets:
        df = all_sheets["products"]
        _validate_required_columns(df, ["code", "name"], source="'products' sheet")
        products = df

    transactions = None
    if "transactions" in all_sheets:
        df = all_sheets["transactions"]
        _validate_required_columns(
            df, ["code", "name", "table", "esa_code"], source="'transactions' sheet"
        )
        invalid_table_values = set(df["table"]) - _VALID_TABLE_VALUES
        if invalid_table_values:
            invalid_str = ", ".join(f"'{v}'" for v in sorted(invalid_table_values))
            raise ValueError(
                f"Invalid values in 'table' column of 'transactions' sheet: {invalid_str}. "
                f"Each row must be 'supply' or 'use'."
            )
        invalid_esa_values = set(df["esa_code"]) - _VALID_ESA_CODES
        if invalid_esa_values:
            invalid_str = ", ".join(f"'{v}'" for v in sorted(invalid_esa_values))
            valid_str = ", ".join(sorted(_VALID_ESA_CODES))
            raise ValueError(
                f"Invalid values in 'esa_code' column of 'transactions' sheet: {invalid_str}. "
                f"Valid values are: {valid_str}."
            )
        transactions = df

    industries = None
    if "industries" in all_sheets:
        df = all_sheets["industries"]
        _validate_required_columns(df, ["code", "name"], source="'industries' sheet")
        industries = df

    individual_consumption = None
    if "individual_consumption" in all_sheets:
        df = all_sheets["individual_consumption"]
        _validate_required_columns(
            df, ["code", "name"], source="'individual_consumption' sheet"
        )
        individual_consumption = df

    collective_consumption = None
    if "collective_consumption" in all_sheets:
        df = all_sheets["collective_consumption"]
        _validate_required_columns(
            df, ["code", "name"], source="'collective_consumption' sheet"
        )
        collective_consumption = df

    return SUTClassifications(
        classification_names=classification_names,
        products=products,
        transactions=transactions,
        industries=industries,
        individual_consumption=individual_consumption,
        collective_consumption=collective_consumption,
    )


def load_metadata_from_excel(
    columns_path: str | Path,
    classifications_path: str | Path,
) -> SUTMetadata:
    """
    Load full SUT metadata from two Excel files.

    Calls :func:`load_metadata_columns_from_excel` and
    :func:`load_metadata_classifications_from_excel`, then assembles and
    returns a :class:`~sutlab.sut.SUTMetadata`. The classifications file must
    contain a ``transactions`` sheet, which is required to split supply and
    use rows when loading SUT data from parquet files.

    Parameters
    ----------
    columns_path : str or Path
        Path to the columns Excel file.
    classifications_path : str or Path
        Path to the classifications Excel file.

    Returns
    -------
    SUTMetadata

    Raises
    ------
    ValueError
        If the classifications file does not contain a ``transactions`` sheet.
    ValueError
        Any error raised by the underlying loader functions.
    """
    columns = load_metadata_columns_from_excel(columns_path)
    classifications = load_metadata_classifications_from_excel(classifications_path)

    if classifications.transactions is None:
        raise ValueError(
            "The classifications file must contain a 'transactions' sheet. "
            "This sheet is required to split supply and use rows when loading "
            f"SUT data. File: {classifications_path}"
        )

    return SUTMetadata(columns=columns, classifications=classifications)


def load_sut_from_parquet(
    id_values: list[str | int],
    paths: list[str | Path],
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
) -> SUT:
    """
    Load a SUT collection from combined supply+use parquet files.

    Each file in ``paths`` contains both supply and use rows for one collection
    member (typically one year). The corresponding entry in ``id_values`` is
    added as the id column. Supply and use rows are split using the
    ``table`` column of ``metadata.classifications.transactions``.

    The product, transaction, and category columns are cast to ``str`` on
    load, regardless of how they are stored in the parquet file. The id column
    is added with the type given in ``id_values`` (preserved as-is).

    Parameters
    ----------
    id_values : list of str or int
        Id values for each collection member, one per file. The type is
        preserved (e.g. pass integers if you want an integer id column).
    paths : list of str or Path
        Paths to the parquet files, in the same order as ``id_values``.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.

    Returns
    -------
    SUT
        SUT with supply and use DataFrames populated and ``metadata`` set.
        ``balancing_id`` is ``None``; use :func:`~sutlab.sut.set_balancing_id`
        to designate a member for balancing.

    Raises
    ------
    ValueError
        If ``id_values`` and ``paths`` have different lengths.
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If any transaction code in the data is not found in
        ``metadata.classifications.transactions``.
    """
    if len(id_values) != len(paths):
        raise ValueError(
            f"id_values and paths must have the same length. "
            f"Got {len(id_values)} id values and {len(paths)} paths."
        )

    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows. Load metadata using load_metadata_from_excel, which "
            "requires a 'transactions' sheet."
        )

    cols = metadata.columns
    trans_df = metadata.classifications.transactions

    supply_codes = set(trans_df.loc[trans_df["table"] == "supply", "code"])

    # Load each file, cast string columns, and label with the id value
    frames = []
    for id_value, path in zip(id_values, paths):
        df = pd.read_parquet(path)
        df[cols.product] = df[cols.product].astype(str)
        df[cols.transaction] = df[cols.transaction].astype(str)
        df[cols.category] = df[cols.category].astype(str)
        df.insert(0, cols.id, id_value)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Validate that all transaction codes in the data are known
    known_codes = set(trans_df["code"])
    data_codes = set(combined[cols.transaction].unique())
    unknown_codes = data_codes - known_codes
    if unknown_codes:
        unknown_str = ", ".join(f"'{c}'" for c in sorted(unknown_codes))
        known_str = ", ".join(f"'{c}'" for c in sorted(known_codes))
        raise ValueError(
            f"Transaction codes in data not found in classifications.transactions: "
            f"{unknown_str}. Known codes: {known_str}"
        )

    # Split into supply and use
    supply_mask = combined[cols.transaction].isin(supply_codes)
    supply_raw = combined[supply_mask].reset_index(drop=True)
    use_raw = combined[~supply_mask].reset_index(drop=True)

    # Supply: id, product, transaction, category, price_basic
    supply_col_order = [
        cols.id, cols.product, cols.transaction, cols.category, cols.price_basic,
    ]
    supply = supply_raw[supply_col_order]

    # Use: id, product, transaction, category, price_basic, [layers], price_purchasers
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]
    use_col_order = (
        [cols.id, cols.product, cols.transaction, cols.category, cols.price_basic]
        + layer_cols
        + [cols.price_purchasers]
    )
    use = use_raw[use_col_order]

    return SUT(
        price_basis=price_basis,
        supply=supply,
        use=use,
        metadata=metadata,
    )
