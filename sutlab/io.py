"""
I/O functions for loading SUT data and metadata from files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from sutlab.sut import (
    BalancingConfig,
    BalancingTargets,
    Locks,
    SUT,
    SUTClassifications,
    SUTColumns,
    SUTMetadata,
    TargetTolerances,
)


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

_VALID_ESA_CODES: set[str] = {"D2121", "P1", "P2", "P3", "P31", "P32", "P51g", "P52", "P53", "P6", "P7"}

# Default short codes used in file names for each price basis.
_DEFAULT_PRICE_BASIS_CODES: dict[str, str] = {
    "current_year": "l",
    "previous_year": "d",
}

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

def _format_price_basis(price_basis: str) -> str:
    """Return a human-readable price basis label, e.g. 'current year'."""
    return price_basis.replace("_", " ")


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

def _load_metadata_columns_from_excel(path: str | Path) -> SUTColumns:
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


def _load_metadata_classifications_from_excel(
    path: str | Path,
    columns: SUTColumns,
) -> SUTClassifications:
    """
    Load classification tables from a multi-sheet Excel file.

    Known sheets: ``classifications``, ``products``, ``transactions``,
    ``industries``, ``individual_consumption``, ``collective_consumption``,
    ``margin_products``.
    Unknown sheets are silently ignored. Each known sheet is optional; its
    corresponding field is set to ``None`` if the sheet is absent.

    Classification column names are derived from ``columns`` rather than
    being hardcoded. Each sheet uses the actual column name from the SUT
    data and a ``'_txt'`` variant for the label:

    - ``products``: ``{columns.product}``, ``{columns.product}_txt``
    - ``transactions``: ``{columns.transaction}``,
      ``{columns.transaction}_txt``, ``table``, ``esa_code``
    - ``industries``, ``individual_consumption``, ``collective_consumption``:
      ``{columns.category}``, ``{columns.category}_txt``
    - ``margin_products``: ``{columns.product}``, optionally
      ``{columns.product}_txt``, and ``price_layer`` (actual price layer
      column name, validated against the price layer columns in ``columns``)

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
    columns : SUTColumns
        Column role mappings for the SUT. Used to determine the expected
        column names in each classification sheet.

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

    prod_col = columns.product
    prod_txt_col = f"{columns.product}_txt"
    trans_col = columns.transaction
    trans_txt_col = f"{columns.transaction}_txt"
    cat_col = columns.category
    cat_txt_col = f"{columns.category}_txt"

    classification_names = None
    if "classifications" in all_sheets:
        df = all_sheets["classifications"]
        _validate_required_columns(
            df, ["dimension", "classification"], source="'classifications' sheet"
        )
        classification_names = df[["dimension", "classification"]].copy()

    products = None
    if "products" in all_sheets:
        df = all_sheets["products"]
        _validate_required_columns(
            df, [prod_col, prod_txt_col], source="'products' sheet"
        )
        products = df[[prod_col, prod_txt_col]].copy()

    transactions = None
    if "transactions" in all_sheets:
        df = all_sheets["transactions"]
        _validate_required_columns(
            df,
            [trans_col, trans_txt_col, "table", "esa_code"],
            source="'transactions' sheet",
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
        transactions = df[[trans_col, trans_txt_col, "table", "esa_code"]].copy()

    industries = None
    if "industries" in all_sheets:
        df = all_sheets["industries"]
        _validate_required_columns(
            df, [cat_col, cat_txt_col], source="'industries' sheet"
        )
        industries = df[[cat_col, cat_txt_col]].copy()

    individual_consumption = None
    if "individual_consumption" in all_sheets:
        df = all_sheets["individual_consumption"]
        _validate_required_columns(
            df, [cat_col, cat_txt_col], source="'individual_consumption' sheet"
        )
        individual_consumption = df[[cat_col, cat_txt_col]].copy()

    collective_consumption = None
    if "collective_consumption" in all_sheets:
        df = all_sheets["collective_consumption"]
        _validate_required_columns(
            df, [cat_col, cat_txt_col], source="'collective_consumption' sheet"
        )
        collective_consumption = df[[cat_col, cat_txt_col]].copy()

    margin_products = None
    if "margin_products" in all_sheets:
        df = all_sheets["margin_products"]
        _validate_required_columns(
            df, [prod_col, "price_layer"], source="'margin_products' sheet"
        )
        known_layer_cols = [
            getattr(columns, role) for role in _PRICE_LAYER_ROLES
            if getattr(columns, role) is not None
        ]
        unknown = [v for v in df["price_layer"].tolist() if v not in known_layer_cols]
        if unknown:
            unknown_str = ", ".join(f"'{v}'" for v in unknown)
            known_str = ", ".join(f"'{c}'" for c in known_layer_cols)
            raise ValueError(
                f"'margin_products' sheet contains unknown price layer column "
                f"names: {unknown_str}. Known price layer columns from metadata: {known_str}"
            )
        keep_cols = [prod_col, "price_layer"]
        if prod_txt_col in df.columns:
            keep_cols = [prod_col, prod_txt_col, "price_layer"]
        margin_products = df[keep_cols].copy()

    return SUTClassifications(
        classification_names=classification_names,
        products=products,
        transactions=transactions,
        industries=industries,
        individual_consumption=individual_consumption,
        collective_consumption=collective_consumption,
        margin_products=margin_products,
    )


def load_metadata_from_excel(
    columns_path: str | Path,
    classifications_path: str | Path,
    *,
    print_paths: bool = False,
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
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

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
    if print_paths:
        print("Loading metadata:")
        print(f"  columns: {columns_path}")
        print(f"  classifications: {classifications_path}")

    columns = _load_metadata_columns_from_excel(columns_path)
    classifications = _load_metadata_classifications_from_excel(classifications_path, columns)

    if classifications.transactions is None:
        raise ValueError(
            "The classifications file must contain a 'transactions' sheet. "
            "This sheet is required to split supply and use rows when loading "
            f"SUT data. File: {classifications_path}"
        )

    return SUTMetadata(columns=columns, classifications=classifications)


def _assemble_sut(
    df: pd.DataFrame,
    metadata: SUTMetadata,
    price_basis: str,
) -> SUT:
    """Validate, split, sort, and assemble a SUT from a combined DataFrame.

    The DataFrame must already contain the id column. Product, transaction,
    and category columns are cast to ``str``; category NaN is filled with
    ``""``. Price columns must already be numeric.

    Parameters
    ----------
    df : DataFrame
        Combined supply+use data for all collection members, with the id
        column already present. ``metadata.classifications.transactions``
        must be present.
    metadata : SUTMetadata
        Metadata for the SUT.
    price_basis : str
        Price basis for the collection.

    Returns
    -------
    SUT
    """
    cols = metadata.columns
    trans_df = metadata.classifications.transactions  # type: ignore[union-attr]

    df = df.copy()
    df[cols.product] = df[cols.product].astype(str)
    df[cols.transaction] = df[cols.transaction].astype(str)
    df[cols.category] = df[cols.category].fillna("").astype(str)

    # Validate that all transaction codes in the data are known
    known_codes = set(trans_df[cols.transaction])
    data_codes = set(df[cols.transaction].unique())
    unknown_codes = data_codes - known_codes
    if unknown_codes:
        unknown_str = ", ".join(f"'{c}'" for c in sorted(unknown_codes))
        known_str = ", ".join(f"'{c}'" for c in sorted(known_codes))
        raise ValueError(
            f"Transaction codes in data not found in classifications.transactions: "
            f"{unknown_str}. Known codes: {known_str}"
        )

    # Split into supply and use
    supply_codes = set(trans_df.loc[trans_df["table"] == "supply", cols.transaction])
    supply_mask = df[cols.transaction].isin(supply_codes)
    supply_raw = df[supply_mask]
    use_raw = df[~supply_mask]

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

    sort_cols = [cols.id, cols.product, cols.transaction, cols.category]
    supply = supply.sort_values(sort_cols).reset_index(drop=True)
    use = use.sort_values(sort_cols).reset_index(drop=True)

    return SUT(price_basis=price_basis, supply=supply, use=use, metadata=metadata)


def _resolve_price_basis_code(sut: SUT, price_basis_code: str | None) -> str:
    """Return the price basis code to use in file names.

    If ``price_basis_code`` is provided, return it as-is. Otherwise look up
    the default from :data:`_DEFAULT_PRICE_BASIS_CODES`.
    """
    if price_basis_code is not None:
        return price_basis_code
    code = _DEFAULT_PRICE_BASIS_CODES.get(sut.price_basis)
    if code is None:
        raise ValueError(
            f"No default price basis code for '{sut.price_basis}'. "
            f"Pass price_basis_code explicitly."
        )
    return code


def _combine_supply_use(sut: SUT) -> pd.DataFrame:
    """Concatenate supply and use into a single DataFrame.

    Supply rows will have NaN in the price layer and purchasers' price columns.
    """
    return pd.concat([sut.supply, sut.use], ignore_index=True)


def load_sut_from_separated_parquet(
    id_values: list[str | int],
    paths: list[str | Path],
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from separate per-member supply+use parquet files.

    Each file in ``paths`` contains both supply and use rows for one collection
    member (typically one year), without an id column. The corresponding entry
    in ``id_values`` is added as the id column on load. Supply and use rows are
    split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are cast to ``str`` on
    load, regardless of how they are stored in the parquet file. The id column
    is added with the type given in ``id_values`` (preserved as-is).

    Rows are sorted by id, product, transaction, category after loading.

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
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

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

    if print_paths:
        basis = _format_price_basis(price_basis)
        n = len(paths)
        print(f"Loading SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, path in zip(id_values, paths):
            print(f"  {id_value}: {path}")

    cols = metadata.columns

    # Load each file and label with the id value
    frames = []
    for id_value, path in zip(id_values, paths):
        df = pd.read_parquet(path)
        df.insert(0, cols.id, id_value)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    return _assemble_sut(combined, metadata, price_basis)


def load_sut_from_combined_parquet(
    path: str | Path,
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from a single combined supply+use parquet file.

    The file contains both supply and use rows for all collection members
    (typically all years), with the id column already present in the file.
    Supply and use rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are cast to ``str`` on
    load, regardless of how they are stored in the parquet file. The id column
    is read as-is from the file (type preserved).

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    path : str or Path
        Path to the combined parquet file.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.
    print_paths : bool, optional
        If ``True``, print the path being read before loading. Defaults to
        ``False``.

    Returns
    -------
    SUT
        SUT with supply and use DataFrames populated and ``metadata`` set.
        ``balancing_id`` is ``None``; use :func:`~sutlab.sut.set_balancing_id`
        to designate a member for balancing.

    Raises
    ------
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If any transaction code in the data is not found in
        ``metadata.classifications.transactions``.
    """
    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows. Load metadata using load_metadata_from_excel, which "
            "requires a 'transactions' sheet."
        )

    if print_paths:
        basis = _format_price_basis(price_basis)
        print(f"Loading SUT ({basis}) from: {path}")

    df = pd.read_parquet(path)
    return _assemble_sut(df, metadata, price_basis)


def load_sut_from_separated_csv(
    id_values: list[str | int],
    paths: list[str | Path],
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    sep: str = ",",
    encoding: str | None = None,
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from separate per-member supply+use CSV files.

    Each file in ``paths`` contains both supply and use rows for one collection
    member (typically one year), without an id column. The corresponding entry
    in ``id_values`` is added as the id column on load. Supply and use rows are
    split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are read as strings. Price
    columns (basic, any price layers, purchasers) are converted to float. The
    id column is added with the type given in ``id_values`` (preserved as-is).

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    id_values : list of str or int
        Id values for each collection member, one per file. The type is
        preserved (e.g. pass integers if you want an integer id column).
    paths : list of str or Path
        Paths to the CSV files, in the same order as ``id_values``.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.
    sep : str, optional
        Column separator. Defaults to ``','``.
    encoding : str or None, optional
        File encoding. Defaults to ``None`` (pandas default).
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

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

    if print_paths:
        basis = _format_price_basis(price_basis)
        n = len(paths)
        print(f"Loading SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, path in zip(id_values, paths):
            print(f"  {id_value}: {path}")

    cols = metadata.columns
    str_dtypes = {
        cols.product: str,
        cols.transaction: str,
        cols.category: str,
    }
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]
    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    frames = []
    for id_value, path in zip(id_values, paths):
        df = pd.read_csv(path, dtype=str_dtypes, sep=sep, encoding=encoding)
        for col in price_cols:
            df[col] = pd.to_numeric(df[col])
        df.insert(0, cols.id, id_value)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    return _assemble_sut(combined, metadata, price_basis)


def load_sut_from_combined_csv(
    path: str | Path,
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    sep: str = ",",
    encoding: str | None = None,
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from a single combined supply+use CSV file.

    The file contains both supply and use rows for all collection members
    (typically all years), with the id column already present. Supply and use
    rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are read as strings. Price
    columns (basic, any price layers, purchasers) are converted to float. The
    id column type is inferred by pandas from the file contents.

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    path : str or Path
        Path to the combined CSV file.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.
    sep : str, optional
        Column separator. Defaults to ``','``.
    encoding : str or None, optional
        File encoding. Defaults to ``None`` (pandas default).
    print_paths : bool, optional
        If ``True``, print the path being read before loading. Defaults to
        ``False``.

    Returns
    -------
    SUT
        SUT with supply and use DataFrames populated and ``metadata`` set.
        ``balancing_id`` is ``None``; use :func:`~sutlab.sut.set_balancing_id`
        to designate a member for balancing.

    Raises
    ------
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If any transaction code in the data is not found in
        ``metadata.classifications.transactions``.
    """
    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows. Load metadata using load_metadata_from_excel, which "
            "requires a 'transactions' sheet."
        )

    if print_paths:
        basis = _format_price_basis(price_basis)
        print(f"Loading SUT ({basis}) from: {path}")

    cols = metadata.columns
    str_dtypes = {
        cols.product: str,
        cols.transaction: str,
        cols.category: str,
    }
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]
    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    df = pd.read_csv(path, dtype=str_dtypes, sep=sep, encoding=encoding)
    for col in price_cols:
        df[col] = pd.to_numeric(df[col])

    return _assemble_sut(df, metadata, price_basis)


def load_sut_from_separated_excel(
    id_values: list[str | int],
    paths: list[str | Path],
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    sheet_name: str | int = 0,
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from separate per-member supply+use Excel files.

    Each file in ``paths`` contains both supply and use rows for one collection
    member (typically one year), without an id column. The corresponding entry
    in ``id_values`` is added as the id column on load. Supply and use rows are
    split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are read as strings. Price
    columns (basic, any price layers, purchasers) are converted to float. The
    id column is added with the type given in ``id_values`` (preserved as-is).

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    id_values : list of str or int
        Id values for each collection member, one per file. The type is
        preserved (e.g. pass integers if you want an integer id column).
    paths : list of str or Path
        Paths to the Excel files, in the same order as ``id_values``.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.
    sheet_name : str or int, optional
        Sheet to read from each file. Accepts a sheet name (str) or zero-based
        index (int). The same sheet name is used for every file. Defaults to
        ``0`` (first sheet).
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

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

    if print_paths:
        basis = _format_price_basis(price_basis)
        n = len(paths)
        print(f"Loading SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, path in zip(id_values, paths):
            print(f"  {id_value}: {path}")

    cols = metadata.columns
    str_dtypes = {
        cols.product: str,
        cols.transaction: str,
        cols.category: str,
    }
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]
    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    frames = []
    for id_value, path in zip(id_values, paths):
        df = pd.read_excel(path, sheet_name=sheet_name, dtype=str_dtypes)
        for col in price_cols:
            df[col] = pd.to_numeric(df[col])
        df.insert(0, cols.id, id_value)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    return _assemble_sut(combined, metadata, price_basis)


def load_sut_from_combined_excel(
    path: str | Path,
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    sheet_name: str | int = 0,
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from a single combined supply+use Excel file.

    The file contains both supply and use rows for all collection members
    (typically all years) in a single sheet, with the id column already
    present. Supply and use rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are read as strings. Price
    columns (basic, any price layers, purchasers) are converted to float. The
    id column type is inferred by pandas from the file contents.

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    path : str or Path
        Path to the combined Excel file.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.
    sheet_name : str or int, optional
        Sheet to read from the file. Accepts a sheet name (str) or zero-based
        index (int). Defaults to ``0`` (first sheet).
    print_paths : bool, optional
        If ``True``, print the path being read before loading. Defaults to
        ``False``.

    Returns
    -------
    SUT
        SUT with supply and use DataFrames populated and ``metadata`` set.
        ``balancing_id`` is ``None``; use :func:`~sutlab.sut.set_balancing_id`
        to designate a member for balancing.

    Raises
    ------
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If any transaction code in the data is not found in
        ``metadata.classifications.transactions``.
    """
    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows. Load metadata using load_metadata_from_excel, which "
            "requires a 'transactions' sheet."
        )

    if print_paths:
        basis = _format_price_basis(price_basis)
        print(f"Loading SUT ({basis}) from: {path}")

    cols = metadata.columns
    str_dtypes = {
        cols.product: str,
        cols.transaction: str,
        cols.category: str,
    }
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]
    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    df = pd.read_excel(path, sheet_name=sheet_name, dtype=str_dtypes)
    for col in price_cols:
        df[col] = pd.to_numeric(df[col])

    return _assemble_sut(df, metadata, price_basis)


def load_sut_from_dataframe(
    df: pd.DataFrame,
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
) -> SUT:
    """
    Load a SUT collection from a combined supply+use DataFrame.

    The DataFrame contains both supply and use rows for all collection members
    (typically all years), with the id column already present. Supply and use
    rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The product, transaction, and category columns are cast to ``str``.
    The id column type is preserved as-is. Price columns must already be
    numeric.

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    df : DataFrame
        Combined supply+use data for all collection members. The id column
        must be present.
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
    TypeError
        If ``df`` is not a pandas DataFrame.
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If any transaction code in the data is not found in
        ``metadata.classifications.transactions``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}."
        )

    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows. Load metadata using load_metadata_from_excel, which "
            "requires a 'transactions' sheet."
        )

    return _assemble_sut(df, metadata, price_basis)


def write_sut_to_separated_parquet(
    sut: SUT,
    id_values: list[str | int],
    paths: list[str | Path],
    *,
    print_paths: bool = False,
) -> None:
    """
    Write selected SUT members to separate per-member parquet files.

    One file is written per entry in ``id_values``. Each file contains the
    combined supply and use rows for that member, without the id column.
    Supply rows have NaN in the price layer and purchasers' price columns.

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present.
    id_values : list of str or int
        Id values to write, one per output file. Must all be present in the
        SUT.
    paths : list of str or Path
        Output file paths, in the same order as ``id_values``.
    print_paths : bool, optional
        If ``True``, print the paths being written before writing. Defaults to
        ``False``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is absent.
    ValueError
        If ``id_values`` and ``paths`` have different lengths.
    ValueError
        If any value in ``id_values`` is not present in the SUT.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify the id column for writing."
        )
    if len(id_values) != len(paths):
        raise ValueError(
            f"id_values and paths must have the same length. "
            f"Got {len(id_values)} id values and {len(paths)} paths."
        )

    id_col = sut.metadata.columns.id
    combined = _combine_supply_use(sut)
    available = list(combined[id_col].unique())
    missing = [v for v in id_values if v not in available]
    if missing:
        raise ValueError(
            f"id_values not found in SUT: {missing}. Available: {available}"
        )

    cols = sut.metadata.columns
    sort_cols = [cols.product, cols.transaction, cols.category]
    paths = [Path(p) for p in paths]

    if print_paths:
        basis = _format_price_basis(sut.price_basis)
        n = len(id_values)
        print(f"Writing SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, output_path in zip(id_values, paths):
            print(f"  {id_value}: {output_path}")

    for id_value, output_path in zip(id_values, paths):
        member = (
            combined[combined[id_col] == id_value]
            .drop(columns=[id_col])
            .sort_values(sort_cols)
            .reset_index(drop=True)
        )
        member.to_parquet(output_path, index=False)


def write_sut_to_combined_parquet(
    sut: SUT,
    folder: str | Path,
    prefix: str,
    *,
    price_basis_code: str | None = None,
    print_paths: bool = False,
) -> None:
    """
    Write a SUT collection to a single combined parquet file.

    The file contains supply and use rows for all collection members, with
    the id column present. Supply rows have NaN in the price layer and
    purchasers' price columns. Rows are sorted by id, product, transaction,
    category before writing.

    The file is named ``{prefix}_{code}.parquet``, where ``code`` is the
    price basis code (default: ``"l"`` for current year, ``"d"`` for
    previous year).

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present.
    folder : str or Path
        Directory to write the file into.
    prefix : str
        File name prefix, e.g. ``"ta"``.
    price_basis_code : str or None, optional
        Short code for the price basis used in the file name. Defaults to
        ``"l"`` (current year) or ``"d"`` (previous year).
    print_paths : bool, optional
        If ``True``, print the path being written before writing. Defaults to
        ``False``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is absent.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify sort columns for writing."
        )

    folder = Path(folder)
    code = _resolve_price_basis_code(sut, price_basis_code)
    output_path = folder / f"{prefix}_{code}.parquet"

    if print_paths:
        basis = _format_price_basis(sut.price_basis)
        print(f"Writing SUT ({basis}) to: {output_path}")

    cols = sut.metadata.columns
    sort_cols = [cols.id, cols.product, cols.transaction, cols.category]
    combined = _combine_supply_use(sut).sort_values(sort_cols).reset_index(drop=True)
    combined.to_parquet(output_path, index=False)


def write_sut_to_separated_csv(
    sut: SUT,
    id_values: list[str | int],
    paths: list[str | Path],
    *,
    sep: str = ",",
    encoding: str | None = None,
    print_paths: bool = False,
) -> None:
    """
    Write selected SUT members to separate per-member CSV files.

    One file is written per entry in ``id_values``. Each file contains the
    combined supply and use rows for that member, without the id column.
    Supply rows have NaN in the price layer and purchasers' price columns.

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present.
    id_values : list of str or int
        Id values to write, one per output file. Must all be present in the
        SUT.
    paths : list of str or Path
        Output file paths, in the same order as ``id_values``.
    sep : str, optional
        Column separator. Defaults to ``','``.
    encoding : str or None, optional
        File encoding. Defaults to ``None`` (pandas default).
    print_paths : bool, optional
        If ``True``, print the paths being written before writing. Defaults to
        ``False``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is absent.
    ValueError
        If ``id_values`` and ``paths`` have different lengths.
    ValueError
        If any value in ``id_values`` is not present in the SUT.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify the id column for writing."
        )
    if len(id_values) != len(paths):
        raise ValueError(
            f"id_values and paths must have the same length. "
            f"Got {len(id_values)} id values and {len(paths)} paths."
        )

    cols = sut.metadata.columns
    id_col = cols.id
    sort_cols = [cols.product, cols.transaction, cols.category]
    combined = _combine_supply_use(sut)
    available = list(combined[id_col].unique())
    missing = [v for v in id_values if v not in available]
    if missing:
        raise ValueError(
            f"id_values not found in SUT: {missing}. Available: {available}"
        )

    paths = [Path(p) for p in paths]

    if print_paths:
        basis = _format_price_basis(sut.price_basis)
        n = len(id_values)
        print(f"Writing SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, output_path in zip(id_values, paths):
            print(f"  {id_value}: {output_path}")

    for id_value, output_path in zip(id_values, paths):
        member = (
            combined[combined[id_col] == id_value]
            .drop(columns=[id_col])
            .sort_values(sort_cols)
            .reset_index(drop=True)
        )
        member.to_csv(
            output_path,
            index=False,
            sep=sep,
            encoding=encoding,
        )


def write_sut_to_combined_csv(
    sut: SUT,
    folder: str | Path,
    prefix: str,
    *,
    price_basis_code: str | None = None,
    sep: str = ",",
    encoding: str | None = None,
    print_paths: bool = False,
) -> None:
    """
    Write a SUT collection to a single combined CSV file.

    The file contains supply and use rows for all collection members, with
    the id column present. Supply rows have NaN in the price layer and
    purchasers' price columns. Rows are sorted by id, product, transaction,
    category before writing.

    The file is named ``{prefix}_{code}.csv``, where ``code`` is the price
    basis code (default: ``"l"`` for current year, ``"d"`` for previous year).

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present.
    folder : str or Path
        Directory to write the file into.
    prefix : str
        File name prefix, e.g. ``"ta"``.
    price_basis_code : str or None, optional
        Short code for the price basis used in the file name. Defaults to
        ``"l"`` (current year) or ``"d"`` (previous year).
    sep : str, optional
        Column separator. Defaults to ``','``.
    encoding : str or None, optional
        File encoding. Defaults to ``None`` (pandas default).
    print_paths : bool, optional
        If ``True``, print the path being written before writing. Defaults to
        ``False``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is absent.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify sort columns for writing."
        )

    folder = Path(folder)
    code = _resolve_price_basis_code(sut, price_basis_code)
    output_path = folder / f"{prefix}_{code}.csv"

    if print_paths:
        basis = _format_price_basis(sut.price_basis)
        print(f"Writing SUT ({basis}) to: {output_path}")

    cols = sut.metadata.columns
    sort_cols = [cols.id, cols.product, cols.transaction, cols.category]
    combined = _combine_supply_use(sut).sort_values(sort_cols).reset_index(drop=True)
    combined.to_csv(
        output_path,
        index=False,
        sep=sep,
        encoding=encoding,
    )


