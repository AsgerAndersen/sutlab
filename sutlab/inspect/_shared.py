"""
Shared helpers used by multiple inspect modules.
"""

from __future__ import annotations

import dataclasses
from copy import copy
from pathlib import Path
from typing import Any

import openpyxl.utils
import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.inspect._style import _REL_BASE_SYMBOLS


def _sort_by_id_value(
    df: pd.DataFrame,
    group_levels: list[str],
    sort_id,
) -> pd.DataFrame:
    """Sort non-total rows within groups by sort_id column value, descending.

    Within each group (defined by ``group_levels``), rows where
    ``transaction == ""`` are treated as total/summary rows and kept at the
    end. All other rows are sorted by the value in the ``sort_id`` column,
    largest first. Row order between groups is preserved.

    Parameters
    ----------
    df : pd.DataFrame
        Wide-format inspection table with a MultiIndex containing a
        ``"transaction"`` level and id values as columns.
    group_levels : list of str
        Index level names defining the groups within which rows are sorted.
        Use ``["product"]`` for product detail tables,
        ``["industry"]`` for industry detail tables, and
        ``["product", "price_layer"]`` for price layer tables.
    sort_id : hashable
        Column name (id value, e.g. ``2021``) to sort by.

    Returns
    -------
    pd.DataFrame
        Same DataFrame with rows reordered within each group.
    """
    if df.empty:
        return df

    trans_vals = df.index.get_level_values("transaction")
    total_mask = trans_vals == ""

    level_arrays = {level: df.index.get_level_values(level) for level in group_levels}
    group_tuples = list(dict.fromkeys(
        zip(*[level_arrays[level] for level in group_levels])
    ))

    blocks = []
    for group_key in group_tuples:
        group_mask = level_arrays[group_levels[0]] == group_key[0]
        for level, key in zip(group_levels[1:], group_key[1:]):
            group_mask = group_mask & (level_arrays[level] == key)

        data_rows = df[group_mask & ~total_mask]
        total_rows = df[group_mask & total_mask]

        sorted_data = data_rows.sort_values(by=sort_id, ascending=False)
        blocks.append(pd.concat([sorted_data, total_rows]))

    return pd.concat(blocks)


def _make_sheet_name(field_name: str) -> str:
    """Convert a dataclass field name to an Excel sheet name.

    Excel sheet names are limited to 31 characters. If ``field_name`` is 31
    characters or fewer it is returned unchanged. If it exceeds 31 characters,
    each underscore-separated segment is truncated to its first three
    characters and the segments are rejoined with underscores.

    Parameters
    ----------
    field_name : str
        The dataclass field name to convert.

    Returns
    -------
    str
        A string of at most 31 characters.
    """
    if len(field_name) <= 31:
        return field_name
    segments = field_name.split("_")
    return "_".join(s[:3] for s in segments)


# Field name suffixes that indicate all data columns hold fraction values that
# should be displayed as percentages in Excel (0.05 → 5.0 %).
_PERCENTAGE_FIELD_SUFFIXES = ("_distribution", "_rates", "_growth")

# Excel number format strings used for data cells.
_EXCEL_NUMBER_FORMAT = "#,##0.0"
_EXCEL_PERCENTAGE_FORMAT = "0.0%"

# Default width applied to value (non-index) columns.  Wide enough to
# comfortably show a formatted number like "1,234,567.8" (11 chars) plus
# a small margin.
_EXCEL_VALUE_COLUMN_WIDTH = 13


def _apply_number_formats(
    ws,
    df: pd.DataFrame,
    field_name: str,
    display_unit: float | None = None,
    rel_base: int = 100,
) -> None:
    """Apply Excel number formats to the data cells of a written worksheet.

    The format applied to each cell depends on the field name and column name:

    - If ``field_name`` ends with ``_distribution``, ``_rates``, or ``_growth``
      all data cells receive the percentage format (``0.0%``).
    - Otherwise data cells receive the number format (``#,##0.0``), except
      columns whose name starts with ``rel_``, which receive ``0.0%``.

    Non-numeric cells (strings, ``None``) are left unchanged.  Header rows
    and index columns are skipped.

    Parameters
    ----------
    ws : openpyxl.worksheet.worksheet.Worksheet
        The worksheet to modify, in place.
    df : pd.DataFrame
        The DataFrame that was written to ``ws``.  Used to determine the
        number of header rows (``df.columns.nlevels``) and index columns
        (``df.index.nlevels``), and to identify ``rel_`` column positions.
    field_name : str
        The dataclass field name corresponding to this sheet (e.g.
        ``"balance_distribution"``).  Drives the all-percentage detection.
    """
    n_header_rows = df.columns.nlevels
    n_index_cols = df.index.nlevels
    data_cols = list(df.columns)

    is_all_percentage = field_name.endswith(_PERCENTAGE_FIELD_SUFFIXES)

    # For "mostly number" tables, track which data-column positions carry
    # relative values and should be formatted as percentages instead.
    rel_col_positions: set[int] = set()
    if not is_all_percentage:
        rel_col_positions = {
            i for i, col in enumerate(data_cols)
            if isinstance(col, str) and col.startswith("rel_")
        }

    for row in ws.iter_rows(
        min_row=n_header_rows + 1,
        min_col=n_index_cols + 1,
    ):
        for col_offset, cell in enumerate(row):
            if not isinstance(cell.value, (int, float)):
                continue
            if is_all_percentage or col_offset in rel_col_positions:
                if rel_base == 100:
                    cell.number_format = _EXCEL_PERCENTAGE_FORMAT  # Excel auto-multiplies by 100
                else:
                    symbol = _REL_BASE_SYMBOLS[rel_base]
                    cell.value = cell.value * rel_base
                    cell.number_format = f'0.0"{symbol}"'
            else:
                cell.number_format = _EXCEL_NUMBER_FORMAT
                if display_unit is not None:
                    cell.value = cell.value / display_unit


