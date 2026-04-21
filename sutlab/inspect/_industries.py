"""
inspect_industries: inspection tables for one or more industries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes, _natural_sort_key
from sutlab.inspect._shared import _build_growth_table, _display_index, _sort_by_id_value, _write_inspection_to_excel
import dataclasses

from sutlab.derive import compute_price_layer_rates
from sutlab.inspect._style import (
    _format_number,
    _format_percentage,
    _make_number_formatter,
    _make_percentage_formatter,
    _style_detail_table,
    _style_industry_balance_table,
    _style_price_layers_table,
    _style_products_summary_table,
    _style_tables_description,
)
from sutlab.inspect._products import _get_price_layer_columns
from sutlab.inspect._tables_comparison import TablesComparison, _compute_comparison_table_fields


@dataclass
class IndustryInspectionData:
    """Raw DataFrames underlying an :class:`IndustryInspection`.

    Use these directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding properties on :class:`IndustryInspection`,
    which return styled versions.
    """

    balance: pd.DataFrame
    balance_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_products: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_products_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_products_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_products_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_coefficients: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
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
                    "Output, input, gross value added, and input coefficient per industry.",
                    "Year-on-year growth rates of the balance table.",
                    "Supply values broken down by product for each industry.",
                    "Supply products expressed as shares of total output.",
                    "Year-on-year growth rates of supply product values.",
                    "Per-transaction statistics summarising the supply product breakdown (totals, counts, percentiles).",
                    "Use values broken down by product for each industry, at purchasers' prices.",
                    "Use products expressed as shares of total input.",
                    "Use product values expressed as coefficients relative to total output.",
                    "Year-on-year growth rates of use product values.",
                    "Per-transaction statistics summarising the use product breakdown (totals, counts, percentiles).",
                    "Price layer values (gap between basic and purchasers' prices) by layer.",
                    "Each price layer expressed as a rate relative to basic-price use.",
                    "Each price layer expressed as a share of total price layers.",
                    "Year-on-year growth rates of price layer values.",
                ]
            },
            index=pd.Index(
                [
                    "balance",
                    "balance_growth",
                    "supply_products",
                    "supply_products_distribution",
                    "supply_products_growth",
                    "supply_products_summary",
                    "use_products",
                    "use_products_distribution",
                    "use_products_coefficients",
                    "use_products_growth",
                    "use_products_summary",
                    "price_layers",
                    "price_layers_rates",
                    "price_layers_distribution",
                    "price_layers_growth",
                ],
                name="name",
            ),
        )


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
    supply_products : pd.DataFrame
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
    supply_products_distribution : pd.DataFrame
        Same structure as ``supply_products``. For each industry and year,
        every value is divided by the sum across all transactions and
        products for that industry in that year. Values therefore express
        each product's share of total output. Division by zero yields
        ``NaN``.
    supply_products_growth : pd.DataFrame
        Same structure as ``supply_products``, with year-on-year growth:
        ``(current − previous) / previous``. The first id column is
        ``NaN`` throughout. Division by zero also yields ``NaN``.
    supply_products_summary : pd.DataFrame
        Per-transaction summary statistics for P1 supply, aggregated over
        products. Five-level MultiIndex:
        ``(industry, industry_txt, transaction, transaction_txt, summary)``.
        One block per ``(industry, P1 transaction)`` combination. The
        ``summary`` level contains the following rows in order:

        - ``"total"`` — sum of all product values for that transaction and
          year.
        - ``"n_products"`` — count of products with non-zero values.
        - ``"value_{label}"`` — one row per requested percentile of the
          absolute product values (non-zero products only).
        - ``"share_{label}"`` — one row per requested percentile of each
          product's share of the transaction total (non-zero products only).
          ``NaN`` when the total is zero.
        - ``"n_products_{label}"`` — one row per coverage threshold: the
          minimum number of products (sorted by value descending, per year)
          needed to account for that fraction of the total. ``NaN`` when
          the total is zero or there are no non-zero products.

        Percentile labels: ``0.0`` → ``"min"``, ``0.5`` → ``"median"``,
        ``1.0`` → ``"max"``, others → ``"p{int(p*100)}"``.
        Coverage threshold labels follow the same convention.
    use_products : pd.DataFrame
        Wide-format product breakdown for P2 (input) transactions. Same
        six-level MultiIndex structure as ``supply_products``. Within each
        industry block, rows appear ordered by (P2 transaction, product) —
        one row per combination present in the data, followed by a single
        ``"Total use"`` row. Values are at purchasers' prices. ``sort_id``
        applies the same descending sort as for ``supply_products``.
    use_products_distribution : pd.DataFrame
        Same structure as ``use_products``. For each industry and year,
        every value is divided by the sum across all transactions and
        products for that industry in that year. Division by zero yields
        ``NaN``.
    use_products_coefficients : pd.DataFrame
        Same structure as ``use_products``. For each industry and year,
        every value is divided by the industry's total output (sum of P1
        transactions at basic prices). Values therefore express each
        product's contribution to the input coefficient. Division by zero
        yields ``NaN``.
    use_products_growth : pd.DataFrame
        Same structure as ``use_products``, with year-on-year growth:
        ``(current − previous) / previous``. The first id column is
        ``NaN`` throughout. Division by zero also yields ``NaN``.
    use_products_summary : pd.DataFrame
        Per-transaction summary statistics for P2 use, aggregated over
        products. Same structure as ``supply_products_summary`` but for P2
        transactions. Values are at purchasers' prices.
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
    display_unit: float | None = None
    rel_base: int = 100
    decimals: int = 1
    _all_rel: bool = field(default=False, repr=False)

    def _number_fmt(self):
        if self._all_rel:
            return _make_percentage_formatter(self.rel_base, self.decimals)
        return _make_number_formatter(self.display_unit, self.decimals)

    @property
    def balance(self) -> Styler:
        """Styled industry balance table for display in a Jupyter notebook."""
        if self._all_rel:
            fmt = _make_percentage_formatter(self.rel_base, self.decimals)
        else:
            fmt = None  # mixed: number for most rows, percentage for Input coefficient
        return _style_industry_balance_table(self.data.balance, self._p1_trans, format_func=fmt, display_unit=self.display_unit, rel_base=self.rel_base, decimals=self.decimals)

    @property
    def supply_products(self) -> Styler:
        """Styled product breakdown of industry output for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.supply_products,
            self._number_fmt(),
            "supply",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def supply_products_distribution(self) -> Styler:
        """Styled product-share distribution of industry output for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.supply_products_distribution,
            _make_percentage_formatter(self.rel_base, self.decimals),
            "supply",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def supply_products_growth(self) -> Styler:
        """Styled year-on-year growth of industry output detail for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.supply_products_growth,
            _make_percentage_formatter(self.rel_base, self.decimals),
            "supply",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def supply_products_summary(self) -> Styler:
        """Styled per-transaction supply summary statistics for display in a Jupyter notebook."""
        return _style_products_summary_table(
            self.data.supply_products_summary,
            "supply",
            self.display_unit,
            self.rel_base,
            all_rel=self._all_rel,
            decimals=self.decimals,
        )

    @property
    def use_products(self) -> Styler:
        """Styled product breakdown of industry input for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_products,
            self._number_fmt(),
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_products_distribution(self) -> Styler:
        """Styled product-share distribution of industry input for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_products_distribution,
            _make_percentage_formatter(self.rel_base, self.decimals),
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_products_coefficients(self) -> Styler:
        """Styled input coefficients by product for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_products_coefficients,
            _make_percentage_formatter(self.rel_base, self.decimals),
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_products_growth(self) -> Styler:
        """Styled year-on-year growth of industry input detail for display in a Jupyter notebook."""
        return _style_detail_table(
            self.data.use_products_growth,
            _make_percentage_formatter(self.rel_base, self.decimals),
            "use",
            outer_level="industry",
            outer_txt_level="industry_txt",
            inner_level="product",
            inner_txt_level="product_txt",
        )

    @property
    def use_products_summary(self) -> Styler:
        """Styled per-transaction use summary statistics for display in a Jupyter notebook."""
        return _style_products_summary_table(
            self.data.use_products_summary,
            "use",
            self.display_unit,
            self.rel_base,
            all_rel=self._all_rel,
            decimals=self.decimals,
        )

    @property
    def price_layers(self) -> Styler:
        """Styled price layer breakdown of industry input for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers,
            self._number_fmt(),
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def price_layers_rates(self) -> Styler:
        """Styled price layer rates for industry input for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers_rates,
            _make_percentage_formatter(self.rel_base, self.decimals),
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def price_layers_distribution(self) -> Styler:
        """Styled price layer distribution of industry input for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers_distribution,
            _make_percentage_formatter(self.rel_base, self.decimals),
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def price_layers_growth(self) -> Styler:
        """Styled year-on-year growth of price layers for display in a Jupyter notebook."""
        return _style_price_layers_table(
            self.data.price_layers_growth,
            _make_percentage_formatter(self.rel_base, self.decimals),
            outer_level="industry",
            outer_txt_level="industry_txt",
        )

    @property
    def balance_growth(self) -> Styler:
        """Styled year-on-year growth table for display in a Jupyter notebook.

        All values are formatted as percentages.
        """
        return _style_industry_balance_table(
            self.data.balance_growth, self._p1_trans, format_func=_make_percentage_formatter(self.rel_base, self.decimals)
        )

    def display_products_n_largest(self, n: int, id) -> "IndustryInspection":
        """Return a copy with supply/use product tables filtered to the n largest products.

        Within each ``(industry, transaction)`` block, keeps the ``n`` products
        with the largest values in the ``id`` year column. Total/derived rows
        (``transaction == ""``) are always kept. All non-products tables
        (``balance``, ``price_layers``, etc.) and summary tables are copied
        unchanged without recomputation.

        Parameters
        ----------
        n : int
            Number of largest products to keep per ``(industry, transaction)`` block.
        id : value
            Id value (e.g. year) whose column is used for ranking.

        Returns
        -------
        IndustryInspection
            New inspection with filtered products tables.
        """
        return _display_products_n_largest(self, n, id)

    def display_products_threshold_value(
        self, threshold: float, id
    ) -> "IndustryInspection":
        """Return a copy with supply/use product tables filtered by an absolute value threshold.

        Within each ``(industry, transaction)`` block, keeps products whose
        value in the ``id`` year column is greater than or equal to
        ``threshold``. Total/derived rows (``transaction == ""``) are always
        kept. All non-products tables and summary tables are copied unchanged.

        Parameters
        ----------
        threshold : float
            Minimum value (inclusive) in the ``id`` column for a product to
            be kept.
        id : value
            Id value (e.g. year) whose column is used for filtering.

        Returns
        -------
        IndustryInspection
            New inspection with filtered products tables.
        """
        return _display_products_threshold_value(self, threshold, id)

    def display_products_threshold_share(
        self, threshold: float, id
    ) -> "IndustryInspection":
        """Return a copy with supply/use product tables filtered by a share threshold.

        Within each ``(industry, transaction)`` block, keeps products whose
        share of the transaction total in the ``id`` year column is greater
        than or equal to ``threshold``. Shares are taken from
        ``supply_products_distribution`` / ``use_products_distribution``.
        Total/derived rows (``transaction == ""``) are always kept. All
        non-products tables and summary tables are copied unchanged.

        Parameters
        ----------
        threshold : float
            Minimum share (inclusive, in [0, 1]) in the ``id`` column for a
            product to be kept.
        id : value
            Id value (e.g. year) whose column is used for filtering.

        Returns
        -------
        IndustryInspection
            New inspection with filtered products tables.
        """
        return _display_products_threshold_share(self, threshold, id)

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

    def set_display_unit(self, display_unit: float | None) -> "IndustryInspection":
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

    def set_rel_base(self, rel_base: int) -> "IndustryInspection":
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

    def set_decimals(self, decimals: int) -> "IndustryInspection":
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
    ) -> "IndustryInspection":
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
        IndustryInspection
            A new inspection result with filtered tables.
        """
        return _display_index(self, values, level)

    @property
    def tables_description(self) -> Styler:
        """Styled table with ``name`` as index and a ``description`` column."""
        return _style_tables_description(self.data.tables_description)

    def inspect_tables_comparison(self, other: "IndustryInspection") -> TablesComparison:
        """Compare all tables in this inspection with another :class:`IndustryInspection`.

        Computes element-wise differences and relative changes between
        corresponding tables. Index alignment uses an outer join.

        Parameters
        ----------
        other : IndustryInspection
            The inspection result to compare against.

        Returns
        -------
        TablesComparison
            Contains ``.diff`` and ``.rel`` as :class:`IndustryInspection`
            instances.

        Raises
        ------
        TypeError
            If ``other`` is not a :class:`IndustryInspection`.
        """
        if not isinstance(other, IndustryInspection):
            raise TypeError(
                f"Expected IndustryInspection, got {type(other).__name__}."
            )
        diff_fields, rel_fields = _compute_comparison_table_fields(self.data, other.data)
        diff = IndustryInspection(
            data=IndustryInspectionData(**diff_fields),
            _p1_trans=self._p1_trans,
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            decimals=self.decimals,
        )
        rel = IndustryInspection(
            data=IndustryInspectionData(**rel_fields),
            _p1_trans=self._p1_trans,
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


def _keep_products_by_index(
    table: pd.DataFrame,
    keep_index: pd.Index,
) -> pd.DataFrame:
    """Return ``table`` keeping all total/derived rows plus product rows in ``keep_index``.

    Total/derived rows are identified by an empty ``transaction`` level value.
    ``keep_index`` should contain only product-row index tuples (i.e. those
    with non-empty ``transaction``).

    Parameters
    ----------
    table : pd.DataFrame
        A products table (``supply_products``, ``use_products``, or a
        derived variant) with a six-level MultiIndex whose ``transaction``
        level is ``""`` for total/derived rows and non-empty for product rows.
    keep_index : pd.Index
        MultiIndex of product rows to retain. Rows not in this index and not
        total rows are dropped.

    Returns
    -------
    pd.DataFrame
        Filtered table preserving original row order.
    """
    if table.empty:
        return table
    total_mask = table.index.get_level_values("transaction") == ""
    product_keep_mask = table.index.isin(keep_index)
    return table[total_mask | product_keep_mask]


def _apply_products_filter(
    inspection: IndustryInspection,
    supply_keep_index: pd.Index,
    use_keep_index: pd.Index,
) -> IndustryInspection:
    """Build a new IndustryInspection with filtered products tables.

    Applies ``supply_keep_index`` to all ``supply_products*`` tables and
    ``use_keep_index`` to all ``use_products*`` tables (except the summary
    tables, which have no product dimension and are copied unchanged).
    All other tables are copied as-is.

    Parameters
    ----------
    inspection : IndustryInspection
        Source inspection result.
    supply_keep_index : pd.Index
        Product-row index values to keep in supply tables.
    use_keep_index : pd.Index
        Product-row index values to keep in use tables.

    Returns
    -------
    IndustryInspection
        New inspection with filtered products tables.
    """
    d = inspection.data
    new_data = IndustryInspectionData(
        balance=d.balance,
        balance_growth=d.balance_growth,
        supply_products=_keep_products_by_index(d.supply_products, supply_keep_index),
        supply_products_distribution=_keep_products_by_index(
            d.supply_products_distribution, supply_keep_index
        ),
        supply_products_growth=_keep_products_by_index(
            d.supply_products_growth, supply_keep_index
        ),
        supply_products_summary=d.supply_products_summary,
        use_products=_keep_products_by_index(d.use_products, use_keep_index),
        use_products_distribution=_keep_products_by_index(
            d.use_products_distribution, use_keep_index
        ),
        use_products_coefficients=_keep_products_by_index(
            d.use_products_coefficients, use_keep_index
        ),
        use_products_growth=_keep_products_by_index(
            d.use_products_growth, use_keep_index
        ),
        use_products_summary=d.use_products_summary,
        price_layers=d.price_layers,
        price_layers_rates=d.price_layers_rates,
        price_layers_distribution=d.price_layers_distribution,
        price_layers_growth=d.price_layers_growth,
    )
    return IndustryInspection(data=new_data, _p1_trans=inspection._p1_trans, display_unit=inspection.display_unit, rel_base=inspection.rel_base)


def _n_largest_keep_index(products_table: pd.DataFrame, n: int, id_val) -> pd.Index:
    """Return the index of the n largest product rows per (industry, transaction) block.

    Rows with empty ``transaction`` (total/derived rows) are excluded from
    consideration — only product rows participate in ranking. Ties are broken
    arbitrarily (``method="first"``). NaN values rank last.

    Parameters
    ----------
    products_table : pd.DataFrame
        A products table with a six-level MultiIndex.
    n : int
        Number of largest products to keep per block.
    id_val
        Column label to rank by.

    Returns
    -------
    pd.Index
        MultiIndex containing the index tuples of product rows to keep.
    """
    if products_table.empty:
        return products_table.index[:0]
    product_mask = products_table.index.get_level_values("transaction") != ""
    product_rows = products_table[product_mask]
    if product_rows.empty:
        return product_rows.index[:0]
    ranks = product_rows.groupby(
        level=["industry", "transaction"], dropna=False
    )[id_val].rank(method="first", ascending=False, na_option="bottom")
    return product_rows.index[ranks <= n]


def _threshold_value_keep_index(
    products_table: pd.DataFrame, threshold: float, id_val
) -> pd.Index:
    """Return the index of product rows whose value in ``id_val`` >= ``threshold``.

    Parameters
    ----------
    products_table : pd.DataFrame
        A products table with a six-level MultiIndex.
    threshold : float
        Minimum value (inclusive).
    id_val
        Column label to filter by.

    Returns
    -------
    pd.Index
        MultiIndex containing the index tuples of product rows to keep.
    """
    if products_table.empty:
        return products_table.index[:0]
    product_mask = products_table.index.get_level_values("transaction") != ""
    product_rows = products_table[product_mask]
    if product_rows.empty:
        return product_rows.index[:0]
    return product_rows.index[product_rows[id_val] >= threshold]


def _threshold_share_keep_index(
    dist_table: pd.DataFrame, threshold: float, id_val
) -> pd.Index:
    """Return the index of product rows whose share in ``id_val`` >= ``threshold``.

    Shares are read from the distribution table (``supply_products_distribution``
    or ``use_products_distribution``).

    Parameters
    ----------
    dist_table : pd.DataFrame
        A products distribution table with a six-level MultiIndex.
    threshold : float
        Minimum share (inclusive, in [0, 1]).
    id_val
        Column label to filter by.

    Returns
    -------
    pd.Index
        MultiIndex containing the index tuples of product rows to keep.
    """
    if dist_table.empty:
        return dist_table.index[:0]
    product_mask = dist_table.index.get_level_values("transaction") != ""
    product_rows = dist_table[product_mask]
    if product_rows.empty:
        return product_rows.index[:0]
    return product_rows.index[product_rows[id_val] >= threshold]


def _display_products_n_largest(
    inspection: IndustryInspection, n: int, id_val
) -> IndustryInspection:
    """Filter supply/use products tables to the n largest products per block."""
    supply_keep = _n_largest_keep_index(inspection.data.supply_products, n, id_val)
    use_keep = _n_largest_keep_index(inspection.data.use_products, n, id_val)
    return _apply_products_filter(inspection, supply_keep, use_keep)


def _display_products_threshold_value(
    inspection: IndustryInspection, threshold: float, id_val
) -> IndustryInspection:
    """Filter supply/use products tables to products with value >= threshold."""
    supply_keep = _threshold_value_keep_index(
        inspection.data.supply_products, threshold, id_val
    )
    use_keep = _threshold_value_keep_index(
        inspection.data.use_products, threshold, id_val
    )
    return _apply_products_filter(inspection, supply_keep, use_keep)


def _display_products_threshold_share(
    inspection: IndustryInspection, threshold: float, id_val
) -> IndustryInspection:
    """Filter supply/use products tables to products with share >= threshold."""
    supply_keep = _threshold_share_keep_index(
        inspection.data.supply_products_distribution, threshold, id_val
    )
    use_keep = _threshold_share_keep_index(
        inspection.data.use_products_distribution, threshold, id_val
    )
    return _apply_products_filter(inspection, supply_keep, use_keep)


def inspect_industries(
    sut: SUT,
    industries: str | list[str],
    ids=None,
    sort_id=None,
    *,
    percentiles: list[float] = None,
    coverage_thresholds: list[float] = None,
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
    percentiles : list of float, optional
        Percentiles to include in ``supply_products_summary`` and
        ``use_products_summary``. Each value must be between 0.0 and 1.0.
        Special labels: ``0.0`` → ``"min"``, ``0.5`` → ``"median"``,
        ``1.0`` → ``"max"``; others → ``"p{int(p*100)}"``.
        Default: ``[0.5, 1.0]`` (median and max).
    coverage_thresholds : list of float, optional
        Coverage thresholds for the ``n_products_*`` rows in the summary
        tables. Each value must be between 0.0 and 1.0. A threshold of
        ``0.8`` produces an ``"n_products_p80"`` row containing the minimum
        number of products (sorted by value descending, per year) needed to
        account for 80% of the transaction total. Default: ``[0.8, 0.95]``.

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
    if percentiles is None:
        percentiles = [0.5, 1.0]
    if coverage_thresholds is None:
        coverage_thresholds = [0.5, 0.8, 0.95]

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

    supply_products = _build_industry_supply_products(
        sut=sut,
        matched_industries=matched_industries,
        p1_trans=p1_trans,
        trans_names=trans_names,
        industry_names=industry_names,
        product_names=product_names,
        all_ids=all_ids,
    )
    if sort_id is not None and not supply_products.empty:
        supply_products = _sort_by_id_value(supply_products, ["industry"], sort_id)
    supply_products_distribution = _build_supply_products_distribution(supply_products)
    supply_products_growth = _build_growth_table(supply_products)
    supply_products_summary = _build_products_summary(
        supply_products, percentiles, coverage_thresholds, total_label="total_supply"
    )

    use_products = _build_industry_use_products(
        sut=sut,
        matched_industries=matched_industries,
        p2_trans=p2_trans,
        trans_names=trans_names,
        industry_names=industry_names,
        product_names=product_names,
        all_ids=all_ids,
    )
    if sort_id is not None and not use_products.empty:
        use_products = _sort_by_id_value(use_products, ["industry"], sort_id)
    use_products_distribution = _build_use_products_distribution(use_products)
    use_products_summary = _build_products_summary(
        use_products, percentiles, coverage_thresholds, total_label="total_use"
    )
    use_products_coefficients = _build_use_products_coefficients(
        sut=sut,
        use_products=use_products,
        matched_industries=matched_industries,
        p1_trans=p1_trans,
        all_ids=all_ids,
    )
    use_products_growth = _build_growth_table(use_products)

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
        supply_products=supply_products,
        supply_products_distribution=supply_products_distribution,
        supply_products_growth=supply_products_growth,
        supply_products_summary=supply_products_summary,
        use_products=use_products,
        use_products_distribution=use_products_distribution,
        use_products_coefficients=use_products_coefficients,
        use_products_growth=use_products_growth,
        use_products_summary=use_products_summary,
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


def _build_industry_supply_products(
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


def _build_industry_use_products(
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


def _build_use_products_coefficients(
    sut: SUT,
    use_products: pd.DataFrame,
    matched_industries: list[str],
    p1_trans: list[str],
    all_ids: list,
) -> pd.DataFrame:
    """Build input-coefficient breakdown by product for the given industries.

    Each value in ``use_products`` is divided by the industry's total output
    (sum of all P1 transactions at basic prices) for that year. The result
    expresses each product's contribution to the industry's overall input
    coefficient. Division by zero yields ``NaN``.

    Parameters
    ----------
    sut : SUT
        The SUT collection (used to recompute total output per industry).
    use_products : pd.DataFrame
        Use detail table as produced by :func:`_build_industry_use_products`.
    matched_industries : list of str
        Industry codes in display order.
    p1_trans : list of str
        P1 transaction codes used to compute total output.
    all_ids : list
        Collection ids (years) — used as columns.
    """
    if use_products.empty:
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

    # Align denominators to every row of use_products.
    industry_vals = use_products.index.get_level_values("industry")
    # Industries missing from supply get NaN denominators, which propagates to NaN.
    denominators = safe_totals.reindex(industry_vals).values

    return pd.DataFrame(
        use_products.astype(float).values / denominators,
        index=use_products.index,
        columns=use_products.columns,
    )


def _build_use_products_distribution(use_products: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalised version of the industry use detail table.

    For each industry and year, every value is divided by the sum across all
    transactions and products for that industry in that year (the
    ``"Total use"`` denominator). Division by zero yields ``NaN``.
    """
    if use_products.empty:
        return pd.DataFrame()

    detail_float = use_products.astype(float)
    industry_vals = use_products.index.get_level_values("industry")

    non_summary_mask = use_products.index.get_level_values("transaction") != ""
    industry_totals = (
        detail_float[non_summary_mask]
        .groupby(level="industry", dropna=False)
        .sum()
    )
    safe_totals = industry_totals.replace(0, float("nan"))
    denominators = safe_totals.loc[industry_vals].values

    return pd.DataFrame(
        detail_float.values / denominators,
        index=use_products.index,
        columns=use_products.columns,
    )


