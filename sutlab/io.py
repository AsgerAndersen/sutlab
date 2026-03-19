"""
I/O functions for loading SUT metadata from Excel files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sutlab.sut import SUTClassifications, SUTColumns, SUTMetadata


_REQUIRED_ROLES = {
    "id",
    "product",
    "transaction",
    "category",
    "price_basic",
    "price_purchasers",
}

_OPTIONAL_ROLES = {
    "trade_margins",
    "wholesale_margins",
    "retail_margins",
    "transport_margins",
    "product_taxes",
    "product_subsidies",
    "product_taxes_less_subsidies",
    "vat",
}

_ALL_ROLES = _REQUIRED_ROLES | _OPTIONAL_ROLES

_CLASSIFICATION_SHEET_COLUMNS = {
    "classifications":        ("dimension", "classification"),
    "products":               ("code", "name"),
    "transactions":           ("code", "name"),
    "industries":             ("code", "name"),
    "individual_consumption": ("code", "name"),
    "collective_consumption": ("code", "name"),
}


def _strip_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns in a DataFrame."""
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    return df


def _load_classification_sheet(
    sheets: dict[str, pd.DataFrame],
    sheet_name: str,
    expected_cols: tuple[str, ...],
) -> pd.DataFrame | None:
    """
    Return the named sheet projected to expected_cols, or None if not present.

    Raises ValueError if the sheet exists but is missing expected columns.
    """
    if sheet_name not in sheets:
        return None

    df = sheets[sheet_name]
    missing_cols = [c for c in expected_cols if c not in df.columns]

    if missing_cols:
        missing_str = ", ".join(f"'{c}'" for c in missing_cols)
        found_str = ", ".join(f"'{c}'" for c in df.columns)
        raise ValueError(
            f"Sheet '{sheet_name}' must have columns "
            f"{', '.join(repr(c) for c in expected_cols)}. "
            f"Missing: {missing_str}. Found: {found_str}."
        )

    return df[list(expected_cols)]


def load_metadata_columns_from_excel(path: str | Path) -> SUTColumns:
    """
    Load a :class:`~sutlab.sut.SUTColumns` from a two-column Excel file.

    The file must have a ``column`` column (the actual DataFrame column name)
    and a ``role`` column (the conceptual role from the fixed list). All six
    required roles must be present; optional roles missing from the file are
    set to ``None``. Leading and trailing whitespace is stripped from all
    values automatically.

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
        If the file is missing the ``column`` or ``role`` headers.
    ValueError
        If a role value is not in the list of valid roles.
    ValueError
        If a role appears more than once.
    ValueError
        If any required role is absent.
    """
    path = Path(path)
    df = pd.read_excel(path, dtype=str)
    df = _strip_string_columns(df)

    missing_headers = {"column", "role"} - set(df.columns)
    if missing_headers:
        missing_str = ", ".join(f"'{c}'" for c in sorted(missing_headers))
        found_str = ", ".join(f"'{c}'" for c in df.columns)
        raise ValueError(
            f"Columns file must have 'column' and 'role' headers. "
            f"Missing: {missing_str}. Found: {found_str}."
        )

    role_to_column: dict[str, str] = {}

    for _, row in df.iterrows():
        role = row["role"]
        column = row["column"]

        if role not in _ALL_ROLES:
            valid_str = ", ".join(sorted(_ALL_ROLES))
            raise ValueError(
                f"Unknown role '{role}'. Valid roles are: {valid_str}."
            )

        if role in role_to_column:
            raise ValueError(
                f"Role '{role}' appears more than once in the columns file."
            )

        role_to_column[role] = column

    missing_required = _REQUIRED_ROLES - set(role_to_column)
    if missing_required:
        missing_str = ", ".join(f"'{r}'" for r in sorted(missing_required))
        required_str = ", ".join(sorted(_REQUIRED_ROLES))
        raise ValueError(
            f"Missing required roles: {missing_str}. "
            f"Required roles are: {required_str}."
        )

    return SUTColumns(
        id=role_to_column["id"],
        product=role_to_column["product"],
        transaction=role_to_column["transaction"],
        category=role_to_column["category"],
        price_basic=role_to_column["price_basic"],
        price_purchasers=role_to_column["price_purchasers"],
        trade_margins=role_to_column.get("trade_margins"),
        wholesale_margins=role_to_column.get("wholesale_margins"),
        retail_margins=role_to_column.get("retail_margins"),
        transport_margins=role_to_column.get("transport_margins"),
        product_taxes=role_to_column.get("product_taxes"),
        product_subsidies=role_to_column.get("product_subsidies"),
        product_taxes_less_subsidies=role_to_column.get("product_taxes_less_subsidies"),
        vat=role_to_column.get("vat"),
    )


def load_metadata_classifications_from_excel(path: str | Path) -> SUTClassifications:
    """
    Load a :class:`~sutlab.sut.SUTClassifications` from a multi-sheet Excel file.

    Each sheet is optional — omit any sheet you do not have. Sheets with names
    not in the known list are ignored. Leading and trailing whitespace is
    stripped from all values automatically.

    Expected sheets and their columns:

    - ``classifications``: ``dimension``, ``classification``
    - ``products``: ``code``, ``name``
    - ``transactions``: ``code``, ``name``
    - ``industries``: ``code``, ``name``
    - ``individual_consumption``: ``code``, ``name``
    - ``collective_consumption``: ``code``, ``name``

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
        If a present sheet is missing its expected columns.
    """
    path = Path(path)
    all_sheets: dict[str, pd.DataFrame] = pd.read_excel(path, sheet_name=None, dtype=str)

    for sheet_name in all_sheets:
        all_sheets[sheet_name] = _strip_string_columns(all_sheets[sheet_name])

    classification_names = _load_classification_sheet(
        all_sheets, "classifications", ("dimension", "classification")
    )
    products = _load_classification_sheet(
        all_sheets, "products", ("code", "name")
    )
    transactions = _load_classification_sheet(
        all_sheets, "transactions", ("code", "name")
    )
    industries = _load_classification_sheet(
        all_sheets, "industries", ("code", "name")
    )
    individual_consumption = _load_classification_sheet(
        all_sheets, "individual_consumption", ("code", "name")
    )
    collective_consumption = _load_classification_sheet(
        all_sheets, "collective_consumption", ("code", "name")
    )

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
    classifications_path: str | Path | None = None,
) -> SUTMetadata:
    """
    Load a :class:`~sutlab.sut.SUTMetadata` from Excel files.

    Parameters
    ----------
    columns_path : str or Path
        Path to the columns Excel file. See
        :func:`load_metadata_columns_from_excel`.
    classifications_path : str or Path or None
        Path to the classifications Excel file. If ``None``, the returned
        ``SUTMetadata`` will have ``classifications=None``. See
        :func:`load_metadata_classifications_from_excel`.

    Returns
    -------
    SUTMetadata
    """
    columns = load_metadata_columns_from_excel(columns_path)

    if classifications_path is not None:
        classifications = load_metadata_classifications_from_excel(classifications_path)
    else:
        classifications = None

    return SUTMetadata(columns=columns, classifications=classifications)
