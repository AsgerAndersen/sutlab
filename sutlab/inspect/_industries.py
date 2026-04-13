"""
inspect_industries: inspection tables for one or more industries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes, _natural_sort_key
from sutlab.inspect._shared import _sort_by_id_value, _write_inspection_to_excel
import dataclasses

from sutlab.derive import compute_price_layer_rates
from sutlab.inspect._style import (
    _format_number,
    _format_percentage,
    _style_detail_table,
    _style_industry_balance_table,
    _style_price_layers_table,
)
from sutlab.inspect._products import _get_price_layer_columns


@dataclass
class IndustryInspectionData:
    """Raw DataFrames underlying an :class:`IndustryInspection`.

    Use these directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding properties on :class:`IndustryInspection`,
    which return styled versions.
    """

    balance: pd.DataFrame
    balance_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_detail_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_detail_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail_coefficients: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_detail_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_rates: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_growth: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class IndustryInspection:
    """
    Result of :func:`inspect_industries`.

    Raw DataFrames are available under ``result.data``. Properties on this
    class will return styled :class:`~pandas.io.formats.style.Styler` objects
    for Jupyter display (to be added).

    Attributes
    ----------
    balance : pd.DataFrame
        Wide-format balance table. Rows have a four-level MultiIndex with
        names ``industry``, ``industry_txt``, ``transaction``,
        ``transaction_txt``:

        - ``industry``: industry code (value from the category column,
          e.g. ``"X"``).
        - ``industry_txt``: industry name from the ``industries``
          classification, or ``""`` if the classification is not loaded.
        - ``transaction``: transaction code for P1/P2 data rows
          (e.g. ``"0100"``), ``"B1g"`` for Gross value added, or ``""``
          for Total output, Total input, and Input coefficient rows.
        - ``transaction_txt``: transaction name for data rows, or
          ``"Total output"``, ``"Total input"``, ``"Gross value added"``,
          ``"Input coefficient"`` for summary and derived rows.

        Within each industry block, rows appear in this order:

        1. One row per P1 transaction (values from ``sut.supply`` at
           basic prices, summed across all products for the industry).
        2. ``"Total output"`` — only present when
           ``classifications.transactions`` contains two or more P1
           transaction codes.
        3. One row per P2 transaction (values from ``sut.use`` at
           purchasers' prices, summed across all products).
        4. ``"Total input"`` — only present when
           ``classifications.transactions`` contains two or more P2
           transaction codes.
        5. ``"Gross value added"`` — Total output minus Total input.
        6. ``"Input coefficient"`` — Total input divided by Total output.
           ``NaN`` where Total output is zero.

        Columns are the collection ids (e.g. years). Missing cells are
        filled with ``0``.
    balance_growth : pd.DataFrame
        Year-on-year growth of ``balance`` values: ``(current − previous) /
        previous``. Same MultiIndex structure as ``balance``. The first id
        column is ``NaN`` throughout (no prior year). Division by zero also
        yields ``NaN``. Values are fractions (e.g. ``0.05`` for 5% growth).
    supply_detail : pd.DataFrame
        Wide-format product breakdown for P1 (output) transactions. Rows
        have a six-level MultiIndex with names ``industry``,
        ``industry_txt``, ``transaction``, ``transaction_txt``, ``product``,
        ``product_txt``:

        - ``industry``: industry code.
        - ``industry_txt``: industry name from the ``industries``
          classification, or ``""`` if not loaded.
        - ``transaction``: P1 transaction code, or ``""`` for the Total row.
        - ``transaction_txt``: P1 transaction name, or ``"Total supply"``
          for the summary row.
        - ``product``: product code contributing to this industry's output,
          or ``""`` for the Total row.
        - ``product_txt``: product name from the ``products``
          classification, or ``""`` if not loaded.

        Within each industry block, rows appear ordered by (P1 transaction,
        product) — one row per combination present in the data, followed by
        a single ``"Total supply"`` row that sums across all transactions
        and products. Values are at basic prices. If ``sort_id`` is given,
        non-total rows within each industry block are sorted by that id
        value, descending — transactions and products are ordered together
        by value.
    supply_detail_distribution : pd.DataFrame
        Same structure as ``supply_detail``. For each industry and year,
        every value is divided by the sum across all transactions and
        products for that industry in that year. Values therefore express
        each product's share of total output. Division by zero yields
        ``NaN``.
    supply_detail_growth : pd.DataFrame
        Same structure as ``supply_detail``, with year-on-year growth:
        ``(current − previous) / previous``. The first id column is
        ``NaN`` throughout. Division by zero also yields ``NaN``.
    use_detail : pd.DataFrame
        Wide-format product breakdown for P2 (input) transactions. Same
        six-level MultiIndex structure as ``supply_detail``. Within each
        industry block, rows appear ordered by (P2 transaction, product) —
        one row per combination present in the data, followed by a single
        ``"Total use"`` row. Values are at purchasers' prices. ``sort_id``
        applies the same descending sort as for ``supply_detail``.
    use_detail_distribution : pd.DataFrame
        Same structure as ``use_detail``. For each industry and year,
        every value is divided by the sum across all transactions and
        products for that industry in that year. Division by zero yields
        ``NaN``.
    use_detail_coefficients : pd.DataFrame
        Same structure as ``use_detail``. For each industry and year,
        every value is divided by the industry's total output (sum of P1
        transactions at basic prices). Values therefore express each
        product's contribution to the input coefficient. Division by zero
        yields ``NaN``.
    use_detail_growth : pd.DataFrame
        Same structure as ``use_detail``, with year-on-year growth:
        ``(current − previous) / previous``. The first id column is
        ``NaN`` throughout. Division by zero also yields ``NaN``.
    price_layers : pd.DataFrame
        Five-level MultiIndex: ``(industry, industry_txt, price_layer,
        transaction, transaction_txt)``. One block per ``(industry,
        price_layer)`` combination. Within each block: one row per P2
        transaction with non-zero layer values across any id, plus a
        ``"Total"`` row (only when ≥ 2 P2 transactions exist in the
        classifications metadata). Values are absolute amounts.
    price_layers_rates : pd.DataFrame
        Same structure as ``price_layers`` but without Total rows. Each
        value is the step-wise rate for that price layer within the
        ``(transaction, industry)`` group: layer value divided by the
        cumulative price up to (not including) that layer. Division by
        zero yields ``NaN``.
    price_layers_distribution : pd.DataFrame
        Same structure as ``price_layers``. Within each
        ``(industry, price_layer)`` block, every value is divided by the
        Total row for that block and year. Division by zero yields ``NaN``.
        Empty when only one P2 transaction exists in the classifications
        metadata (distribution would be 1.0 everywhere).
    price_layers_growth : pd.DataFrame
        Same structure as ``price_layers``, with year-on-year growth:
        ``(current − previous) / previous``. The first id column is
        ``NaN`` throughout. Division by zero also yields ``NaN``.
    """

    data: IndustryInspectionData
    # P1 transaction codes — used by the balance property for colour assignment.
    _p1_trans: frozenset = field(default_factory=frozenset, repr=False)

    @property
    def balance(self) -> Styler:
        """Styled industry balance table for display in a Jupyter notebook."""
        return _style_industry_balance_table(self.data.balance, self._p1_trans)

    @property
    def supply_detail(self) -> Styler:
        """Styled product breakdown of industry output for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.supply_detail,
            _format_number,
            "supply",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def supply_detail_distribution(self) -> Styler:
        """Styled product-share distribution of industry output for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.supply_detail_distribution,
            _format_percentage,
            "supply",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def supply_detail_growth(self) -> Styler:
        """Styled year-on-year growth of industry output detail for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.supply_detail_growth,
            _format_percentage,
            "supply",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_detail(self) -> Styler:
        """Styled product breakdown of industry input for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_detail,
            _format_number,
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_detail_distribution(self) -> Styler:
        """Styled product-share distribution of industry input for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_detail_distribution,
            _format_percentage,
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_detail_coefficients(self) -> Styler:
        """Styled input coefficients by product for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_detail_coefficients,
            _format_percentage,
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_detail_growth(self) -> Styler:
        """Styled year-on-year growth of industry input detail for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_detail_growth,
            _format_percentage,
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def price_layers(self) -> Styler:
        """Styled price layer breakdown of industry input for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers,
            _format_number,
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def price_layers_rates(self) -> Styler:
        """Styled price layer rates for industry input for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers_rates,
            _format_percentage,
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def price_layers_distribution(self) -> Styler:
        """Styled price layer distribution of industry input for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers_distribution,
            _format_percentage,
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def price_layers_growth(self) -> Styler:
        """Styled year-on-year growth of price layers for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers_growth,
            _format_percentage,
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def balance_growth(self) -> Styler:
        """Styled year-on-year growth table for display in a Jupyter notebook.

        All values are formatted as percentages.
        """
        return _style_industry_balance_table(
            self.data.balance_growth, self._p1_trans, format_func=_format_percentage
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
        _write_inspection_to_excel(self, path)


def inspect_industries(
    sut: SUT,
    industries: str | list[str],
    ids=None,
    sort_id=None,
) -> IndustryInspection:
    """
    Return inspection tables for one or more industries.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    industries : str or list of str
        Industry codes to include. Accepts the same pattern syntax as
        :func:`filter_rows`: exact codes, wildcards (``*``), ranges (``:``),
        and negation (``~``).
    ids : value, list of values, or range, optional
        Id values (e.g. years) to include as columns. When ``None`` (the
        default), all ids present in the collection are included. Accepts a
        single value (``ids=2021``), a list (``ids=[2019, 2020]``), or a
        range (``ids=range(2015, 2022)``). Column order follows the sorted
        order of the full collection.
    sort_id : value, optional
        Reserved for future use. Balance tables are not sorted.

    Returns
    -------
    IndustryInspection
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
        If any value in ``ids`` is not found in the collection.
    ValueError
        If ``sort_id`` is not found in the collection ids (after applying
        the ``ids`` filter).
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call inspect_industries. "
            "Provide a SUTMetadata with column name mappings."
        )
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            "sut.metadata.classifications.transactions is required to call "
            "inspect_industries. Load a classifications file with a "
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

    # Identify P1 and P2 transaction codes from metadata, in classification order.
    p1_trans_df = trans_df[
        (trans_df["esa_code"] == "P1") & (trans_df["table"] == "supply")
    ]
    p2_trans_df = trans_df[
        (trans_df["esa_code"] == "P2") & (trans_df["table"] == "use")
    ]
    p1_trans = p1_trans_df[cols.transaction].astype(str).tolist()
    p2_trans = p2_trans_df[cols.transaction].astype(str).tolist()

    # Summary rows only appear when there are multiple transactions of that type.
    show_total_output = len(p1_trans) >= 2
    show_total_input = len(p2_trans) >= 2

    # Resolve industry patterns to concrete codes.
    # Industry codes only appear as category values in P1 supply rows and P2 use rows —
    # other transactions (P31, P32, ...) carry different category dimensions and must
    # not contribute to the candidate set.
    if isinstance(industries, str):
        patterns = [industries]
    else:
        patterns = list(industries)

    supply_p1_cats = (
        sut.supply[sut.supply[cols.transaction].isin(p1_trans)][cols.category]
        .dropna().unique().tolist()
    )
    use_p2_cats = (
        sut.use[sut.use[cols.transaction].isin(p2_trans)][cols.category]
        .dropna().unique().tolist()
    )
    all_cats = sorted(set(supply_p1_cats) | set(use_p2_cats), key=_natural_sort_key)
    matched_industries = _match_codes(all_cats, patterns)

    # All ids, sorted — shared across all tables for consistent columns.
    supply_ids = sut.supply[cols.id].unique().tolist()
    use_ids = sut.use[cols.id].unique().tolist()
    all_ids = sorted(set(supply_ids) | set(use_ids))

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

    # Transaction name lookup: code → name.
    trans_names = dict(zip(
        trans_df[cols.transaction].astype(str),
        trans_df[trans_txt_col].astype(str),
    ))

    # Industry name lookup — silently empty strings if classification not loaded.
    ind_txt_col = f"{cols.category}_txt"
    industries_cls = sut.metadata.classifications.industries
    if industries_cls is not None and ind_txt_col in industries_cls.columns:
        industry_names = dict(zip(
            industries_cls[cols.category].astype(str),
            industries_cls[ind_txt_col].astype(str),
        ))
    else:
        industry_names = {}

    # Product name lookup — silently empty strings if classification not loaded.
    prod_txt_col = f"{cols.product}_txt"
    classifications = sut.metadata.classifications
    if (
        classifications is not None
        and classifications.products is not None
        and prod_txt_col in classifications.products.columns
    ):
        product_names = dict(zip(
            classifications.products[cols.product].astype(str),
            classifications.products[prod_txt_col].astype(str),
        ))
    else:
        product_names = {}

    balance = _build_industry_balance_table(
        sut=sut,
        matched_industries=matched_industries,
        p1_trans=p1_trans,
        p2_trans=p2_trans,
        trans_names=trans_names,
        industry_names=industry_names,
        all_ids=all_ids,
        show_total_output=show_total_output,
        show_total_input=show_total_input,
    )

    balance_growth = _build_growth_table(balance)

    supply_detail = _build_industry_supply_detail(
        sut=sut,
        matched_industries=matched_industries,
        p1_trans=p1_trans,
        trans_names=trans_names,
        industry_names=industry_names,
        product_names=product_names,
        all_ids=all_ids,
    )
    if sort_id is not None and not supply_detail.empty:
        supply_detail = _sort_by_id_value(supply_detail, ["industry"], sort_id)
    supply_detail_distribution = _build_supply_detail_distribution(supply_detail)
    supply_detail_growth = _build_growth_table(supply_detail)

    use_detail = _build_industry_use_detail(
        sut=sut,
        matched_industries=matched_industries,
        p2_trans=p2_trans,
        trans_names=trans_names,
        industry_names=industry_names,
        product_names=product_names,
        all_ids=all_ids,
    )
    if sort_id is not None and not use_detail.empty:
        use_detail = _sort_by_id_value(use_detail, ["industry"], sort_id)
    use_detail_distribution = _build_use_detail_distribution(use_detail)
    use_detail_coefficients = _build_use_detail_coefficients(
        sut=sut,
        use_detail=use_detail,
        matched_industries=matched_industries,
        p1_trans=p1_trans,
        all_ids=all_ids,
    )
    use_detail_growth = _build_growth_table(use_detail)

    price_layers = _build_industry_price_layers_table(
        sut=sut,
        matched_industries=matched_industries,
        p2_trans=p2_trans,
        trans_names=trans_names,
        industry_names=industry_names,
        all_ids=all_ids,
        show_total=show_total_input,
    )
    if sort_id is not None and not price_layers.empty:
        price_layers = _sort_by_id_value(price_layers, ["industry", "price_layer"], sort_id)
    price_layers_rates = _build_industry_price_layers_rates(
        price_layers=price_layers,
        sut=sut,
        matched_industries=matched_industries,
        p2_trans=p2_trans,
        all_ids=all_ids,
    )
    price_layers_distribution = (
        _build_price_layers_distribution(price_layers)
        if show_total_input
        else pd.DataFrame()
    )
    price_layers_growth = _build_growth_table(price_layers)

    data = IndustryInspectionData(
        balance=balance,
        balance_growth=balance_growth,
        supply_detail=supply_detail,
        supply_detail_distribution=supply_detail_distribution,
        supply_detail_growth=supply_detail_growth,
        use_detail=use_detail,
        use_detail_distribution=use_detail_distribution,
        use_detail_coefficients=use_detail_coefficients,
        use_detail_growth=use_detail_growth,
        price_layers=price_layers,
        price_layers_rates=price_layers_rates,
        price_layers_distribution=price_layers_distribution,
        price_layers_growth=price_layers_growth,
    )
    return IndustryInspection(data=data, _p1_trans=frozenset(p1_trans))


def _build_industry_balance_table(
    sut: SUT,
    matched_industries: list[str],
    p1_trans: list[str],
    p2_trans: list[str],
    trans_names: dict[str, str],
    industry_names: dict[str, str],
    all_ids: list,
    show_total_output: bool,
    show_total_input: bool,
) -> pd.DataFrame:
    """Build the wide-format balance table for the given industries.

    Aggregates supply (P1 transactions) and use (P2 transactions) across all
    products, then assembles the ordered row blocks for each industry.

    Parameters
    ----------
    sut : SUT
        The SUT collection.
    matched_industries : list of str
        Industry codes to include, in display order.
    p1_trans : list of str
        P1 transaction codes in classification order.
    p2_trans : list of str
        P2 transaction codes in classification order.
    trans_names : dict
        Maps transaction code → transaction label.
    industry_names : dict
        Maps industry code → industry label (empty string if not loaded).
    all_ids : list
        Collection ids to use as columns.
    show_total_output : bool
        Whether to insert a Total output row after the P1 transaction rows.
    show_total_input : bool
        Whether to insert a Total input row after the P2 transaction rows.

    Returns
    -------
    pd.DataFrame
        Wide-format balance table with a four-level MultiIndex.
    """
    cols = sut.metadata.columns
    id_col = cols.id
    cat_col = cols.category
    trans_col = cols.transaction
    bas_col = cols.price_basic
    purch_col = cols.price_purchasers

    # --- Vectorized aggregation ---
    # Supply: filter to P1 transactions and matched industries, then group by
    # (industry, transaction, id) and sum basic prices.
    supply_p1 = sut.supply[
        sut.supply[trans_col].isin(p1_trans)
        & sut.supply[cat_col].isin(matched_industries)
    ]
    supply_agg = (
        supply_p1
        .groupby([cat_col, trans_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
    )

    # Use: filter to P2 transactions and matched industries, then group by
    # (industry, transaction, id) and sum purchasers' prices.
    use_p2 = sut.use[
        sut.use[trans_col].isin(p2_trans)
        & sut.use[cat_col].isin(matched_industries)
    ]
    use_agg = (
        use_p2
        .groupby([cat_col, trans_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )

    # Pivot both to wide format — one call covers all industries and transactions.
    # Index: (industry, transaction). Columns: id values.
    if not supply_agg.empty:
        supply_wide = supply_agg.pivot_table(
            index=[cat_col, trans_col],
            columns=id_col,
            values=bas_col,
            aggfunc="sum",
            fill_value=0,
        )
        supply_wide.columns.name = None
    else:
        supply_wide = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([], names=[cat_col, trans_col]),
            columns=all_ids,
            dtype=float,
        )

    if not use_agg.empty:
        use_wide = use_agg.pivot_table(
            index=[cat_col, trans_col],
            columns=id_col,
            values=purch_col,
            aggfunc="sum",
            fill_value=0,
        )
        use_wide.columns.name = None
    else:
        use_wide = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([], names=[cat_col, trans_col]),
            columns=all_ids,
            dtype=float,
        )

    # --- Per-industry row assembly ---
    # The aggregation above is fully vectorized. The loop below only assembles
    # the pre-computed values into the ordered MultiIndex structure.
    blocks = []
    supply_industry_codes = supply_wide.index.get_level_values(cat_col)
    use_industry_codes = use_wide.index.get_level_values(cat_col)

    for industry in matched_industries:
        industry_txt = industry_names.get(industry, "")
        row_labels = []
        row_data = []

        # Extract P1 rows for this industry: sub-DataFrame with transaction as index.
        # Reindex to ensure all p1_trans rows and all_ids columns are present.
        if industry in supply_industry_codes:
            ind_supply = supply_wide.xs(industry, level=cat_col).reindex(
                index=p1_trans, columns=all_ids, fill_value=0
            )
        else:
            ind_supply = pd.DataFrame(0.0, index=p1_trans, columns=all_ids)

        for trans in p1_trans:
            trans_txt = trans_names.get(trans, trans)
            row_labels.append((industry, industry_txt, trans, trans_txt))
            row_data.append(ind_supply.loc[trans].tolist())

        # Total output is always computed (needed for GVA and input coefficient),
        # but only added as a row when there are multiple P1 transactions.
        total_output = ind_supply.sum(axis=0)
        if show_total_output:
            row_labels.append((industry, industry_txt, "", "Total output"))
            row_data.append(total_output.tolist())

        # Extract P2 rows for this industry.
        if industry in use_industry_codes:
            ind_use = use_wide.xs(industry, level=cat_col).reindex(
                index=p2_trans, columns=all_ids, fill_value=0
            )
        else:
            ind_use = pd.DataFrame(0.0, index=p2_trans, columns=all_ids)

        for trans in p2_trans:
            trans_txt = trans_names.get(trans, trans)
            row_labels.append((industry, industry_txt, trans, trans_txt))
            row_data.append(ind_use.loc[trans].tolist())

        # Total input is always computed, but only added as a row when there
        # are multiple P2 transactions.
        total_input = ind_use.sum(axis=0)
        if show_total_input:
            row_labels.append((industry, industry_txt, "", "Total input"))
            row_data.append(total_input.tolist())

        # GVA = Total output (basic prices) - Total input (purchasers' prices).
        gva = total_output - total_input
        row_labels.append((industry, industry_txt, "B1g", "Gross value added"))
        row_data.append(gva.tolist())

        # Input coefficient = Total input / Total output. NaN where output is zero.
        output_denom = total_output.where(total_output != 0)
        input_coeff = total_input / output_denom
        row_labels.append((industry, industry_txt, "", "Input coefficient"))
        row_data.append(input_coeff.tolist())

        block = pd.DataFrame(
            row_data,
            index=pd.MultiIndex.from_tuples(
                row_labels,
                names=["industry", "industry_txt", "transaction", "transaction_txt"],
            ),
            columns=all_ids,
        )
        blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)


def _build_industry_supply_detail(
    sut: SUT,
    matched_industries: list[str],
    p1_trans: list[str],
    trans_names: dict[str, str],
    industry_names: dict[str, str],
    product_names: dict[str, str],
    all_ids: list,
) -> pd.DataFrame:
    """Build the product-breakdown supply detail table for the given industries.

    For each industry, produces one row per (P1 transaction, product)
    combination present in the supply data, followed by a single
    ``"Total supply"`` row summing across all transactions and products.
    Values are at basic prices.

    Parameters
    ----------
    sut : SUT
        The SUT collection.
    matched_industries : list of str
        Industry codes to include, in display order.
    p1_trans : list of str
        P1 transaction codes in classification order.
    trans_names : dict
        Maps transaction code → transaction label.
    industry_names : dict
        Maps industry code → industry label (empty string if not loaded).
    product_names : dict
        Maps product code → product label (empty string if not loaded).
    all_ids : list
        Collection ids to use as columns.

    Returns
    -------
    pd.DataFrame
        Wide-format supply detail table with a six-level MultiIndex:
        ``(industry, industry_txt, transaction, transaction_txt, product,
        product_txt)``.
    """
    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category
    bas_col = cols.price_basic

    # Filter to P1 transactions and matched industries.
    supply_p1 = sut.supply[
        sut.supply[trans_col].isin(p1_trans)
        & sut.supply[cat_col].isin(matched_industries)
    ]

    if supply_p1.empty:
        return pd.DataFrame()

    # Aggregate: sum basic prices by (industry, transaction, product, id).
    agg = (
        supply_p1
        .groupby([cat_col, trans_col, prod_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
    )

    # Pivot to wide format: index = (industry, transaction, product), columns = id.
    wide = agg.pivot_table(
        index=[cat_col, trans_col, prod_col],
        columns=id_col,
        values=bas_col,
        aggfunc="sum",
        fill_value=0,
    )
    wide.columns.name = None
    for id_val in all_ids:
        if id_val not in wide.columns:
            wide[id_val] = 0
    wide = wide[all_ids]

    # Sort rows: industry in matched_industries order, transaction in p1_trans order,
    # product in natural sort order within each (industry, transaction).
    product_order = sorted(
        wide.index.get_level_values(prod_col).unique().tolist(),
        key=_natural_sort_key,
    )
    ind_cat = pd.Categorical(
        wide.index.get_level_values(cat_col), categories=matched_industries, ordered=True
    )
    trans_cat = pd.Categorical(
        wide.index.get_level_values(trans_col), categories=p1_trans, ordered=True
    )
    prod_cat = pd.Categorical(
        wide.index.get_level_values(prod_col), categories=product_order, ordered=True
    )
    sort_key_df = pd.DataFrame(
        {"ind": ind_cat, "trans": trans_cat, "prod": prod_cat},
        index=range(len(wide)),
    )
    sorted_positions = sort_key_df.sort_values(["ind", "trans", "prod"]).index.tolist()
    wide = wide.iloc[sorted_positions]

    # Build full MultiIndex with text labels.
    industries = wide.index.get_level_values(cat_col)
    transactions = wide.index.get_level_values(trans_col)
    products = wide.index.get_level_values(prod_col)
    wide.index = pd.MultiIndex.from_arrays(
        [
            industries,
            [industry_names.get(i, "") for i in industries],
            transactions,
            [trans_names.get(t, t) for t in transactions],
            products,
            [product_names.get(p, "") for p in products],
        ],
        names=["industry", "industry_txt", "transaction", "transaction_txt", "product", "product_txt"],
    )

    # Append one "Total supply" row at the end of each industry block,
    # summing across all transactions and products for that industry.
    industry_vals = wide.index.get_level_values("industry")
    industry_txt_vals = wide.index.get_level_values("industry_txt")
    ordered_industries = list(dict.fromkeys(industry_vals))
    blocks = []
    for industry in ordered_industries:
        mask = industry_vals == industry
        block = wide[mask]
        ind_txt = industry_txt_vals[mask][0]
        total_values = block[all_ids].sum()
        total_index = pd.MultiIndex.from_tuples(
            [(industry, ind_txt, "", "Total supply", "", "")],
            names=wide.index.names,
        )
        total_row = pd.DataFrame([total_values.tolist()], index=total_index, columns=all_ids)
        blocks.append(pd.concat([block, total_row]))

    return pd.concat(blocks)


def _build_industry_use_detail(
    sut: SUT,
    matched_industries: list[str],
    p2_trans: list[str],
    trans_names: dict[str, str],
    industry_names: dict[str, str],
    product_names: dict[str, str],
    all_ids: list,
) -> pd.DataFrame:
    """Build the product-breakdown use detail table for the given industries.

    For each industry, produces one row per (P2 transaction, product)
    combination present in the use data, followed by a single ``"Total use"``
    row summing across all transactions and products. Values are at
    purchasers' prices.

    Parameters
    ----------
    sut : SUT
        The SUT collection.
    matched_industries : list of str
        Industry codes to include, in display order.
    p2_trans : list of str
        P2 transaction codes in classification order.
    trans_names : dict
        Maps transaction code → transaction label.
    industry_names : dict
        Maps industry code → industry label (empty string if not loaded).
    product_names : dict
        Maps product code → product label (empty string if not loaded).
    all_ids : list
        Collection ids to use as columns.

    Returns
    -------
    pd.DataFrame
        Wide-format use detail table with a six-level MultiIndex:
        ``(industry, industry_txt, transaction, transaction_txt, product,
        product_txt)``.
    """
    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category
    purch_col = cols.price_purchasers

    # Filter to P2 transactions and matched industries.
    use_p2 = sut.use[
        sut.use[trans_col].isin(p2_trans)
        & sut.use[cat_col].isin(matched_industries)
    ]

    if use_p2.empty:
        return pd.DataFrame()

    # Aggregate: sum purchasers' prices by (industry, transaction, product, id).
    agg = (
        use_p2
        .groupby([cat_col, trans_col, prod_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )

    # Pivot to wide format: index = (industry, transaction, product), columns = id.
    wide = agg.pivot_table(
        index=[cat_col, trans_col, prod_col],
        columns=id_col,
        values=purch_col,
        aggfunc="sum",
        fill_value=0,
    )
    wide.columns.name = None
    for id_val in all_ids:
        if id_val not in wide.columns:
            wide[id_val] = 0
    wide = wide[all_ids]

    # Sort rows: industry in matched_industries order, transaction in p2_trans order,
    # product in natural sort order within each (industry, transaction).
    product_order = sorted(
        wide.index.get_level_values(prod_col).unique().tolist(),
        key=_natural_sort_key,
    )
    ind_cat = pd.Categorical(
        wide.index.get_level_values(cat_col), categories=matched_industries, ordered=True
    )
    trans_cat = pd.Categorical(
        wide.index.get_level_values(trans_col), categories=p2_trans, ordered=True
    )
    prod_cat = pd.Categorical(
        wide.index.get_level_values(prod_col), categories=product_order, ordered=True
    )
    sort_key_df = pd.DataFrame(
        {"ind": ind_cat, "trans": trans_cat, "prod": prod_cat},
        index=range(len(wide)),
    )
    sorted_positions = sort_key_df.sort_values(["ind", "trans", "prod"]).index.tolist()
    wide = wide.iloc[sorted_positions]

    # Build full MultiIndex with text labels.
    industries = wide.index.get_level_values(cat_col)
    transactions = wide.index.get_level_values(trans_col)
    products = wide.index.get_level_values(prod_col)
    wide.index = pd.MultiIndex.from_arrays(
        [
            industries,
            [industry_names.get(i, "") for i in industries],
            transactions,
            [trans_names.get(t, t) for t in transactions],
            products,
            [product_names.get(p, "") for p in products],
        ],
        names=["industry", "industry_txt", "transaction", "transaction_txt", "product", "product_txt"],
    )

    # Append one "Total use" row at the end of each industry block,
    # summing across all transactions and products for that industry.
    industry_vals = wide.index.get_level_values("industry")
    industry_txt_vals = wide.index.get_level_values("industry_txt")
    ordered_industries = list(dict.fromkeys(industry_vals))
    blocks = []
    for industry in ordered_industries:
        mask = industry_vals == industry
        block = wide[mask]
        ind_txt = industry_txt_vals[mask][0]
        total_values = block[all_ids].sum()
        total_index = pd.MultiIndex.from_tuples(
            [(industry, ind_txt, "", "Total use", "", "")],
            names=wide.index.names,
        )
        total_row = pd.DataFrame([total_values.tolist()], index=total_index, columns=all_ids)
        blocks.append(pd.concat([block, total_row]))

    return pd.concat(blocks)


def _build_use_detail_coefficients(
    sut: SUT,
    use_detail: pd.DataFrame,
    matched_industries: list[str],
    p1_trans: list[str],
    all_ids: list,
) -> pd.DataFrame:
    """Build input-coefficient breakdown by product for the given industries.

    Each value in ``use_detail`` is divided by the industry's total output
    (sum of all P1 transactions at basic prices) for that year. The result
    expresses each product's contribution to the industry's overall input
    coefficient. Division by zero yields ``NaN``.

    Parameters
    ----------
    sut : SUT
        The SUT collection (used to recompute total output per industry).
    use_detail : pd.DataFrame
        Use detail table as produced by :func:`_build_industry_use_detail`.
    matched_industries : list of str
        Industry codes in display order.
    p1_trans : list of str
        P1 transaction codes used to compute total output.
    all_ids : list
        Collection ids (years) — used as columns.
    """
    if use_detail.empty:
        return pd.DataFrame()

    cols = sut.metadata.columns
    id_col = cols.id
    trans_col = cols.transaction
    cat_col = cols.category
    bas_col = cols.price_basic

    # Compute total P1 output per industry per year from sut.supply.
    supply_p1 = sut.supply[
        sut.supply[trans_col].isin(p1_trans)
        & sut.supply[cat_col].isin(matched_industries)
    ]
    output_totals = (
        supply_p1
        .groupby([cat_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
        .pivot_table(index=cat_col, columns=id_col, values=bas_col, aggfunc="sum", fill_value=0)
    )
    output_totals.columns.name = None
    for id_val in all_ids:
        if id_val not in output_totals.columns:
            output_totals[id_val] = 0
    output_totals = output_totals[all_ids]

    # Replace zero totals with NaN so division yields NaN rather than inf.
    safe_totals = output_totals.replace(0, float("nan"))

    # Align denominators to every row of use_detail.
    industry_vals = use_detail.index.get_level_values("industry")
    # Industries missing from supply get NaN denominators, which propagates to NaN.
    denominators = safe_totals.reindex(industry_vals).values

    return pd.DataFrame(
        use_detail.astype(float).values / denominators,
        index=use_detail.index,
        columns=use_detail.columns,
    )


def _build_use_detail_distribution(use_detail: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalised version of the industry use detail table.

    For each industry and year, every value is divided by the sum across all
    transactions and products for that industry in that year (the
    ``"Total use"`` denominator). Division by zero yields ``NaN``.
    """
    if use_detail.empty:
        return pd.DataFrame()

    detail_float = use_detail.astype(float)
    industry_vals = use_detail.index.get_level_values("industry")

    non_summary_mask = use_detail.index.get_level_values("transaction") != ""
    industry_totals = (
        detail_float[non_summary_mask]
        .groupby(level="industry", dropna=False)
        .sum()
    )
    safe_totals = industry_totals.replace(0, float("nan"))
    denominators = safe_totals.loc[industry_vals].values

    return pd.DataFrame(
        detail_float.values / denominators,
        index=use_detail.index,
        columns=use_detail.columns,
    )


def _build_supply_detail_distribution(supply_detail: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalised version of the industry supply detail table.

    For each industry and year, every value is divided by the sum across all
    transactions and products for that industry in that year (i.e. the
    "Total supply" denominator). Division by zero yields ``NaN``.
    """
    if supply_detail.empty:
        return pd.DataFrame()

    detail_float = supply_detail.astype(float)
    industry_vals = supply_detail.index.get_level_values("industry")

    # Sum non-summary rows per industry in one groupby, then align to every row.
    non_summary_mask = supply_detail.index.get_level_values("transaction") != ""
    industry_totals = (
        detail_float[non_summary_mask]
        .groupby(level="industry", dropna=False)
        .sum()
    )
    # Replace zero totals with NaN so division yields NaN rather than inf.
    safe_totals = industry_totals.replace(0, float("nan"))
    # Build a denominator array aligned to every row of supply_detail.
    denominators = safe_totals.loc[industry_vals].values

    return pd.DataFrame(
        detail_float.values / denominators,
        index=supply_detail.index,
        columns=supply_detail.columns,
    )


def _build_industry_price_layers_table(
    sut: SUT,
    matched_industries: list[str],
    p2_trans: list[str],
    trans_names: dict[str, str],
    industry_names: dict[str, str],
    all_ids: list,
    show_total: bool,
) -> pd.DataFrame:
    """Build the price layers table for the given industries.

    Returns a DataFrame with a five-level MultiIndex:
    ``(industry, industry_txt, price_layer, transaction, transaction_txt)``.
    One block per ``(industry, price_layer)`` combination. Within each block:
    one row per P2 transaction with non-zero layer values across any id, plus
    a ``"Total"`` row (only when ``show_total`` is ``True``).

    Parameters
    ----------
    sut : SUT
        Full SUT collection.
    matched_industries : list of str
        Industry (category) codes in display order.
    p2_trans : list of str
        P2 transaction codes.
    trans_names : dict
        Maps transaction code → label.
    industry_names : dict
        Maps industry code → label.
    all_ids : list
        Collection ids (years) — column order.
    show_total : bool
        Whether to append a Total row to each block. Should be ``True`` only
        when ≥ 2 P2 transactions exist in the classifications metadata.
    """
    cols = sut.metadata.columns
    id_col = cols.id
    trans_col = cols.transaction
    cat_col = cols.category

    layer_cols = _get_price_layer_columns(cols, sut.use)
    if not layer_cols:
        return pd.DataFrame()

    # Filter use to P2 transactions and matched industries only.
    use_p2 = sut.use[
        sut.use[trans_col].isin(p2_trans)
        & sut.use[cat_col].isin(matched_industries)
    ]

    if use_p2.empty:
        return pd.DataFrame()

    # Pre-aggregate per layer across all industries at once: one groupby per layer
    # instead of N_industries × N_layers groupbys.
    layer_aggs: dict[str, pd.DataFrame] = {}
    for layer_col in layer_cols:
        layer_data = use_p2[use_p2[layer_col].notna()]
        if not layer_data.empty:
            layer_aggs[layer_col] = (
                layer_data
                .groupby([cat_col, trans_col, id_col], as_index=False, dropna=False)[layer_col]
                .sum()
            )

    blocks = []

    for industry in matched_industries:
        industry_txt = industry_names.get(industry, "")

        for layer_col in layer_cols:
            if layer_col not in layer_aggs:
                continue

            ind_agg = layer_aggs[layer_col]
            ind_agg = ind_agg[ind_agg[cat_col] == industry]

            if ind_agg.empty:
                continue

            wide = ind_agg.pivot_table(
                index=trans_col,
                columns=id_col,
                values=layer_col,
                aggfunc="sum",
                fill_value=0,
            )
            wide.columns.name = None
            for id_val in all_ids:
                if id_val not in wide.columns:
                    wide[id_val] = 0
            wide = wide[all_ids]

            # Drop transactions that are all zero across all ids.
            non_zero_mask = (wide != 0).any(axis=1)
            wide = wide[non_zero_mask]

            if wide.empty:
                continue

            use_trans = sorted(wide.index.tolist(), key=_natural_sort_key)

            row_labels = []
            row_data = []

            for trans in use_trans:
                trans_txt = trans_names.get(trans, trans)
                row_labels.append((industry, industry_txt, layer_col, trans, trans_txt))
                row_data.append(wide.loc[trans, all_ids].tolist())

            if show_total:
                total = wide.loc[use_trans].sum()
                row_labels.append((industry, industry_txt, layer_col, "", "Total"))
                row_data.append(total.tolist())

            block = pd.DataFrame(
                row_data,
                index=pd.MultiIndex.from_tuples(
                    row_labels,
                    names=["industry", "industry_txt", "price_layer",
                           "transaction", "transaction_txt"],
                ),
                columns=all_ids,
            )
            blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)


def _build_industry_price_layers_rates(
    price_layers: pd.DataFrame,
    sut: SUT,
    matched_industries: list[str],
    p2_trans: list[str],
    all_ids: list,
) -> pd.DataFrame:
    """Build price layer rates with the same structure as ``price_layers``, without Total rows.

    Each transaction row's rate is computed within the ``(transaction,
    industry)`` group: the layer value is divided by the cumulative price up
    to (not including) that layer. Total rows are excluded — a summed rate
    across transactions is not meaningful.

    Rates are derived from
    :func:`~sutlab.derive.compute_price_layer_rates` at
    ``aggregation_level=["transaction", "category"]``, using a SUT whose
    ``use`` is pre-filtered to matched industries and P2 transactions.

    Parameters
    ----------
    price_layers : pd.DataFrame
        As produced by :func:`_build_industry_price_layers_table`.
    sut : SUT
        Full SUT collection (used to build the filtered SUT for rate computation).
    matched_industries : list of str
        Industry (category) codes.
    p2_trans : list of str
        P2 transaction codes.
    all_ids : list
        Collection ids (years) — column order.
    """
    if price_layers.empty:
        return pd.DataFrame()

    cols = sut.metadata.columns
    id_col = cols.id
    trans_col = cols.transaction
    cat_col = cols.category

    # Non-total rows only.
    non_total_mask = price_layers.index.get_level_values("transaction") != ""
    price_layers_trans = price_layers[non_total_mask]

    if price_layers_trans.empty:
        return pd.DataFrame()

    # Build a filtered SUT (use only) for rate computation.
    filtered_use = sut.use[
        sut.use[trans_col].isin(p2_trans)
        & sut.use[cat_col].isin(matched_industries)
    ]
    filtered_sut = dataclasses.replace(sut, use=filtered_use)

    trans_cat_rates = compute_price_layer_rates(
        filtered_sut, ["transaction", "category"]
    )

    if trans_cat_rates.empty:
        return pd.DataFrame()

    # Build lookup: (transaction, industry, layer_col) → list of rates aligned to all_ids.
    layer_cols_in_rates = [
        c for c in trans_cat_rates.columns
        if c not in [trans_col, cat_col, id_col]
    ]
    nan_row = [float("nan")] * len(all_ids)

    trans_cat_wide = trans_cat_rates.pivot_table(
        index=[trans_col, cat_col],
        columns=id_col,
        values=layer_cols_in_rates,
        aggfunc="sum",
    )
    trans_cat_wide = trans_cat_wide.reindex(
        columns=all_ids, level=id_col, fill_value=float("nan")
    )

    # Build position map: layer_col → column indices in trans_cat_wide.
    layer_col_positions: dict[str, list[int]] = {}
    for j, (layer_name, _) in enumerate(trans_cat_wide.columns.tolist()):
        if layer_name not in layer_col_positions:
            layer_col_positions[layer_name] = []
        layer_col_positions[layer_name].append(j)

    values_2d = trans_cat_wide.to_numpy()
    index_list = trans_cat_wide.index.tolist()
    rate_lookup: dict[tuple, list] = {}
    for i, (trans, industry) in enumerate(index_list):
        row = values_2d[i]
        for layer_col_name, positions in layer_col_positions.items():
            rate_lookup[(trans, industry, layer_col_name)] = row[positions].tolist()

    industry_vals = price_layers_trans.index.get_level_values("industry")
    layer_vals = price_layers_trans.index.get_level_values("price_layer")
    trans_vals = price_layers_trans.index.get_level_values("transaction")

    rates_rows = [
        rate_lookup.get((transaction, industry, layer_col), nan_row)
        for transaction, industry, layer_col in zip(trans_vals, industry_vals, layer_vals)
    ]
    return pd.DataFrame(rates_rows, index=price_layers_trans.index, columns=all_ids)


def _build_price_layers_distribution(price_layers: pd.DataFrame) -> pd.DataFrame:
    """Build distribution table: each value divided by the Total row for its block.

    Within each ``(industry, price_layer)`` block, every value is divided by
    the Total row for that block and year. If the block has no Total row (i.e.
    only one transaction and ``show_total`` was ``False``), the single row is
    divided by itself, yielding 1.0. Division by zero yields ``NaN``.

    Parameters
    ----------
    price_layers : pd.DataFrame
        As produced by :func:`_build_industry_price_layers_table`.
    """
    if price_layers.empty:
        return pd.DataFrame()

    industry_vals = price_layers.index.get_level_values("industry")
    layer_vals = price_layers.index.get_level_values("price_layer")
    trans_vals = price_layers.index.get_level_values("transaction")

    # Build (industry, price_layer) → Total row values.
    # If no explicit Total row exists, sum across all transaction rows.
    total_mask = trans_vals == ""
    result_data = price_layers.astype(float).copy()

    blocks = list(dict.fromkeys(zip(industry_vals, layer_vals)))
    for industry, layer in blocks:
        block_mask = (industry_vals == industry) & (layer_vals == layer)
        total_row_mask = block_mask & total_mask

        if total_row_mask.any():
            total_vals = price_layers[total_row_mask].iloc[0].astype(float)
        else:
            # No explicit total — sum all transaction rows to use as denominator.
            total_vals = price_layers[block_mask].astype(float).sum()

        safe_total = total_vals.where(total_vals != 0, other=float("nan"))
        result_data.loc[block_mask] = (
            price_layers[block_mask].astype(float).div(safe_total).values
        )

    return result_data


def _build_growth_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build year-on-year growth table: change relative to the previous year.

    Each value is ``(current - previous) / previous``, so a 5% increase gives
    ``0.05``. The first id column is ``NaN`` throughout. Division by zero also
    yields ``NaN``. Infinite values (from dividing a non-zero change by zero)
    are replaced with ``NaN``.
    """
    if df.empty:
        return pd.DataFrame()

    floats = df.astype(float)
    previous = floats.shift(axis=1)
    growth = (floats - previous).div(previous)
    growth = growth.replace([float("inf"), float("-inf")], float("nan"))
    return growth