def _apply_bold_headers(ws, df: pd.DataFrame) -> None:
    """Make all cells in the header rows bold.

    After ``df.to_excel()``, the first ``df.columns.nlevels`` rows hold the
    column headers (including any index-level name cells in those rows).
    This function sets ``bold=True`` on every cell in those rows while
    preserving all other font properties already applied by the Styler.

    Parameters
    ----------
    ws : openpyxl.worksheet.worksheet.Worksheet
        The worksheet to modify, in place.
    df : pd.DataFrame
        The DataFrame that was written to ``ws``.  Used to determine the
        number of header rows (``df.columns.nlevels``).
    """
    n_header_rows = df.columns.nlevels
    for row in ws.iter_rows(min_row=1, max_row=n_header_rows):
        for cell in row:
            font = copy(cell.font)
            font.bold = True
            cell.font = font


def _set_value_column_widths(ws, n_index_cols: int, n_data_cols: int) -> None:
    """Set a fixed default width on all value (non-index) columns.

    Parameters
    ----------
    ws : openpyxl.worksheet.worksheet.Worksheet
        The worksheet to modify, in place.
    n_index_cols : int
        Number of leading columns that represent index levels (skipped).
    n_data_cols : int
        Number of data columns to widen.
    """
    for col_idx in range(n_index_cols + 1, n_index_cols + n_data_cols + 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = _EXCEL_VALUE_COLUMN_WIDTH


def _fit_index_column_widths(ws, n_index_cols: int) -> None:
    """Set the width of index-level columns to fit their widest cell value.

    Iterates the first ``n_index_cols`` columns in the worksheet, measures
    the string length of every cell value (including the header row), and
    sets the column width to the maximum length plus a small padding of two
    characters.

    Parameters
    ----------
    ws : openpyxl.worksheet.worksheet.Worksheet
        The worksheet to modify, in place.
    n_index_cols : int
        Number of leading columns that represent index levels.
    """
    for col_idx in range(1, n_index_cols + 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        max_len = 0
        for cell in ws[col_letter]:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max_len + 2


def _build_growth_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build year-on-year growth table: change relative to the previous year.

    Each value is ``(current - previous) / previous``, so a 5% increase gives
    ``0.05``. The first id column is ``NaN`` throughout. Division by zero also
    yields ``NaN``. Infinite values (from dividing a non-zero change by zero)
    are replaced with ``NaN``.

    Row filtering (e.g. dropping Balance rows) is the caller's responsibility.

    Parameters
    ----------
    df : pd.DataFrame
        Wide-format table with id values as columns.

    Returns
    -------
    pd.DataFrame
        Same shape as ``df`` with growth rates. Empty if ``df`` is empty.
    """
    if df.empty:
        return pd.DataFrame()

    floats = df.astype(float)
    previous = floats.shift(axis=1)
    growth = (floats - previous).div(previous)
    growth = growth.replace([float("inf"), float("-inf")], float("nan"))
    return growth


def _write_inspection_to_excel(inspection_obj: Any, path: str | Path, display_unit: float | None = None, rel_base: int = 100) -> None:
    """Write all non-None tables in an inspection result to an Excel file.

    Each field on ``inspection_obj.data`` that holds a
    :class:`~pandas.DataFrame` is written to a separate sheet. Fields whose
    value is not a DataFrame (e.g. ``None`` or internal non-table attributes)
    are skipped silently. Fields whose value is an empty DataFrame are written
    as empty sheets.

    Where a matching styled property exists on ``inspection_obj``, it is used
    to write the sheet so that colours, number formats, and other Styler
    formatting are preserved in Excel. Otherwise the raw DataFrame is written.

    After writing each sheet, the width of the index-level columns is fitted
    to the widest cell value in that column (including the header row).

    Sheet names are derived from the field name; names exceeding Excel's
    31-character limit are shortened using :func:`_make_sheet_name`.

    Parameters
    ----------
    inspection_obj : inspection result object
        Any inspection result with a ``.data`` attribute that is a dataclass
        (e.g. :class:`~sutlab.inspect.ProductInspection`).
    path : str or Path
        Destination ``.xlsx`` file path.
    """
    path = Path(path)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for f in dataclasses.fields(inspection_obj.data):
            raw = getattr(inspection_obj.data, f.name)
            if not isinstance(raw, pd.DataFrame):
                continue

            sheet_name = _make_sheet_name(f.name)

            try:
                styled = getattr(inspection_obj, f.name, None)
            except Exception:
                styled = None

            if isinstance(styled, Styler):
                try:
                    styled.to_excel(writer, sheet_name=sheet_name)
                except Exception:
                    # Styling failed (e.g. DataFrame structure doesn't match
                    # what the style function expects). Fall back to raw data.
                    raw.to_excel(writer, sheet_name=sheet_name)
            else:
                raw.to_excel(writer, sheet_name=sheet_name)

            ws = writer.sheets[sheet_name]
            _apply_bold_headers(ws, raw)
            _fit_index_column_widths(ws, raw.index.nlevels)
            _set_value_column_widths(ws, raw.index.nlevels, len(raw.columns))
            _apply_number_formats(ws, raw, f.name, display_unit, rel_base)
