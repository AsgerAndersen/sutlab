"""DisplayConfiguration: per-inspection display state shared by all inspection classes.

All styled properties on inspection result objects apply the display configuration
before rendering. ``.data`` always returns the full, unfiltered data.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field


@dataclass
class DisplayConfiguration:
    """Holds display preferences and per-class constraints for an inspection result.

    Attributes
    ----------
    display_unit : float or None
        Positive power of 10 to divide absolute values by before display.
        ``None`` disables division.
    rel_base : int
        Base for relative (percentage) values: 100 (%), 1000 (‰), or 10000 (‱).
    decimals : int
        Number of decimal places in formatted numbers and percentages.
    display_index : dict[str, list]
        Mapping of index level name → list of values/patterns to keep.
        Applied additively across ``set_display_index`` calls (same level
        merges). Pattern syntax: exact codes, wildcards (``*``), ranges
        (``:``), negation (``~``). Protected index values are always included.
    sort_column : str or None
        Column name to sort rows by. Applied within each table's
        ``index_grouping`` groups. Protected rows are excluded from sorting
        and kept at the end of each group.
    sort_ascending : bool
        Direction for ``sort_column``. Default ``False`` (descending).
    display_values_n_largest : tuple[int, str] or None
        ``(n, column)`` — keep only the n rows with the largest values for
        the given column within each ``index_grouping`` group. Protected rows
        are always kept.
    protected_tables : frozenset[str]
        Table field names excluded from all display operations. Hard-coded
        per class; preserved by ``set_display_configuration_to_defaults``.
    protected_index_values : dict[str, list]
        Index level name → values always shown, pinned to end of their group.
        Hard-coded per class; preserved by ``set_display_configuration_to_defaults``.
    index_grouping : dict[str, list[str] or None]
        Table field name → index levels defining groups within which
        ``sort_column`` and ``display_values_n_largest`` operate. ``None``
        means the whole table is one group (global). Hard-coded per class;
        preserved by ``set_display_configuration_to_defaults``.
    """

    # User-settable
    display_unit: float | None = None
    rel_base: int = 100
    decimals: int = 1
    display_index: dict[str, list] = field(default_factory=dict)
    sort_column: str | None = None
    sort_ascending: bool = False
    display_values_n_largest: tuple[int, str] | None = None

    # Hard-coded per class (preserved by reset)
    protected_tables: frozenset = field(default_factory=frozenset)
    protected_index_values: dict[str, list] = field(default_factory=dict)
    index_grouping: dict[str, list | None] = field(default_factory=dict)


def _validate_display_unit(display_unit: float | None) -> None:
    if display_unit is not None:
        log = math.log10(display_unit) if display_unit > 0 else float("nan")
        if not (display_unit > 0 and abs(log - round(log)) < 1e-9):
            raise ValueError(
                f"display_unit must be a positive power of 10 "
                f"(e.g. 1_000, 1_000_000). Got {display_unit}."
            )


def _validate_rel_base(rel_base: int) -> None:
    if rel_base not in (100, 1000, 10000):
        raise ValueError(
            f"rel_base must be 100, 1000, or 10000. Got {rel_base}."
        )


def _validate_decimals(decimals: int) -> None:
    if not isinstance(decimals, int) or decimals < 0:
        raise ValueError(
            f"decimals must be a non-negative integer. Got {decimals!r}."
        )


def _cfg_set_display_unit(config: DisplayConfiguration, display_unit: float | None) -> DisplayConfiguration:
    _validate_display_unit(display_unit)
    return dataclasses.replace(config, display_unit=display_unit)


def _cfg_set_display_rel_base(config: DisplayConfiguration, rel_base: int) -> DisplayConfiguration:
    _validate_rel_base(rel_base)
    return dataclasses.replace(config, rel_base=rel_base)


def _cfg_set_display_decimals(config: DisplayConfiguration, decimals: int) -> DisplayConfiguration:
    _validate_decimals(decimals)
    return dataclasses.replace(config, decimals=decimals)


def _cfg_set_display_index(
    config: DisplayConfiguration,
    level: str,
    values,
) -> DisplayConfiguration:
    """Return a copy with the given level's values merged (union) into display_index."""
    new_values = list(values) if isinstance(values, list) else [values]
    existing = list(config.display_index.get(level, []))
    merged = existing + [v for v in new_values if v not in existing]
    new_display_index = {**config.display_index, level: merged}
    return dataclasses.replace(config, display_index=new_display_index)


def _cfg_set_display_sort_column(
    config: DisplayConfiguration,
    column: str | None,
    ascending: bool = False,
) -> DisplayConfiguration:
    return dataclasses.replace(config, sort_column=column, sort_ascending=ascending)


def _cfg_set_display_values_n_largest(
    config: DisplayConfiguration,
    n: int,
    column: str,
) -> DisplayConfiguration:
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"n must be a positive integer. Got {n!r}.")
    return dataclasses.replace(config, display_values_n_largest=(n, column))


def _cfg_reset_to_defaults(config: DisplayConfiguration) -> DisplayConfiguration:
    """Return a copy with user-settable fields at defaults; hard-coded fields preserved."""
    return DisplayConfiguration(
        protected_tables=config.protected_tables,
        protected_index_values=config.protected_index_values,
        index_grouping=config.index_grouping,
    )
