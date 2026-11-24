"""
Loading, writing and locating SUT files in the legacy Statistics Denmark
national accounts (NR) fixed-width format.

This module is specific to Statistics Denmark: the file layout is hardcoded
and the path helper knows where the final annual SUTs are stored. The general
file formats (parquet, CSV, Excel) are in :mod:`sutlab.io`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from sutlab.io import _PRICE_LAYER_ROLES, _assemble_sut, _format_price_basis
from sutlab.sut import SUT, SUTColumns, SUTMetadata


# Fixed-width layout of the legacy Statistics Denmark SUT file format.
# Character positions are (start, end) with end exclusive. Everything after
# position 140 (status flags, user initials, timestamps) is ignored.
_FWF_KEY_POSITIONS: list[tuple[int, int]] = [
    (0, 7),     # product
    (16, 20),   # transaction
    (30, 36),   # category
]

# Six value fields of 16 characters each, starting at position 44.
# The roles are given in the order the fields appear in the file.
_FWF_VALUE_ROLES: list[str] = [
    "price_basic",
    "wholesale_margins",
    "retail_margins",
    "product_taxes_less_subsidies",
    "vat",
    "price_purchasers",
]
_FWF_VALUE_START = 44
_FWF_VALUE_WIDTH = 16

# Maximum lengths of the key fields (the field plus the blank gap after it).
_FWF_PRODUCT_WIDTH = 7
_FWF_TRANSACTION_WIDTH = 4
_FWF_CATEGORY_WIDTH = 6


def _validate_fwf_columns(cols: SUTColumns) -> None:
    """Check that the metadata columns match the fixed-width format.

    The format has value fields for exactly four price layers, so the metadata
    must define all of them and no other price layer roles.
    """
    missing_roles = [
        role for role in _FWF_VALUE_ROLES if getattr(cols, role) is None
    ]
    if missing_roles:
        raise ValueError(
            f"The fixed-width format has value fields for {_FWF_VALUE_ROLES}, "
            f"but the metadata does not define the role(s): {missing_roles}."
        )

    extra_roles = [
        role for role in _PRICE_LAYER_ROLES
        if role not in _FWF_VALUE_ROLES and getattr(cols, role) is not None
    ]
    if extra_roles:
        raise ValueError(
            f"The metadata defines price layer role(s) {extra_roles} which the "
            f"fixed-width format has no value field for."
        )


def load_sut_from_separated_nr_legacy_fwf(
    id_values: list[str | int],
    paths: list[str | Path],
    metadata: SUTMetadata,
    price_basis: Literal["current_year", "previous_year"],
    *,
    encoding: str = "latin-1",
    print_paths: bool = False,
) -> SUT:
    """
    Load a SUT collection from legacy fixed-width files.

    This is the old Statistics Denmark SUT file format: no header, no id
    column, fixed character positions, and extra columns (status flags, user
    initials, timestamps) after position 140 which are ignored. Each file
    holds both supply and use rows for one collection member (typically one
    year). The corresponding entry in ``id_values`` is added as the id column
    on load. Supply and use rows are split using the ``table`` column of
    ``metadata.classifications.transactions``.

    The layout is fixed and not configurable:

    - characters 0-7: product
    - characters 16-20: transaction
    - characters 30-36: category (blank for many rows)
    - characters 44-140: six value fields of 16 characters each, in the
      order basic prices, wholesale margins, retail margins, taxes less
      subsidies on products, VAT, purchasers' prices

    Columns are named after the actual column names in ``metadata.columns``.
    The metadata must therefore define the roles ``wholesale_margins``,
    ``retail_margins``, ``product_taxes_less_subsidies`` and ``vat``.

    Supply rows only have a value in basic prices; the other value fields are
    blank and end up as NaN (and are dropped from the supply table).

    Rows are sorted by id, product, transaction, category after loading.

    Parameters
    ----------
    id_values : list of str or int
        Id values for each collection member, one per file. The type is
        preserved.
    paths : list of str or Path
        Paths to the files, in the same order as ``id_values``.
    metadata : SUTMetadata
        Metadata for the SUT. ``metadata.classifications.transactions`` must
        be present — it is used to split supply and use rows.
    price_basis : {"current_year", "previous_year"}
        Price basis for the collection.
    encoding : str, optional
        File encoding. Defaults to ``"latin-1"``, which can read any byte
        sequence (the ignored trailing columns may contain non-UTF-8
        characters).
    print_paths : bool, optional
        If ``True``, print the paths being read before loading. Defaults to
        ``False``.

    Returns
    -------
    SUT
        SUT with supply and use DataFrames populated and ``metadata`` set.
        ``balancing_id`` is ``None``.

    Raises
    ------
    ValueError
        If ``id_values`` and ``paths`` have different lengths.
    ValueError
        If ``metadata.classifications.transactions`` is absent.
    ValueError
        If the metadata does not define all four price layer roles used by
        the format.
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
    _validate_fwf_columns(cols)

    if print_paths:
        basis = _format_price_basis(price_basis)
        n = len(paths)
        print(f"Loading SUT ({basis}, {n} member{'s' if n != 1 else ''}):")
        for id_value, path in zip(id_values, paths):
            print(f"  {id_value}: {path}")

    key_names = [cols.product, cols.transaction, cols.category]
    value_names = [getattr(cols, role) for role in _FWF_VALUE_ROLES]

    value_positions = [
        (
            _FWF_VALUE_START + i * _FWF_VALUE_WIDTH,
            _FWF_VALUE_START + (i + 1) * _FWF_VALUE_WIDTH,
        )
        for i in range(len(_FWF_VALUE_ROLES))
    ]
    colspecs = _FWF_KEY_POSITIONS + value_positions
    dtypes = {name: str for name in key_names}
    dtypes.update({name: float for name in value_names})

    frames = []
    for id_value, path in zip(id_values, paths):
        df = pd.read_fwf(
            path,
            colspecs=colspecs,
            header=None,
            names=key_names + value_names,
            dtype=dtypes,
            encoding=encoding,
        )
        # Rows without a product are not data (e.g. a stray trailing line)
        df = df.dropna(subset=[cols.product])
        df.insert(0, cols.id, id_value)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    return _assemble_sut(combined, metadata, price_basis)


