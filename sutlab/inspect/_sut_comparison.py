"""
inspect_sut_comparison: row-level differences between two SUT objects.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _filter_sut_by_ids, _filter_sut_by_column
from sutlab.inspect._style import (
    _style_comparison_table,
    _style_comparison_layers_table,
    _style_summary_table,
)


@dataclass
class SUTComparisonData:
    """Raw DataFrames underlying a :class:`SUTComparisonInspection`.

    Use this directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding properties on
    :class:`SUTComparisonInspection` once styling is added.

    Attributes
    ----------
    supply : pd.DataFrame
        Row-level comparison of supply at basic prices. One row per
        (id, product, transaction, category) combination present in
        either SUT. Columns: ``before_{price_basic}``,
        ``after_{price_basic}``, ``diff_{price_basic}``,
        ``rel_{price_basic}``. Only rows where ``abs(diff) > diff_tolerance``
        or ``abs(rel) > rel_tolerance`` are included; rows that appear in
        only one SUT are always included unless ``filter_nan_as_zero=True``
        suppresses the NaN-vs-zero cases.
    use_basic : pd.DataFrame
        Row-level comparison of use at basic prices. Same structure as
        ``supply`` but drawn from the use DataFrames.
    use_purchasers : pd.DataFrame
        Row-level comparison of use at purchasers' prices. Columns:
        ``before_{price_purchasers}``, ``after_{price_purchasers}``,
        ``diff_{price_purchasers}``, ``rel_{price_purchasers}``.
    use_price_layers : pd.DataFrame
        Long-format comparison of all price layer columns. One row per
        (id, product, transaction, category, price_layer) combination that
        differs beyond tolerance. The ``price_layer`` index level holds the
        actual column name (e.g. ``"vat"``). Value columns: ``before``,
        ``after``, ``diff``, ``rel``.
    balancing_targets_supply : pd.DataFrame or None
        Row-level comparison of supply balancing targets at basic prices.
        Same column structure as ``supply`` but indexed on
        (id, transaction, category) — no product dimension. ``None`` when
        either SUT has no balancing targets.
    balancing_targets_use_basic : pd.DataFrame or None
        Row-level comparison of use balancing targets at basic prices.
        ``None`` when either SUT has no balancing targets.
    balancing_targets_use_purchasers : pd.DataFrame or None
        Row-level comparison of use balancing targets at purchasers' prices.
        ``None`` when either SUT has no balancing targets.
    balancing_targets_use_price_layers : pd.DataFrame or None
        Long-format comparison of use balancing target price layer columns.
        Indexed on (id, transaction, category, price_layer). ``None`` when
        either SUT has no balancing targets.
    summary : pd.DataFrame
        One row per comparison table. Index is the table name; column is
        ``n_differences`` (the number of rows in that table). Balancing
        targets rows are omitted when either SUT has no balancing targets.
    """

    supply: pd.DataFrame
    use_basic: pd.DataFrame
    use_purchasers: pd.DataFrame
    use_price_layers: pd.DataFrame
    balancing_targets_supply: pd.DataFrame | None
    balancing_targets_use_basic: pd.DataFrame | None
    balancing_targets_use_purchasers: pd.DataFrame | None
    balancing_targets_use_price_layers: pd.DataFrame | None
    summary: pd.DataFrame


@dataclass
class SUTComparisonInspection:
    """
    Result of :func:`inspect_sut_comparison`.

    Raw DataFrames are available under ``result.data``.

    Attributes
    ----------
    data : SUTComparisonData
        Raw DataFrames. See :class:`SUTComparisonData` for table structures.

    Notes
    -----
    The index of each table contains the key columns
    (``id``, ``product``, ``transaction``, ``category``). When classification
    tables are available in the metadata, each key column is followed by a
    ``{col}_txt`` companion level with the human-readable label. The
    ``use_price_layers`` table has an additional ``price_layer`` index level
    (no text companion) after the category levels.
    """

    data: SUTComparisonData

    def _rel_col(self, df: pd.DataFrame) -> str:
        return next((c for c in df.columns if c.startswith("rel_")), "")

    @property
    def supply(self) -> Styler:
        """Styled supply comparison table."""
        df = self.data.supply
        return _style_comparison_table(df, "supply", self._rel_col(df))

    @property
    def use_basic(self) -> Styler:
        """Styled use at basic prices comparison table."""
        df = self.data.use_basic
        return _style_comparison_table(df, "use", self._rel_col(df))

    @property
    def use_purchasers(self) -> Styler:
        """Styled use at purchasers' prices comparison table."""
        df = self.data.use_purchasers
        return _style_comparison_table(df, "use", self._rel_col(df))

    @property
    def use_price_layers(self) -> Styler:
        """Styled price layers comparison table."""
        return _style_comparison_layers_table(self.data.use_price_layers)

    @property
    def balancing_targets_supply(self) -> Styler | None:
        """Styled supply balancing targets comparison table, or None."""
        if self.data.balancing_targets_supply is None:
            return None
        df = self.data.balancing_targets_supply
        return _style_comparison_table(df, "supply", self._rel_col(df))

    @property
    def balancing_targets_use_basic(self) -> Styler | None:
        """Styled use balancing targets at basic prices comparison table, or None."""
        if self.data.balancing_targets_use_basic is None:
            return None
        df = self.data.balancing_targets_use_basic
        return _style_comparison_table(df, "use", self._rel_col(df))

    @property
    def balancing_targets_use_purchasers(self) -> Styler | None:
        """Styled use balancing targets at purchasers' prices comparison table, or None."""
        if self.data.balancing_targets_use_purchasers is None:
            return None
        df = self.data.balancing_targets_use_purchasers
        return _style_comparison_table(df, "use", self._rel_col(df))

    @property
    def balancing_targets_use_price_layers(self) -> Styler | None:
        """Styled use balancing targets price layers comparison table, or None."""
        if self.data.balancing_targets_use_price_layers is None:
            return None
        return _style_comparison_layers_table(self.data.balancing_targets_use_price_layers)

    @property
    def summary(self) -> Styler:
        """Styled summary table."""
        return _style_summary_table(self.data.summary)


