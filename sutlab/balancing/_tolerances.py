"""
resolve_target_tolerances: attach computed tolerance columns to balancing targets.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sutlab.sut import SUT, TargetTolerances


def resolve_target_tolerances(sut: SUT) -> SUT:
    """Attach computed tolerance columns to the balancing targets.

    For each (transaction, category) combination in the balancing targets,
    looks up the effective tolerance from
    ``sut.balancing_config.target_tolerances`` and appends a
    ``tol_{price_basic}`` column to the supply targets and a
    ``tol_{price_purchasers}`` column to the use targets.

    Tolerance lookup uses two levels:

    - ``target_tolerances.categories`` is checked first for an exact
      (transaction, category) match.
    - ``target_tolerances.transactions`` is used as a fallback for the
      transaction code alone.

    The tolerance value for each row is::

        min(abs(rel * target), abs_tol)

    where ``target`` is the value in the target price column for that row,
    ``rel`` is the relative tolerance (0–1), and ``abs_tol`` is the absolute
    tolerance. Rows with a NaN target value receive a NaN tolerance.

    Parameters
    ----------
    sut : SUT
        The SUT collection. Must have ``metadata``, ``balancing_targets``,
        and ``balancing_config.target_tolerances`` set.

    Returns
    -------
    SUT
        New SUT with updated ``balancing_targets``. The supply targets gain a
        ``tol_{price_basic}`` column; the use targets gain a
        ``tol_{price_purchasers}`` column. All other fields are unchanged.

    Raises
    ------
    ValueError
        If ``sut.metadata``, ``sut.balancing_targets``, or
        ``sut.balancing_config.target_tolerances`` is ``None``.
    ValueError
        If any (transaction, category) combination with a non-NaN target has
        no tolerance entry in either ``target_tolerances.categories`` or
        ``target_tolerances.transactions``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call resolve_target_tolerances. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.balancing_targets is None:
        raise ValueError(
            "sut.balancing_targets is not set. Call set_balancing_targets "
            "first to provide column targets."
        )
    if sut.balancing_config is None or sut.balancing_config.target_tolerances is None:
        raise ValueError(
            "sut.balancing_config.target_tolerances is not set. Call "
            "set_balancing_config first with a BalancingConfig that includes "
            "target_tolerances."
        )

    cols = sut.metadata.columns
    tolerances = sut.balancing_config.target_tolerances

    new_supply = _add_tolerance_column(
        targets_df=sut.balancing_targets.supply,
        tolerances=tolerances,
        trans_col=cols.transaction,
        cat_col=cols.category,
        target_price_col=cols.price_basic,
        tol_col_name=f"tol_{cols.price_basic}",
    )

    new_use = _add_tolerance_column(
        targets_df=sut.balancing_targets.use,
        tolerances=tolerances,
        trans_col=cols.transaction,
        cat_col=cols.category,
        target_price_col=cols.price_purchasers,
        tol_col_name=f"tol_{cols.price_purchasers}",
    )

    new_targets = replace(sut.balancing_targets, supply=new_supply, use=new_use)
    return replace(sut, balancing_targets=new_targets)


def _resolve_transaction_tolerances(
    trans_targets: pd.DataFrame,
    tolerances: TargetTolerances,
    trans_col: str,
    target_price_col: str,
    n_cat_col: str,
    tol_col_name: str,
) -> pd.DataFrame:
    """Resolve transaction-level tolerances for aggregated transaction targets.

    Uses only the ``transactions`` tolerance table — category-level overrides
    are ignored. The absolute tolerance component is scaled by the number of
    categories per transaction::

        abs_tol_effective = n_categories * abs_tol
        tol = min(abs(rel * aggregated_target), abs_tol_effective)

    This reflects what the balancing config implies at the transaction level:
    if each category is allowed to be off by at most ``abs_tol``, the
    transaction total can be off by at most ``n_categories * abs_tol``.

    When no entry exists in ``tolerances.transactions`` for a transaction,
    the tolerance is left as ``NaN`` (no error raised).

    Parameters
    ----------
    trans_targets : DataFrame
        Aggregated targets, one row per transaction. Must contain
        ``trans_col``, ``target_price_col``, and ``n_cat_col``.
    tolerances : TargetTolerances
        Tolerance specification. Only ``transactions`` is used.
    trans_col : str
        Name of the transaction column.
    target_price_col : str
        Name of the aggregated target price column.
    n_cat_col : str
        Name of the column holding the count of categories per transaction.
    tol_col_name : str
        Name of the new tolerance column to add.

    Returns
    -------
    DataFrame
        Copy of ``trans_targets`` with ``tol_col_name`` appended.
    """
    df = trans_targets.copy()
    original_index = df.index

    if tolerances.transactions is not None:
        trans_tol = tolerances.transactions.rename(
            columns={"rel": "_rel", "abs": "_abs"}
        )
        df = df.merge(trans_tol, on=[trans_col], how="left")
    else:
        df["_rel"] = float("nan")
        df["_abs"] = float("nan")

    df.index = original_index

    has_target = df[target_price_col].notna()

    # Scale absolute tolerance by number of categories.
    scaled_abs = df["_abs"] * df[n_cat_col]
    rel_component = (df["_rel"] * df[target_price_col]).abs()

    df["_rel_component"] = rel_component
    df["_scaled_abs"] = scaled_abs
    df[tol_col_name] = df[["_rel_component", "_scaled_abs"]].min(axis=1, skipna=True)
    df.loc[~has_target, tol_col_name] = float("nan")

    df = df.drop(columns=["_rel", "_abs", "_rel_component", "_scaled_abs"])
    return df


