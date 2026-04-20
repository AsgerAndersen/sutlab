"""
inspect_products: inspection tables for one or more products.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes, _natural_sort_key, filter_rows
from sutlab.derive import compute_price_layer_rates
from sutlab.inspect._shared import _build_growth_table, _sort_by_id_value, _write_inspection_to_excel
from sutlab.inspect._style import (
    _format_number,
    _format_percentage,
    _make_number_formatter,
    _make_percentage_formatter,
    _style_balance_table,
    _style_detail_table,
    _style_price_layers_table,
)
from sutlab.inspect._tables_comparison import TablesComparison, _compute_comparison_table_fields


# ESA code → attribute name on SUTClassifications for category label lookup.
# Transactions with ESA codes outside this mapping (P6, P7, P51g, P52, ...)
# are not expected to have category breakdowns.
_ESA_TO_CLASSIFICATION_ATTR: dict[str, str] = {
    "P1":  "industries",
    "P2":  "industries",
    "P31": "individual_consumption",
    "P32": "collective_consumption",
}


@dataclass
class ProductInspectionData:
    """Raw DataFrames underlying a :class:`ProductInspection`.

    Use these directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding properties on :class:`ProductInspection`,
    which return styled versions.
    """

    balance: pd.DataFrame
    supply_products: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_products_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    supply_products_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_products_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_distribution: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_layers_rates: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class ProductInspection:
    """
    Result of :func:`inspect_products`.

    Raw DataFrames are available under ``result.data``. The properties on
    this class return :class:`~pandas.io.formats.style.Styler` objects that
    render with European number formatting in Jupyter notebooks.

    Attributes
    ----------
    balance : pd.DataFrame
        Wide-format balance table. Rows have a four-level MultiIndex with
        names ``product``, ``product_txt``, ``transaction``,
        ``transaction_txt``:

        - ``product``: product code (e.g. ``"V10100"``).
        - ``product_txt``: product name from classifications, or ``""`` if
          no product classification is loaded.
        - ``transaction``: transaction code for data rows (e.g. ``"0100"``),
          or ``""`` for summary rows.
        - ``transaction_txt``: transaction name for data rows
          (e.g. ``"Output at basic prices"``), or ``"Total supply"``,
          ``"Total use"``, ``"Balance"`` for summary rows.

        Supply transactions appear first (values at basic prices), then
        ``"Price layers"`` (total intermediate price layers summed across all
        use rows for that product and year — the difference between
        purchasers' and basic prices), then ``"Total supply"`` (basic prices
        plus price layers, i.e. purchasers' prices), then use transactions
        (values at purchasers' prices), then ``"Total use"``, then
        ``"Balance"`` (Total supply minus Total use). All totals are at
        purchasers' prices. Columns are the collection ids (e.g. years).
        Missing cells are filled with ``0``.

    supply_products : pd.DataFrame
        Wide-format category breakdown for supply transactions. Rows have a
        six-level MultiIndex with names ``product``, ``product_txt``,
        ``transaction``, ``transaction_txt``, ``category``, ``category_txt``:

        - ``product``: product code.
        - ``product_txt``: product name from classifications, or ``""`` if
          no product classification is loaded.
        - ``transaction``: transaction code (e.g. ``"0100"``).
        - ``transaction_txt``: transaction name (e.g. ``"Output at basic
          prices"``).
        - ``category``: category code (e.g. industry code).
        - ``category_txt``: category name from the matching classification
          (``industries``, ``individual_consumption``, or
          ``collective_consumption``), determined via the ``esa_code`` column
          in the transaction classification. ``""`` if the classification is
          not loaded or the ESA code is not in the mapping.

        Only transactions where at least one selected product has non-empty
        categories are included. Products with no rows for a given transaction
        are omitted. Columns are the collection ids (e.g. years). Values are
        at basic prices. Missing cells are filled with ``0``.

    use_products : pd.DataFrame
        Same structure as ``supply_products``, for use-side transactions.
        Values are at purchasers' prices.

    balance_distribution : pd.DataFrame
        Same structure as ``balance``. Supply-side rows (up to and including
        ``"Total supply"``) are divided by ``"Total supply"`` for each year.
        Use-side rows (up to and including ``"Total use"``) are divided by
        ``"Total use"`` for each year. The ``"Balance"`` row is divided by
        ``"Total supply"``. Where the denominator is zero the result is
        ``NaN``.

    supply_products_distribution : pd.DataFrame
        Same structure as ``supply_products``. For each product and year, every
        value is divided by the sum across all transactions and categories for
        that product in that year. Values therefore express each category's
        share of total supply for the product in each year.

    use_products_distribution : pd.DataFrame
        Same structure as ``use_products``, with the same normalization as
        ``supply_products_distribution`` but relative to total use.

    balance_growth : pd.DataFrame
        Same structure as ``balance``. Each value is the change relative to
        the previous year: ``(current - previous) / previous``, so 5% growth
        is stored as ``0.05``. The first year column is ``NaN`` throughout.
        Division by zero also yields ``NaN``.

    supply_products_growth : pd.DataFrame
        Same structure as ``supply_products``, with the same year-on-year
        growth calculation as ``balance_growth``.

    use_products_growth : pd.DataFrame
        Same structure as ``use_products``, with the same year-on-year
        growth calculation as ``balance_growth``.

    price_layers : pd.DataFrame
        Wide-format price layer breakdown for use-side transactions. Rows
        have a five-level MultiIndex with names ``product``, ``product_txt``,
        ``price_layer``, ``transaction``, ``transaction_txt``:

        - ``product``: product code.
        - ``product_txt``: product name from classifications, or ``""`` if
          no product classification is loaded.
        - ``price_layer``: the actual column name of the price layer in the
          use DataFrame (e.g. ``"ava"``, ``"moms"``), in the order the
          columns appear in ``sut.use``. Only layers mapped to a non-``None``
          role in ``SUTColumns`` and present in ``sut.use`` are included.
        - ``transaction``: transaction code for data rows, or ``""`` for
          the Total row.
        - ``transaction_txt``: transaction name for data rows, or
          ``"Total"`` for the summary row.

        One block per ``(product, price_layer)`` combination. Within each
        block, only use transactions with at least one non-zero value for
        that layer are included, followed by a Total row summing across
        them. Columns are the collection ids. Empty DataFrame if no price
        layer columns are present.

    price_layers_distribution : pd.DataFrame
        Same structure as ``price_layers``. Within each
        ``(product, price_layer)`` block, every row is divided by the
        Total row for that year. The Total row itself becomes ``1.0``.
        Division by zero yields ``NaN``.

    price_layers_growth : pd.DataFrame
        Same structure as ``price_layers``, with the same year-on-year
        growth calculation as ``balance_growth``.

    price_layers_rates : pd.DataFrame
        Same structure as ``price_layers`` but without Total rows. Each value
        is divided by the cumulative price level just before that layer is
        added, computed within each transaction. Division by zero yields
        ``NaN``.
    """

    data: ProductInspectionData
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
        return _style_balance_table(self.data.balance, self._number_fmt())

    @property
    def supply_products(self) -> Styler:
        return _style_detail_table(self.data.supply_products, self._number_fmt(), "supply")

    @property
    def use_products(self) -> Styler:
        return _style_detail_table(self.data.use_products, self._number_fmt(), "use")

    @property
    def balance_distribution(self) -> Styler:
        return _style_balance_table(self.data.balance_distribution, _make_percentage_formatter(self.rel_base, self.decimals))

    @property
    def supply_products_distribution(self) -> Styler:
        return _style_detail_table(self.data.supply_products_distribution, _make_percentage_formatter(self.rel_base, self.decimals), "supply")

    @property
    def use_products_distribution(self) -> Styler:
        return _style_detail_table(self.data.use_products_distribution, _make_percentage_formatter(self.rel_base, self.decimals), "use")

    @property
    def balance_growth(self) -> Styler:
        return _style_balance_table(self.data.balance_growth, _make_percentage_formatter(self.rel_base, self.decimals))

    @property
    def supply_products_growth(self) -> Styler:
        return _style_detail_table(self.data.supply_products_growth, _make_percentage_formatter(self.rel_base, self.decimals), "supply")

    @property
    def use_products_growth(self) -> Styler:
        return _style_detail_table(self.data.use_products_growth, _make_percentage_formatter(self.rel_base, self.decimals), "use")

    @property
    def price_layers(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers, self._number_fmt())

    @property
    def price_layers_distribution(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers_distribution, _make_percentage_formatter(self.rel_base, self.decimals))

    @property
    def price_layers_growth(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers_growth, _make_percentage_formatter(self.rel_base, self.decimals))

    @property
    def price_layers_rates(self) -> Styler:
        return _style_price_layers_table(self.data.price_layers_rates, _make_percentage_formatter(self.rel_base, self.decimals))

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

    def set_display_unit(self, display_unit: float | None) -> "ProductInspection":
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

    def set_rel_base(self, rel_base: int) -> "ProductInspection":
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

    def set_decimals(self, decimals: int) -> "ProductInspection":
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

    def inspect_tables_comparison(self, other: "ProductInspection") -> TablesComparison:
        """Compare all tables in this inspection with another :class:`ProductInspection`.

        Computes element-wise differences and relative changes between
        corresponding tables. Index alignment uses an outer join: rows
        present in only one object contribute ``NaN`` on the missing side.

        Parameters
        ----------
        other : ProductInspection
            The inspection result to compare against.

        Returns
        -------
        TablesComparison
            Contains ``.diff`` and ``.rel`` as :class:`ProductInspection`
            instances. Access raw data via e.g. ``result.diff.data.balance``
            and styled views via ``result.diff.balance``.

        Raises
        ------
        TypeError
            If ``other`` is not a :class:`ProductInspection`.
        """
        if not isinstance(other, ProductInspection):
            raise TypeError(
                f"Expected ProductInspection, got {type(other).__name__}."
            )
        diff_fields, rel_fields = _compute_comparison_table_fields(self.data, other.data)
        diff = ProductInspection(
            data=ProductInspectionData(**diff_fields),
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            decimals=self.decimals,
        )
        rel = ProductInspection(
            data=ProductInspectionData(**rel_fields),
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


def inspect_products(
    sut: SUT,
    products: str | list[str],
    ids=None,
    sort_id=None,
) -> ProductInspection:
    """
    Return inspection tables for one or more products.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    products : str or list of str
        Product codes to include. Accepts the same pattern syntax as
        :func:`filter_rows`: exact codes, wildcards (``*``), ranges (``:``),
        and negation (``~``).
    ids : value, list of values, or range, optional
        Id values (e.g. years) to include as columns. When ``None`` (the
        default), all ids present in the collection are included. Accepts a
        single value (``ids=2021``), a list (``ids=[2019, 2020]``), or a
        range (``ids=range(2015, 2022)``). The column order follows the
        sorted order of the full collection, not the order of the argument.
    sort_id : value, optional
        When set, rows within each product (or product/price-layer) block are
        sorted by their value in this id's column, largest first. Balance
        tables are not sorted. Supply/use detail tables are sorted within
        each product block. Price layer tables are sorted within each
        ``(product, price_layer)`` block. Total and summary rows always stay
        fixed at the end of their block. Must be one of the ids present in
        the collection after applying the ``ids`` filter.

    Returns
    -------
    ProductInspection
        A dataclass with 13 inspection tables. Raw DataFrames are available
        under ``result.data``; the same-named properties on the returned
        object give styled versions for Jupyter display. See
        :class:`ProductInspection` for field descriptions.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.metadata.classifications`` or
        ``sut.metadata.classifications.transactions`` is ``None`` — required
        to look up transaction names.
    ValueError
        If ``sut.metadata.classifications.transactions`` does not have a
        ``name`` column.
    ValueError
        If any value in ``ids`` is not found in the collection.
    ValueError
        If ``sort_id`` is not found in the collection ids (after applying the
        ``ids`` filter).
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call inspect_products. "
            "Provide a SUTMetadata with column name mappings."
        )
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            "sut.metadata.classifications.transactions is required to call "
            "inspect_products. Load a classifications file with a "
            "'transactions' sheet."
        )

    trans_df = sut.metadata.classifications.transactions
    cols = sut.metadata.columns

    trans_txt_col = f"{cols.transaction}_txt"
    if trans_txt_col not in trans_df.columns:
        raise ValueError(
            f"sut.metadata.classifications.transactions must have a '{trans_txt_col}' column."
        )

    # Resolve product patterns to concrete codes
    if isinstance(products, str):
        patterns = [products]
    else:
        patterns = list(products)

    supply_codes = sut.supply[cols.product].dropna().unique().tolist()
    use_codes = sut.use[cols.product].dropna().unique().tolist()
    all_codes = sorted(set(supply_codes) | set(use_codes), key=_natural_sort_key)
    matched_products = _match_codes(all_codes, patterns)

    # All ids, sorted — shared by all table builders so tables have consistent columns
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

    # Transaction name lookup: code → name
    trans_names = dict(zip(
        trans_df[cols.transaction].astype(str),
        trans_df[trans_txt_col].astype(str),
    ))

    # Product name lookup: code → name, empty string if not available
    prod_txt_col = f"{cols.product}_txt"
    products_df = sut.metadata.classifications.products
    if products_df is not None and prod_txt_col in products_df.columns:
        product_names = dict(zip(
            products_df[cols.product].astype(str),
            products_df[prod_txt_col].astype(str),
        ))
    else:
        product_names = {}

    # Category name lookup per transaction: {trans_code: {cat_code: cat_name}}
    # Uses esa_code on each transaction to find the right classification table.
    category_names_by_trans = _build_category_names_by_trans(
        trans_df, sut.metadata.classifications, cols
    )

    balance = _build_balance_table(
        sut, matched_products, trans_names, product_names, all_ids
    )
    supply_products = _append_detail_total(
        _build_detail_df(
            sut.supply, matched_products, product_names,
            trans_names, category_names_by_trans, cols, all_ids,
            price_col=cols.price_basic,
        ).sort_index(),
        all_ids,
        total_label="Total supply",
    )
    if sort_id is not None:
        supply_products = _sort_by_id_value(supply_products, ["product"], sort_id)
    use_products = _append_detail_total(
        _build_detail_df(
            sut.use, matched_products, product_names,
            trans_names, category_names_by_trans, cols, all_ids,
            price_col=cols.price_purchasers,
        ).sort_index(),
        all_ids,
        total_label="Total use",
    )
    if sort_id is not None:
        use_products = _sort_by_id_value(use_products, ["product"], sort_id)
    balance_distribution = _build_balance_distribution(balance)
    supply_products_distribution = _build_detail_distribution(supply_products)
    use_products_distribution = _build_detail_distribution(use_products)
    balance_growth = _build_growth_table(balance)
    if "transaction_txt" in balance_growth.index.names:
        _balance_mask = balance_growth.index.get_level_values("transaction_txt") == "Balance"
        balance_growth = balance_growth[~_balance_mask]
    supply_products_growth = _build_growth_table(supply_products)
    use_products_growth = _build_growth_table(use_products)
    price_layers = _build_price_layers_table(
        sut, matched_products, trans_names, product_names, all_ids
    )
    if sort_id is not None:
        price_layers = _sort_by_id_value(price_layers, ["product", "price_layer"], sort_id)
    price_layers_distribution = _build_price_layers_distribution(price_layers)
    price_layers_growth = _build_growth_table(price_layers)

    # Compute filtered SUT and price layer rates.
    if not price_layers.empty:
        filtered_sut = filter_rows(sut, products=matched_products)
        trans_rates = compute_price_layer_rates(filtered_sut, ["product", "transaction"])
    else:
        trans_rates = pd.DataFrame()

    price_layers_rates = _build_price_layers_rates(
        price_layers, sut, all_ids, trans_rates
    )
    if sort_id is not None:
        price_layers_rates = _sort_by_id_value(
            price_layers_rates, ["product", "price_layer"], sort_id
        )

    data = ProductInspectionData(
        balance=balance,
        supply_products=supply_products,
        use_products=use_products,
        balance_distribution=balance_distribution,
        supply_products_distribution=supply_products_distribution,
        use_products_distribution=use_products_distribution,
        balance_growth=balance_growth,
        supply_products_growth=supply_products_growth,
        use_products_growth=use_products_growth,
        price_layers=price_layers,
        price_layers_distribution=price_layers_distribution,
        price_layers_growth=price_layers_growth,
        price_layers_rates=price_layers_rates,
    )
    return ProductInspection(data=data)


def _build_category_names_by_trans(
    trans_df: pd.DataFrame,
    classifications,
    cols,
) -> dict[str, dict[str, str]]:
    """Return {trans_code: {cat_code: cat_name}} for category label lookup.

    Uses the ``esa_code`` column in ``trans_df`` to determine which
    classification table provides category names for each transaction.
    Returns an empty inner dict for transactions whose ESA code is not in
    ``_ESA_TO_CLASSIFICATION_ATTR``, or whose matching classification table
    is not loaded or has no category label column.
    """
    if classifications is None or "esa_code" not in trans_df.columns:
        return {}

    cat_txt_col = f"{cols.category}_txt"

    # Build one category-name dict per ESA code upfront, then assign per transaction.
    cat_name_dicts: dict[str, dict[str, str]] = {}
    for esa_code, cls_attr in _ESA_TO_CLASSIFICATION_ATTR.items():
        cls_df = getattr(classifications, cls_attr, None)
        if cls_df is not None and cat_txt_col in cls_df.columns:
            cat_name_dicts[esa_code] = dict(zip(
                cls_df[cols.category].astype(str),
                cls_df[cat_txt_col].astype(str),
            ))
        else:
            cat_name_dicts[esa_code] = {}

    return {
        str(trans): cat_name_dicts.get(str(esa), {})
        for trans, esa in zip(trans_df[cols.transaction], trans_df["esa_code"])
    }


def _build_balance_table(
    sut: SUT,
    matched_products: list[str],
    trans_names: dict[str, str],
    product_names: dict[str, str],
    all_ids: list,
) -> pd.DataFrame:
    """Build the wide-format balance table for the given products."""
    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    bas_col = cols.price_basic
    purch_col = cols.price_purchasers

    # Filter to matched products before aggregating — avoids groupby on the full table.
    supply_selected = sut.supply[sut.supply[prod_col].isin(matched_products)]
    use_selected = sut.use[sut.use[prod_col].isin(matched_products)]

    # Aggregate supply to (product, transaction, id) → sum of price_basic
    supply_agg = (
        supply_selected
        .groupby([prod_col, trans_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
    )
    # Aggregate use to (product, transaction, id) → sum of price_purchasers
    use_agg_purch = (
        use_selected
        .groupby([prod_col, trans_col, id_col], as_index=False, dropna=False)[purch_col]
        .sum()
    )
    # Aggregate use to (product, id) → sum of (price_purchasers - price_basic).
    # Used to build the "Price layers" row on the supply side.
    use_layers_agg = (
        use_selected
        .assign(_layers=use_selected[purch_col] - use_selected[bas_col])
        .groupby([prod_col, id_col], as_index=False, dropna=False)["_layers"]
        .sum()
    )

    blocks = []

    for product in matched_products:
        product_txt = product_names.get(product, "")

        # --- Supply side for this product ---
        prod_supply_agg = supply_agg[supply_agg[prod_col] == product]

        if not prod_supply_agg.empty:
            prod_supply_wide = prod_supply_agg.pivot_table(
                index=trans_col,
                columns=id_col,
                values=bas_col,
                aggfunc="sum",
                fill_value=0,
            )
            prod_supply_wide.columns.name = None
            for id_val in all_ids:
                if id_val not in prod_supply_wide.columns:
                    prod_supply_wide[id_val] = 0
            prod_supply_wide = prod_supply_wide[all_ids]
            supply_trans = sorted(prod_supply_wide.index.tolist(), key=_natural_sort_key)
        else:
            prod_supply_wide = pd.DataFrame(columns=all_ids)
            supply_trans = []

        # --- Use side for this product ---
        prod_use_agg = use_agg_purch[use_agg_purch[prod_col] == product]

        if not prod_use_agg.empty:
            prod_use_wide = prod_use_agg.pivot_table(
                index=trans_col,
                columns=id_col,
                values=purch_col,
                aggfunc="sum",
                fill_value=0,
            )
            prod_use_wide.columns.name = None
            for id_val in all_ids:
                if id_val not in prod_use_wide.columns:
                    prod_use_wide[id_val] = 0
            prod_use_wide = prod_use_wide[all_ids]
            use_trans = sorted(prod_use_wide.index.tolist(), key=_natural_sort_key)
        else:
            prod_use_wide = pd.DataFrame(columns=all_ids)
            use_trans = []

        # --- Assemble rows for this product ---
        # Each row label is a 4-tuple: (product, product_txt, transaction, transaction_txt)
        # Summary rows use "" for transaction and the summary label for transaction_txt.
        row_labels = []
        row_data = []

        for trans in supply_trans:
            trans_txt = trans_names.get(trans, trans)
            row_labels.append((product, product_txt, trans, trans_txt))
            row_data.append(prod_supply_wide.loc[trans, all_ids].tolist())

        # "Price layers" — total intermediate price layers from use side
        # (purchasers' minus basic across all use rows for this product).
        prod_layers_agg = use_layers_agg[use_layers_agg[prod_col] == product]
        if not prod_layers_agg.empty:
            layers_by_id = prod_layers_agg.set_index(id_col)["_layers"]
            price_layers_total = layers_by_id.reindex(all_ids, fill_value=0.0)
        else:
            price_layers_total = pd.Series(0.0, index=all_ids)
        row_labels.append((product, product_txt, "", "Price layers"))
        row_data.append(price_layers_total.tolist())

        row_labels.append((product, product_txt, "", "Total supply"))
        if supply_trans:
            supply_basic_total = prod_supply_wide.loc[supply_trans, all_ids].sum()
        else:
            supply_basic_total = pd.Series(0.0, index=all_ids)
        total_supply = supply_basic_total + price_layers_total
        row_data.append(total_supply.tolist())

        for trans in use_trans:
            trans_txt = trans_names.get(trans, trans)
            row_labels.append((product, product_txt, trans, trans_txt))
            row_data.append(prod_use_wide.loc[trans, all_ids].tolist())

        row_labels.append((product, product_txt, "", "Total use"))
        if use_trans:
            total_use = prod_use_wide.loc[use_trans, all_ids].sum()
        else:
            total_use = pd.Series(0.0, index=all_ids)
        row_data.append(total_use.tolist())

        row_labels.append((product, product_txt, "", "Balance"))
        row_data.append((total_supply - total_use).tolist())

        block = pd.DataFrame(
            row_data,
            index=pd.MultiIndex.from_tuples(
                row_labels,
                names=["product", "product_txt", "transaction", "transaction_txt"],
            ),
            columns=all_ids,
        )
        blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)


def _append_detail_total(df: pd.DataFrame, all_ids: list, total_label: str) -> pd.DataFrame:
    """Append a total row at the bottom of each product block.

    ``total_label`` becomes the ``transaction_txt`` value of the summary row
    (e.g. ``"Total supply"`` or ``"Total use"``). The row sums all
    transactions and categories for that product and year. Called after
    ``sort_index()``.
    """
    if df.empty:
        return df

    product_vals = df.index.get_level_values("product")
    product_txt_vals = df.index.get_level_values("product_txt")
    ordered_products = list(dict.fromkeys(product_vals))
    blocks = []

    for product in ordered_products:
        product_mask = product_vals == product
        block_rows = df[product_mask]
        product_txt = product_txt_vals[product_mask][0]
        total_values = block_rows[all_ids].sum()
        total_index = pd.MultiIndex.from_tuples(
            [(product, product_txt, "", total_label, "", "")],
            names=df.index.names,
        )
        total_row = pd.DataFrame([total_values.tolist()], index=total_index, columns=all_ids)
        blocks.append(pd.concat([block_rows, total_row]))

    return pd.concat(blocks)


def _build_detail_df(
    df: pd.DataFrame,
    matched_products: list[str],
    product_names: dict[str, str],
    trans_names: dict[str, str],
    category_names_by_trans: dict[str, dict[str, str]],
    cols,
    all_ids: list,
    price_col: str,
) -> pd.DataFrame:
    """Build a category-breakdown DataFrame for one side (supply or use).

    Returns a single DataFrame with a six-level MultiIndex:
    (product, product_txt, transaction, transaction_txt, category, category_txt).
    Transactions with category breakdowns show one row per category.
    Transactions with no categories appear as a single row with category="".
    Products with no rows for a given transaction are omitted.
    """
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction
    cat_col = cols.category
    bas_col = price_col

    df_selected = df[df[prod_col].isin(matched_products)]

    if df_selected.empty:
        return pd.DataFrame()

    trans_codes = sorted(
        df_selected[trans_col].unique().tolist(), key=_natural_sort_key
    )

    # Compute which transactions have non-empty category breakdowns.
    # For those, only aggregate non-empty-category rows; for the rest, aggregate all rows.
    non_empty_cat_mask = df_selected[cat_col].notna() & (df_selected[cat_col] != "")
    trans_with_cats = set(df_selected.loc[non_empty_cat_mask, trans_col].unique())

    # One upfront aggregation: include non-empty-category rows for transactions that
    # have them, and all rows for transactions that don't.
    rows_for_agg = df_selected[
        non_empty_cat_mask | ~df_selected[trans_col].isin(trans_with_cats)
    ]
    agg_all = (
        rows_for_agg
        .groupby([prod_col, trans_col, cat_col, id_col], as_index=False, dropna=False)[bas_col]
        .sum()
    )

    if agg_all.empty:
        return pd.DataFrame()

    # One pivot for all (product, transaction, category) × ids — avoids one pivot_table
    # call per (transaction, product) pair.
    wide_all = agg_all.pivot_table(
        index=[prod_col, trans_col, cat_col],
        columns=id_col,
        values=bas_col,
        aggfunc="sum",
        fill_value=0,
    )
    wide_all.columns.name = None
    for id_val in all_ids:
        if id_val not in wide_all.columns:
            wide_all[id_val] = 0
    wide_all = wide_all[all_ids]

    # Pre-group by (product, transaction) so the inner loop is a plain dict lookup.
    wide_by_prod_trans = {
        (prod, trans): grp.droplevel([prod_col, trans_col])
        for (prod, trans), grp in wide_all.groupby(level=[prod_col, trans_col], sort=False)
    }

    row_labels = []
    row_data = []

    for trans_code in trans_codes:
        trans_txt = trans_names.get(trans_code, trans_code)
        cat_name_lookup = category_names_by_trans.get(trans_code, {})

        for product in matched_products:
            wide = wide_by_prod_trans.get((product, trans_code))
            if wide is None:
                continue

            product_txt = product_names.get(product, "")
            categories = sorted(wide.index.tolist(), key=_natural_sort_key)

            for cat in categories:
                cat_txt = cat_name_lookup.get(cat, "")
                row_labels.append((product, product_txt, trans_code, trans_txt, cat, cat_txt))
                row_data.append(wide.loc[cat].tolist())


    if not row_labels:
        return pd.DataFrame()

    return pd.DataFrame(
        row_data,
        index=pd.MultiIndex.from_tuples(
            row_labels,
            names=["product", "product_txt", "transaction", "transaction_txt",
                   "category", "category_txt"],
        ),
        columns=all_ids,
    )


def _build_balance_distribution(balance: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalized version of the balance table.

    Within each product block, supply-side rows (up to and including
    "Total supply") are divided by "Total supply" per year. Use-side rows
    (up to and including "Total use") are divided by "Total use" per year.
    The "Balance" row is excluded — it is not meaningful as a share.
    Division by zero yields NaN.
    """
    if balance.empty:
        return pd.DataFrame()

    dist = balance.copy().astype(float)
    product_vals = balance.index.get_level_values("product")
    trans_txt_vals = balance.index.get_level_values("transaction_txt")

    for product in product_vals.unique():
        abs_positions = (product_vals == product).nonzero()[0]
        block_txts = trans_txt_vals[abs_positions]

        total_supply_pos = block_txts.tolist().index("Total supply")
        total_use_pos = block_txts.tolist().index("Total use")

        total_supply = balance.iloc[abs_positions[total_supply_pos]].astype(float)
        total_use = balance.iloc[abs_positions[total_use_pos]].astype(float)

        # Divide the supply block (up to and including "Total supply") at once.
        supply_slice = abs_positions[:total_supply_pos + 1]
        dist.iloc[supply_slice] = balance.iloc[supply_slice].astype(float).div(total_supply).values

        # Divide the use block (up to and including "Total use") at once.
        use_slice = abs_positions[total_supply_pos + 1:total_use_pos + 1]
        dist.iloc[use_slice] = balance.iloc[use_slice].astype(float).div(total_use).values

    balance_mask = trans_txt_vals == "Balance"
    return dist[~balance_mask]


def _get_price_layer_columns(cols, use_df: pd.DataFrame) -> list[str]:
    """Return intermediate price layer column names in use DataFrame column order.

    Considers only the optional roles on ``SUTColumns`` between ``price_basic``
    and ``price_purchasers`` (trade_margins, wholesale_margins, retail_margins,
    transport_margins, product_taxes, product_subsidies,
    product_taxes_less_subsidies, vat). Returns only those that are both
    mapped (not ``None``) and present as actual columns in ``use_df``.
    """
    optional_layer_cols = {
        cols.trade_margins,
        cols.wholesale_margins,
        cols.retail_margins,
        cols.transport_margins,
        cols.product_taxes,
        cols.product_subsidies,
        cols.product_taxes_less_subsidies,
        cols.vat,
    }
    layer_cols_set = {col for col in optional_layer_cols if col is not None}
    return [col for col in use_df.columns if col in layer_cols_set]


def _build_price_layers_table(
    sut,
    matched_products: list[str],
    trans_names: dict[str, str],
    product_names: dict[str, str],
    all_ids: list,
) -> pd.DataFrame:
    """Build the price layers table for the given products.

    Returns a DataFrame with a five-level MultiIndex:
    (product, product_txt, price_layer, transaction, transaction_txt).
    Columns are the collection ids. One block per (product, price_layer)
    combination: one row per use transaction that has non-zero layer values
    across any id, plus a Total row summing across those transactions.
    Price layer blocks follow the column order in ``sut.use``.
    """
    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction

    layer_cols = _get_price_layer_columns(cols, sut.use)
    if not layer_cols:
        return pd.DataFrame()

    # Pre-aggregate per layer before the product loop: N_layers groupbys instead of
    # N_products × N_layers. Filter to matched products once upfront.
    use_selected = sut.use[sut.use[prod_col].isin(matched_products)]
    layer_aggs: dict[str, pd.DataFrame] = {}
    for layer_col in layer_cols:
        layer_data = use_selected[use_selected[layer_col].notna()]
        if not layer_data.empty:
            layer_aggs[layer_col] = (
                layer_data
                .groupby([prod_col, trans_col, id_col], as_index=False, dropna=False)[layer_col]
                .sum()
            )

    blocks = []

    for product in matched_products:
        product_txt = product_names.get(product, "")

        for layer_col in layer_cols:
            if layer_col not in layer_aggs:
                continue

            prod_agg = layer_aggs[layer_col]
            prod_agg = prod_agg[prod_agg[prod_col] == product]

            if prod_agg.empty:
                continue

            # Pivot to wide: transactions as rows, ids as columns
            wide = prod_agg.pivot_table(
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

            # Drop transactions that are all zero across all ids
            non_zero_mask = (wide != 0).any(axis=1)
            wide = wide[non_zero_mask]

            if wide.empty:
                continue

            use_trans = sorted(wide.index.tolist(), key=_natural_sort_key)

            row_labels = []
            row_data = []

            for trans in use_trans:
                trans_txt = trans_names.get(trans, trans)
                row_labels.append((product, product_txt, layer_col, trans, trans_txt))
                row_data.append(wide.loc[trans, all_ids].tolist())

            # Total row sums across all transactions for this (product, layer)
            total = wide.loc[use_trans].sum()
            row_labels.append((product, product_txt, layer_col, "", "Total"))
            row_data.append(total.tolist())

            block = pd.DataFrame(
                row_data,
                index=pd.MultiIndex.from_tuples(
                    row_labels,
                    names=["product", "product_txt", "price_layer",
                           "transaction", "transaction_txt"],
                ),
                columns=all_ids,
            )
            blocks.append(block)

    if not blocks:
        return pd.DataFrame()

    return pd.concat(blocks)


def _build_price_layers_rates(
    price_layers: pd.DataFrame,
    sut,
    all_ids: list,
    trans_rates: pd.DataFrame,
) -> pd.DataFrame:
    """Build price layer rates with the same structure as price_layers.

    Transaction rows use rates computed within each transaction: each layer
    is divided by the cumulative price for that transaction up to (not
    including) that layer. Total rows use product-level rates: the summed
    layer is divided by the product-wide cumulative.

    ``trans_rates`` must be the output of
    :func:`~sutlab.derive.compute_price_layer_rates` at
    ``aggregation_level="transaction"``, pre-filtered to the relevant products.
    """
    if price_layers.empty:
        return pd.DataFrame()

    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    trans_col = cols.transaction

    # Total rows are excluded — a summed rate across transactions is not
    # meaningful at the transaction level.
    non_total_mask = price_layers.index.get_level_values("transaction") != ""
    price_layers_trans = price_layers[non_total_mask]

    if price_layers_trans.empty:
        return pd.DataFrame()

    if trans_rates.empty:
        return pd.DataFrame()

    # Build lookup: (product, transaction, layer_col) → list of rates aligned to all_ids.
    # Single pivot_table + single reindex replaces N_groups × N_layers set_index/reindex calls.
    # pivot_table produces MultiIndex columns (layer_col, id_val); reindex aligns all_ids at once.
    # numpy row extraction then fills the dict without per-row pandas overhead.
    nan_row = [float("nan")] * len(all_ids)
    layer_cols_in_rates = [
        c for c in trans_rates.columns if c not in [prod_col, trans_col, id_col]
    ]
    trans_wide = trans_rates.pivot_table(
        index=[prod_col, trans_col],
        columns=id_col,
        values=layer_cols_in_rates,
        aggfunc="sum",
    )
    trans_wide = trans_wide.reindex(columns=all_ids, level=id_col, fill_value=float("nan"))
    layer_col_positions: dict[str, list[int]] = {}
    for j, (layer_name, _) in enumerate(trans_wide.columns.tolist()):
        if layer_name not in layer_col_positions:
            layer_col_positions[layer_name] = []
        layer_col_positions[layer_name].append(j)
    values_2d = trans_wide.to_numpy()
    index_list = trans_wide.index.tolist()
    trans_lookup: dict[tuple, list] = {}
    for i, (prod, trans) in enumerate(index_list):
        row = values_2d[i]
        for layer_col_name, positions in layer_col_positions.items():
            trans_lookup[(prod, trans, layer_col_name)] = row[positions].tolist()

    product_vals = price_layers_trans.index.get_level_values("product")
    layer_vals = price_layers_trans.index.get_level_values("price_layer")
    trans_vals = price_layers_trans.index.get_level_values("transaction")

    rates_rows = [
        trans_lookup.get((product, transaction, layer_col), nan_row)
        for product, layer_col, transaction in zip(product_vals, layer_vals, trans_vals)
    ]
    return pd.DataFrame(rates_rows, index=price_layers_trans.index, columns=all_ids)


def _build_price_layers_distribution(price_layers: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalised version of the price layers table.

    Within each (product, price_layer) block, every row is divided by the
    Total row for that year. The Total row itself becomes 1.0 (100%).
    Division by zero yields NaN.
    """
    if price_layers.empty:
        return pd.DataFrame()

    dist = price_layers.copy().astype(float)
    product_vals = price_layers.index.get_level_values("product")
    layer_vals = price_layers.index.get_level_values("price_layer")
    trans_txt_vals = price_layers.index.get_level_values("transaction_txt")

    for product in list(dict.fromkeys(product_vals)):
        prod_positions = (product_vals == product).nonzero()[0]
        prod_layers = list(dict.fromkeys(layer_vals[prod_positions]))

        for layer in prod_layers:
            block_positions = prod_positions[layer_vals[prod_positions] == layer]
            block_txts = trans_txt_vals[block_positions]

            total_pos = block_txts.tolist().index("Total")
            total_row = price_layers.iloc[block_positions[total_pos]].astype(float)

            # Divide the entire block at once instead of row by row.
            dist.iloc[block_positions] = (
                price_layers.iloc[block_positions].astype(float).div(total_row).values
            )

    return dist


def _build_detail_distribution(detail: pd.DataFrame) -> pd.DataFrame:
    """Build column-wise normalized version of a detail table.

    For each product, values in each year column are divided by the sum
    across all transactions and categories for that product in that year.
    Division by zero yields NaN.
    """
    if detail.empty:
        return pd.DataFrame()

    detail_float = detail.astype(float)
    product_vals = detail.index.get_level_values("product")

    # Sum non-summary rows per product in one groupby, then align to every row.
    non_summary_mask = detail.index.get_level_values("transaction") != ""
    product_totals = (
        detail_float[non_summary_mask]
        .groupby(level="product", dropna=False)
        .sum()
    )
    # Replace zero totals with NaN so division yields NaN rather than a warning.
    safe_totals = product_totals.replace(0, float("nan"))
    # Build a denominator array aligned to all rows of detail.
    denominators = safe_totals.loc[product_vals].values

    dist = pd.DataFrame(
        detail_float.values / denominators,
        index=detail.index,
        columns=detail.columns,
    )
    return dist
