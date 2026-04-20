"""
TablesComparison: element-wise comparison between two inspection result objects of the same class.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd


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
    display_unit : float or None
        Display unit applied to absolute-value tables in ``diff``. Copied
        from the object ``inspect_tables_comparison`` was called on.
    rel_base : int
        Relative-value display base (100, 1000, or 10000). Copied from
        the object ``inspect_tables_comparison`` was called on.
    """

    diff: Any
    rel: Any
    display_unit: float | None = None
    rel_base: int = 100

    def set_display_unit(self, display_unit: float | None) -> "TablesComparison":
        """Return a copy with ``display_unit`` updated on this object and both inner objects.

        Only affects the ``diff`` inner object (absolute values). The ``rel``
        inner object is unaffected because relative values are not divided by
        a display unit.

        Parameters
        ----------
        display_unit : float or None
            Must be a positive power of 10 (e.g. 1000, 1_000_000). ``None``
            disables division.
        """
        if display_unit is not None:
            log = math.log10(display_unit) if display_unit > 0 else float("nan")
            if not (display_unit > 0 and abs(log - round(log)) < 1e-9):
                raise ValueError(
                    f"display_unit must be a positive power of 10 "
                    f"(e.g. 1_000, 1_000_000). Got {display_unit}."
                )
        new_diff = dataclasses.replace(self.diff, display_unit=display_unit)
        new_rel = dataclasses.replace(self.rel, display_unit=display_unit)
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, display_unit=display_unit)

    def set_rel_base(self, rel_base: int) -> "TablesComparison":
        """Return a copy with ``rel_base`` updated on this object and both inner objects.

        Parameters
        ----------
        rel_base : int
            Must be 100, 1000, or 10000.
        """
        if rel_base not in (100, 1000, 10000):
            raise ValueError(
                f"rel_base must be 100, 1000, or 10000. Got {rel_base}."
            )
        new_diff = dataclasses.replace(self.diff, rel_base=rel_base)
        new_rel = dataclasses.replace(self.rel, rel_base=rel_base)
        return dataclasses.replace(self, diff=new_diff, rel=new_rel, rel_base=rel_base)


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