def _add_tolerance_column(
    targets_df: pd.DataFrame,
    tolerances: TargetTolerances,
    trans_col: str,
    cat_col: str,
    target_price_col: str,
    tol_col_name: str,
) -> pd.DataFrame:
    """Resolve per-(transaction, category) tolerance and add it as a column.

    Parameters
    ----------
    targets_df : DataFrame
        Supply or use targets DataFrame.
    tolerances : TargetTolerances
        Two-level tolerance specification.
    trans_col : str
        Name of the transaction column.
    cat_col : str
        Name of the category column.
    target_price_col : str
        Name of the price column used for the relative component:
        ``price_basic`` for supply, ``price_purchasers`` for use.
    tol_col_name : str
        Name of the new tolerance column to add.

    Returns
    -------
    DataFrame
        Copy of ``targets_df`` with ``tol_col_name`` appended.
    """
    df = targets_df.copy()
    original_index = df.index

    # Merge categories-level overrides (exact transaction + category match).
    if tolerances.categories is not None:
        cats_tol = tolerances.categories.rename(
            columns={"rel": "_rel_cat", "abs": "_abs_cat"}
        )
        df = df.merge(cats_tol, on=[trans_col, cat_col], how="left")
    else:
        df["_rel_cat"] = float("nan")
        df["_abs_cat"] = float("nan")

    # Merge transaction-level fallback (transaction match only).
    if tolerances.transactions is not None:
        trans_tol = tolerances.transactions.rename(
            columns={"rel": "_rel_trans", "abs": "_abs_trans"}
        )
        df = df.merge(trans_tol, on=[trans_col], how="left")
    else:
        df["_rel_trans"] = float("nan")
        df["_abs_trans"] = float("nan")

    df.index = original_index  # merges reset the index; restore it

    # Categories-level value takes priority; fall back to transaction-level.
    df["_rel"] = df["_rel_cat"].where(df["_rel_cat"].notna(), df["_rel_trans"])
    df["_abs"] = df["_abs_cat"].where(df["_abs_cat"].notna(), df["_abs_trans"])

    # Raise if any row with a non-NaN target has neither rel nor abs set.
    # A row with only one component set is valid — NaN for the other is allowed.
    has_target = df[target_price_col].notna()
    missing_tol = has_target & df["_rel"].isna() & df["_abs"].isna()
    if missing_tol.any():
        missing_pairs = df.loc[missing_tol, [trans_col, cat_col]].drop_duplicates()
        missing_str = ", ".join(
            f"({row[trans_col]!r}, {row[cat_col]!r})"
            for _, row in missing_pairs.iterrows()
        )
        raise ValueError(
            f"No tolerance found for the following (transaction, category) "
            f"combinations: {missing_str}. Add entries to "
            f"target_tolerances.transactions or target_tolerances.categories."
        )

    # Compute tolerance depending on which components are present:
    #   both set  → min(abs(rel * target), abs_tol)
    #   rel only  → abs(rel * target)
    #   abs only  → abs_tol
    # skipna=True handles the partial cases: min ignores NaN components.
    # Rows with a NaN target always receive NaN tolerance regardless.
    rel_component = (df["_rel"] * df[target_price_col]).abs()
    df["_rel_component"] = rel_component
    df[tol_col_name] = df[["_rel_component", "_abs"]].min(axis=1, skipna=True)
    df.loc[~has_target, tol_col_name] = float("nan")

    helper_cols = ["_rel_cat", "_abs_cat", "_rel_trans", "_abs_trans", "_rel", "_abs", "_rel_component"]
    df = df.drop(columns=helper_cols)

    return df