def write_sut_to_separated_excel(
    sut: SUT,
    id_values: list[str | int],
    paths: list[str | Path],
    *,
    print_paths: bool = False,
) -> None:
    """
    Write selected SUT members to separate per-member Excel files.

    One file is written per entry in ``id_values``. Each file contains the
    combined supply and use rows for that member, without the id column.
    Supply rows have NaN in the price layer and purchasers' price columns.

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present.
    id_values : list of str or int
        Id values to write, one per output file. Must all be present in the
        SUT.
    paths : list of str or Path
        Output file paths, in the same order as ``id_values``.
    print_paths : bool, optional
        If ``True``, print the paths being written before writing. Defaults to
        ``False``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is absent.
    ValueError
        If ``id_values`` and ``paths`` have different lengths.
    ValueError
        If any value in ``id_values`` is not present in the SUT.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify the id column for writing."
        )
    if len(id_values) != len(paths):
        raise ValueError(
            f"id_values and paths must have the same length. "
            f"Got {len(id_values)} id values and {len(paths)} paths."
        )

    cols = sut.metadata.columns
    id_col = cols.id
    sort_cols = [cols.product, cols.transaction, cols.category]
    combined = _combine_supply_use(sut)
    available = list(combined[id_col].unique())
    missing = [v for v in id_values if v not in available]
    if missing:
        raise ValueError(
            f"id_values not found in SUT: {missing}. Available: {available}"
        )

    paths = [Path(p) for p in paths]

    if print_paths:
        basis = _format_price_basis(sut.price_basis)
        n = len(id_values)
        print(f"Writing SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, output_path in zip(id_values, paths):
            print(f"  {id_value}: {output_path}")

    for id_value, output_path in zip(id_values, paths):
        member = (
            combined[combined[id_col] == id_value]
            .drop(columns=[id_col])
            .sort_values(sort_cols)
            .reset_index(drop=True)
        )
        member.to_excel(output_path, index=False)


def write_sut_to_combined_excel(
    sut: SUT,
    folder: str | Path,
    prefix: str,
    *,
    price_basis_code: str | None = None,
    print_paths: bool = False,
) -> None:
    """
    Write a SUT collection to a single combined Excel file.

    The file contains supply and use rows for all collection members, with
    the id column present. Supply rows have NaN in the price layer and
    purchasers' price columns. Rows are sorted by id, product, transaction,
    category before writing.

    The file is named ``{prefix}_{code}.xlsx``, where ``code`` is the price
    basis code (default: ``"l"`` for current year, ``"d"`` for previous year).

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present.
    folder : str or Path
        Directory to write the file into.
    prefix : str
        File name prefix, e.g. ``"ta"``.
    price_basis_code : str or None, optional
        Short code for the price basis used in the file name. Defaults to
        ``"l"`` (current year) or ``"d"`` (previous year).
    print_paths : bool, optional
        If ``True``, print the path being written before writing. Defaults to
        ``False``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is absent.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify sort columns for writing."
        )

    folder = Path(folder)
    code = _resolve_price_basis_code(sut, price_basis_code)
    output_path = folder / f"{prefix}_{code}.xlsx"

    if print_paths:
        basis = _format_price_basis(sut.price_basis)
        print(f"Writing SUT ({basis}) to: {output_path}")

    cols = sut.metadata.columns
    sort_cols = [cols.id, cols.product, cols.transaction, cols.category]
    combined = _combine_supply_use(sut).sort_values(sort_cols).reset_index(drop=True)
    combined.to_excel(output_path, index=False)