def _format_fwf_text_field(
    values: pd.Series,
    width: int,
    field_name: str,
    column_name: str,
) -> pd.Series:
    """Left-align a text column in a field of ``width`` characters.

    Raises if any value is too long for the field.
    """
    text = values.fillna("").astype(str)
    too_long = text[text.str.len() > width]
    if not too_long.empty:
        examples = ", ".join(f"'{v}'" for v in too_long.unique()[:5])
        raise ValueError(
            f"{field_name} values in column '{column_name}' can be at most "
            f"{width} characters in the fixed-width format, but found: {examples}."
        )
    return text


def _format_fwf_value_field(values: pd.Series, column_name: str) -> pd.Series:
    """Round a value column to whole numbers and right-align it in 16 characters.

    NaN is written as 0. Raises if a value does not fit the field.
    """
    rounded = values.fillna(0).round(0).astype("int64")
    text = rounded.astype(str)
    too_wide = text[text.str.len() > _FWF_VALUE_WIDTH]
    if not too_wide.empty:
        examples = ", ".join(f"'{v}'" for v in too_wide.unique()[:5])
        raise ValueError(
            f"Values in column '{column_name}' can be at most "
            f"{_FWF_VALUE_WIDTH} characters wide in the fixed-width format, "
            f"but found: {examples}."
        )
    return text.str.rjust(_FWF_VALUE_WIDTH)


def _build_fwf_lines(
    table: pd.DataFrame,
    cols: SUTColumns,
    value_roles: list[str],
) -> pd.DataFrame:
    """Format the rows of one table as fixed-width lines.

    Returns a DataFrame with the sort keys and a ``line`` column.
    """
    product = _format_fwf_text_field(
        table[cols.product], _FWF_PRODUCT_WIDTH, "Product", cols.product
    )
    transaction = _format_fwf_text_field(
        table[cols.transaction], _FWF_TRANSACTION_WIDTH, "Transaction", cols.transaction
    )
    category = _format_fwf_text_field(
        table[cols.category], _FWF_CATEGORY_WIDTH, "Category", cols.category
    )

    line = (
        product.str.ljust(16)
        + transaction.str.ljust(14)
        + category.str.ljust(14)
    )
    for role in value_roles:
        name = getattr(cols, role)
        line = line + _format_fwf_value_field(table[name], name)

    result = table[[cols.product, cols.transaction, cols.category]].copy()
    result["line"] = line
    return result


