"""
TablesComparison: element-wise comparison between two inspection result objects of the same class.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ._display_config import DisplayConfiguration


@dataclass
class TablesComparison:
    """
    Result of ``inspect_tables_comparison`` called on an inspection result object.

    Contains two inspection objects of the same class as the one
    ``inspect_tables_comparison`` was called on:

    - ``.diff`` — element-wise difference (``self − other``).
    - ``.rel`` — relative change (``(self − other) / other``), formatted
      as percentages in styled views.

    Styled views are accessed directly on ``.diff`` and ``.rel`` (e.g.
    ``comparison.diff.balance``). Raw DataFrames are accessed via the
    ``.data`` attribute on each (e.g. ``comparison.diff.data.balance``).

    Index alignment uses an outer join: rows present in only one object
    contribute ``NaN`` on the missing side. For ``.diff``, this means the
    difference is ``NaN`` for unmatched rows. For ``.rel``, division by zero
    or by ``NaN`` yields ``NaN``.

    Attributes
    ----------
    diff : inspection result object
        Same class as the object ``inspect_tables_comparison`` was called on.
        Each table holds the element-wise difference (``self − other``).
    rel : inspection result object
        Same class as ``diff``. Each table holds the relative change:
        ``(self − other) / other``. Division by zero yields ``NaN``.
        All numeric values are formatted as percentages in styled views.
    display_configuration : DisplayConfiguration
        Display settings applied to both inner objects. Copied from the
        object ``inspect_tables_comparison`` was called on.
    """

    diff: Any
    rel: Any
    display_configuration: DisplayConfiguration = field(default_factory=DisplayConfiguration)

    def set_display_unit(self, display_unit: float | None) -> "TablesComparison":
        """Return a copy with ``display_unit`` updated on this object and both inner objects.

        Parameters
        ----------
        display_unit : float or None
            Must be a positive power of 10 (e.g. 1000, 1_000_000). ``None``
            disables division.
        """
        new_diff = self.diff.set_display_unit(display_unit)
        new_rel = self.rel.set_display_unit(display_unit)
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def set_display_rel_base(self, rel_base: int) -> "TablesComparison":
        """Return a copy with ``rel_base`` updated on this object and both inner objects.

        Parameters
        ----------
        rel_base : int
            Must be 100, 1000, or 10000.
        """
        new_diff = self.diff.set_display_rel_base(rel_base)
        new_rel = self.rel.set_display_rel_base(rel_base)
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def set_display_decimals(self, decimals: int) -> "TablesComparison":
        """Return a copy with ``decimals`` updated on this object and both inner objects.

        Parameters
        ----------
        decimals : int
            Number of decimal places in formatted numbers and percentages.
            Must be a non-negative integer.
        """
        new_diff = self.diff.set_display_decimals(decimals)
        new_rel = self.rel.set_display_decimals(decimals)
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def set_display_index(self, level: str, values: list) -> "TablesComparison":
        """Return a copy with the display index filter updated on both inner objects.

        Parameters
        ----------
        level : str
            Index level name to filter on.
        values : list
            Values to keep at that level (additive — previous values retained).
        """
        new_diff = self.diff.set_display_index(level, values)
        new_rel = self.rel.set_display_index(level, values)
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def set_display_sort_column(self, column: str, ascending: bool = False) -> "TablesComparison":
        """Return a copy with the sort column updated on both inner objects.

        Parameters
        ----------
        column : str
            Column name to sort by.
        ascending : bool
            Sort direction. Default ``False`` (descending).
        """
        new_diff = self.diff.set_display_sort_column(column, ascending)
        new_rel = self.rel.set_display_sort_column(column, ascending)
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def set_display_values_n_largest(self, n: int, column: str) -> "TablesComparison":
        """Return a copy with n-largest filter updated on both inner objects.

        Parameters
        ----------
        n : int
            Number of largest rows to keep per group.
        column : str
            Column to rank by.
        """
        new_diff = self.diff.set_display_values_n_largest(n, column)
        new_rel = self.rel.set_display_values_n_largest(n, column)
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def set_display_configuration_to_defaults(self) -> "TablesComparison":
        """Return a copy with display settings reset to defaults on both inner objects."""
        new_diff = self.diff.set_display_configuration_to_defaults()
        new_rel = self.rel.set_display_configuration_to_defaults()
        new_cfg = new_diff.display_configuration
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_configuration=new_cfg)

    def get_index_values(self, table: str, levels: str | list[str], *, as_list: bool = False) -> pd.DataFrame | list:
        """Return unique index value combinations using dot notation to address inner tables.

        Use ``"diff.<table>"`` or ``"rel.<table>"`` to address a table within
        the inner ``.diff`` or ``.rel`` inspection objects. The display
        configuration of the addressed inner object is applied before extracting
        values.

        Parameters
        ----------
        table : str
            Dot-prefixed table name, e.g. ``"diff.balance"`` or
            ``"rel.supply"``.
        levels : str or list of str
            One or more index level names whose unique value combinations to return.
        as_list : bool, default False
            If ``True``, return a plain list of unique values. Requires exactly
            one level; raises ``ValueError`` if more than one level is requested.

        Returns
        -------
        pd.DataFrame or list
            When ``as_list=False``: one column per requested level, unique
            combinations only. Rows where all values are ``""`` or ``NaN`` are
            dropped. Index is a default RangeIndex.
            When ``as_list=True``: a plain list of unique values for the single
            requested level.

        Raises
        ------
        ValueError
            If ``table`` does not use dot notation, if the prefix is not
            ``"diff"`` or ``"rel"``, if the inner object raises, or if
            ``as_list=True`` and more than one level is requested.
        """
        if "." not in table:
            raise ValueError(
                f"Table name for TablesComparison must use dot notation: "
                f"'diff.<table>' or 'rel.<table>'. Got {table!r}."
            )
        attr, table_name = table.split(".", 1)
        if attr not in ("diff", "rel"):
            raise ValueError(
                f"First part of dot-notation table name must be 'diff' or 'rel'. "
                f"Got {attr!r}."
            )
        return getattr(self, attr).get_index_values(table_name, levels, as_list=as_list)


def _compute_comparison_table_fields(
    self_data,
    other_data,
) -> tuple[dict, dict]:
    """Compute diff and rel field dicts from two inspection data objects.

    For each DataFrame field in ``self_data``:

    - If either side is ``None``, the result for that field is ``None``.
    - If either side is not a ``pd.DataFrame``, the result is an empty
      ``pd.DataFrame``.
    - If both are empty DataFrames (no rows or no columns), the result is
      an empty ``pd.DataFrame``.
    - Otherwise, DataFrames are aligned with an outer join. The diff is
      ``self − other``; the rel is ``(self − other) / other``. Infinite
      values (non-zero divided by zero) are replaced with ``NaN``.

    Parameters
    ----------
    self_data : inspection data object
        The ``.data`` attribute of the object ``inspect_tables_comparison``
        was called on.
    other_data : inspection data object
        The ``.data`` attribute of the ``other`` argument.

    Returns
    -------
    diff_fields : dict
        Field name → diff DataFrame (or ``None``).
    rel_fields : dict
        Field name → rel DataFrame (or ``None``).
    """
    diff_fields: dict = {}
    rel_fields: dict = {}

    for f in dataclasses.fields(self_data):
        self_val = getattr(self_data, f.name)
        other_val = getattr(other_data, f.name)

        if self_val is None or other_val is None:
            diff_fields[f.name] = None
            rel_fields[f.name] = None
            continue

        if not isinstance(self_val, pd.DataFrame) or not isinstance(other_val, pd.DataFrame):
            diff_fields[f.name] = pd.DataFrame()
            rel_fields[f.name] = pd.DataFrame()
            continue

        if (self_val.empty and other_val.empty) or (self_val.columns.empty and other_val.columns.empty):
            diff_fields[f.name] = pd.DataFrame()
            rel_fields[f.name] = pd.DataFrame()
            continue

        aligned_self, aligned_other = self_val.align(other_val, join="outer")
        diff_df = aligned_self - aligned_other
        rel_df = diff_df / aligned_other
        rel_df = rel_df.replace([float("inf"), float("-inf")], float("nan"))
        diff_fields[f.name] = diff_df
        rel_fields[f.name] = rel_df

    return diff_fields, rel_fields