def _build_supply_products_distribution(supply_products: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalised version of the industry supply detail table.

    For each industry and year, every value is divided by the sum across all
    transactions and products for that industry in that year (i.e. the
    "Total supply" denominator). Division by zero yields ``NaN``.
    """
    if supply_products.empty:
        return pd.DataFrame()

    detail_float = supply_products.astype(float)
    industry_vals = supply_products.index.get_level_values("industry")

    # Sum non-summary rows per industry in one groupby, then align to every row.
    non_summary_mask = supply_products.index.get_level_values("transaction") != ""
    industry_totals = (
        detail_float[non_summary_mask]
        .groupby(level="industry", dropna=False)
        .sum()
    )
    # Replace zero totals with NaN so division yields NaN rather than inf.
    safe_totals = industry_totals.replace(0, float("nan"))
    # Build a denominator array aligned to every row of supply_products.
    denominators = safe_totals.loc[industry_vals].values

    return pd.DataFrame(
        detail_float.values / denominators,
        index=supply_products.index,
        columns=supply_products.columns,
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


def _percentile_label(p: float) -> str:
    """Return the canonical display name for a percentile value.

    Parameters
    ----------
    p : float
        Percentile in [0, 1].

    Returns
    -------
    str
        ``"min"`` for 0.0, ``"median"`` for 0.5, ``"max"`` for 1.0,
        ``"p{int(p*100)}"`` for all other values.
    """
    if p == 0.0:
        return "min"
    if p == 0.5:
        return "median"
    if p == 1.0:
        return "max"
    return f"p{int(p * 100)}"


def _build_products_summary(
    products_table: pd.DataFrame,
    percentiles: list[float],
    coverage_thresholds: list[float],
    total_label: str = "total_supply",
) -> pd.DataFrame:
    """Build per-transaction summary statistics from a supply_products or use_products table.

    Aggregates over the product dimension within each
    ``(industry, transaction)`` group. Only non-zero product values
    contribute to n_products, percentiles, shares, and coverage counts.

    Parameters
    ----------
    products_table : pd.DataFrame
        Wide-format DataFrame with a six-level MultiIndex:
        ``(industry, industry_txt, transaction, transaction_txt, product,
        product_txt)``. Non-total rows have ``transaction != ""``.
    percentiles : list of float
        Percentile values in [0, 1] to compute for absolute values and
        shares. Labels follow :func:`_percentile_label`. Value and share
        rows appear in descending percentile order.
    coverage_thresholds : list of float
        Fraction-of-total thresholds in [0, 1]. For each threshold ``t``,
        the result contains an ``"n_products_{label}"`` row with the minimum
        number of products (sorted by value descending, per year) needed to
        reach ``t * total``. Coverage rows appear in ascending threshold order.
    total_label : str
        Label for the total row in the ``summary`` index level. Default
        ``"total_supply"``; pass ``"total_use"`` for use tables.

    Returns
    -------
    pd.DataFrame
        Wide-format summary table with a five-level MultiIndex:
        ``(industry, industry_txt, transaction, transaction_txt, summary)``.
        Columns match ``products_table.columns``. Empty when
        ``products_table`` is empty or contains no non-total rows.

        Row order within each ``(industry, transaction)`` block:

        1. ``total_label`` — sum of all products.
        2. ``n_products`` — count of non-zero products.
        3. ``n_products_{label}`` — one row per coverage threshold, ascending.
        4. ``value_{label}`` — one row per percentile, descending.
        5. ``share_{label}`` — one row per percentile, descending.
    """
    if products_table.empty:
        return pd.DataFrame()

    group_levels = ["industry", "industry_txt", "transaction", "transaction_txt"]
    id_cols = list(products_table.columns)

    # Non-total rows: transaction code is non-empty.
    product_mask = products_table.index.get_level_values("transaction") != ""
    product_rows = products_table[product_mask].astype(float)

    if product_rows.empty:
        return pd.DataFrame()

    # --- Vectorized aggregation ---

    # Group totals: sum of all product values per (group, year).
    totals_wide = product_rows.groupby(level=group_levels, dropna=False).sum()

    # n_products: count of non-zero values per (group, year).
    n_products_wide = (product_rows != 0).groupby(level=group_levels, dropna=False).sum()

    # Replace zeros with NaN so groupby quantile skips them.
    nonzero_values = product_rows.where(product_rows != 0)

    # Value percentiles over non-zero products.
    value_quantiles = {
        p: nonzero_values.groupby(level=group_levels, dropna=False).quantile(p)
        for p in percentiles
    }

    # Shares = value / group total. Align group totals to every product row.
    safe_totals = totals_wide.replace(0, float("nan"))
    group_keys = list(
        zip(*[product_rows.index.get_level_values(lv) for lv in group_levels])
    )
    denominators = safe_totals.loc[group_keys].values
    shares = pd.DataFrame(
        product_rows.values / denominators,
        index=product_rows.index,
        columns=id_cols,
    )
    nonzero_shares = shares.where(product_rows != 0)

    # Share percentiles over non-zero products.
    share_quantiles = {
        p: nonzero_shares.groupby(level=group_levels, dropna=False).quantile(p)
        for p in percentiles
    }

    # Coverage counts: for each threshold t, find the minimum number of
    # products (sorted by value descending, per year) whose cumulative sum
    # reaches >= t * total. Computed in a single melt+sort+cumsum pass.
    coverage_wide: dict[float, pd.DataFrame] = {}
    if coverage_thresholds:
        # Flatten to long format: (group, product, year) → value.
        flat = product_rows.reset_index()
        long = flat.melt(
            id_vars=group_levels + [products_table.index.names[4]],  # product col
            value_vars=id_cols,
            var_name="_year",
            value_name="_value",
        )
        # Drop product_txt by not including it — it was not in id_vars.
        long = long[long["_value"].notna() & (long["_value"] != 0)].copy()

        if not long.empty:
            group_key = group_levels + ["_year"]
            long = long.sort_values(
                group_key + ["_value"],
                ascending=[True] * len(group_key) + [False],
            )
            long["_cumsum"] = long.groupby(group_key, sort=False)["_value"].cumsum()
            long["_total"] = long.groupby(group_key, sort=False)["_value"].transform("sum")
            long["_rank"] = long.groupby(group_key, sort=False).cumcount() + 1

            for t in coverage_thresholds:
                covered = long[long["_cumsum"] >= t * long["_total"]]
                first = (
                    covered.groupby(group_key, sort=False)["_rank"]
                    .first()
                    .reset_index()
                )
                first.columns = group_levels + ["_year", "_count"]
                wide = first.pivot_table(
                    index=group_levels,
                    columns="_year",
                    values="_count",
                    aggfunc="first",
                )
                wide.columns.name = None
                for id_val in id_cols:
                    if id_val not in wide.columns:
                        wide[id_val] = float("nan")
                coverage_wide[t] = wide[id_cols]

    # --- Ordered assembly ---
    # Determine distinct (industry, transaction) groups in appearance order.
    seen: set = set()
    ordered_groups: list = []
    for idx_tuple in product_rows.index:
        key = (idx_tuple[0], idx_tuple[1], idx_tuple[2], idx_tuple[3])
        if key not in seen:
            seen.add(key)
            ordered_groups.append(key)

    # Summary row labels in the desired display order:
    # total, n_products, coverage (asc), value (desc), share (desc).
    sorted_thresholds = sorted(coverage_thresholds)
    sorted_percentiles_desc = sorted(percentiles, reverse=True)
    summary_labels = (
        [total_label, "n_products"]
        + [f"n_products_p{int(t * 100)}" for t in sorted_thresholds]
        + [f"value_{_percentile_label(p)}" for p in sorted_percentiles_desc]
        + [f"share_{_percentile_label(p)}" for p in sorted_percentiles_desc]
    )

    blocks = []
    for group in ordered_groups:
        industry, industry_txt, transaction, transaction_txt = group
        row_data = [
            totals_wide.loc[group].tolist(),
            n_products_wide.loc[group].tolist(),
        ]
        for t in sorted_thresholds:
            if t in coverage_wide and group in coverage_wide[t].index:
                row_data.append(coverage_wide[t].loc[group].tolist())
            else:
                row_data.append([float("nan")] * len(id_cols))
        for p in sorted_percentiles_desc:
            row_data.append(value_quantiles[p].loc[group].tolist())
        for p in sorted_percentiles_desc:
            row_data.append(share_quantiles[p].loc[group].tolist())

        row_labels = [
            (industry, industry_txt, transaction, transaction_txt, label)
            for label in summary_labels
        ]
        block = pd.DataFrame(
            row_data,
            index=pd.MultiIndex.from_tuples(
                row_labels, names=group_levels + ["summary"]
            ),
            columns=id_cols,
        )
        blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)
