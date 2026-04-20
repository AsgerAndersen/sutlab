"""
inspect_aggregates_nominal: nominal GDP decomposition from a supply-use table.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pandas.io.formats.style import Styler

from sutlab.sut import SUT
from sutlab.inspect._shared import _build_growth_table, _write_inspection_to_excel
from sutlab.inspect._style import (
    _make_number_formatter,
    _make_percentage_formatter,
    _style_aggregates_nominal_table,
)
from sutlab.inspect._tables_comparison import TablesComparison, _compute_comparison_table_fields


# --- Block names ---
_PRODUCTION_BLOCK = "Production"
_EXPENDITURE_BLOCK = "Expenditure"

# --- Derived row labels ---
_LABEL_GVA = "Gross Value Added"
_LABEL_IMPORT_DUTIES = "Import duties"
_LABEL_TOTAL_PRODUCT_TAXES = "Total product taxes, netto"
_LABEL_GDP = "GDP"
_BALANCE_BLOCK = "Balance"
_LABEL_DOMESTIC_FINAL_EXPENDITURE = "Domestic final expenditure"
_LABEL_EXPORT_NETTO = "Export, netto"

# --- ESA codes ---
_ESA_OUTPUT = "P1"
_ESA_INTERMEDIATE = "P2"
_ESA_EXPORTS = "P6"
_ESA_IMPORTS = "P7"
_ESA_IMPORT_DUTIES = "D2121"


@dataclass
class AggregatesNominalData:
    """Raw DataFrames underlying an :class:`AggregatesNominalInspection`.

    Use this directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding properties on
    :class:`AggregatesNominalInspection` once styling is added.
    """

    gdp: pd.DataFrame
    gdp_growth: pd.DataFrame
    gdp_distribution: pd.DataFrame


@dataclass
class AggregatesNominalInspection:
    """
    Result of :func:`inspect_aggregates_nominal`.

    Raw DataFrames are available under ``result.data``.

    Attributes
    ----------
    data.gdp : pd.DataFrame
        Nominal GDP decomposition table. Columns are id values (years).
        Rows have a 2-level MultiIndex: level 0 is the block name
        (``"Production"`` or ``"Expenditure"``), level 1 is the component
        label. Derived rows (GVA, GDP, etc.) appear inline after their
        components.
    data.gdp_growth : pd.DataFrame
        Year-on-year growth rates for each row in ``data.gdp``. Same
        structure as ``data.gdp`` but without the Balance block (growth of
        a statistical discrepancy is not meaningful). Values are fractions
        (e.g. ``0.05`` for a 5% increase). The first id column is ``NaN``
        throughout.
    data.gdp_distribution : pd.DataFrame
        Shares of GDP for each row. Same structure as ``data.gdp`` but
        without the Balance block. Production block rows are expressed as
        shares of Production GDP; Expenditure block rows as shares of
        Expenditure GDP. Values are fractions (e.g. ``0.10`` for 10%).
        The GDP rows themselves are included and always equal 1.0.
    """

    data: AggregatesNominalData
    display_unit: float | None = None
    rel_base: int = 100
    _all_rel: bool = dataclasses.field(default=False, repr=False)

    def _number_fmt(self):
        if self._all_rel:
            return _make_percentage_formatter(self.rel_base)
        return _make_number_formatter(self.display_unit)

    @property
    def gdp(self) -> Styler:
        """Styled GDP decomposition table for display in a Jupyter notebook."""
        return _style_aggregates_nominal_table(
            self.data.gdp, self._number_fmt()
        )

    @property
    def gdp_growth(self) -> Styler:
        """Styled year-on-year growth table for display in a Jupyter notebook."""
        return _style_aggregates_nominal_table(
            self.data.gdp_growth, _make_percentage_formatter(self.rel_base)
        )

    @property
    def gdp_distribution(self) -> Styler:
        """Styled GDP share table for display in a Jupyter notebook."""
        return _style_aggregates_nominal_table(
            self.data.gdp_distribution, _make_percentage_formatter(self.rel_base)
        )

    def write_to_excel(self, path: str | Path) -> None:
        """Write the inspection tables to an Excel file.

        Parameters
        ----------
        path : str or Path
            Destination ``.xlsx`` file path.
        """
        _write_inspection_to_excel(self, path, self.display_unit, self.rel_base)

    def set_display_unit(self, display_unit: float | None) -> "AggregatesNominalInspection":
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

    def set_rel_base(self, rel_base: int) -> "AggregatesNominalInspection":
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

    def inspect_tables_comparison(self, other: "AggregatesNominalInspection") -> TablesComparison:
        """Compare all tables in this inspection with another :class:`AggregatesNominalInspection`.

        Computes element-wise differences and relative changes between
        corresponding tables. Index alignment uses an outer join.

        Parameters
        ----------
        other : AggregatesNominalInspection
            The inspection result to compare against.

        Returns
        -------
        TablesComparison
            Contains ``.diff`` and ``.rel`` as
            :class:`AggregatesNominalInspection` instances.

        Raises
        ------
        TypeError
            If ``other`` is not a :class:`AggregatesNominalInspection`.
        """
        if not isinstance(other, AggregatesNominalInspection):
            raise TypeError(
                f"Expected AggregatesNominalInspection, got {type(other).__name__}."
            )
        diff_fields, rel_fields = _compute_comparison_table_fields(self.data, other.data)
        diff = AggregatesNominalInspection(
            data=AggregatesNominalData(**diff_fields),
            display_unit=self.display_unit,
            rel_base=self.rel_base,
        )
        rel = AggregatesNominalInspection(
            data=AggregatesNominalData(**rel_fields),
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            _all_rel=True,
        )
        return TablesComparison(
            diff=diff,
            rel=rel,
            display_unit=self.display_unit,
            rel_base=self.rel_base,
        )


def inspect_aggregates_nominal(
    sut: SUT,
    gdp_decomp: pd.DataFrame | None = None,
) -> AggregatesNominalInspection:
    """
    Build a nominal GDP decomposition table from a supply-use table.

    Produces a single DataFrame decomposing GDP from two angles —
    Production and Expenditure. Both approaches are shown simultaneously;
    any discrepancy reflects an unbalanced SUT and is part of the
    inspection value.

    The Production block sums output (P1) minus intermediate consumption
    (P2) to get Gross Value Added, then adds product taxes and import
    duties to reach GDP.

    The Expenditure block sums domestic final use (all use-side
    transactions except P2 and P6), then adds net exports (P6 minus P7)
    to reach GDP.

    Parameters
    ----------
    sut : SUT
        Supply-use table collection. Must have ``price_basis =
        "current_year"``. Metadata with a transactions classification
        (including ``esa_code`` and ``table`` columns) is required. The
        ``gdp_decomp`` column on the transactions classification is used
        unless overridden.
    gdp_decomp : DataFrame or None, optional
        Override for the ``gdp_decomp`` mapping. When provided, must have
        two columns: the actual transaction column name (from
        ``SUTColumns``) and ``"gdp_decomp"``. Overrides the ``gdp_decomp``
        column from the transactions classification. Transaction codes not
        present in the override are treated as having no ``gdp_decomp``
        label and are excluded from the table.

    Returns
    -------
    AggregatesNominalInspection
        Inspection result with a ``.data.gdp`` DataFrame. Columns are id
        values sorted ascending. Rows have a 2-level MultiIndex:
        ``"Production"`` or ``"Expenditure"`` as level 0, component label
        as level 1.

    Raises
    ------
    ValueError
        If ``sut.price_basis`` is not ``"current_year"``, if metadata or
        the transactions classification is absent, or if the ``gdp_decomp``
        column is absent from both the classification table and the
        override argument.
    """
    if sut.price_basis != "current_year":
        raise ValueError(
            f"inspect_aggregates_nominal requires price_basis='current_year', "
            f"got '{sut.price_basis}'."
        )

    if sut.metadata is None:
        raise ValueError(
            "inspect_aggregates_nominal requires sut.metadata to be set."
        )

    cols = sut.metadata.columns

    classifications = sut.metadata.classifications
    if classifications is None or classifications.transactions is None:
        raise ValueError(
            "inspect_aggregates_nominal requires a transactions classification "
            "table (SUTClassifications.transactions) with 'esa_code' and "
            "'table' columns."
        )

    trans_class = classifications.transactions
    trans_col = cols.transaction
    id_col = cols.id

    # --- Resolve gdp_decomp mapping ---
    trans_info = _resolve_trans_info(trans_class, trans_col, gdp_decomp)

    # --- Collect sorted id values (columns of the output DataFrame) ---
    id_values = _get_sorted_id_values(sut.supply, sut.use, id_col)

    # --- Build blocks ---
    production_rows = _build_production_rows(sut, cols, trans_info, trans_col, id_col, id_values)
    expenditure_rows = _build_expenditure_rows(sut, cols, trans_info, trans_col, id_col, id_values)

    # --- Balance row: GDP (production) - GDP (expenditure) ---
    prod_gdp = dict(next(vals for label, vals in production_rows if label == _LABEL_GDP))
    exp_gdp = dict(next(vals for label, vals in expenditure_rows if label == _LABEL_GDP))
    balance_values = {id_val: prod_gdp.get(id_val, float("nan")) - exp_gdp.get(id_val, float("nan"))
                      for id_val in id_values}

    # --- Assemble into final DataFrame ---
    index_tuples = (
        [(_PRODUCTION_BLOCK, label) for label, _ in production_rows] +
        [(_EXPENDITURE_BLOCK, label) for label, _ in expenditure_rows] +
        [(_BALANCE_BLOCK, _LABEL_GDP)]
    )
    data_rows = [values for _, values in production_rows + expenditure_rows] + [balance_values]

    index = pd.MultiIndex.from_tuples(index_tuples)
    gdp_df = pd.DataFrame(data_rows, index=index, columns=id_values)

    # Growth and distribution tables: drop the Balance block.
    gdp_without_balance = gdp_df[gdp_df.index.get_level_values(0) != _BALANCE_BLOCK]

    gdp_growth_df = _build_growth_table(gdp_without_balance)
    gdp_distribution_df = _build_gdp_distribution(gdp_without_balance)

    return AggregatesNominalInspection(
        data=AggregatesNominalData(
            gdp=gdp_df,
            gdp_growth=gdp_growth_df,
            gdp_distribution=gdp_distribution_df,
        )
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_trans_info(
    trans_class: pd.DataFrame,
    trans_col: str,
    gdp_decomp_override: pd.DataFrame | None,
) -> pd.DataFrame:
    """Return a DataFrame with [trans_col, esa_code, table, gdp_decomp].

    If ``gdp_decomp_override`` is provided it replaces any existing
    ``gdp_decomp`` column from ``trans_class``. Otherwise ``trans_class``
    must already contain a ``gdp_decomp`` column.

    Parameters
    ----------
    trans_class : pd.DataFrame
        The transactions classification table from
        ``SUTClassifications.transactions``.
    trans_col : str
        Actual transaction column name (e.g. ``"trans"``).
    gdp_decomp_override : pd.DataFrame or None
        Optional override with columns ``[trans_col, "gdp_decomp"]``.

    Returns
    -------
    pd.DataFrame
        Merged table with at least ``trans_col``, ``"esa_code"``,
        ``"table"``, and ``"gdp_decomp"`` columns.
    """
    if gdp_decomp_override is not None:
        if trans_col not in gdp_decomp_override.columns:
            raise ValueError(
                f"gdp_decomp override must have a '{trans_col}' column. "
                f"Found columns: {list(gdp_decomp_override.columns)}."
            )
        if "gdp_decomp" not in gdp_decomp_override.columns:
            raise ValueError(
                "gdp_decomp override must have a 'gdp_decomp' column. "
                f"Found columns: {list(gdp_decomp_override.columns)}."
            )
        base = trans_class.drop(columns=["gdp_decomp"], errors="ignore")
        trans_info = base.merge(
            gdp_decomp_override[[trans_col, "gdp_decomp"]],
            on=trans_col,
            how="left",
        )
    else:
        if "gdp_decomp" not in trans_class.columns:
            raise ValueError(
                "inspect_aggregates_nominal requires a 'gdp_decomp' column on "
                "the transactions classification. Either add it to the "
                "classification table or supply it via the gdp_decomp argument."
            )
        trans_info = trans_class.copy()

    return trans_info


def _get_sorted_id_values(
    supply: pd.DataFrame,
    use: pd.DataFrame,
    id_col: str,
) -> list:
    """Return sorted unique id values from supply and use combined."""
    supply_ids = supply[id_col].unique().tolist()
    use_ids = use[id_col].unique().tolist()
    all_ids = list(dict.fromkeys(supply_ids + use_ids))
    return sorted(all_ids)


def _sum_gdp_rows(
    df: pd.DataFrame,
    value_col: str,
    trans_subset: pd.DataFrame,
    trans_col: str,
    id_col: str,
    id_values: list,
    sign: int = 1,
) -> list[tuple[str, dict]]:
    """Sum a price column from df for each gdp_decomp label in trans_subset.

    Multiple transaction codes that share the same ``gdp_decomp`` label are
    summed into a single row. Row order follows the first appearance of each
    label in ``trans_subset``.

    Parameters
    ----------
    df : pd.DataFrame
        Supply or use DataFrame to read values from.
    value_col : str
        Price column to sum (e.g. ``price_basic`` or ``price_purchasers``).
    trans_subset : pd.DataFrame
        Subset of the transactions classification. Must have columns
        ``trans_col`` and ``"gdp_decomp"``. Rows where ``gdp_decomp`` is
        NaN are ignored.
    trans_col : str
        Actual transaction column name.
    id_col : str
        Actual id column name.
    id_values : list
        Ordered id values to use as the result dict keys.
    sign : int, optional
        Multiply every value by this factor. Use ``-1`` for P2 and P7 rows.
        Default ``1``.

    Returns
    -------
    list of (label, {id: value}) tuples
        One tuple per unique gdp_decomp label, in first-appearance order.
        Values are NaN where the id is absent from the data.
    """
    relevant = trans_subset.dropna(subset=["gdp_decomp"])
    if relevant.empty:
        return []

    # Ordered unique gdp_decomp labels (preserving first-appearance order)
    label_order = list(dict.fromkeys(relevant["gdp_decomp"].tolist()))

    # Map: transaction code → gdp_decomp label
    trans_to_label = dict(zip(relevant[trans_col], relevant["gdp_decomp"]))

    # Filter df to relevant transaction codes and attach the label
    filtered = df[df[trans_col].isin(trans_to_label)].copy()
    filtered["_gdp_label"] = filtered[trans_col].map(trans_to_label)

    # Group by (gdp_label, id) and sum
    if not filtered.empty:
        grouped = (
            filtered
            .groupby(["_gdp_label", id_col], dropna=False)[value_col]
            .sum(min_count=1)
        )
    else:
        grouped = pd.Series(dtype=float, name=value_col)

    result = []
    for label in label_order:
        if not filtered.empty and label in grouped.index.get_level_values("_gdp_label"):
            series = grouped.loc[label].reindex(id_values)
        else:
            series = pd.Series(float("nan"), index=id_values)

        if sign != 1:
            series = series * sign

        result.append((label, series.to_dict()))

    return result


def _sum_row_dicts(row_dicts: list[dict], id_values: list) -> dict:
    """Sum a list of {id: value} dicts with NaN-aware addition.

    Uses ``sum(min_count=1)``: if every component for a given id is NaN the
    result is NaN; otherwise NaN components are treated as zero.

    Parameters
    ----------
    row_dicts : list of dict
        Each dict maps id values to numeric values (or NaN).
    id_values : list
        Ordered id values; the result dict will have exactly these keys.

    Returns
    -------
    dict
        {id: summed_value} with the same key set as ``id_values``.
    """
    if not row_dicts:
        return {id_val: float("nan") for id_val in id_values}

    series_list = [pd.Series(d) for d in row_dicts]
    total = pd.concat(series_list, axis=1).sum(axis=1, min_count=1)
    return total.reindex(id_values).to_dict()


def _get_product_tax_columns(cols, use_df: pd.DataFrame) -> list[str]:
    """Return product tax/subsidy column names in use DataFrame column order.

    Considers only the four tax/subsidy roles on ``SUTColumns``:
    ``product_taxes``, ``product_subsidies``,
    ``product_taxes_less_subsidies``, and ``vat``. Margin roles
    (trade, wholesale, retail, transport) are excluded. Returns only
    columns that are both mapped (not ``None``) and present in ``use_df``.

    Parameters
    ----------
    cols : SUTColumns
        Column role mapping.
    use_df : pd.DataFrame
        Use DataFrame; column order determines the result order.

    Returns
    -------
    list of str
        Actual column names for present product tax/subsidy columns.
    """
    tax_roles = {
        cols.product_taxes,
        cols.product_subsidies,
        cols.product_taxes_less_subsidies,
        cols.vat,
    }
    tax_cols_set = {col for col in tax_roles if col is not None}
    return [col for col in use_df.columns if col in tax_cols_set]


def _build_production_rows(
    sut: SUT,
    cols,
    trans_info: pd.DataFrame,
    trans_col: str,
    id_col: str,
    id_values: list,
) -> list[tuple[str, dict]]:
    """Build (label, values) pairs for the Production block.

    Row order:
      1. P1 (output) rows — one per gdp_decomp label, basic prices
      2. P2 (intermediate consumption) rows — purchasers' prices, sign × -1
      3. Gross Value Added (derived sum of rows 1-2)
      4. One row per present product tax/subsidy column in use — actual column
         name with first letter capitalised (product_taxes,
         product_subsidies, product_taxes_less_subsidies, vat roles only;
         margin columns excluded)
      5. Import duties (if D2121 transactions present) — basic prices
      6. Total product taxes, netto (derived sum of rows 4-5)
      7. GDP (derived: GVA + Total product taxes, netto)
    """
    rows = []

    # --- P1: Output (supply, basic prices, as-is) ---
    p1_trans = trans_info[trans_info["esa_code"] == _ESA_OUTPUT]
    p1_rows = _sum_gdp_rows(
        df=sut.supply,
        value_col=cols.price_basic,
        trans_subset=p1_trans,
        trans_col=trans_col,
        id_col=id_col,
        id_values=id_values,
    )
    rows.extend(p1_rows)

    # --- P2: Intermediate consumption (use, purchasers' prices, × -1) ---
    p2_trans = trans_info[trans_info["esa_code"] == _ESA_INTERMEDIATE]
    p2_rows = _sum_gdp_rows(
        df=sut.use,
        value_col=cols.price_purchasers,
        trans_subset=p2_trans,
        trans_col=trans_col,
        id_col=id_col,
        id_values=id_values,
        sign=-1,
    )
    rows.extend(p2_rows)

    # --- Gross Value Added (derived) ---
    gva_values = _sum_row_dicts([vals for _, vals in p1_rows + p2_rows], id_values)
    rows.append((_LABEL_GVA, gva_values))

    # --- Product tax/subsidy rows (one per present column, label capitalised) ---
    tax_layer_cols = _get_product_tax_columns(cols, sut.use)
    tax_component_dicts = []

    for layer_col in tax_layer_cols:
        layer_series = (
            sut.use
            .groupby(id_col, dropna=False)[layer_col]
            .sum(min_count=1)
            .reindex(id_values)
        )
        layer_values = layer_series.to_dict()
        rows.append((layer_col.capitalize(), layer_values))
        tax_component_dicts.append(layer_values)

    # --- D2121: Import duties (supply, basic prices, as-is) ---
    d2121_trans_codes = trans_info.loc[
        trans_info["esa_code"] == _ESA_IMPORT_DUTIES, trans_col
    ].tolist()

    if d2121_trans_codes:
        d2121_mask = sut.supply[trans_col].isin(d2121_trans_codes)
        import_duties_series = (
            sut.supply.loc[d2121_mask]
            .groupby(id_col, dropna=False)[cols.price_basic]
            .sum(min_count=1)
            .reindex(id_values)
        )
        import_duties_values = import_duties_series.to_dict()
        rows.append((_LABEL_IMPORT_DUTIES, import_duties_values))
        tax_component_dicts.append(import_duties_values)

    # --- Total product taxes, netto (derived) ---
    total_tax_values = _sum_row_dicts(tax_component_dicts, id_values)
    rows.append((_LABEL_TOTAL_PRODUCT_TAXES, total_tax_values))

    # --- GDP (derived: GVA + total product taxes) ---
    gdp_values = _sum_row_dicts([gva_values, total_tax_values], id_values)
    rows.append((_LABEL_GDP, gdp_values))

    return rows


def _build_expenditure_rows(
    sut: SUT,
    cols,
    trans_info: pd.DataFrame,
    trans_col: str,
    id_col: str,
    id_values: list,
) -> list[tuple[str, dict]]:
    """Build (label, values) pairs for the Expenditure block.

    Row order:
      1. Domestic final use rows — use-side transactions, esa_code not in
         {P2, P6}, purchasers' prices, as-is
      2. Domestic final expenditure (derived sum of rows above)
      3. P6 (exports) rows — use-side, purchasers' prices, as-is
      4. P7 (imports) rows — supply-side, basic prices, sign × -1
      5. Export, netto (derived sum of P6 + P7 rows)
      6. GDP (derived: Domestic final expenditure + Export, netto)
    """
    rows = []

    # --- Domestic final use (use-side, esa_code not P2 or P6) ---
    domestic_trans = trans_info[
        (trans_info["table"] == "use") &
        (~trans_info["esa_code"].isin({_ESA_INTERMEDIATE, _ESA_EXPORTS}))
    ]
    domestic_rows = _sum_gdp_rows(
        df=sut.use,
        value_col=cols.price_purchasers,
        trans_subset=domestic_trans,
        trans_col=trans_col,
        id_col=id_col,
        id_values=id_values,
    )
    rows.extend(domestic_rows)

    # --- Domestic final expenditure (derived) ---
    dfe_values = _sum_row_dicts([vals for _, vals in domestic_rows], id_values)
    rows.append((_LABEL_DOMESTIC_FINAL_EXPENDITURE, dfe_values))

    # --- P6: Exports (use-side, purchasers' prices, as-is) ---
    p6_trans = trans_info[trans_info["esa_code"] == _ESA_EXPORTS]
    p6_rows = _sum_gdp_rows(
        df=sut.use,
        value_col=cols.price_purchasers,
        trans_subset=p6_trans,
        trans_col=trans_col,
        id_col=id_col,
        id_values=id_values,
    )
    rows.extend(p6_rows)

    # --- P7: Imports (supply-side, basic prices, × -1) ---
    p7_trans = trans_info[trans_info["esa_code"] == _ESA_IMPORTS]
    p7_rows = _sum_gdp_rows(
        df=sut.supply,
        value_col=cols.price_basic,
        trans_subset=p7_trans,
        trans_col=trans_col,
        id_col=id_col,
        id_values=id_values,
        sign=-1,
    )
    rows.extend(p7_rows)

    # --- Export, netto (derived: P6 + P7, where P7 already negated) ---
    export_netto_values = _sum_row_dicts(
        [vals for _, vals in p6_rows + p7_rows],
        id_values,
    )
    rows.append((_LABEL_EXPORT_NETTO, export_netto_values))

    # --- GDP (derived: DFE + Export, netto) ---
    gdp_values = _sum_row_dicts([dfe_values, export_netto_values], id_values)
    rows.append((_LABEL_GDP, gdp_values))

    return rows


def _build_gdp_distribution(gdp_without_balance: pd.DataFrame) -> pd.DataFrame:
    """Build GDP share table from a gdp DataFrame with Balance block already removed.

    Each row in the Production block is divided by the Production GDP row;
    each row in the Expenditure block is divided by the Expenditure GDP row.
    Division by zero or NaN denominators yields NaN via pandas.

    Parameters
    ----------
    gdp_without_balance : pd.DataFrame
        The ``gdp`` DataFrame with the Balance block rows removed. Must have
        a 2-level MultiIndex with block name at level 0 and component label
        at level 1. Columns are id values.

    Returns
    -------
    pd.DataFrame
        Same shape and index as ``gdp_without_balance``, with fractional
        share values.
    """
    blocks = []
    for block, label_gdp in [
        (_PRODUCTION_BLOCK, _LABEL_GDP),
        (_EXPENDITURE_BLOCK, _LABEL_GDP),
    ]:
        block_df = gdp_without_balance.loc[block]
        denominator = block_df.loc[label_gdp].astype(float)
        block_dist = block_df.astype(float).div(denominator)
        blocks.append((block, block_dist))

    return pd.concat(
        [df for _, df in blocks],
        keys=[block for block, _ in blocks],
    )
