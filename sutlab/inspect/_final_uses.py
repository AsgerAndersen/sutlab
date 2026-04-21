"""
inspect_final_uses: inspection tables for final use categories.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes, _natural_sort_key
from sutlab.derive import compute_price_layer_rates
from sutlab.inspect._products import _get_price_layer_columns
from sutlab.inspect._shared import _build_growth_table, _display_index, _write_inspection_to_excel
from sutlab.inspect._tables_comparison import TablesComparison, _compute_comparison_table_fields
from sutlab.inspect._style import (
    _format_number,
    _format_percentage,
    _make_number_formatter,
    _make_percentage_formatter,
    _style_final_use_use_table,
    _style_final_use_use_categories_table,
    _style_final_use_use_products_table,
    _style_final_use_price_layers_table,
    _style_tables_description,
)


# ESA code → attribute name on SUTClassifications for category label lookup.
# Only final-use ESA codes that have category classifications are listed here.
_ESA_TO_CLASSIFICATION_ATTR: dict[str, str] = {
    "P31": "individual_consumption",
    "P32": "collective_consumption",
}

# ESA codes excluded from the candidate set for the ``transactions`` argument.
# P2 (intermediate consumption) is the only use-side non-final-use transaction.
# P1 is supply-side and will not appear as table == "use" in the metadata.
_NON_FINAL_USE_ESA_CODES = {"P2"}


@dataclass
class FinalUseInspectionData:
    """Raw DataFrames underlying a :class:`FinalUseInspection`.

    Use these directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding attributes on :class:`FinalUseInspection`
    once styling is added.
    """

    use: pd.DataFrame
    use_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_categories: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_categories_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_categories_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_rates: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_growth: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def tables_description(self) -> pd.DataFrame:
        """DataFrame with ``name`` as index and a ``description`` column."""
        return pd.DataFrame(
            {
                "description": [
                    "Final use totals by transaction (and category where applicable), at purchasers' prices.",
                    "Each transaction expressed as a share of total final use.",
                    "Year-on-year growth rates of final use totals.",
                    "Final use broken down by transaction and category.",
                    "Category values expressed as shares within each transaction.",
                    "Year-on-year growth rates of category values.",
                    "Final use broken down by transaction, category, and product.",
                    "Product values expressed as shares within each transaction-category group.",
                    "Year-on-year growth rates of product-level use values.",
                    "Price layer values (gap between basic and purchasers' prices) by layer.",
                    "Each price layer expressed as a rate relative to basic-price use.",
                    "Each price layer expressed as a share of total price layers.",
                    "Year-on-year growth rates of price layer values.",
                ]
            },
            index=pd.Index(
                [
                    "use",
                    "use_distribution",
                    "use_growth",
                    "use_categories",
                    "use_categories_distribution",
                    "use_categories_growth",
                    "use_products",
                    "use_products_distribution",
                    "use_products_growth",
                    "price_layers",
                    "price_layers_rates",
                    "price_layers_distribution",
                    "price_layers_growth",
                ],
                name="name",
            ),
        )


@dataclass
class FinalUseInspection:
    """
    Result of :func:`inspect_final_uses`.

    Raw DataFrames are available under ``result.data``.

    Attributes
    ----------
    use : pd.DataFrame
        Wide-format use table. Rows have a four-level MultiIndex with
        names ``transaction``, ``transaction_txt``, ``category``,
        ``category_txt``:

        - ``transaction``: transaction code (e.g. ``"3110"``), or ``""``
          for the ``"Total use"`` summary row.
        - ``transaction_txt``: transaction name from the ``transactions``
          classification, or ``"Total use"`` for the summary row.
        - ``category``: category code for categorised transactions (e.g.
          ``"FKO01"``), or ``""`` for uncategorised transactions and the
          summary row.
        - ``category_txt``: category name from the appropriate
          classification (``individual_consumption`` for P31,
          ``collective_consumption`` for P32), or ``""`` when no
          classification is loaded, the row is uncategorised, or it is
          the summary row.

        Rows appear in this order:

        1. For each selected transaction: one row per category code,
           ordered by the classification table row order. Codes not in
           the classification table appear at the end, in natural sort
           order. Uncategorised rows (empty category column) appear after
           categorised rows.
        2. A single ``"Total use"`` summary row at the bottom, summing
           all selected transactions and categories.

        Values are at purchasers' prices. Columns are the collection ids
        (e.g. years). Missing cells are filled with ``0``.
    use_distribution : pd.DataFrame
        Same four-level MultiIndex structure as ``use``. For each year,
        every row is divided by the grand total (the ``"Total use"``
        row). Values therefore express each transaction-category
        combination's share of the total across all selected transactions.
        The ``"Total use"`` row has value ``1.0``. Division by zero
        yields ``NaN``.
    use_growth : pd.DataFrame
        Same structure as ``use``. Year-on-year change:
        ``(value[t] - value[t-1]) / value[t-1]``. The first id column is
        ``NaN`` throughout. Division by zero also yields ``NaN``.
    """

    data: FinalUseInspectionData
    display_unit: float | None = None
    rel_base: int = 100
    decimals: int = 1
    _all_rel: bool = field(default=False, repr=False)

    def _number_fmt(self):
        if self._all_rel:
            return _make_percentage_formatter(self.rel_base, self.decimals)
        return _make_number_formatter(self.display_unit, self.decimals)

    @property
    def use(self) -> Styler:
        """Styled transaction-level use table for display in a Jupyter notebook."""
        return _style_final_use_use_table(self.data.use, self._number_fmt())

    @property
    def use_distribution(self) -> Styler:
        """Styled transaction-level share distribution for display in a Jupyter notebook."""
        return _style_final_use_use_table(self.data.use_distribution, _make_percentage_formatter(self.rel_base, self.decimals))

    @property
    def use_growth(self) -> Styler:
        """Styled transaction-level year-on-year growth for display in a Jupyter notebook."""
        return _style_final_use_use_table(self.data.use_growth, _make_percentage_formatter(self.rel_base, self.decimals))

    @property
    def use_categories(self) -> Styler:
        """Styled use table (by transaction+category) for display in a Jupyter notebook."""
        return _style_final_use_use_categories_table(self.data.use_categories, self._number_fmt())

    @property
    def use_categories_distribution(self) -> Styler:
        """Styled category share distribution for display in a Jupyter notebook."""
        return _style_final_use_use_categories_table(
            self.data.use_categories_distribution, _make_percentage_formatter(self.rel_base, self.decimals)
        )

    @property
    def use_categories_growth(self) -> Styler:
        """Styled category year-on-year growth for display in a Jupyter notebook."""
        return _style_final_use_use_categories_table(
            self.data.use_categories_growth, _make_percentage_formatter(self.rel_base, self.decimals)
        )

    @property
    def use_products(self) -> Styler:
        """Styled use-detail table (with product breakdown) for display in a Jupyter notebook."""
        return _style_final_use_use_products_table(self.data.use_products, self._number_fmt())

    @property
    def use_products_distribution(self) -> Styler:
        """Styled use-products distribution table for display in a Jupyter notebook."""
        return _style_final_use_use_products_table(
            self.data.use_products_distribution, _make_percentage_formatter(self.rel_base, self.decimals)
        )

    @property
    def use_products_growth(self) -> Styler:
        """Styled use-products year-on-year growth table for display in a Jupyter notebook."""
        return _style_final_use_use_products_table(
            self.data.use_products_growth, _make_percentage_formatter(self.rel_base, self.decimals)
        )

    @property
    def price_layers(self) -> Styler:
        """Styled price layer decomposition table for display in a Jupyter notebook."""
        return _style_final_use_price_layers_table(self.data.price_layers, self._number_fmt())

    @property
    def price_layers_rates(self) -> Styler:
        """Styled step-wise price layer rates for display in a Jupyter notebook."""
        return _style_final_use_price_layers_table(
            self.data.price_layers_rates, _make_percentage_formatter(self.rel_base, self.decimals)
        )

    @property
    def price_layers_distribution(self) -> Styler:
        """Styled price layer distribution table for display in a Jupyter notebook."""
        return _style_final_use_price_layers_table(
            self.data.price_layers_distribution, _make_percentage_formatter(self.rel_base, self.decimals)
        )

    @property
    def price_layers_growth(self) -> Styler:
        """Styled price layer year-on-year growth table for display in a Jupyter notebook."""
        return _style_final_use_price_layers_table(
            self.data.price_layers_growth, _make_percentage_formatter(self.rel_base, self.decimals)
        )

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
        _write_inspection_to_excel(self, path, self.display_unit, self.rel_base, self.decimals)

    def set_display_unit(self, display_unit: float | None) -> "FinalUseInspection":
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

    def set_rel_base(self, rel_base: int) -> "FinalUseInspection":
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

    def set_decimals(self, decimals: int) -> "FinalUseInspection":
        """Return a copy with ``decimals`` set to the given value.

        Parameters
        ----------
        decimals : int
            Number of decimal places in formatted numbers and percentages.
            Must be a non-negative integer.
        """
        if not isinstance(decimals, int) or decimals < 0:
            raise ValueError(
                f"decimals must be a non-negative integer. Got {decimals!r}."
            )
        return dataclasses.replace(self, decimals=decimals)

    def display_index(
        self,
        values: str | int | list,
        level: str,
    ) -> "FinalUseInspection":
        """Return a copy with all tables filtered to rows matching ``values`` at ``level``.

        Tables whose index does not contain a level named ``level`` are left
        unchanged. ``None`` fields are propagated unchanged. Accepts the same
        pattern syntax as :func:`filter_rows`: exact codes, wildcards (``*``),
        ranges (``:``), and negation (``~``). Non-string values are stringified
        before matching.

        Parameters
        ----------
        values : str, int, or list of str/int
            Values (or patterns) to keep. A single value is treated as a
            one-element list.
        level : str
            Name of the index level to filter on.

        Returns
        -------
        FinalUseInspection
            A new inspection result with filtered tables.
        """
        return _display_index(self, values, level)

    @property
    def tables_description(self) -> Styler:
        """Styled table with ``name`` as index and a ``description`` column."""
        return _style_tables_description(self.data.tables_description)

    def inspect_tables_comparison(self, other: "FinalUseInspection") -> TablesComparison:
        """Compare all tables in this inspection with another :class:`FinalUseInspection`.

        Computes element-wise differences and relative changes between
        corresponding tables. Index alignment uses an outer join.

        Parameters
        ----------
        other : FinalUseInspection
            The inspection result to compare against.

        Returns
        -------
        TablesComparison
            Contains ``.diff`` and ``.rel`` as :class:`FinalUseInspection`
            instances.

        Raises
        ------
        TypeError
            If ``other`` is not a :class:`FinalUseInspection`.
        """
        if not isinstance(other, FinalUseInspection):
            raise TypeError(
                f"Expected FinalUseInspection, got {type(other).__name__}."
            )
        diff_fields, rel_fields = _compute_comparison_table_fields(self.data, other.data)
        diff = FinalUseInspection(
            data=FinalUseInspectionData(**diff_fields),
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            decimals=self.decimals,
        )
        rel = FinalUseInspection(
            data=FinalUseInspectionData(**rel_fields),
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            decimals=self.decimals,
            _all_rel=True,
        )
        return TablesComparison(
            diff=diff,
            rel=rel,
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            decimals=self.decimals,
        )


def inspect_final_uses(
    sut: SUT,
    transactions: str | list[str],
    *,
    categories: str | list[str] | None = None,
    ids=None,
    sort_id=None,
) -> FinalUseInspection:
    """
    Return inspection tables for one or more final use transactions.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    transactions : str or list of str
        Final use transaction codes to include. Accepts the same pattern
        syntax as :func:`filter_rows`: exact codes, wildcards (``*``), ranges
        (``:``), and negation (``~``). Matched against use-side transaction
        codes with ESA codes other than P2 (intermediate consumption).
    categories : str or list of str, optional
        Category codes to include within categorised transactions. When
        ``None`` (the default), all categories are included. For
        uncategorised transactions (those with an empty category column),
        all rows are always included regardless of this filter. Accepts the
        same pattern syntax as ``transactions``.
    ids : value, list of values, or range, optional
        Id values (e.g. years) to include as columns. When ``None`` (the
        default), all ids present in the collection are included. Accepts a
        single value (``ids=2021``), a list (``ids=[2019, 2020]``), or a
        range (``ids=range(2015, 2022)``). Column order follows the sorted
        order of the full collection.
    sort_id : value, optional
        If given, non-total rows within each transaction block are sorted
        descending by the value in that id column. The grand ``"Total use"``
        row always remains at the bottom. ``use_distribution`` and
        ``use_growth`` inherit the same order. Must be one of the ids
        present after applying the ``ids`` filter.

    Returns
    -------
    FinalUseInspection
        A dataclass with inspection tables. Raw DataFrames are available
        under ``result.data``.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.metadata.classifications`` or
        ``sut.metadata.classifications.transactions`` is ``None``.
    ValueError
        If ``sut.metadata.classifications.transactions`` does not have a
        transaction text column.
    ValueError
        If no transaction codes match the given ``transactions`` patterns.
    ValueError
        If any value in ``ids`` is not found in the collection.
    ValueError
        If ``sort_id`` is not found in the collection ids (after applying
        the ``ids`` filter).
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call inspect_final_uses. "
            "Provide a SUTMetadata with column name mappings."
        )
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            "sut.metadata.classifications.transactions is required to call "
            "inspect_final_uses. Load a classifications file with a "
            "'transactions' sheet."
        )

    trans_df = sut.metadata.classifications.transactions
    cols = sut.metadata.columns

    trans_txt_col = f"{cols.transaction}_txt"
    if trans_txt_col not in trans_df.columns:
        raise ValueError(
            f"sut.metadata.classifications.transactions must have a "
            f"'{trans_txt_col}' column."
        )

    # Candidate transaction codes: use-side rows with ESA codes other than P2.
    final_use_trans_df = trans_df[
        (trans_df["table"] == "use")
        & (~trans_df["esa_code"].isin(_NON_FINAL_USE_ESA_CODES))
    ]
    final_use_codes = final_use_trans_df[cols.transaction].astype(str).tolist()

    if isinstance(transactions, str):
        trans_patterns = [transactions]
    else:
        trans_patterns = list(transactions)

    matched_transactions = _match_codes(final_use_codes, trans_patterns)
    if not matched_transactions:
        raise ValueError(
            f"No final use transactions matched the given patterns {trans_patterns!r}. "
            f"Available final use transaction codes: {final_use_codes}"
        )

    # All ids in sorted order — shared across all tables for consistent columns.
    all_ids = sorted(sut.use[cols.id].unique().tolist())

    if ids is not None:
        if isinstance(ids, (list, range)):
            requested_ids = list(ids)
        else:
            requested_ids = [ids]
        missing = [i for i in requested_ids if i not in all_ids]
        if missing:
            raise ValueError(
                f"Id(s) {missing} not found in collection. Available: {all_ids}"
            )
        all_ids = [i for i in all_ids if i in requested_ids]

    if sort_id is not None and sort_id not in all_ids:
        raise ValueError(
            f"sort_id {sort_id!r} not found in collection ids. Available: {all_ids}"
        )

    # Transaction name and ESA code lookups.
    trans_names = dict(zip(
        trans_df[cols.transaction].astype(str),
        trans_df[trans_txt_col].astype(str),
    ))
    trans_esa_codes = dict(zip(
        trans_df[cols.transaction].astype(str),
        trans_df["esa_code"].astype(str),
    ))

    # Filter use data to matched transactions and (optionally) matched categories.
    use_matched = sut.use[sut.use[cols.transaction].isin(matched_transactions)]

    if categories is not None:
        if isinstance(categories, str):
            cat_patterns = [categories]
        else:
            cat_patterns = list(categories)

        # Candidate categories: all non-empty category values across matched transactions.
        all_cats = sorted(
            [
                c for c in use_matched[cols.category].dropna().unique().tolist()
                if c != ""
            ],
            key=_natural_sort_key,
        )
        matched_categories = _match_codes(all_cats, cat_patterns)

        # Include matched categories AND uncategorised rows (empty or NaN category).
        is_uncategorised = use_matched[cols.category].isna() | (
            use_matched[cols.category] == ""
        )
        use_filtered = use_matched[
            is_uncategorised | use_matched[cols.category].isin(matched_categories)
        ]
    else:
        use_filtered = use_matched

    classifications = sut.metadata.classifications

    use = _build_final_use_use_table(
        use_filtered=use_filtered,
        matched_transactions=matched_transactions,
        trans_names=trans_names,
        cols=cols,
        all_ids=all_ids,
    )

    if sort_id is not None and not use.empty:
        trans_vals = use.index.get_level_values("transaction")
        is_total = trans_vals == ""
        data_rows = use[~is_total].sort_values(by=sort_id, ascending=False)
        total_rows = use[is_total]
        use = pd.concat([data_rows, total_rows])

    use_distribution = _build_final_use_use_distribution(use)
    use_growth = _build_growth_table(use)

    use_categories = _build_final_use_use_categories_table(
        use_filtered=use_filtered,
        matched_transactions=matched_transactions,
        trans_names=trans_names,
        trans_esa_codes=trans_esa_codes,
        classifications=classifications,
        cols=cols,
        all_ids=all_ids,
    )

    if sort_id is not None and not use_categories.empty:
        trans_vals_cat = use_categories.index.get_level_values("transaction")
        is_total_cat = trans_vals_cat == ""
        data_rows_cat = use_categories[~is_total_cat].sort_values(
            by=sort_id, ascending=False
        )
        total_rows_cat = use_categories[is_total_cat]
        use_categories = pd.concat([data_rows_cat, total_rows_cat])

    use_categories_distribution = _build_final_use_use_distribution(use_categories)
    use_categories_growth = _build_growth_table(use_categories)

    use_products = _build_final_use_use_products(
        use_filtered=use_filtered,
        matched_transactions=matched_transactions,
        trans_names=trans_names,
        trans_esa_codes=trans_esa_codes,
        classifications=classifications,
        cols=cols,
        all_ids=all_ids,
    )

    if sort_id is not None and not use_products.empty:
        trans_vals_prod = use_products.index.get_level_values("transaction")
        is_total_prod = trans_vals_prod == ""
        data_rows_prod = use_products[~is_total_prod].sort_values(
            by=sort_id, ascending=False
        )
        total_rows_prod = use_products[is_total_prod]
        use_products = pd.concat([data_rows_prod, total_rows_prod])

    use_products_distribution = _build_final_use_use_distribution(use_products)
    use_products_growth = _build_growth_table(use_products)

    price_layers = _build_final_use_price_layers_table(
        use_filtered=use_filtered,
        matched_transactions=matched_transactions,
        trans_names=trans_names,
        trans_esa_codes=trans_esa_codes,
        classifications=classifications,
        cols=cols,
        all_ids=all_ids,
    )

    price_layers_rates = _build_final_use_price_layers_rates(
        price_layers=price_layers,
        sut=sut,
        matched_transactions=matched_transactions,
        cols=cols,
        all_ids=all_ids,
    )
    price_layers_distribution = _build_final_use_price_layers_distribution(price_layers)
    price_layers_growth = _build_growth_table(price_layers)

    data = FinalUseInspectionData(
        use=use,
        use_distribution=use_distribution,
        use_growth=use_growth,
        use_categories=use_categories,
        use_categories_distribution=use_categories_distribution,
        use_categories_growth=use_categories_growth,
        use_products=use_products,
        use_products_distribution=use_products_distribution,
        use_products_growth=use_products_growth,
        price_layers=price_layers,
        price_layers_rates=price_layers_rates,
        price_layers_distribution=price_layers_distribution,
        price_layers_growth=price_layers_growth,
    )
    return FinalUseInspection(data=data)