def _assemble_balancing_targets(
    df: pd.DataFrame,
    metadata: SUTMetadata,
) -> BalancingTargets:
    """Validate, split, and assemble a BalancingTargets from a combined DataFrame.

    The DataFrame must already contain the id column. Transaction and category
    columns are cast to ``str``; category NaN is filled with ``""``. Price
    columns must already be numeric.

    Parameters
    ----------
    df : DataFrame
        Combined supply+use targets for all collection members, with the id
        column already present. ``metadata.classifications.transactions`` must
        be present.
    metadata : SUTMetadata
        Metadata for the SUT.

    Returns
    -------
    BalancingTargets
    """
    cols = metadata.columns
    trans_df = metadata.classifications.transactions  # type: ignore[union-attr]

    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]

    df = df.copy()
    df[cols.transaction] = df[cols.transaction].astype(str)
    df[cols.category] = df[cols.category].fillna("").astype(str)

    # Validate that all transaction codes in the targets are known
    known_codes = set(trans_df[cols.transaction])
    data_codes = set(df[cols.transaction].unique())
    unknown_codes = data_codes - known_codes
    if unknown_codes:
        unknown_str = ", ".join(f"'{c}'" for c in sorted(unknown_codes))
        known_str = ", ".join(f"'{c}'" for c in sorted(known_codes))
        raise ValueError(
            f"Transaction codes in targets not found in classifications.transactions: "
            f"{unknown_str}. Known codes: {known_str}"
        )

    # Split into supply and use
    supply_codes = set(trans_df.loc[trans_df["table"] == "supply", cols.transaction])
    supply_mask = df[cols.transaction].isin(supply_codes)

    # Supply: id, transaction, category, price_basic
    supply_col_order = [cols.id, cols.transaction, cols.category, cols.price_basic]
    supply = df[supply_mask][supply_col_order].reset_index(drop=True)

    # Use: id, transaction, category, price_basic, [layers], price_purchasers
    use_col_order = (
        [cols.id, cols.transaction, cols.category, cols.price_basic]
        + layer_cols
        + [cols.price_purchasers]
    )
    use = df[~supply_mask][use_col_order].reset_index(drop=True)

    return BalancingTargets(supply=supply, use=use)