def inspect_sut_comparison(
    before: SUT,
    after: SUT,
    *,
    ids: str | int | Iterable[str | int] | None = None,
    products: str | list[str] | None = None,
    transactions: str | list[str] | None = None,
    categories: str | list[str] | None = None,
    diff_tolerance: float = 0,
    rel_tolerance: float = 0,
    filter_nan_as_zero: bool = False,
    sort: bool = False,
) -> SUTComparisonInspection:
    """
    Return a row-level comparison between two SUT objects.

    Computes the difference between ``before`` and ``after`` for every
    price column, and returns only the rows that differ beyond the given
    tolerances. Rows present in only one SUT are always included.

    Both SUTs must have metadata with identical column structures.

    Parameters
    ----------
    before : SUT
        The SUT before the operation (e.g. before balancing or adjustment).
    after : SUT
        The SUT after the operation.
    ids : str, int, iterable of str or int, or None, optional
        Filter by collection member id. Accepts the same pattern syntax as
        :func:`~sutlab.sut.get_rows`. Applied to both SUTs before comparing.
        ``None`` (the default) includes all ids.
    products : str, list of str, or None, optional
        Filter by product code. Same pattern syntax as ``ids``.
    transactions : str, list of str, or None, optional
        Filter by transaction code. Same pattern syntax as ``ids``.
    categories : str, list of str, or None, optional
        Filter by category code. Same pattern syntax as ``ids``.
    diff_tolerance : float, optional
        Absolute tolerance. A row is included when
        ``abs(diff) > diff_tolerance``. Default ``0`` (any non-zero
        difference).
    rel_tolerance : float, optional
        Relative tolerance. A row is included when
        ``abs(rel) > rel_tolerance``. Default ``0``.
    filter_nan_as_zero : bool, optional
        When ``True``, rows where one side is ``NaN`` and the other is ``0``
        are excluded from all tables. This suppresses the noise that arises
        when a new row is added to a SUT with zero values — such a row
        would otherwise always appear as a one-sided difference. Default
        ``False`` preserves all one-sided rows regardless of value.
    sort : bool, optional
        When ``True``, rows are sorted by ``abs(diff)`` descending within
        each id (for ``supply``, ``use_basic``, ``use_purchasers``) or
        within each ``(id, price_layer)`` group (for ``use_price_layers``).
        Default ``False`` preserves natural sort order.

    Returns
    -------
    SUTComparisonInspection
        A dataclass whose ``data`` attribute holds four DataFrames.
        See :class:`SUTComparisonInspection` for the table structures.

    Raises
    ------
    ValueError
        If ``before.metadata`` or ``after.metadata`` is ``None``.
    ValueError
        If the ``SUTColumns`` of ``before`` and ``after`` differ in any field.

    Examples
    --------
    Compare a SUT before and after balancing:

    >>> balanced = balance_columns(sut)
    >>> result = inspect_sut_comparison(sut, balanced)
    >>> result.data.supply
    >>> result.data.use_purchasers
    """
    _validate_column_structures(before, after)

    cols = before.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category
    price_basic_col = cols.price_basic
    price_purchasers_col = cols.price_purchasers
    key_cols = [id_col, prod_col, trans_col, cat_col]

    # Apply filters to both SUTs independently before comparing.
    filtered_before = _apply_filters(before, cols, ids, products, transactions, categories)
    filtered_after = _apply_filters(after, cols, ids, products, transactions, categories)

    # Collect price layer columns present in either SUT's use DataFrame.
    layer_cols = _get_union_price_layer_columns(cols, filtered_before.use, filtered_after.use)

    # Build label lookup dicts from classifications (empty dicts when unavailable).
    classifications = before.metadata.classifications
    prod_names = _build_product_names(classifications, prod_col)
    trans_names = _build_transaction_names(classifications, trans_col)
    cat_names = _build_combined_category_names(classifications, cat_col)
    has_labels = bool(prod_names or trans_names or cat_names)

    # Build supply comparison: one merge of the supply sides.
    supply_table = _build_single_price_comparison(
        before_df=filtered_before.supply,
        after_df=filtered_after.supply,
        key_cols=key_cols,
        price_col=price_basic_col,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    supply_table = _set_key_index(
        supply_table, key_cols, prod_col, trans_col, cat_col,
        prod_names, trans_names, cat_names, has_labels,
    )

    # Build all three use tables from a single merge of the use sides.
    # Merging once on key_cols and reusing the result avoids repeating the
    # same expensive join for use_basic, use_purchasers, and each price layer.
    all_use_price_cols = [price_basic_col] + layer_cols + [price_purchasers_col]
    merged_use = _merge_sides(
        filtered_before.use, filtered_after.use, key_cols, all_use_price_cols
    )

    use_basic_table = _extract_price_comparison(
        merged_use=merged_use,
        key_cols=key_cols,
        price_col=price_basic_col,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    use_basic_table = _set_key_index(
        use_basic_table, key_cols, prod_col, trans_col, cat_col,
        prod_names, trans_names, cat_names, has_labels,
    )

    use_purchasers_table = _extract_price_comparison(
        merged_use=merged_use,
        key_cols=key_cols,
        price_col=price_purchasers_col,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    use_purchasers_table = _set_key_index(
        use_purchasers_table, key_cols, prod_col, trans_col, cat_col,
        prod_names, trans_names, cat_names, has_labels,
    )

    use_price_layers_table = _extract_layers_comparison(
        merged_use=merged_use,
        key_cols=key_cols,
        layer_cols=layer_cols,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    use_price_layers_table = _set_layers_index(
        use_price_layers_table, key_cols, prod_col, trans_col, cat_col,
        prod_names, trans_names, cat_names, has_labels,
    )

    # Build balancing targets comparison when both SUTs have targets.
    if before.balancing_targets is not None and after.balancing_targets is not None:
        (
            targets_supply,
            targets_use_basic,
            targets_use_purchasers,
            targets_use_price_layers,
        ) = _build_targets_comparison(
            before=before,
            after=after,
            cols=cols,
            ids=ids,
            transactions=transactions,
            categories=categories,
            diff_tolerance=diff_tolerance,
            rel_tolerance=rel_tolerance,
            filter_nan_as_zero=filter_nan_as_zero,
            sort=sort,
            trans_names=trans_names,
            cat_names=cat_names,
        )
    else:
        targets_supply = None
        targets_use_basic = None
        targets_use_purchasers = None
        targets_use_price_layers = None

    summary_entries = {
        "supply": len(supply_table),
        "use_basic": len(use_basic_table),
        "use_price_layers": len(use_price_layers_table),
        "use_purchasers": len(use_purchasers_table),
    }
    if targets_supply is not None:
        summary_entries["balancing_targets_supply"] = len(targets_supply)
        summary_entries["balancing_targets_use_basic"] = len(targets_use_basic)
        summary_entries["balancing_targets_use_price_layers"] = len(targets_use_price_layers)
        summary_entries["balancing_targets_use_purchasers"] = len(targets_use_purchasers)

    summary = pd.DataFrame(
        {"n_differences": list(summary_entries.values())},
        index=pd.Index(list(summary_entries.keys()), name="table"),
    )

    return SUTComparisonInspection(
        data=SUTComparisonData(
            supply=supply_table,
            use_basic=use_basic_table,
            use_purchasers=use_purchasers_table,
            use_price_layers=use_price_layers_table,
            balancing_targets_supply=targets_supply,
            balancing_targets_use_basic=targets_use_basic,
            balancing_targets_use_purchasers=targets_use_purchasers,
            balancing_targets_use_price_layers=targets_use_price_layers,
            summary=summary,
        )
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_column_structures(before: SUT, after: SUT) -> None:
    """Raise if either SUT lacks metadata or their SUTColumns differ."""
    if before.metadata is None:
        raise ValueError(
            "before.metadata is required for inspect_sut_comparison. "
            "Provide a SUTMetadata with column name mappings."
        )
    if after.metadata is None:
        raise ValueError(
            "after.metadata is required for inspect_sut_comparison. "
            "Provide a SUTMetadata with column name mappings."
        )

    before_cols = before.metadata.columns
    after_cols = after.metadata.columns

    mismatches = []
    for field in dataclasses.fields(before_cols):
        before_val = getattr(before_cols, field.name)
        after_val = getattr(after_cols, field.name)
        if before_val != after_val:
            mismatches.append(
                f"  {field.name}: before={before_val!r}, after={after_val!r}"
            )

    if mismatches:
        raise ValueError(
            "before and after SUTs have different column structures:\n"
            + "\n".join(mismatches)
        )


def _apply_filters(
    sut: SUT,
    cols,
    ids,
    products,
    transactions,
    categories,
) -> SUT:
    """Apply the optional row filters to a SUT, returning a filtered copy."""
    result = sut
    if ids is not None:
        result = _filter_sut_by_ids(result, ids)
    if products is not None:
        result = _filter_sut_by_column(result, cols.product, products)
    if transactions is not None:
        result = _filter_sut_by_column(result, cols.transaction, transactions)
    if categories is not None:
        result = _filter_sut_by_column(result, cols.category, categories)
    return result


def _get_union_price_layer_columns(cols, before_use: pd.DataFrame, after_use: pd.DataFrame) -> list[str]:
    """Return price layer column names present in either use DataFrame, in SUTColumns order."""
    optional_layer_attrs = [
        "trade_margins",
        "wholesale_margins",
        "retail_margins",
        "transport_margins",
        "product_taxes",
        "product_subsidies",
        "product_taxes_less_subsidies",
        "vat",
    ]
    result = []
    for attr in optional_layer_attrs:
        col_name = getattr(cols, attr)
        if col_name is None:
            continue
        if col_name in before_use.columns or col_name in after_use.columns:
            result.append(col_name)
    return result


def _merge_sides(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    key_cols: list[str],
    price_cols: list[str],
) -> pd.DataFrame:
    """Outer-merge before and after on key_cols for all given price columns.

    Each price column gets ``_before`` and ``_after`` suffixes. Columns
    absent from one side are filled with NaN so that ``{col}_before`` and
    ``{col}_after`` always exist in the result. The ``_merge`` indicator
    column is included so callers can detect one-sided rows.
    """
    before_side = before_df[key_cols].copy()
    after_side = after_df[key_cols].copy()
    for col in price_cols:
        before_side[col] = before_df[col].values if col in before_df.columns else float("nan")
        after_side[col] = after_df[col].values if col in after_df.columns else float("nan")

    return before_side.merge(
        after_side,
        on=key_cols,
        how="outer",
        indicator=True,
        suffixes=("_before", "_after"),
    )


def _build_single_price_comparison(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    key_cols: list[str],
    price_col: str,
    diff_tolerance: float,
    rel_tolerance: float,
    filter_nan_as_zero: bool,
    sort: bool,
    id_col: str,
) -> pd.DataFrame:
    """Build a before/after/diff/rel comparison for a single price column.

    Used for the supply table, which has its own merge separate from use.
    Rows missing from one side are always included; rows present on both
    sides are included only when diff or rel exceeds the tolerances.
    """
    merged = _merge_sides(before_df, after_df, key_cols, [price_col])
    return _extract_price_comparison(merged, key_cols, price_col, diff_tolerance, rel_tolerance, filter_nan_as_zero, sort, id_col)


def _extract_price_comparison(
    merged_use: pd.DataFrame,
    key_cols: list[str],
    price_col: str,
    diff_tolerance: float,
    rel_tolerance: float,
    filter_nan_as_zero: bool,
    sort: bool,
    id_col: str,
) -> pd.DataFrame:
    """Extract a before/after/diff/rel table for one price column from an already-merged frame.

    The merged frame uses ``{col}_before`` / ``{col}_after`` suffixes (from
    ``_merge_sides``). Output columns are renamed to ``before_{col}`` /
    ``after_{col}`` to match the agreed output convention.
    """
    # Internal names as produced by _merge_sides suffixes.
    src_before = f"{price_col}_before"
    src_after = f"{price_col}_after"
    # Output names.
    out_before = f"before_{price_col}"
    out_after = f"after_{price_col}"
    diff_col = f"diff_{price_col}"
    rel_col = f"rel_{price_col}"

    diff = merged_use[src_after] - merged_use[src_before]
    safe_before = merged_use[src_before].replace(0, float("nan"))
    rel = merged_use[src_after] / safe_before - 1

    is_one_sided = merged_use["_merge"] != "both"
    keep = is_one_sided | (diff.abs() > diff_tolerance) | (rel.abs() > rel_tolerance)

    if filter_nan_as_zero:
        nan_vs_zero = (
            (merged_use[src_before].isna() & merged_use[src_after].eq(0))
            | (merged_use[src_before].eq(0) & merged_use[src_after].isna())
        )
        keep = keep & ~nan_vs_zero

    result = merged_use[key_cols][keep].copy()
    result[out_before] = merged_use[src_before][keep].values
    result[out_after] = merged_use[src_after][keep].values
    result[diff_col] = diff[keep].values
    result[rel_col] = rel[keep].values

    if sort:
        result["_abs_diff"] = result[diff_col].abs()
        result = result.sort_values([id_col, "_abs_diff"], ascending=[True, False])
        result = result.drop(columns=["_abs_diff"])

    return result.reset_index(drop=True)


def _extract_layers_comparison(
    merged_use: pd.DataFrame,
    key_cols: list[str],
    layer_cols: list[str],
    diff_tolerance: float,
    rel_tolerance: float,
    filter_nan_as_zero: bool,
    sort: bool,
    id_col: str,
) -> pd.DataFrame:
    """Extract the long-format price layers comparison from an already-merged frame.

    Iterates over layer columns without any additional merges — all data is
    already present in ``merged_use`` with ``_before`` / ``_after`` suffixes.
    """
    empty_cols = key_cols + ["price_layer", "before", "after", "diff", "rel"]

    if not layer_cols:
        return pd.DataFrame(columns=empty_cols)

    is_one_sided = merged_use["_merge"] != "both"

    layer_frames = []
    for layer_col in layer_cols:
        before_vals = merged_use[f"{layer_col}_before"]
        after_vals = merged_use[f"{layer_col}_after"]

        diff = after_vals - before_vals
        safe_before = before_vals.replace(0, float("nan"))
        rel = after_vals / safe_before - 1

        keep = is_one_sided | (diff.abs() > diff_tolerance) | (rel.abs() > rel_tolerance)

        if filter_nan_as_zero:
            nan_vs_zero = (
                (before_vals.isna() & after_vals.eq(0))
                | (before_vals.eq(0) & after_vals.isna())
            )
            keep = keep & ~nan_vs_zero

        layer_df = merged_use[key_cols][keep].copy()
        layer_df["price_layer"] = layer_col
        layer_df["before"] = before_vals[keep].values
        layer_df["after"] = after_vals[keep].values
        layer_df["diff"] = diff[keep].values
        layer_df["rel"] = rel[keep].values

        layer_frames.append(layer_df[key_cols + ["price_layer", "before", "after", "diff", "rel"]])

    result = pd.concat(layer_frames, ignore_index=True)

    if sort:
        result["_abs_diff"] = result["diff"].abs()
        result = result.sort_values(
            [id_col, "price_layer", "_abs_diff"],
            ascending=[True, True, False],
        )
        result = result.drop(columns=["_abs_diff"])

    return result.reset_index(drop=True)


def _set_key_index(
    df: pd.DataFrame,
    key_cols: list[str],
    prod_col: str,
    trans_col: str,
    cat_col: str,
    prod_names: dict[str, str],
    trans_names: dict[str, str],
    cat_names: dict[str, str],
    has_labels: bool,
) -> pd.DataFrame:
    """Set key_cols as the index, adding _txt companion levels when available."""
    id_col = key_cols[0]
    df = df.set_index(key_cols)

    if not has_labels:
        return df

    id_vals = df.index.get_level_values(id_col)
    prod_vals = df.index.get_level_values(prod_col)
    trans_vals = df.index.get_level_values(trans_col)
    cat_vals = df.index.get_level_values(cat_col)

    prod_txt_col = f"{prod_col}_txt"
    trans_txt_col = f"{trans_col}_txt"
    cat_txt_col = f"{cat_col}_txt"

    df.index = pd.MultiIndex.from_arrays(
        [
            id_vals,
            prod_vals,
            [prod_names.get(str(p), "") for p in prod_vals],
            trans_vals,
            [trans_names.get(str(t), "") for t in trans_vals],
            cat_vals,
            [cat_names.get(str(c), "") for c in cat_vals],
        ],
        names=[id_col, prod_col, prod_txt_col, trans_col, trans_txt_col, cat_col, cat_txt_col],
    )

    return df


def _set_layers_index(
    df: pd.DataFrame,
    key_cols: list[str],
    prod_col: str,
    trans_col: str,
    cat_col: str,
    prod_names: dict[str, str],
    trans_names: dict[str, str],
    cat_names: dict[str, str],
    has_labels: bool,
) -> pd.DataFrame:
    """Set (key_cols + price_layer) as the index for the price layers table.

    Text companion levels are added for product, transaction, and category
    when available. The ``price_layer`` level has no text companion.
    """
    id_col = key_cols[0]
    index_cols = key_cols + ["price_layer"]
    df = df.set_index(index_cols)

    if not has_labels:
        return df

    id_vals = df.index.get_level_values(id_col)
    prod_vals = df.index.get_level_values(prod_col)
    trans_vals = df.index.get_level_values(trans_col)
    cat_vals = df.index.get_level_values(cat_col)
    layer_vals = df.index.get_level_values("price_layer")

    prod_txt_col = f"{prod_col}_txt"
    trans_txt_col = f"{trans_col}_txt"
    cat_txt_col = f"{cat_col}_txt"

    df.index = pd.MultiIndex.from_arrays(
        [
            id_vals,
            prod_vals,
            [prod_names.get(str(p), "") for p in prod_vals],
            trans_vals,
            [trans_names.get(str(t), "") for t in trans_vals],
            cat_vals,
            [cat_names.get(str(c), "") for c in cat_vals],
            layer_vals,
        ],
        names=[
            id_col, prod_col, prod_txt_col,
            trans_col, trans_txt_col,
            cat_col, cat_txt_col,
            "price_layer",
        ],
    )

    return df


def _build_targets_comparison(
    before: SUT,
    after: SUT,
    cols,
    ids,
    transactions,
    categories,
    diff_tolerance: float,
    rel_tolerance: float,
    filter_nan_as_zero: bool,
    sort: bool,
    trans_names: dict[str, str],
    cat_names: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build the four balancing targets comparison tables.

    Returns (targets_supply, targets_use_basic, targets_use_purchasers,
    targets_use_price_layers). Reuses the same merge and extraction helpers
    as the SUT data comparison, with (id, transaction, category) as key_cols.
    """
    id_col = cols.id
    trans_col = cols.transaction
    cat_col = cols.category
    price_basic_col = cols.price_basic
    price_purchasers_col = cols.price_purchasers
    targets_key_cols = [id_col, trans_col, cat_col]

    has_labels = bool(trans_names or cat_names)

    # Apply filters to both targets DataFrames independently.
    before_targets_supply = before.balancing_targets.supply
    after_targets_supply = after.balancing_targets.supply
    before_targets_use = before.balancing_targets.use
    after_targets_use = after.balancing_targets.use

    if ids is not None:
        before_targets_supply = _filter_targets_by_ids(before_targets_supply, id_col, ids)
        after_targets_supply = _filter_targets_by_ids(after_targets_supply, id_col, ids)
        before_targets_use = _filter_targets_by_ids(before_targets_use, id_col, ids)
        after_targets_use = _filter_targets_by_ids(after_targets_use, id_col, ids)
    if transactions is not None:
        before_targets_supply = _filter_targets_by_column(before_targets_supply, trans_col, transactions)
        after_targets_supply = _filter_targets_by_column(after_targets_supply, trans_col, transactions)
        before_targets_use = _filter_targets_by_column(before_targets_use, trans_col, transactions)
        after_targets_use = _filter_targets_by_column(after_targets_use, trans_col, transactions)
    if categories is not None:
        before_targets_supply = _filter_targets_by_column(before_targets_supply, cat_col, categories)
        after_targets_supply = _filter_targets_by_column(after_targets_supply, cat_col, categories)
        before_targets_use = _filter_targets_by_column(before_targets_use, cat_col, categories)
        after_targets_use = _filter_targets_by_column(after_targets_use, cat_col, categories)

    # Collect price layer columns present in either use targets DataFrame.
    layer_cols = _get_union_price_layer_columns(cols, before_targets_use, after_targets_use)

    # Supply: one merge on (id, transaction, category) for price_basic only.
    targets_supply = _build_single_price_comparison(
        before_df=before_targets_supply,
        after_df=after_targets_supply,
        key_cols=targets_key_cols,
        price_col=price_basic_col,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    targets_supply = _set_targets_index(
        targets_supply, targets_key_cols, trans_col, cat_col,
        trans_names, cat_names, has_labels,
    )

    # Use: one merge covering all price columns.
    all_use_price_cols = [price_basic_col] + layer_cols + [price_purchasers_col]
    merged_targets_use = _merge_sides(
        before_targets_use, after_targets_use, targets_key_cols, all_use_price_cols
    )

    targets_use_basic = _extract_price_comparison(
        merged_use=merged_targets_use,
        key_cols=targets_key_cols,
        price_col=price_basic_col,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    targets_use_basic = _set_targets_index(
        targets_use_basic, targets_key_cols, trans_col, cat_col,
        trans_names, cat_names, has_labels,
    )

    targets_use_purchasers = _extract_price_comparison(
        merged_use=merged_targets_use,
        key_cols=targets_key_cols,
        price_col=price_purchasers_col,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    targets_use_purchasers = _set_targets_index(
        targets_use_purchasers, targets_key_cols, trans_col, cat_col,
        trans_names, cat_names, has_labels,
    )

    targets_use_price_layers = _extract_layers_comparison(
        merged_use=merged_targets_use,
        key_cols=targets_key_cols,
        layer_cols=layer_cols,
        diff_tolerance=diff_tolerance,
        rel_tolerance=rel_tolerance,
        filter_nan_as_zero=filter_nan_as_zero,
        sort=sort,
        id_col=id_col,
    )
    targets_use_price_layers = _set_targets_layers_index(
        targets_use_price_layers, targets_key_cols, trans_col, cat_col,
        trans_names, cat_names, has_labels,
    )

    return targets_supply, targets_use_basic, targets_use_purchasers, targets_use_price_layers


def _filter_targets_by_ids(df: pd.DataFrame, id_col: str, ids) -> pd.DataFrame:
    """Filter a targets DataFrame to matching id values using string coercion."""
    from sutlab.sut import _match_codes
    if isinstance(ids, (str, int)):
        ids_list = [ids]
    else:
        ids_list = list(ids)
    ids_as_str = [str(v) for v in ids_list]
    all_codes = [str(v) for v in df[id_col].unique()]
    matched = _match_codes(all_codes, ids_as_str)
    return df[df[id_col].astype(str).isin(matched)]


def _filter_targets_by_column(df: pd.DataFrame, col: str, patterns: str | list[str]) -> pd.DataFrame:
    """Filter a targets DataFrame by code patterns on a given column."""
    from sutlab.sut import _match_codes
    if isinstance(patterns, str):
        patterns = [patterns]
    all_codes = df[col].dropna().unique().tolist()
    matched = _match_codes(all_codes, patterns)
    return df[df[col].isin(matched)]


def _set_targets_index(
    df: pd.DataFrame,
    key_cols: list[str],
    trans_col: str,
    cat_col: str,
    trans_names: dict[str, str],
    cat_names: dict[str, str],
    has_labels: bool,
) -> pd.DataFrame:
    """Set (id, transaction, category) as the index, adding _txt companions when available."""
    id_col = key_cols[0]
    df = df.set_index(key_cols)

    if not has_labels:
        return df

    id_vals = df.index.get_level_values(id_col)
    trans_vals = df.index.get_level_values(trans_col)
    cat_vals = df.index.get_level_values(cat_col)

    trans_txt_col = f"{trans_col}_txt"
    cat_txt_col = f"{cat_col}_txt"

    df.index = pd.MultiIndex.from_arrays(
        [
            id_vals,
            trans_vals,
            [trans_names.get(str(t), "") for t in trans_vals],
            cat_vals,
            [cat_names.get(str(c), "") for c in cat_vals],
        ],
        names=[id_col, trans_col, trans_txt_col, cat_col, cat_txt_col],
    )

    return df


def _set_targets_layers_index(
    df: pd.DataFrame,
    key_cols: list[str],
    trans_col: str,
    cat_col: str,
    trans_names: dict[str, str],
    cat_names: dict[str, str],
    has_labels: bool,
) -> pd.DataFrame:
    """Set (id, transaction, category, price_layer) as the index for the targets layers table."""
    id_col = key_cols[0]
    index_cols = key_cols + ["price_layer"]
    df = df.set_index(index_cols)

    if not has_labels:
        return df

    id_vals = df.index.get_level_values(id_col)
    trans_vals = df.index.get_level_values(trans_col)
    cat_vals = df.index.get_level_values(cat_col)
    layer_vals = df.index.get_level_values("price_layer")

    trans_txt_col = f"{trans_col}_txt"
    cat_txt_col = f"{cat_col}_txt"

    df.index = pd.MultiIndex.from_arrays(
        [
            id_vals,
            trans_vals,
            [trans_names.get(str(t), "") for t in trans_vals],
            cat_vals,
            [cat_names.get(str(c), "") for c in cat_vals],
            layer_vals,
        ],
        names=[id_col, trans_col, trans_txt_col, cat_col, cat_txt_col, "price_layer"],
    )

    return df


def _build_product_names(classifications, prod_col: str) -> dict[str, str]:
    """Return ``{product_code: label}`` from classifications, or empty dict."""
    if classifications is None or classifications.products is None:
        return {}
    prod_df = classifications.products
    prod_txt_col = f"{prod_col}_txt"
    if prod_txt_col not in prod_df.columns:
        return {}
    return dict(zip(
        prod_df[prod_col].astype(str),
        prod_df[prod_txt_col].astype(str),
    ))


def _build_transaction_names(classifications, trans_col: str) -> dict[str, str]:
    """Return ``{transaction_code: label}`` from classifications, or empty dict."""
    if classifications is None or classifications.transactions is None:
        return {}
    trans_df = classifications.transactions
    trans_txt_col = f"{trans_col}_txt"
    if trans_txt_col not in trans_df.columns:
        return {}
    return dict(zip(
        trans_df[trans_col].astype(str),
        trans_df[trans_txt_col].astype(str),
    ))


def _build_combined_category_names(classifications, cat_col: str) -> dict[str, str]:
    """Return ``{category_code: label}`` merged from all category classifications.

    Draws from ``industries``, ``individual_consumption``, and
    ``collective_consumption`` classification tables.
    """
    result: dict[str, str] = {}
    if classifications is None:
        return result
    cat_txt_col = f"{cat_col}_txt"
    for attr in ("industries", "individual_consumption", "collective_consumption"):
        cls_df = getattr(classifications, attr, None)
        if cls_df is None:
            continue
        if cat_txt_col not in cls_df.columns:
            continue
        for code, label in zip(cls_df[cat_col].astype(str), cls_df[cat_txt_col].astype(str)):
            result[code] = label
    return result