def write_sut_to_separated_nr_legacy_fwf(
    sut: SUT,
    id_values: list[str | int],
    paths: list[str | Path],
    *,
    encoding: str = "latin-1",
    print_paths: bool = False,
) -> None:
    """
    Write selected SUT members to legacy fixed-width files.

    One file is written per entry in ``id_values``, in the old Statistics
    Denmark SUT format read by :func:`load_sut_from_separated_nr_legacy_fwf` (see that
    function for the layout). Each file contains the supply and use rows for
    that member, without an id column, sorted by product, transaction,
    category.

    Supply rows only get the basic prices field; the other value fields are
    left blank. Use rows get all six value fields, with NaN written as 0.
    Values are **rounded to whole numbers**, so a use row's layers may no
    longer add up exactly to purchasers' prices after rounding. The extra
    columns after position 140 (status flags, user initials, timestamps) are
    not written.

    Parameters
    ----------
    sut : SUT
        The SUT collection to write. ``sut.metadata`` must be present and
        define exactly the price layer roles ``wholesale_margins``,
        ``retail_margins``, ``product_taxes_less_subsidies`` and ``vat``.
    id_values : list of str or int
        Id values to write, one per output file. Must all be present in the
        SUT.
    paths : list of str or Path
        Output file paths, in the same order as ``id_values``.
    encoding : str, optional
        File encoding. Defaults to ``"latin-1"``.
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
    ValueError
        If the metadata does not match the format's price layers.
    ValueError
        If a product (more than 7 characters), transaction (more than 4),
        category (more than 6) or value (more than 16 characters wide) does not
        fit its field.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to identify the columns for writing."
        )
    if len(id_values) != len(paths):
        raise ValueError(
            f"id_values and paths must have the same length. "
            f"Got {len(id_values)} id values and {len(paths)} paths."
        )

    cols = sut.metadata.columns
    _validate_fwf_columns(cols)

    id_col = cols.id
    available = list(
        pd.concat([sut.supply[id_col], sut.use[id_col]]).unique()
    )
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

    sort_cols = [cols.product, cols.transaction, cols.category]
    for id_value, output_path in zip(id_values, paths):
        supply = sut.supply[sut.supply[id_col] == id_value]
        use = sut.use[sut.use[id_col] == id_value]

        supply_lines = _build_fwf_lines(supply, cols, ["price_basic"])
        use_lines = _build_fwf_lines(use, cols, _FWF_VALUE_ROLES)
        lines = (
            pd.concat([supply_lines, use_lines], ignore_index=True)
            .sort_values(sort_cols, kind="stable")
        )

        text = "".join(line + "\n" for line in lines["line"])
        with open(output_path, "w", encoding=encoding, newline="\n") as file:
            file.write(text)



def make_final_annual_sut_paths(
    years: list[int],
    drive: str,
    price_basis: Literal["current_year", "previous_year"],
) -> list[Path]:
    """
    Build the paths to the final annual SUT files for a list of years.

    The final annual SUTs are stored in the legacy fixed-width format, so the
    paths can be passed to :func:`load_sut_from_separated_nr_legacy_fwf`
    (with ``years`` as the ``id_values``).

    The path for 2019 in current year's prices on drive ``"r"`` is
    ``Path("r:/afstem19/ta/ta19l")``. In previous year's prices the file name ends
    with the previous year's two digits: ``Path("r:/afstem19/ta/ta19f18")``.

    Parameters
    ----------
    years : list of int
        The years to build paths for.
    drive : str
        The drive letter the SUTs are stored on, without a colon (e.g.
        ``"r"``).
    price_basis : {"current_year", "previous_year"}
        Which of the two files to point to for each year.

    Returns
    -------
    list of Path
        One path per year, in the same order as ``years``.

    Raises
    ------
    ValueError
        If ``price_basis`` is not ``"current_year"`` or ``"previous_year"``.
    """
    if price_basis not in ("current_year", "previous_year"):
        raise ValueError(
            f"price_basis must be 'current_year' or 'previous_year', "
            f"got '{price_basis}'."
        )

    paths = []
    for year in years:
        yy = str(year)[-2:]
        path = f"{drive}:/afstem{yy}/ta/ta{yy}"
        if price_basis == "current_year":
            path += "l"
        else:
            path += "f" + str(year - 1)[-2:]
        paths.append(Path(path))
    return paths