def load_balancing_targets_from_separated_excel(
    id_values: list[str | int],
    paths: list[str | Path],
    metadata: SUTMetadata,
    *,
    sheet_name: str | int = 0,
    print_paths: bool = False,
) -> BalancingTargets:
    """
    Load a balancing targets collection from one Excel file per id value.

    Each targets file mirrors the combined SUT long-format but without the
    product dimension. It must contain the transaction, category, and all
    price columns defined in ``metadata.columns`` (basic price, any price
    layers, and purchasers' price). No id column in the file — the
    corresponding entry in ``id_values`` is added on load.

    Supply and use rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The output supply DataFrame has columns:
    id, transaction, category, price_basic.

    The output use DataFrame has columns:
    id, transaction, category, price_basic, [price layers], price_purchasers.

    A NaN in a price column means no target for that price basis for that
    (id, transaction, category) combination. Balancing functions skip
    combinations with no target.

    All columns are read with ``dtype=str`` to preserve leading zeros in
    transaction codes. Price columns are converted to numeric after loading.
    Empty category cells are filled with ``""`` to match the SUT convention.

    Parameters
    ----------
    id_values : list of str or int
        Id values for each collection member, one per file. The type is
        preserved (e.g. pass integers if you want an integer id column).
    paths : list of str or Path
        Paths to the targets Excel files, in the same order as ``id_values``.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    sheet_name : str or int, optional
        Sheet to read from each file. Accepts a sheet name (str) or zero-based
        index (int). The same sheet name is used for every file. Defaults to
        ``0`` (first sheet).
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

    Returns
    -------
    BalancingTargets

    Raises
    ------
    ValueError
        If ``id_values`` and ``paths`` have different lengths.
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If any targets file is missing a required column.
    ValueError
        If any transaction code is not found in
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
            "and use rows in load_balancing_targets_from_separated_excel."
        )

    if print_paths:
        n = len(paths)
        print(f"Loading balancing targets ({n} member{'s' if n != 1 else ''}):")
        for id_value, path in zip(id_values, paths):
            print(f"  {id_value}: {path}")

    cols = metadata.columns

    # Price layer columns present in metadata (in order)
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]

    # All price columns: these must all be present in the targets file
    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    required_cols = [cols.transaction, cols.category] + price_cols

    frames = []
    for id_value, path in zip(id_values, paths):
        df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
        df = _strip_whitespace(df)
        _validate_required_columns(df, required_cols, source=f"Targets file '{path}'")
        df.insert(0, cols.id, id_value)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Convert all price columns from string to numeric
    for col in price_cols:
        combined[col] = pd.to_numeric(combined[col])

    return _assemble_balancing_targets(combined, metadata)


def load_balancing_targets_from_combined_excel(
    path: str | Path,
    metadata: SUTMetadata,
    *,
    sheet_name: str | int = 0,
    print_paths: bool = False,
) -> BalancingTargets:
    """
    Load a balancing targets collection from a single combined Excel file.

    The file contains rows for all collection members, with the id column
    present. It mirrors the combined SUT long-format but without the product
    dimension. It must contain the id, transaction, category, and all price
    columns defined in ``metadata.columns`` (basic price, any price layers,
    and purchasers' price).

    Supply and use rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The output supply DataFrame has columns:
    id, transaction, category, price_basic.

    The output use DataFrame has columns:
    id, transaction, category, price_basic, [price layers], price_purchasers.

    A NaN in a price column means no target for that price basis for that
    (id, transaction, category) combination. Balancing functions skip
    combinations with no target.

    Transaction and category columns are read as strings to preserve leading
    zeros. Price columns are converted to numeric after loading. Empty
    category cells are filled with ``""`` to match the SUT convention.
    The id column type is inferred by pandas.

    Parameters
    ----------
    path : str or Path
        Path to the combined targets Excel file.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    sheet_name : str or int, optional
        Sheet to read from the file. Accepts a sheet name (str) or zero-based
        index (int). Defaults to ``0`` (first sheet).
    print_paths : bool, optional
        If ``True``, print the path being read before loading. Defaults to
        ``False``.

    Returns
    -------
    BalancingTargets

    Raises
    ------
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If the file is missing a required column.
    ValueError
        If any transaction code is not found in
        ``metadata.classifications.transactions``.
    """
    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows in load_balancing_targets_from_combined_excel."
        )

    if print_paths:
        print(f"Loading balancing targets from: {path}")

    cols = metadata.columns

    # Price layer columns present in metadata (in order)
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]

    # All price columns: these must all be present in the targets file
    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]

    required_cols = [cols.id, cols.transaction, cols.category] + price_cols

    # Only override dtypes for columns that need string preservation (leading
    # zeros in transaction codes). The id column is left to pandas inference.
    str_dtypes = {cols.transaction: str, cols.category: str}
    combined = pd.read_excel(path, sheet_name=sheet_name, dtype=str_dtypes)
    combined = _strip_whitespace(combined)
    _validate_required_columns(combined, required_cols, source=f"Targets file '{path}'")

    # Convert all price columns from string to numeric
    for col in price_cols:
        combined[col] = pd.to_numeric(combined[col])

    return _assemble_balancing_targets(combined, metadata)


def load_balancing_targets_from_dataframe(
    df: pd.DataFrame,
    metadata: SUTMetadata,
) -> BalancingTargets:
    """
    Load a balancing targets collection from a combined DataFrame.

    The DataFrame contains rows for all collection members, with the id column
    present. It mirrors the combined SUT long-format but without the product
    dimension. It must contain the id, transaction, category, and all price
    columns defined in ``metadata.columns`` (basic price, any price layers,
    and purchasers' price).

    Supply and use rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The output supply DataFrame has columns:
    id, transaction, category, price_basic.

    The output use DataFrame has columns:
    id, transaction, category, price_basic, [price layers], price_purchasers.

    A NaN in a price column means no target for that price basis for that
    (id, transaction, category) combination. Balancing functions skip
    combinations with no target.

    Transaction and category columns are cast to ``str``. Empty category
    cells are filled with ``""`` to match the SUT convention. Price columns
    must already be numeric. The id column type is preserved as-is.

    Parameters
    ----------
    df : DataFrame
        Combined supply+use targets for all collection members. The id column
        must be present.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.

    Returns
    -------
    BalancingTargets

    Raises
    ------
    TypeError
        If ``df`` is not a pandas DataFrame.
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If the DataFrame is missing a required column.
    ValueError
        If any transaction code is not found in
        ``metadata.classifications.transactions``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}."
        )

    if metadata.classifications is None or metadata.classifications.transactions is None:
        raise ValueError(
            "metadata.classifications.transactions is required to split supply "
            "and use rows in load_balancing_targets_from_dataframe."
        )

    cols = metadata.columns

    # Price layer columns present in metadata (in order)
    layer_cols = [
        getattr(cols, role)
        for role in _PRICE_LAYER_ROLES
        if getattr(cols, role) is not None
    ]

    price_cols = [cols.price_basic] + layer_cols + [cols.price_purchasers]
    required_cols = [cols.id, cols.transaction, cols.category] + price_cols
    _validate_required_columns(df, required_cols, source="DataFrame")

    return _assemble_balancing_targets(df, metadata)


