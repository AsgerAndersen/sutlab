"""
inspect_unbalanced_targets: supply and use column totals vs. balancing targets,
filtered to rows where the absolute difference exceeds 1.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes
from sutlab.inspect._style import _style_balancing_targets_table, _style_unbalanced_targets_summary
from sutlab.inspect._shared import _write_inspection_to_excel


@dataclass
class UnbalancedTargetsData:
    """Raw DataFrames underlying a :class:`UnbalancedTargetsInspection`.

    Use this directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding property on
    :class:`UnbalancedTargetsInspection` once styling is added.
    """

    supply_categories: pd.DataFrame
    use_categories: pd.DataFrame
    supply_categories_violations: pd.DataFrame | None
    use_categories_violations: pd.DataFrame | None
    supply_transactions: pd.DataFrame
    use_transactions: pd.DataFrame
    supply_transactions_violations: pd.DataFrame | None
    use_transactions_violations: pd.DataFrame | None
    summary: pd.DataFrame


@dataclass
class UnbalancedTargetsInspection:
    """
    Result of :func:`inspect_unbalanced_targets`.

    Only rows where ``abs(diff_*) > 1`` are included in all tables.
    Raw DataFrames are available under ``result.data``.

    Attributes
    ----------
    supply_categories : pd.DataFrame
        One row per (transaction, category) in the supply balancing targets
        for the active balancing member, where ``abs(diff_{price_basic}) > 1``.
        Columns: ``{price_basic}``, ``target_{price_basic}``,
        ``diff_{price_basic}``, ``rel_{price_basic}``, ``tol_{price_basic}``,
        ``violation_{price_basic}``.
        Row index: two-level ``(transaction, category)`` MultiIndex, or
        four-level with label columns when classifications are loaded.

    use_categories : pd.DataFrame
        Same structure as ``supply_categories`` but for the use side,
        using ``{price_purchasers}``.

    supply_categories_violations : pd.DataFrame or None
        Subset of ``supply_categories`` where ``violation_{price_basic} != 0``.
        Empty DataFrame when no violations exist. ``None`` when no
        ``target_tolerances`` configured.

    use_categories_violations : pd.DataFrame or None
        Subset of ``use_categories`` where ``violation_{price_purchasers} != 0``.
        Empty DataFrame when no violations exist. ``None`` when no
        ``target_tolerances`` configured.

    supply_transactions : pd.DataFrame
        One row per transaction in the supply targets, where
        ``abs(diff_{price_basic}) > 1``. Targets and actuals are aggregated
        by summing over all categories. Columns same as ``supply_categories``
        minus the category index level. Tolerances use transaction-level
        ``rel`` from the config; the absolute component is scaled by the
        number of categories per transaction.
        Row index: single-level transaction (or two-level with label).

    use_transactions : pd.DataFrame
        Same structure as ``supply_transactions`` for the use side.

    supply_transactions_violations : pd.DataFrame or None
        Subset of ``supply_transactions`` where ``violation_{price_basic} != 0``.
        ``None`` when no ``target_tolerances`` configured.

    use_transactions_violations : pd.DataFrame or None
        Subset of ``use_transactions`` where ``violation_{price_purchasers} != 0``.
        ``None`` when no ``target_tolerances`` configured.

    summary : pd.DataFrame
        One row per non-``None`` table. Index is the table name; column is
        ``n_unbalanced`` (the number of rows in that table, i.e. rows where
        ``abs(diff_*) > 1``). Violations tables are omitted when no
        ``target_tolerances`` are configured.
    """

    data: UnbalancedTargetsData
    display_unit: float | None = None
    rel_base: int = 100

    def _supply_styler(self, df: pd.DataFrame) -> Styler:
        """Return a styled Styler for a supply-side targets table."""
        price_col = next(c for c in df.columns if not c.startswith(("target_", "diff_", "rel_", "tol_", "violation_")))
        rel_col = next((c for c in df.columns if c.startswith("rel_")), "")
        return _style_balancing_targets_table(df, price_col=price_col, rel_col=rel_col, palette="supply", display_unit=self.display_unit, rel_base=self.rel_base)

    def _use_styler(self, df: pd.DataFrame) -> Styler:
        """Return a styled Styler for a use-side targets table."""
        price_col = next(c for c in df.columns if not c.startswith(("target_", "diff_", "rel_", "tol_", "violation_")))
        rel_col = next((c for c in df.columns if c.startswith("rel_")), "")
        return _style_balancing_targets_table(df, price_col=price_col, rel_col=rel_col, palette="use", display_unit=self.display_unit, rel_base=self.rel_base)

    @property
    def supply_categories(self) -> Styler:
        """Styled supply category-level targets table."""
        return self._supply_styler(self.data.supply_categories)

    @property
    def use_categories(self) -> Styler:
        """Styled use category-level targets table."""
        return self._use_styler(self.data.use_categories)

    @property
    def supply_categories_violations(self) -> Styler | None:
        """Styled supply category violations, or ``None`` if no tolerances configured."""
        if self.data.supply_categories_violations is None:
            return None
        return self._supply_styler(self.data.supply_categories_violations)

    @property
    def use_categories_violations(self) -> Styler | None:
        """Styled use category violations, or ``None`` if no tolerances configured."""
        if self.data.use_categories_violations is None:
            return None
        return self._use_styler(self.data.use_categories_violations)

    @property
    def supply_transactions(self) -> Styler:
        """Styled supply transaction-level targets table."""
        return self._supply_styler(self.data.supply_transactions)

    @property
    def use_transactions(self) -> Styler:
        """Styled use transaction-level targets table."""
        return self._use_styler(self.data.use_transactions)

    @property
    def supply_transactions_violations(self) -> Styler | None:
        """Styled supply transaction violations, or ``None`` if no tolerances configured."""
        if self.data.supply_transactions_violations is None:
            return None
        return self._supply_styler(self.data.supply_transactions_violations)

    @property
    def use_transactions_violations(self) -> Styler | None:
        """Styled use transaction violations, or ``None`` if no tolerances configured."""
        if self.data.use_transactions_violations is None:
            return None
        return self._use_styler(self.data.use_transactions_violations)

    @property
    def summary(self) -> Styler:
        """Styled summary table."""
        return _style_unbalanced_targets_summary(self.data.summary, display_unit=self.display_unit)

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
        _write_inspection_to_excel(self, path, self.display_unit, self.rel_base)

    def set_display_unit(self, display_unit: float | None) -> "UnbalancedTargetsInspection":
        """Return a copy with ``display_unit`` set to the given value.

        Parameters
        ----------
        display_unit : float or None
            Must be a positive power of 10 (e.g. 1000, 1_000_000). ``None``
            disables division.
        """
        if display_unit is not None:
            import math
            log = math.log10(display_unit) if display_unit > 0 else float("nan")
            if not (display_unit > 0 and abs(log - round(log)) < 1e-9):
                raise ValueError(
                    f"display_unit must be a positive power of 10 "
                    f"(e.g. 1_000, 1_000_000). Got {display_unit}."
                )
        return dataclasses.replace(self, display_unit=display_unit)

    def set_rel_base(self, rel_base: int) -> "UnbalancedTargetsInspection":
        """Return a copy with ``rel_base`` set to the given value.

        Parameters
        ----------
        rel_base : int
            Must be 100, 1000, or 10000.
        """
        if rel_base not in (100, 1000, 10000):
            raise ValueError(
                f"rel_base must be 100, 1000, or 10000. Got {rel_base}."
            )
        return dataclasses.replace(self, rel_base=rel_base)


def inspect_unbalanced_targets(
    sut: SUT,
    transactions: str | list[str] | None = None,
    categories: str | list[str] | None = None,
    sort: bool = False,
) -> UnbalancedTargetsInspection:
    """
    Return supply and use column totals compared against balancing targets,
    restricted to rows where the absolute difference exceeds 1.

    Produces eight tables: category-level and transaction-level views for
    supply and use, each with a corresponding violations subset.

    The category-level tables show one row per (transaction, category)
    combination. The transaction-level tables aggregate targets and actuals
    by summing over categories, with tolerances scaled accordingly.

    Only rows where ``abs(diff_*) > 1`` appear in any table.

    Parameters
    ----------
    sut : SUT
        The SUT collection. Must have ``balancing_id``, ``metadata``, and
        ``balancing_targets`` set.
    transactions : str, list of str, or None, optional
        Transaction codes to include. Accepts the same pattern syntax as
        :func:`~sutlab.sut.filter_rows`. ``None`` includes all transactions.
        Applied to both category-level and transaction-level tables.
    categories : str, list of str, or None, optional
        Category codes to include. Same pattern syntax as ``transactions``.
        ``None`` includes all categories.
        Applied to the category-level tables only; the transaction-level
        tables always aggregate over all categories.
    sort : bool, optional
        When ``True``, rows are sorted by ``abs(diff_*)`` descending.
        Default ``False`` preserves the order from the targets DataFrame.

    Returns
    -------
    UnbalancedTargetsInspection
        A dataclass whose ``data`` attribute holds the raw DataFrames.

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
            "sut.metadata is required to call inspect_unbalanced_targets. "
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

    # If tolerances are configured but tol columns are not yet present on the
    # category-level targets, resolve them silently before building the tables.
    working_sut = sut
    if has_tolerances:
        tol_col_supply = f"tol_{cols.price_basic}"
        tol_col_use = f"tol_{cols.price_purchasers}"
        supply_needs_resolve = tol_col_supply not in sut.balancing_targets.supply.columns
        use_needs_resolve = tol_col_use not in sut.balancing_targets.use.columns
        if supply_needs_resolve or use_needs_resolve:
            from sutlab.balancing import resolve_target_tolerances
            working_sut = resolve_target_tolerances(sut)

    tolerances = (
        working_sut.balancing_config.target_tolerances
        if has_tolerances
        else None
    )

    classifications = sut.metadata.classifications

    trans_names = _build_transaction_names(classifications, cols.transaction)
    cat_names = _build_combined_category_names(classifications, cols.category)
    has_labels = bool(trans_names or cat_names)

    supply_categories = _build_categories_table(
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

    use_categories = _build_categories_table(
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

    supply_transactions = _build_transactions_table(
        sut=working_sut,
        data_df=working_sut.supply,
        targets_df=working_sut.balancing_targets.supply,
        price_col=cols.price_basic,
        id_col=cols.id,
        trans_col=cols.transaction,
        cat_col=cols.category,
        transactions_filter=transactions,
        has_tolerances=has_tolerances,
        tolerances=tolerances,
        sort=sort,
        trans_names=trans_names,
        has_labels=has_labels,
    )

    use_transactions = _build_transactions_table(
        sut=working_sut,
        data_df=working_sut.use,
        targets_df=working_sut.balancing_targets.use,
        price_col=cols.price_purchasers,
        id_col=cols.id,
        trans_col=cols.transaction,
        cat_col=cols.category,
        transactions_filter=transactions,
        has_tolerances=has_tolerances,
        tolerances=tolerances,
        sort=sort,
        trans_names=trans_names,
        has_labels=has_labels,
    )

    if has_tolerances:
        supply_viol_col = f"violation_{cols.price_basic}"
        supply_cat_viol_mask = supply_categories[supply_viol_col].notna() & (supply_categories[supply_viol_col] != 0)
        supply_categories_violations = supply_categories[supply_cat_viol_mask].copy()

        use_viol_col = f"violation_{cols.price_purchasers}"
        use_cat_viol_mask = use_categories[use_viol_col].notna() & (use_categories[use_viol_col] != 0)
        use_categories_violations = use_categories[use_cat_viol_mask].copy()

        supply_trans_viol_mask = supply_transactions[supply_viol_col].notna() & (supply_transactions[supply_viol_col] != 0)
        supply_transactions_violations = supply_transactions[supply_trans_viol_mask].copy()

        use_trans_viol_mask = use_transactions[use_viol_col].notna() & (use_transactions[use_viol_col] != 0)
        use_transactions_violations = use_transactions[use_trans_viol_mask].copy()
    else:
        supply_categories_violations = None
        use_categories_violations = None
        supply_transactions_violations = None
        use_transactions_violations = None

    def _largest_diff(df, col_prefix):
        """Return the signed value with the largest absolute value in the first
        column whose name starts with ``col_prefix``. NaN when the table is empty."""
        matching = [c for c in df.columns if c.startswith(col_prefix)]
        if not matching or df.empty:
            return float("nan")
        col = matching[0]
        return df[col].loc[df[col].abs().idxmax()]

    supply_diff_col = f"diff_{cols.price_basic}"
    use_diff_col = f"diff_{cols.price_purchasers}"
    supply_viol_col_name = f"violation_{cols.price_basic}"
    use_viol_col_name = f"violation_{cols.price_purchasers}"

    summary_rows = {
        "supply_transactions": (len(supply_transactions), _largest_diff(supply_transactions, supply_diff_col)),
        "supply_categories": (len(supply_categories), _largest_diff(supply_categories, supply_diff_col)),
        "use_transactions": (len(use_transactions), _largest_diff(use_transactions, use_diff_col)),
        "use_categories": (len(use_categories), _largest_diff(use_categories, use_diff_col)),
    }
    if has_tolerances:
        summary_rows["supply_transactions_violations"] = (len(supply_transactions_violations), _largest_diff(supply_transactions_violations, supply_viol_col_name))
        summary_rows["supply_categories_violations"] = (len(supply_categories_violations), _largest_diff(supply_categories_violations, supply_viol_col_name))
        summary_rows["use_transactions_violations"] = (len(use_transactions_violations), _largest_diff(use_transactions_violations, use_viol_col_name))
        summary_rows["use_categories_violations"] = (len(use_categories_violations), _largest_diff(use_categories_violations, use_viol_col_name))
    summary = pd.DataFrame(
        {
            "n_unbalanced": [v[0] for v in summary_rows.values()],
            "largest_diff": [v[1] for v in summary_rows.values()],
        },
        index=pd.Index(list(summary_rows.keys()), name="table"),
    )

    return UnbalancedTargetsInspection(
        data=UnbalancedTargetsData(
            supply_categories=supply_categories,
            use_categories=use_categories,
            supply_categories_violations=supply_categories_violations,
            use_categories_violations=use_categories_violations,
            supply_transactions=supply_transactions,
            use_transactions=use_transactions,
            supply_transactions_violations=supply_transactions_violations,
            use_transactions_violations=use_transactions_violations,
            summary=summary,
        ),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_categories_table(
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
    """Build supply or use comparison table at (transaction, category) level."""
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

    # Filter to rows with abs(diff) > 1 — NaN diff rows are excluded.
    result = result[result[diff_col].abs() > 1]

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


def _build_transactions_table(
    sut: SUT,
    data_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    price_col: str,
    id_col: str,
    trans_col: str,
    cat_col: str,
    transactions_filter: str | list[str] | None,
    has_tolerances: bool,
    tolerances,
    sort: bool,
    trans_names: dict[str, str],
    has_labels: bool,
) -> pd.DataFrame:
    """Build supply or use comparison table aggregated to transaction level.

    Targets and actuals are summed over all categories. The ``categories``
    filter is intentionally not applied — the transaction-level table always
    reflects the full transaction total. The absolute tolerance component is
    scaled by the number of categories per transaction.
    """
    tol_col = f"tol_{price_col}"
    violation_col = f"violation_{price_col}"
    target_col = f"target_{price_col}"
    diff_col = f"diff_{price_col}"
    rel_col = f"rel_{price_col}"
    n_cat_col = "_n_categories"

    # Filter targets to the active balancing member.
    member_targets = targets_df[targets_df[id_col] == sut.balancing_id].copy()

    # Apply transactions filter.
    if transactions_filter is not None:
        patterns = (
            [transactions_filter]
            if isinstance(transactions_filter, str)
            else list(transactions_filter)
        )
        all_trans = member_targets[trans_col].dropna().unique().tolist()
        matched_trans = _match_codes(all_trans, patterns)
        member_targets = member_targets[member_targets[trans_col].isin(matched_trans)]

    # Count categories per transaction (used to scale absolute tolerance).
    n_cats = (
        member_targets
        .groupby(trans_col, dropna=False)[cat_col]
        .count()
        .reset_index()
        .rename(columns={cat_col: n_cat_col})
    )

    # Aggregate targets to transaction level (NaN preserved via min_count=1).
    agg_targets = (
        member_targets
        .groupby(trans_col, dropna=False)[price_col]
        .sum(min_count=1)
        .reset_index()
        .rename(columns={price_col: target_col})
    )

    # Aggregate actuals to transaction level.
    member_data = data_df[data_df[id_col] == sut.balancing_id]
    actuals = (
        member_data
        .groupby(trans_col, dropna=False)[price_col]
        .sum(min_count=1)
        .reset_index()
    )

    # Build result from aggregated targets.
    result = agg_targets.merge(actuals, on=[trans_col], how="left")
    result[price_col] = result[price_col].fillna(0.0)
    result = result.merge(n_cats, on=[trans_col], how="left")

    # Derived columns.
    result[diff_col] = result[price_col] - result[target_col]
    result[rel_col] = (
        result[price_col]
        / result[target_col].replace(0, float("nan"))
        - 1
    )

    # Transaction-level tolerances with n_categories-scaled absolute component.
    if has_tolerances and tolerances is not None:
        from sutlab.balancing._tolerances import _resolve_transaction_tolerances
        result = _resolve_transaction_tolerances(
            trans_targets=result,
            tolerances=tolerances,
            trans_col=trans_col,
            target_price_col=target_col,
            n_cat_col=n_cat_col,
            tol_col_name=tol_col,
        )
    else:
        result[tol_col] = float("nan")

    result = result.drop(columns=[n_cat_col])

    # Tolerance violation.
    result[violation_col] = _compute_tol_violation(result[diff_col], result[tol_col])

    # Column order.
    result = result[[trans_col, price_col, target_col, diff_col, rel_col, tol_col, violation_col]]

    # Sort by absolute diff if requested.
    if sort:
        result = result.sort_values(diff_col, key=lambda s: s.abs(), ascending=False)

    # Filter to rows with abs(diff) > 1 — NaN diff rows are excluded.
    result = result[result[diff_col].abs() > 1]

    # Build index.
    result = result.set_index([trans_col])
    if has_labels:
        trans_vals = result.index.get_level_values(trans_col)
        trans_txt_col = f"{trans_col}_txt"
        result.index = pd.MultiIndex.from_arrays(
            [
                trans_vals,
                [trans_names.get(str(t), "") for t in trans_vals],
            ],
            names=[trans_col, trans_txt_col],
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
