# sutlab/aggregate/_shared.py — shared helpers for aggregate_classification_* functions

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from sutlab.sut import SUT


def _validate_mapping(mapping: pd.DataFrame) -> None:
    if not isinstance(mapping, pd.DataFrame):
        raise TypeError(
            f"mapping must be a DataFrame, got {type(mapping).__name__}."
        )
    for col in ("from", "to"):
        if col not in mapping.columns:
            raise ValueError(
                f"mapping must have a '{col}' column. "
                f"Found columns: {list(mapping.columns)}."
            )
    if mapping["from"].isna().any():
        raise ValueError("mapping['from'] must not contain NaN values.")
    if mapping["to"].isna().any():
        raise ValueError("mapping['to'] must not contain NaN values.")
    duplicates = mapping["from"][mapping["from"].duplicated()].tolist()
    if duplicates:
        raise ValueError(
            f"mapping['from'] must not contain duplicate values. "
            f"Duplicates found: {duplicates}."
        )


def _validate_full_coverage(
    mapping: pd.DataFrame,
    dfs: list[pd.DataFrame],
    col: str,
) -> None:
    data_codes: set = set()
    for df in dfs:
        if col in df.columns:
            data_codes |= set(df[col].dropna())
    missing = sorted(data_codes - set(mapping["from"]))
    if missing:
        raise ValueError(
            f"full_coverage=True but the following codes appear in the "
            f"data but are not covered by mapping['from']: {missing}."
        )


def _validate_from_in_classification(
    mapping: pd.DataFrame,
    cls_df: pd.DataFrame,
    col: str,
    cls_label: str,
) -> None:
    known_codes = set(cls_df[col].dropna())
    unknown = sorted(set(mapping["from"]) - known_codes)
    if unknown:
        raise ValueError(
            f"The following codes in mapping['from'] are not present in the "
            f"existing {cls_label} classification: {unknown}. "
            f"Available codes: {sorted(known_codes)}."
        )


def _validate_metadata_columns_simple(metadata: pd.DataFrame, col: str) -> None:
    txt_col = f"{col}_txt"
    if col not in metadata.columns:
        raise ValueError(
            f"metadata must have a '{col}' column. "
            f"Found columns: {list(metadata.columns)}."
        )
    unexpected = set(metadata.columns) - {col, txt_col}
    if unexpected:
        raise ValueError(
            f"metadata has unexpected columns: {sorted(unexpected)}. "
            f"Expected '{col}' and optionally '{txt_col}'."
        )


def _validate_transactions_metadata_columns(metadata: pd.DataFrame, col: str) -> None:
    txt_col = f"{col}_txt"
    required = {col, "table", "esa_code"}
    for req_col in required:
        if req_col not in metadata.columns:
            raise ValueError(
                f"metadata for transactions must have a '{req_col}' column. "
                f"Found columns: {list(metadata.columns)}."
            )
    unexpected = set(metadata.columns) - {col, txt_col, "table", "esa_code"}
    if unexpected:
        raise ValueError(
            f"metadata has unexpected columns: {sorted(unexpected)}. "
            f"Expected '{col}', optionally '{txt_col}', 'table', and 'esa_code'."
        )


def _validate_no_passthrough_collision(
    mapping: pd.DataFrame,
    dfs: list[pd.DataFrame],
    col: str,
) -> None:
    from_codes = set(mapping["from"])
    data_codes: set = set()
    for df in dfs:
        if col in df.columns:
            data_codes |= set(df[col].dropna())
    passthrough_codes = data_codes - from_codes
    collisions = sorted(set(mapping["to"]) & passthrough_codes)
    if collisions:
        raise ValueError(
            f"The following 'to' codes also exist as unmapped (pass-through) "
            f"codes in the data: {collisions}. "
            f"This would silently merge aggregated and original rows."
        )


def _aggregate_long_table(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
    key_cols: list[str],
    col: str,
) -> pd.DataFrame:
    from_to = dict(zip(mapping["from"], mapping["to"]))
    original_codes = df[col]
    mapped_codes = original_codes.map(from_to)
    result = df.copy()
    result[col] = mapped_codes.fillna(original_codes)
    price_cols = [c for c in result.columns if c not in set(key_cols)]
    result = (
        result
        .groupby(key_cols, dropna=False)[price_cols]
        .sum(min_count=1)
        .reset_index()
    )
    return result.sort_values(key_cols).reset_index(drop=True)


def _aggregate_with_esa_filter(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
    key_cols: list[str],
    col: str,
    trans_col: str,
    matching_trans: list[str],
) -> pd.DataFrame:
    """Aggregate col within ESA-relevant rows only; other rows pass through unchanged."""
    mask = df[trans_col].isin(matching_trans)
    relevant = df[mask]
    other = df[~mask]
    if relevant.empty:
        return df.copy().reset_index(drop=True)
    aggregated = _aggregate_long_table(relevant, mapping, key_cols, col)
    if other.empty:
        return aggregated
    result = pd.concat([aggregated, other], ignore_index=True)
    return result.sort_values(key_cols).reset_index(drop=True)


def _build_classification(
    old_cls_df: pd.DataFrame | None,
    mapping: pd.DataFrame,
    metadata: pd.DataFrame | None,
    full_coverage: bool,
    col: str,
) -> pd.DataFrame | None:
    if full_coverage:
        return metadata
    if metadata is None:
        return None
    if old_cls_df is None:
        return metadata
    from_codes = set(mapping["from"])
    unmapped_rows = old_cls_df[~old_cls_df[col].isin(from_codes)]
    return pd.concat([metadata, unmapped_rows], ignore_index=True)


def _update_classification_names(
    classification_names: pd.DataFrame | None,
    col: str,
    classification_name: str | None,
) -> pd.DataFrame | None:
    if classification_names is None:
        return None
    mask = classification_names["dimension"] == col
    if not mask.any():
        return classification_names
    result = classification_names.copy()
    result.loc[mask, "classification"] = classification_name
    return result


def _get_matching_trans(
    transactions_cls: pd.DataFrame,
    trans_col: str,
    esa_codes: list[str],
) -> list[str]:
    """Return transaction codes whose ESA code is in esa_codes."""
    return transactions_cls[transactions_cls["esa_code"].isin(esa_codes)][trans_col].tolist()


def _require_transactions_classification(sut: SUT, function_name: str) -> None:
    """Raise ValueError if transactions classification is absent."""
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            f"sut.metadata.classifications.transactions is required to call "
            f"{function_name}. Load a classifications file with a 'transactions' "
            f"sheet including an 'esa_code' column."
        )