def _load_balancing_config_tolerances_from_excel(
    path: str | Path,
    metadata: SUTMetadata,
) -> TargetTolerances:
    """Load a TargetTolerances from a two-sheet Excel file.

    Known sheets: ``transactions`` (transaction-level tolerances) and
    ``categories`` (transaction-category overrides). Both are optional.
    Unknown sheets are silently ignored.

    Parameters
    ----------
    path : str or Path
        Path to the tolerances Excel file.
    metadata : SUTMetadata
        Metadata for the SUT. Used to identify the actual transaction and
        category column names.

    Returns
    -------
    TargetTolerances

    Raises
    ------
    ValueError
        If a present sheet is missing required columns.
    """
    cols = metadata.columns
    all_sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    all_sheets = {name: _strip_whitespace(df) for name, df in all_sheets.items()}

    trans = None
    if "transactions" in all_sheets:
        df = all_sheets["transactions"]
        _validate_required_columns(
            df,
            [cols.transaction, "rel", "abs"],
            source="'transactions' sheet in tolerances file",
        )
        trans = df[[cols.transaction, "rel", "abs"]].copy()
        trans["rel"] = pd.to_numeric(trans["rel"])
        trans["abs"] = pd.to_numeric(trans["abs"])

    trans_cat = None
    if "categories" in all_sheets:
        df = all_sheets["categories"]
        _validate_required_columns(
            df,
            [cols.transaction, cols.category, "rel", "abs"],
            source="'categories' sheet in tolerances file",
        )
        trans_cat = df[[cols.transaction, cols.category, "rel", "abs"]].copy()
        trans_cat["rel"] = pd.to_numeric(trans_cat["rel"])
        trans_cat["abs"] = pd.to_numeric(trans_cat["abs"])

    return TargetTolerances(transactions=trans, categories=trans_cat)


