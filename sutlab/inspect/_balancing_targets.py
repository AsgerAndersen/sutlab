"""
inspect_balancing_targets: supply and use column totals vs. balancing targets.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes
from sutlab.inspect._style import _style_balancing_targets_table
from sutlab.inspect._shared import _write_inspection_to_excel


@dataclass
class BalancingTargetsData:
    """Raw DataFrames underlying a :class:`BalancingTargetsInspection`.

    Use this directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding property on
    :class:`BalancingTargetsInspection` once styling is added.
    """

    supply: pd.DataFrame
    use: pd.DataFrame
    supply_violations: pd.DataFrame | None
    use_violations: pd.DataFrame | None


@dataclass
class BalancingTargetsInspection:
    """
    Result of :func:`inspect_balancing_targets`.

    Raw DataFrames are available under ``result.data``.

    Attributes
    ----------
    supply : pd.DataFrame
        One row per (transaction, category) combination in the supply
        balancing targets for the active balancing member. Columns:

        - ``{price_basic}`` — actual column total from the supply data.
        - ``target_{price_basic}`` — target value from ``balancing_targets``.
        - ``diff_{price_basic}`` — actual minus target.
        - ``rel_{price_basic}`` — actual / target - 1. ``NaN`` when target
          is zero or ``NaN``.
        - ``tol_{price_basic}`` — resolved tolerance from
          ``balancing_config.target_tolerances``. ``NaN`` when no
          ``target_tolerances`` are configured or when the target is ``NaN``.
        - ``violation_{price_basic}`` — how far the actual value falls outside
          the tolerance band. Positive when actual > target + tolerance;
          negative when actual < target - tolerance; zero when within
          tolerance. ``NaN`` when no ``target_tolerances`` are configured.

        The row index is a two-level MultiIndex
        ``({transaction}, {category})`` when no classifications are loaded,
        or a four-level MultiIndex
        ``({transaction}, {transaction}_txt, {category}, {category}_txt)``
        when classifications are available.

    use : pd.DataFrame
        Same structure as ``supply`` but for the use side, using
        ``{price_purchasers}`` instead of ``{price_basic}``.

    supply_violations : pd.DataFrame or None
        Subset of ``supply`` where ``violation_{price_basic} != 0``. Empty
        DataFrame when no supply violations exist. ``None`` when no
        ``target_tolerances`` are configured.

    use_violations : pd.DataFrame or None
        Subset of ``use`` where ``violation_{price_purchasers} != 0``. Empty
        DataFrame when no use violations exist. ``None`` when no
        ``target_tolerances`` are configured.
    """

    data: BalancingTargetsData

    def _supply_styler(self, df: pd.DataFrame) -> Styler:
        """Return a styled Styler for a supply-side targets table."""
        # Derive column names from the DataFrame columns.
        price_col = next(c for c in df.columns if not c.startswith(("target_", "diff_", "rel_", "tol_", "violation_")))
        rel_col = next((c for c in df.columns if c.startswith("rel_")), "")
        return _style_balancing_targets_table(df, price_col=price_col, rel_col=rel_col, palette="supply")

    def _use_styler(self, df: pd.DataFrame) -> Styler:
        """Return a styled Styler for a use-side targets table."""
        price_col = next(c for c in df.columns if not c.startswith(("target_", "diff_", "rel_", "tol_", "violation_")))
        rel_col = next((c for c in df.columns if c.startswith("rel_")), "")
        return _style_balancing_targets_table(df, price_col=price_col, rel_col=rel_col, palette="use")

    @property
    def supply(self) -> Styler:
        """Styled supply targets table."""
        return self._supply_styler(self.data.supply)

    @property
    def use(self) -> Styler:
        """Styled use targets table."""
        return self._use_styler(self.data.use)

    @property
    def supply_violations(self) -> Styler | None:
        """Styled supply violations table, or ``None`` if no tolerances configured."""
        if self.data.supply_violations is None:
            return None
        return self._supply_styler(self.data.supply_violations)

    @property
    def use_violations(self) -> Styler | None:
        """Styled use violations table, or ``None`` if no tolerances configured."""
        if self.data.use_violations is None:
            return None
        return self._use_styler(self.data.use_violations)

    def write_to_excel(self, path) -> None:
        """Write all tables to an Excel file, one sheet per table.

        Each field in ``self.data`` is written to a separate sheet. Fields
        whose value is ``None`` are skipped. Sheet names match the field name;
        names exceeding Excel's 31-character limit are shortened by truncating
        each underscore-separated segment to its first three characters.

        Parameters
        ----------
        path : str or Path
            Destination ``.xlsx`` file path.
        """
        _write_inspection_to_excel(self, path)


def inspect_balancing_targets(
    sut: SUT,
    transactions: str | list[str] | None = None,
    categories: str | list[str] | None = None,
    sort: bool = False,
) -> BalancingTargetsInspection:
    """
    Return supply and use column totals compared against balancing targets.

    For each (transaction, category) combination in the balancing targets,
    shows the actual column total from the SUT data alongside the target,
    the difference, the relative deviation, the resolved tolerance, and
    whether the tolerance is violated.

    Parameters
    ----------
    sut : SUT
        The SUT collection. Must have ``balancing_id``, ``metadata``, and
        ``balancing_targets`` set.
    transactions : str, list of str, or None, optional
        Transaction codes to include. Accepts the same pattern syntax as
        :func:`~sutlab.sut.get_rows`: exact codes, wildcards (``*``),
        ranges (``:``), and negation (``~``). ``None`` (the default) includes
        all transactions present in the targets.
    categories : str, list of str, or None, optional
        Category codes to include. Same pattern syntax as ``transactions``.
        ``None`` includes all categories.
    sort : bool, optional
        When ``True``, rows are sorted by the absolute value of
        ``diff_{price}`` in descending order (largest deviation first).
        Default ``False`` preserves the order from the targets DataFrame.

    Returns
    -------
    BalancingTargetsInspection
        A dataclass whose ``data`` attribute holds the raw DataFrames.
        See :class:`BalancingTargetsInspection` for the table structures.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.balancing_id`` is ``None``.
    ValueError
        If ``sut.balancing_targets`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call inspect_balancing_targets. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.balancing_id is None:
        raise ValueError(
            "sut.balancing_id is not set. Call set_balancing_id first to "
            "identify which member to inspect."
        )
    if sut.balancing_targets is None:
        raise ValueError(
            "sut.balancing_targets is not set. Call set_balancing_targets "
            "first to provide column targets."
        )

    cols = sut.metadata.columns
    has_tolerances = (
        sut.balancing_config is not None
        and sut.balancing_config.target_tolerances is not None
    )

    # If tolerances are configured but tol columns are not yet present,
    # resolve them silently before building the tables.
    working_sut = sut
    if has_tolerances:
        tol_col_supply = f"tol_{cols.price_basic}"
        tol_col_use = f"tol_{cols.price_purchasers}"
        supply_needs_resolve = tol_col_supply not in sut.balancing_targets.supply.columns
        use_needs_resolve = tol_col_use not in sut.balancing_targets.use.columns
        if supply_needs_resolve or use_needs_resolve:
            from sutlab.balancing import resolve_target_tolerances
            working_sut = resolve_target_tolerances(sut)

    classifications = sut.metadata.classifications

    # Build label lookup dicts (empty when no classifications loaded).
    trans_names = _build_transaction_names(classifications, cols.transaction)
    cat_names = _build_combined_category_names(classifications, cols.category)
    has_labels = bool(trans_names or cat_names)

    supply_table = _build_side_table(
        sut=working_sut,
        data_df=working_sut.supply,
        targets_df=working_sut.balancing_targets.supply,
        price_col=cols.price_basic,
        id_col=cols.id,
        trans_col=cols.transaction,
        cat_col=cols.category,
        transactions_filter=transactions,
        categories_filter=categories,
        has_tolerances=has_tolerances,
        sort=sort,
        trans_names=trans_names,
        cat_names=cat_names,
        has_labels=has_labels,
    )

    use_table = _build_side_table(
        sut=working_sut,
        data_df=working_sut.use,
        targets_df=working_sut.balancing_targets.use,
        price_col=cols.price_purchasers,
        id_col=cols.id,
        trans_col=cols.transaction,
        cat_col=cols.category,
        transactions_filter=transactions,
        categories_filter=categories,
        has_tolerances=has_tolerances,
        sort=sort,
        trans_names=trans_names,
        cat_names=cat_names,
        has_labels=has_labels,
    )

    if has_tolerances:
        supply_viol_col = f"violation_{cols.price_basic}"
        supply_viol_mask = supply_table[supply_viol_col].notna() & (supply_table[supply_viol_col] != 0)
        supply_violations = supply_table[supply_viol_mask].copy()
        use_viol_col = f"violation_{cols.price_purchasers}"
        use_viol_mask = use_table[use_viol_col].notna() & (use_table[use_viol_col] != 0)
        use_violations = use_table[use_viol_mask].copy()
    else:
        supply_violations = None
        use_violations = None

    return BalancingTargetsInspection(
        data=BalancingTargetsData(
            supply=supply_table,
            use=use_table,
            supply_violations=supply_violations,
            use_violations=use_violations,
        )
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_side_table(
    sut: SUT,
    data_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    price_col: str,
    id_col: str,
    trans_col: str,
    cat_col: str,
    transactions_filter: str | list[str] | None,
    categories_filter: str | list[str] | None,
    has_tolerances: bool,
    sort: bool,
    trans_names: dict[str, str],
    cat_names: dict[str, str],
    has_labels: bool,
) -> pd.DataFrame:
    """Build supply or use comparison table for the active balancing member."""
    tol_col = f"tol_{price_col}"
    violation_col = f"violation_{price_col}"
    target_col = f"target_{price_col}"
    diff_col = f"diff_{price_col}"
    rel_col = f"rel_{price_col}"

    # Filter targets to the active balancing member.
    member_targets = targets_df[targets_df[id_col] == sut.balancing_id].copy()

    # Apply transactions and categories filters.
    if transactions_filter is not None:
        patterns = (
            [transactions_filter]
            if isinstance(transactions_filter, str)
            else list(transactions_filter)
        )
        all_trans = member_targets[trans_col].dropna().unique().tolist()
        matched_trans = _match_codes(all_trans, patterns)
        member_targets = member_targets[member_targets[trans_col].isin(matched_trans)]

    if categories_filter is not None:
        patterns = (
            [categories_filter]
            if isinstance(categories_filter, str)
            else list(categories_filter)
        )
        all_cats = member_targets[cat_col].dropna().unique().tolist()
        matched_cats = _match_codes(all_cats, patterns)
        member_targets = member_targets[member_targets[cat_col].isin(matched_cats)]

    # Aggregate actual column totals from the data for the active member.
    member_data = data_df[data_df[id_col] == sut.balancing_id]
    actuals = (
        member_data
        .groupby([trans_col, cat_col], dropna=False)[price_col]
        .sum()
        .reset_index()
        .rename(columns={price_col: price_col})
    )

    # Build the result table: start from targets so every target row is present.
    result = member_targets[[trans_col, cat_col, price_col]].copy()
    result = result.rename(columns={price_col: target_col})

    result = result.merge(
        actuals,
        on=[trans_col, cat_col],
        how="left",
    )

    # Rows with no matching data get 0 (no activity for that transaction/category).
    result[price_col] = result[price_col].fillna(0.0)

    # Derived columns.
    result[diff_col] = result[price_col] - result[target_col]
    result[rel_col] = (
        result[price_col]
        / result[target_col].replace(0, float("nan"))
        - 1
    )

    # Tolerance column: use resolved values when available, else NaN.
    if has_tolerances and tol_col in member_targets.columns:
        tol_values = member_targets[[trans_col, cat_col, tol_col]].copy()
        result = result.merge(tol_values, on=[trans_col, cat_col], how="left")
    else:
        result[tol_col] = float("nan")

    # Tolerance violation.
    result[violation_col] = _compute_tol_violation(result[diff_col], result[tol_col])

    # Column order.
    result = result[[trans_col, cat_col, price_col, target_col, diff_col, rel_col, tol_col, violation_col]]

    # Sort by absolute diff if requested.
    if sort:
        result = result.sort_values(diff_col, key=lambda s: s.abs(), ascending=False)

    # Build MultiIndex.
    result = result.set_index([trans_col, cat_col])
    if has_labels:
        trans_vals = result.index.get_level_values(trans_col)
        cat_vals = result.index.get_level_values(cat_col)
        trans_txt_col = f"{trans_col}_txt"
        cat_txt_col = f"{cat_col}_txt"
        result.index = pd.MultiIndex.from_arrays(
            [
                trans_vals,
                [trans_names.get(str(t), "") for t in trans_vals],
                cat_vals,
                [cat_names.get(str(c), "") for c in cat_vals],
            ],
            names=[trans_col, trans_txt_col, cat_col, cat_txt_col],
        )

    return result


def _compute_tol_violation(diff: pd.Series, tol: pd.Series) -> pd.Series:
    """Compute signed tolerance violation.

    Returns how far ``diff`` falls outside the tolerance band
    ``[-tol, +tol]``:

    - Positive when ``diff > tol`` (actual exceeds upper bound).
    - Negative when ``diff < -tol`` (actual falls below lower bound).
    - Zero when ``abs(diff) <= tol``.
    - ``NaN`` when either ``diff`` or ``tol`` is ``NaN``.
    """
    # Initialise to 0 (in-tolerance assumption).
    violation = pd.Series(0.0, index=diff.index)
    # Replace with (diff - tol) where diff > tol (upper violation, positive).
    violation = violation.where(diff <= tol, diff - tol)
    # Replace with (diff + tol) where diff < -tol (lower violation, negative).
    violation = violation.where(diff >= -tol, diff + tol)
    return violation


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
    ``collective_consumption`` classification tables. Codes are expected to be
    disjoint across the three tables; later tables silently overwrite earlier
    ones if duplicates occur.
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