# ---------------------------------------------------------------------------
# Private builder helpers
# ---------------------------------------------------------------------------


def _get_category_names_for_esa(
    classifications,
    esa_code: str,
    cat_col: str,
) -> dict[str, str]:
    """Return an ordered ``{category_code: category_label}`` dict for the ESA code.

    Returns an empty dict if no classification applies to this ESA code or
    the relevant classification table is not loaded.
    """
    attr = _ESA_TO_CLASSIFICATION_ATTR.get(esa_code)
    if attr is None or classifications is None:
        return {}
    cls_df = getattr(classifications, attr, None)
    if cls_df is None:
        return {}
    cat_txt_col = f"{cat_col}_txt"
    if cat_txt_col not in cls_df.columns:
        return {}
    return dict(zip(
        cls_df[cat_col].astype(str),
        cls_df[cat_txt_col].astype(str),
    ))


def _build_final_use_use_table(
    use_filtered: pd.DataFrame,
    matched_transactions: list[str],
    trans_names: dict[str, str],
    cols,
    all_ids: list,
) -> pd.DataFrame:
    """Build transaction-level use table: one row per transaction.

    Aggregates purchasers' prices across all categories and products for each
    selected transaction. Appends a ``"Total use"`` summary row at the bottom.

    Parameters
    ----------
    use_filtered : pd.DataFrame
        Use DataFrame already filtered to matched transactions and categories.
    matched_transactions : list of str
        Transaction codes to include, in display order.
    trans_names : dict
        Maps transaction code → transaction label.
    cols : SUTColumns
        Column name mappings.
    all_ids : list
        Collection ids to use as columns.

    Returns
    -------
    pd.DataFrame
        Wide-format table with a two-level MultiIndex
        ``(transaction, transaction_txt)``.
    """
    trans_col = cols.transaction
    id_col = cols.id
    purch_col = cols.price_purchasers

    agg = (
        use_filtered
        .groupby([trans_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )

    if not agg.empty:
        wide = agg.pivot_table(
            index=trans_col,
            columns=id_col,
            values=purch_col,
            aggfunc="sum",
            fill_value=0,
        )
        wide.columns.name = None
        wide = wide.reindex(columns=all_ids, fill_value=0)
    else:
        wide = pd.DataFrame(
            index=pd.Index([], name=trans_col),
            columns=all_ids,
            dtype=float,
        )

    row_labels = []
    row_data = []

    for trans in matched_transactions:
        trans_txt = trans_names.get(trans, trans)
        if trans in wide.index:
            vals = wide.loc[trans, all_ids].tolist()
        else:
            vals = [0] * len(all_ids)
        row_labels.append((trans, trans_txt))
        row_data.append(vals)

    if not row_labels:
        return pd.DataFrame()

    grand_total = [sum(r[j] for r in row_data) for j in range(len(all_ids))]
    row_labels.append(("", "Total use"))
    row_data.append(grand_total)

    return pd.DataFrame(
        row_data,
        index=pd.MultiIndex.from_tuples(
            row_labels,
            names=["transaction", "transaction_txt"],
        ),
        columns=all_ids,
    )


def _build_final_use_use_categories_table(
    use_filtered: pd.DataFrame,
    matched_transactions: list[str],
    trans_names: dict[str, str],
    trans_esa_codes: dict[str, str],
    classifications,
    cols,
    all_ids: list,
) -> pd.DataFrame:
    """Build the wide-format use table for the given final use transactions.

    For each transaction, assembles one row per category (in classification
    order where available). A single ``"Total use"`` summary row is appended
    at the very end, summing all transactions and categories.

    Parameters
    ----------
    use_filtered : pd.DataFrame
        Use DataFrame already filtered to matched transactions and categories.
    matched_transactions : list of str
        Transaction codes to include, in display order.
    trans_names : dict
        Maps transaction code → transaction label.
    trans_esa_codes : dict
        Maps transaction code → ESA code (e.g. ``"P31"``).
    classifications : SUTClassifications or None
        Classification tables for category label lookups.
    cols : SUTColumns
        Column name mappings.
    all_ids : list
        Collection ids to use as columns.

    Returns
    -------
    pd.DataFrame
        Wide-format use table with a four-level MultiIndex
        ``(transaction, transaction_txt, category, category_txt)``.
    """
    cat_col = cols.category
    trans_col = cols.transaction
    id_col = cols.id
    purch_col = cols.price_purchasers

    # Aggregate by (transaction, category, id) and sum purchasers' prices.
    agg = (
        use_filtered
        .groupby([trans_col, cat_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )

    if not agg.empty:
        wide = agg.pivot_table(
            index=[trans_col, cat_col],
            columns=id_col,
            values=purch_col,
            aggfunc="sum",
            fill_value=0,
        )
        wide.columns.name = None
    else:
        wide = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([], names=[trans_col, cat_col]),
            columns=all_ids,
            dtype=float,
        )

    wide_trans_codes = wide.index.get_level_values(trans_col).tolist()

    row_labels = []
    row_data = []

    for trans in matched_transactions:
        trans_txt = trans_names.get(trans, trans)
        esa_code = trans_esa_codes.get(trans, "")
        cat_names = _get_category_names_for_esa(classifications, esa_code, cat_col)

        # Extract rows for this transaction as a DataFrame indexed by category.
        if trans in wide_trans_codes:
            trans_wide = wide.xs(trans, level=trans_col)
        else:
            trans_wide = pd.DataFrame(
                index=pd.Index([], name=cat_col),
                columns=all_ids,
                dtype=float,
            )

        trans_wide = trans_wide.reindex(columns=all_ids, fill_value=0)

        # Split into categorised (non-empty) and uncategorised (empty/NaN) rows.
        cat_index = trans_wide.index
        is_empty = pd.isna(cat_index) | (cat_index == "")
        cat_rows = trans_wide[~is_empty]
        uncat_rows = trans_wide[is_empty]

        # Order categorised rows: classification order first, then natural sort.
        if cat_names:
            ordered_cats = [c for c in cat_names if c in cat_rows.index]
            extra_cats = sorted(
                [c for c in cat_rows.index if c not in cat_names],
                key=_natural_sort_key,
            )
            ordered_cats = ordered_cats + extra_cats
        else:
            ordered_cats = sorted(cat_rows.index.tolist(), key=_natural_sort_key)

        for cat in ordered_cats:
            cat_txt = cat_names.get(cat, "")
            row_labels.append((trans, trans_txt, cat, cat_txt))
            row_data.append(cat_rows.loc[cat].tolist())

        # Uncategorised rows: use iloc to avoid issues with empty-string or NaN keys.
        for pos in range(len(uncat_rows)):
            vals = uncat_rows.iloc[pos]
            row_labels.append((trans, trans_txt, "", ""))
            row_data.append(vals.tolist())

    if not row_labels:
        return pd.DataFrame()

    # Grand total row: sum all data rows across all transactions and categories.
    data_df = pd.DataFrame(row_data, columns=all_ids)
    grand_total = data_df.sum(axis=0).tolist()
    row_labels.append(("", "Total use", "", ""))
    row_data.append(grand_total)

    return pd.DataFrame(
        row_data,
        index=pd.MultiIndex.from_tuples(
            row_labels,
            names=["transaction", "transaction_txt", "category", "category_txt"],
        ),
        columns=all_ids,
    )


def _build_final_use_use_distribution(use: pd.DataFrame) -> pd.DataFrame:
    """Build the distribution table from the use table.

    For each year, divides every row by the grand total (the ``"Total use"``
    row). Values express each transaction-category's share of the total
    across all selected transactions. The ``"Total use"`` row has value
    ``1.0``. Division by zero yields ``NaN``.

    Parameters
    ----------
    use : pd.DataFrame
        Wide-format use table as returned by :func:`_build_final_use_use_table`.

    Returns
    -------
    pd.DataFrame
        Same structure as ``use``, values as fractions.
    """
    if use.empty:
        return use.copy()

    # The grand total is the last row ("Total use").
    grand_total = use.iloc[-1]
    denom = grand_total.where(grand_total != 0)
    return use.div(denom, axis=1)


def _get_product_names(classifications, prod_col: str) -> dict[str, str]:
    """Return an ordered ``{product_code: product_label}`` dict.

    Returns an empty dict if ``classifications`` is ``None``, no ``products``
    table is loaded, or the label column is missing.
    """
    if classifications is None:
        return {}
    prods_df = getattr(classifications, "products", None)
    if prods_df is None:
        return {}
    prod_txt_col = f"{prod_col}_txt"
    if prod_txt_col not in prods_df.columns:
        return {}
    return dict(zip(
        prods_df[prod_col].astype(str),
        prods_df[prod_txt_col].astype(str),
    ))


def _build_final_use_use_products(
    use_filtered: pd.DataFrame,
    matched_transactions: list[str],
    trans_names: dict[str, str],
    trans_esa_codes: dict[str, str],
    classifications,
    cols,
    all_ids: list,
) -> pd.DataFrame:
    """Build the wide-format use-detail table with product breakdown.

    For each transaction → category → product, assembles one row. A single
    ``"Total use"`` summary row is appended at the end.

    Parameters
    ----------
    use_filtered : pd.DataFrame
        Use DataFrame already filtered to matched transactions and categories.
    matched_transactions : list of str
        Transaction codes to include, in display order.
    trans_names : dict
        Maps transaction code → transaction label.
    trans_esa_codes : dict
        Maps transaction code → ESA code (e.g. ``"P31"``).
    classifications : SUTClassifications or None
        Classification tables for category and product label lookups.
    cols : SUTColumns
        Column name mappings.
    all_ids : list
        Collection ids to use as columns.

    Returns
    -------
    pd.DataFrame
        Wide-format table with a six-level MultiIndex
        ``(transaction, transaction_txt, category, category_txt, product, product_txt)``.
    """
    cat_col = cols.category
    trans_col = cols.transaction
    prod_col = cols.product
    id_col = cols.id
    purch_col = cols.price_purchasers

    # Aggregate by (transaction, category, product, id) and sum purchasers' prices.
    agg = (
        use_filtered
        .groupby([trans_col, cat_col, prod_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )

    if not agg.empty:
        wide = agg.pivot_table(
            index=[trans_col, cat_col, prod_col],
            columns=id_col,
            values=purch_col,
            aggfunc="sum",
            fill_value=0,
        )
        wide.columns.name = None
    else:
        wide = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([], names=[trans_col, cat_col, prod_col]),
            columns=all_ids,
            dtype=float,
        )

    all_trans_codes = wide.index.get_level_values(trans_col).tolist()
    prod_names = _get_product_names(classifications, prod_col)

    row_labels = []
    row_data = []

    for trans in matched_transactions:
        trans_txt = trans_names.get(trans, trans)
        esa_code = trans_esa_codes.get(trans, "")
        cat_names = _get_category_names_for_esa(classifications, esa_code, cat_col)

        if trans not in all_trans_codes:
            continue

        trans_wide = wide.xs(trans, level=trans_col)
        trans_wide = trans_wide.reindex(columns=all_ids, fill_value=0)

        # Split into categorised (non-empty) and uncategorised (empty/NaN) rows.
        cat_index = trans_wide.index.get_level_values(cat_col)
        is_empty_cat = pd.isna(cat_index) | (cat_index == "")
        cat_rows_df = trans_wide[~is_empty_cat]
        uncat_rows_df = trans_wide[is_empty_cat]

        # Determine category order: classification order first, then natural sort.
        present_cats = list(dict.fromkeys(cat_rows_df.index.get_level_values(cat_col)))
        if cat_names:
            ordered_cats = [c for c in cat_names if c in present_cats]
            extra_cats = sorted(
                [c for c in present_cats if c not in cat_names],
                key=_natural_sort_key,
            )
            ordered_cats = ordered_cats + extra_cats
        else:
            ordered_cats = sorted(present_cats, key=_natural_sort_key)

        for cat in ordered_cats:
            cat_txt = cat_names.get(cat, "")
            cat_prods_wide = cat_rows_df.xs(cat, level=cat_col)
            cat_prods_wide = cat_prods_wide.reindex(columns=all_ids, fill_value=0)

            # Order products: classification order first, then natural sort.
            present_prods = cat_prods_wide.index.tolist()
            if prod_names:
                ordered_prods = [p for p in prod_names if p in present_prods]
                extra_prods = sorted(
                    [p for p in present_prods if p not in prod_names],
                    key=_natural_sort_key,
                )
                ordered_prods = ordered_prods + extra_prods
            else:
                ordered_prods = sorted(present_prods, key=_natural_sort_key)

            for prod in ordered_prods:
                prod_txt = prod_names.get(prod, "")
                row_labels.append((trans, trans_txt, cat, cat_txt, prod, prod_txt))
                row_data.append(cat_prods_wide.loc[prod].tolist())

        # Uncategorised rows: products with an empty or NaN category.
        if not uncat_rows_df.empty:
            uncat_by_prod = uncat_rows_df.groupby(level=prod_col, dropna=False).sum()
            uncat_by_prod = uncat_by_prod.reindex(columns=all_ids, fill_value=0)

            present_uncat_prods = uncat_by_prod.index.tolist()
            if prod_names:
                ordered_uncat_prods = [p for p in prod_names if p in present_uncat_prods]
                extra_prods = sorted(
                    [p for p in present_uncat_prods if p not in prod_names],
                    key=_natural_sort_key,
                )
                ordered_uncat_prods = ordered_uncat_prods + extra_prods
            else:
                ordered_uncat_prods = sorted(present_uncat_prods, key=_natural_sort_key)

            for prod in ordered_uncat_prods:
                prod_txt = prod_names.get(prod, "")
                row_labels.append((trans, trans_txt, "", "", prod, prod_txt))
                row_data.append(uncat_by_prod.loc[prod].tolist())

    if not row_labels:
        return pd.DataFrame()

    # Grand total row: sum all product rows across all transactions and categories.
    data_df = pd.DataFrame(row_data, columns=all_ids)
    grand_total = data_df.sum(axis=0).tolist()
    row_labels.append(("", "Total use", "", "", "", ""))
    row_data.append(grand_total)

    return pd.DataFrame(
        row_data,
        index=pd.MultiIndex.from_tuples(
            row_labels,
            names=[
                "transaction", "transaction_txt",
                "category", "category_txt",
                "product", "product_txt",
            ],
        ),
        columns=all_ids,
    )


def _build_final_use_price_layers_table(
    use_filtered: pd.DataFrame,
    matched_transactions: list[str],
    trans_names: dict[str, str],
    trans_esa_codes: dict[str, str],
    classifications,
    cols,
    all_ids: list,
) -> pd.DataFrame:
    """Build the price layer decomposition table for the given final use transactions.

    For each ``(transaction, category)`` block (in the same order as the
    ``use`` table), assembles rows for each price layer column with at least
    one non-zero value across any id. The first row in each block is
    ``price_basic``; subsequent rows are the intermediate price layer
    columns in ``use`` DataFrame column order. A ``"Total"`` row
    (``price_layer == ""``) is appended to each block only when two or more
    non-zero rows exist (following the industries convention).

    Parameters
    ----------
    use_filtered : pd.DataFrame
        Use DataFrame already filtered to matched transactions and categories.
    matched_transactions : list of str
        Transaction codes to include, in display order.
    trans_names : dict
        Maps transaction code → transaction label.
    trans_esa_codes : dict
        Maps transaction code → ESA code (e.g. ``"P31"``).
    classifications : SUTClassifications or None
        Classification tables for category label lookups.
    cols : SUTColumns
        Column name mappings.
    all_ids : list
        Collection ids to use as columns.

    Returns
    -------
    pd.DataFrame
        Wide-format table with a five-level MultiIndex
        ``(transaction, transaction_txt, category, category_txt, price_layer)``.
        Empty when no price layer columns are present in ``use_filtered``.
    """
    cat_col = cols.category
    trans_col = cols.transaction
    id_col = cols.id

    layer_cols = _get_price_layer_columns(cols, use_filtered)
    if not layer_cols:
        return pd.DataFrame()

    all_value_cols = layer_cols

    # Pre-aggregate each value column by (trans, cat, id) for efficient lookup.
    agg_wide: dict[str, pd.DataFrame] = {}
    for val_col in all_value_cols:
        if val_col not in use_filtered.columns:
            continue
        agg_data = (
            use_filtered
            .groupby([trans_col, cat_col, id_col], as_index=False, dropna=False)[val_col]
            .sum()
        )
        if agg_data.empty:
            continue
        wide = agg_data.pivot_table(
            index=[trans_col, cat_col],
            columns=id_col,
            values=val_col,
            aggfunc="sum",
            fill_value=0,
        )
        wide.columns.name = None
        wide = wide.reindex(columns=all_ids, fill_value=0)
        agg_wide[val_col] = wide

    if not agg_wide:
        return pd.DataFrame()

    # Collect all (trans, cat) pairs present in the data.
    all_tc_pairs: set = set()
    for wide in agg_wide.values():
        for pair in wide.index.tolist():
            all_tc_pairs.add(pair)

    row_labels = []
    row_data = []

    for trans in matched_transactions:
        trans_txt = trans_names.get(trans, trans)
        esa_code = trans_esa_codes.get(trans, "")
        cat_names = _get_category_names_for_esa(classifications, esa_code, cat_col)

        # Find categories present for this transaction.
        trans_cats = {c for t, c in all_tc_pairs if t == trans}
        if not trans_cats:
            continue

        cat_list = [c for c in trans_cats if c != "" and not pd.isna(c)]
        has_uncat = any(c == "" or (isinstance(c, float) and pd.isna(c)) for c in trans_cats)

        if cat_names:
            ordered_cats = [c for c in cat_names if c in cat_list]
            extra_cats = sorted(
                [c for c in cat_list if c not in cat_names],
                key=_natural_sort_key,
            )
            ordered_cats = ordered_cats + extra_cats
        else:
            ordered_cats = sorted(cat_list, key=_natural_sort_key)

        if has_uncat:
            ordered_cats = ordered_cats + [""]

        for cat in ordered_cats:
            cat_txt = cat_names.get(cat, "")

            # Collect non-zero rows for this (trans, cat) block.
            block_rows: list[tuple[str, list]] = []
            for val_col in all_value_cols:
                if val_col not in agg_wide:
                    continue
                wide = agg_wide[val_col]
                key = (trans, cat)
                if key not in wide.index:
                    continue
                vals = wide.loc[key].tolist()
                if any(v != 0 for v in vals):
                    block_rows.append((val_col, vals))

            if not block_rows:
                continue

            for layer_name, vals in block_rows:
                row_labels.append((trans, trans_txt, cat, cat_txt, layer_name))
                row_data.append(vals)

    if not row_labels:
        return pd.DataFrame()

    return pd.DataFrame(
        row_data,
        index=pd.MultiIndex.from_tuples(
            row_labels,
            names=["transaction", "transaction_txt", "category", "category_txt", "price_layer"],
        ),
        columns=all_ids,
    )


def _build_final_use_price_layers_rates(
    price_layers: pd.DataFrame,
    sut: SUT,
    matched_transactions: list[str],
    cols,
    all_ids: list,
) -> pd.DataFrame:
    """Build price layer rates with the same index structure as ``price_layers``.

    Only intermediate layer rows are included — ``price_basic`` rows (which
    serve as the denominator) and Total rows (``price_layer == ""``) are
    excluded. Each row's value is the step-wise rate for that layer within
    the ``(transaction, category)`` group: layer value divided by the
    cumulative price up to (not including) that layer.

    Rates are derived from
    :func:`~sutlab.derive.compute_price_layer_rates` at
    ``aggregation_level=["transaction", "category"]``.

    Parameters
    ----------
    price_layers : pd.DataFrame
        As produced by :func:`_build_final_use_price_layers_table`.
    sut : SUT
        Full SUT collection (used to build the filtered SUT for rate computation).
    matched_transactions : list of str
        Final use transaction codes.
    cols : SUTColumns
        Column name mappings.
    all_ids : list
        Collection ids (years) — column order.
    """
    if price_layers.empty:
        return pd.DataFrame()

    layer_vals = price_layers.index.get_level_values("price_layer")
    # Exclude Total rows (price_layer == "") defensively — they are not produced
    # by _build_final_use_price_layers_table but guard against any future change.
    rates_mask = layer_vals != ""
    price_layers_intermediate = price_layers[rates_mask]

    if price_layers_intermediate.empty:
        return pd.DataFrame()

    trans_col = cols.transaction
    cat_col = cols.category
    id_col = cols.id
    nan_row = [float("nan")] * len(all_ids)

    # Filter sut.use to matched final-use transactions for rate computation.
    filtered_use = sut.use[sut.use[trans_col].isin(matched_transactions)]
    filtered_sut = dataclasses.replace(sut, use=filtered_use)

    trans_cat_rates = compute_price_layer_rates(
        filtered_sut, ["transaction", "category"]
    )

    if trans_cat_rates.empty:
        return pd.DataFrame(
            [nan_row] * len(price_layers_intermediate),
            index=price_layers_intermediate.index,
            columns=all_ids,
        )

    # Build lookup: (transaction, category, layer_col) → list of rates for all_ids.
    layer_cols_in_rates = [
        c for c in trans_cat_rates.columns
        if c not in [trans_col, cat_col, id_col]
    ]

    trans_cat_wide = trans_cat_rates.pivot_table(
        index=[trans_col, cat_col],
        columns=id_col,
        values=layer_cols_in_rates,
        aggfunc="sum",
    )
    trans_cat_wide = trans_cat_wide.reindex(
        columns=all_ids, level=id_col, fill_value=float("nan")
    )

    layer_col_positions: dict[str, list[int]] = {}
    for j, (layer_name, _) in enumerate(trans_cat_wide.columns.tolist()):
        if layer_name not in layer_col_positions:
            layer_col_positions[layer_name] = []
        layer_col_positions[layer_name].append(j)

    values_2d = trans_cat_wide.to_numpy()
    index_list = trans_cat_wide.index.tolist()
    rate_lookup: dict[tuple, list] = {}
    for i, (trans, cat) in enumerate(index_list):
        row = values_2d[i]
        for layer_col_name, positions in layer_col_positions.items():
            rate_lookup[(trans, cat, layer_col_name)] = row[positions].tolist()

    trans_idx = price_layers_intermediate.index.get_level_values("transaction")
    cat_idx = price_layers_intermediate.index.get_level_values("category")
    layer_idx = price_layers_intermediate.index.get_level_values("price_layer")

    rates_rows = [
        rate_lookup.get((t, c, l), nan_row)
        for t, c, l in zip(trans_idx, cat_idx, layer_idx)
    ]
    return pd.DataFrame(
        rates_rows,
        index=price_layers_intermediate.index,
        columns=all_ids,
    )


def _build_final_use_price_layers_distribution(price_layers: pd.DataFrame) -> pd.DataFrame:
    """Build distribution table: within each ``(transaction, category)`` block,
    divide each layer value by the sum of all layer values in that block.

    Division by zero yields ``NaN``.

    Parameters
    ----------
    price_layers : pd.DataFrame
        As produced by :func:`_build_final_use_price_layers_table`.
    """
    if price_layers.empty:
        return pd.DataFrame()

    trans_vals = price_layers.index.get_level_values("transaction")
    cat_vals = price_layers.index.get_level_values("category")
    result_data = price_layers.astype(float).copy()

    tc_pairs = list(dict.fromkeys(zip(trans_vals, cat_vals)))
    for trans, cat in tc_pairs:
        block_mask = (trans_vals == trans) & (cat_vals == cat)
        block_sum = price_layers[block_mask].astype(float).sum()
        safe_denom = block_sum.where(block_sum != 0, other=float("nan"))
        result_data.loc[block_mask] = (
            price_layers[block_mask].astype(float).div(safe_denom).values
        )

    return result_data