def _load_balancing_config_locks_from_excel(
    path: str | Path,
    metadata: SUTMetadata,
) -> Locks:
    """Load a Locks specification from a multi-sheet Excel file.

    Known sheets: ``products``, ``transactions``, ``categories``, ``cells``,
    ``price_layers``. All are optional. Unknown sheets are silently ignored.

    Parameters
    ----------
    path : str or Path
        Path to the locks Excel file.
    metadata : SUTMetadata
        Metadata for the SUT. Used to identify the actual product, transaction,
        and category column names.

    Returns
    -------
    Locks

    Raises
    ------
    ValueError
        If a present sheet is missing required columns.
    """
    cols = metadata.columns
    all_sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    all_sheets = {name: _strip_whitespace(df) for name, df in all_sheets.items()}

    products = None
    if "products" in all_sheets:
        df = all_sheets["products"]
        _validate_required_columns(
            df, [cols.product], source="'products' sheet in locks file"
        )
        products = df[[cols.product]].copy()

    trans = None
    if "transactions" in all_sheets:
        df = all_sheets["transactions"]
        _validate_required_columns(
            df, [cols.transaction], source="'transactions' sheet in locks file"
        )
        trans = df[[cols.transaction]].copy()

    trans_cat = None
    if "categories" in all_sheets:
        df = all_sheets["categories"]
        _validate_required_columns(
            df,
            [cols.transaction, cols.category],
            source="'categories' sheet in locks file",
        )
        trans_cat = df[[cols.transaction, cols.category]].copy()

    cells = None
    if "cells" in all_sheets:
        df = all_sheets["cells"]
        _validate_required_columns(
            df,
            [cols.product, cols.transaction, cols.category],
            source="'cells' sheet in locks file",
        )
        cells = df[[cols.product, cols.transaction, cols.category]].copy()

    price_layers = None
    if "price_layers" in all_sheets:
        df = all_sheets["price_layers"]
        _validate_required_columns(df, ["price_layer"], source="'price_layers' sheet in locks file")
        known_layer_cols = [
            getattr(cols, role) for role in _PRICE_LAYER_ROLES
            if getattr(cols, role) is not None
        ]
        unknown = [v for v in df["price_layer"].tolist() if v not in known_layer_cols]
        if unknown:
            unknown_str = ", ".join(f"'{v}'" for v in unknown)
            known_str = ", ".join(f"'{c}'" for c in known_layer_cols)
            raise ValueError(
                f"'price_layers' sheet in locks file contains unknown price layer column "
                f"names: {unknown_str}. Known price layer columns from metadata: {known_str}"
            )
        price_layers = df[["price_layer"]].copy()

    return Locks(
        products=products,
        transactions=trans,
        categories=trans_cat,
        cells=cells,
        price_layers=price_layers,
    )


def load_balancing_config_from_excel(
    metadata: SUTMetadata,
    *,
    tolerances_path: str | Path | None = None,
    locks_path: str | Path | None = None,
    print_paths: bool = False,
) -> BalancingConfig:
    """
    Load balancing configuration from Excel files.

    Loads target tolerances and/or locked cells from the provided file paths
    and returns a :class:`~sutlab.sut.BalancingConfig`. At least one path
    must be provided.

    The tolerances file has two optional sheets:

    - ``transactions`` — columns: transaction column name, ``rel``
      (relative tolerance, 0–1), ``abs`` (absolute tolerance). One row per
      transaction code.
    - ``categories`` — columns: transaction column name, category column name,
      ``rel``, ``abs``. Overrides for specific (transaction, category) pairs.

    The locks file has four optional sheets:

    - ``products`` — single column: product column name.
    - ``transactions`` — single column: transaction column name.
    - ``categories`` — two columns: transaction and category column names.
    - ``cells`` — three columns: product, transaction, and category column names.

    Column names in all sheets must match the actual data column names defined
    in ``metadata.columns``.

    Parameters
    ----------
    metadata : SUTMetadata
        Metadata for the SUT. Used to identify actual column names.
    tolerances_path : str, Path, or None
        Path to the tolerances Excel file. ``None`` if no tolerances file is
        provided.
    locks_path : str, Path, or None
        Path to the locks Excel file. ``None`` if no locks file is provided.
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

    Returns
    -------
    BalancingConfig

    Raises
    ------
    ValueError
        If both ``tolerances_path`` and ``locks_path`` are ``None``.
    ValueError
        If any present sheet in either file is missing required columns.
    """
    if tolerances_path is None and locks_path is None:
        raise ValueError(
            "At least one of tolerances_path or locks_path must be provided."
        )

    if print_paths:
        print("Loading balancing config:")
        if tolerances_path is not None:
            print(f"  tolerances: {tolerances_path}")
        if locks_path is not None:
            print(f"  locks: {locks_path}")

    target_tolerances = None
    if tolerances_path is not None:
        target_tolerances = _load_balancing_config_tolerances_from_excel(
            tolerances_path, metadata
        )

    locks = None
    if locks_path is not None:
        locks = _load_balancing_config_locks_from_excel(locks_path, metadata)

    return BalancingConfig(target_tolerances=target_tolerances, locks=locks)
