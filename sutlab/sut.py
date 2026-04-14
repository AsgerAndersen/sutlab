"""
Core data structures for supply and use tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal

if TYPE_CHECKING:
    from sutlab.inspect import ProductInspection, IndustryInspection, FinalUseInspection, UnbalancedProductsInspection, UnbalancedTargetsInspection, SUTComparisonInspection

import pandas as pd


@dataclass
class SUTColumns:
    """
    Mapping from conceptual roles to actual column names in the DataFrames.

    The DataFrames in a :class:`SUT` keep whatever column names they were
    loaded with. This dataclass tells the library which column holds which
    piece of information.

    Each field holds the actual column name string (e.g. ``'nrnr'``) for
    that conceptual role, or ``None`` if that price layer is not present in
    the data. Required roles have no default; optional roles default to
    ``None``.

    This dataclass is typically loaded from a two-column Excel table with
    columns ``column`` (the actual column name) and ``role`` (the conceptual
    role from the fixed list below) via the I/O module.

    Parameters
    ----------
    id : str
        Column name for the identifier that distinguishes individual SUTs
        within the collection (e.g. ``'year'`` or ``'quarter'``).
    product : str
        Column name for the product dimension (e.g. ``'nrnr'``).
    transaction : str
        Column name for the transaction code (e.g. ``'trans'``).
    category : str
        Column name for the second dimension of the SUT matrix — identifies
        the industry (for production and intermediate use), the consumption
        function (for final demand), or similar. Empty for imports, exports,
        and investment rows (e.g. ``'brch'``).
    price_basic : str
        Column name for values at basic prices (e.g. ``'bas'``).
    price_purchasers : str
        Column name for values at purchasers' prices (e.g. ``'koeb'``).
        Purchasers' prices equal basic prices plus all price layers.
    trade_margins : str or None
        Column name for total trade margins, when not decomposed into
        wholesale and retail (e.g. ``'mar'``).
    wholesale_margins : str or None
        Column name for wholesale trade margins (e.g. ``'eng'``).
    retail_margins : str or None
        Column name for retail trade margins (e.g. ``'det'``).
    transport_margins : str or None
        Column name for transport margins, if present.
    product_taxes : str or None
        Column name for taxes on products excluding VAT (e.g. ``'afg'``).
    product_subsidies : str or None
        Column name for subsidies on products, if recorded separately.
    product_taxes_less_subsidies : str or None
        Column name for taxes less subsidies on products, if recorded net
        rather than split into taxes and subsidies.
    vat : str or None
        Column name for VAT (e.g. ``'moms'``).
    """

    id: str
    product: str
    transaction: str
    category: str
    price_basic: str
    price_purchasers: str
    trade_margins: str | None = None
    wholesale_margins: str | None = None
    retail_margins: str | None = None
    transport_margins: str | None = None
    product_taxes: str | None = None
    product_subsidies: str | None = None
    product_taxes_less_subsidies: str | None = None
    vat: str | None = None


@dataclass
class SUTClassifications:
    """
    Classification tables for the dimensions of a SUT.

    All fields are optional. Functions that require a specific table will
    raise an informative error if it is not supplied.

    Parameters
    ----------
    classification_names : DataFrame or None
        Maps each dimension name to its classification system
        (e.g. products → ``'NRNR07'``, industries → ``'NBR117A3'``).
        Corresponds to the ``classifications`` sheet in the Excel metadata
        file.
    products : DataFrame or None
        Classification table for products. Columns are the actual product
        column name (e.g. ``'nrnr'``) and that name with ``'_txt'`` suffix
        (e.g. ``'nrnr_txt'`` for the label).
    transactions : DataFrame or None
        Classification table for transaction codes. Columns are the actual
        transaction column name (e.g. ``'trans'``), that name with ``'_txt'``
        suffix (e.g. ``'trans_txt'`` for the label), ``'table'``, and
        ``'esa_code'``. ``'table'`` must be ``"supply"`` or ``"use"`` for
        every row and is validated when loading from Excel. Used to split
        combined long-format SUT data into separate supply and use tables.
    industries : DataFrame or None
        Classification table for industries. Industry codes live in the
        ``category`` column — they are the category values on rows whose
        transaction is output (P1) or intermediate consumption (P2). Columns
        are the actual category column name (e.g. ``'brch'``) and that name
        with ``'_txt'`` suffix (e.g. ``'brch_txt'``).
    individual_consumption : DataFrame or None
        Classification table for individual consumption functions (e.g.
        NCP76). Individual consumption codes live in the ``category`` column
        on rows whose transaction is P31. Same column naming as
        ``industries``.
    collective_consumption : DataFrame or None
        Classification table for collective consumption functions (e.g.
        NCO10). Collective consumption codes live in the ``category`` column
        on rows whose transaction is P32. Same column naming as
        ``industries``.
    margin_products : DataFrame or None
        Table of products whose supply represents a trade margin (e.g.
        wholesale or retail margin supply). Columns are the actual product
        column name (e.g. ``'nrnr'``), optionally that name with ``'_txt'``
        suffix (e.g. ``'nrnr_txt'`` for the label), and ``'price_layer'``
        mapping each product to the actual price layer column name it
        corresponds to (e.g. ``'handelsm'``, ``'transportm'``). These
        products are excluded from :func:`~sutlab.inspect.inspect_unbalanced_products`
        since their supply-use balance is governed by a different mechanism.
        ``None`` if the table is not supplied.
    """

    classification_names: pd.DataFrame | None = None
    products: pd.DataFrame | None = None
    transactions: pd.DataFrame | None = None
    industries: pd.DataFrame | None = None
    individual_consumption: pd.DataFrame | None = None
    collective_consumption: pd.DataFrame | None = None
    margin_products: pd.DataFrame | None = None


@dataclass
class SUTMetadata:
    """
    Column specifications and optional classification tables for a SUT.

    Parameters
    ----------
    columns : SUTColumns
        Mapping from conceptual roles to actual column names.
    classifications : SUTClassifications or None
        Classification tables for products, transactions, industries, and
        consumption functions. ``None`` if no classifications are supplied.
        Functions that require a specific table will raise an informative
        error if it is absent.
    """

    columns: SUTColumns
    classifications: SUTClassifications | None = None


@dataclass
class TargetTolerances:
    """
    Tolerances for balancing target deviations at two aggregation levels.

    A tolerance defines how close a column total must be to the target before
    it is considered balanced. For each (transaction, category) combination,
    the effective tolerance is looked up in :attr:`trans_cat` first; if absent,
    the transaction-level value from :attr:`trans` is used.

    Parameters
    ----------
    transactions : DataFrame or None
        Transaction-level tolerances. Columns: transaction column name,
        ``rel`` (relative tolerance, 0–1), ``abs`` (absolute tolerance). One
        row per transaction code. No id column — applies across all years.
        When set, must cover all transaction codes present in the SUT data.
    categories : DataFrame or None
        Overrides for specific (transaction, category) combinations. Columns:
        transaction column name, category column name, ``rel``, ``abs``. No
        id column. Partial coverage — only combinations that need a different
        tolerance from the transaction-level default need to be listed.
    """

    transactions: pd.DataFrame | None = None
    categories: pd.DataFrame | None = None


@dataclass
class Locks:
    """
    Specification of cells that balancing functions must never modify.

    A cell (product, transaction, category) is locked if it matches **any**
    of the four lock levels — OR logic across all levels.

    Parameters
    ----------
    products : DataFrame or None
        Lock all cells for the listed products. Single-column DataFrame using
        the actual product column name (e.g. ``'nrnr'``).
    transactions : DataFrame or None
        Lock all cells for the listed transactions. Single-column DataFrame
        using the actual transaction column name (e.g. ``'trans'``).
    categories : DataFrame or None
        Lock all cells for the listed (transaction, category) combinations.
        Two-column DataFrame using the actual transaction and category column
        names.
    cells : DataFrame or None
        Lock specific (product, transaction, category) combinations. Three-
        column DataFrame using the actual product, transaction, and category
        column names. Each row corresponds to one locked cell.
    price_layers : DataFrame or None
        Lock entire price layer columns across all rows and products. Single-
        column DataFrame with column name ``"price_layer"``, where each value
        is the actual column name of a price layer in the use DataFrame (e.g.
        ``"afg"`` or ``"moms"``). Balancing functions will not apply any scale
        factor to these columns — their values remain fixed. As a consequence,
        the implied rate for a locked layer changes when basic prices are
        scaled. This differs from the other lock levels, which lock rows;
        ``price_layers`` locks columns.
    """

    products: pd.DataFrame | None = None
    transactions: pd.DataFrame | None = None
    categories: pd.DataFrame | None = None
    cells: pd.DataFrame | None = None
    price_layers: pd.DataFrame | None = None


@dataclass
class BalancingConfig:
    """
    Configuration for balancing functions.

    Holds settings that apply across all balancing operations, regardless of
    which id is currently being balanced. Typically loaded from Excel via
    :func:`~sutlab.io.load_balancing_config_from_excel` and attached to a
    :class:`SUT` via :func:`set_balancing_config`.

    Parameters
    ----------
    target_tolerances : TargetTolerances or None
        Tolerances defining how close a column total must be to its target
        before the column is considered balanced. ``None`` if no tolerances
        are configured.
    locks : Locks or None
        Cells that balancing functions must never modify, regardless of any
        other selection arguments. ``None`` if no cells are locked.
    """

    target_tolerances: TargetTolerances | None = None
    locks: Locks | None = None


@dataclass
class BalancingTargets:
    """
    Target column totals for one balancing round, split into supply and use.

    The DataFrames mirror the SUT supply and use format but without the
    product dimension. Column names match the actual column names in the SUT
    DataFrames (i.e. the concrete names from :class:`SUTColumns`).

    - Supply column order: id, transaction, category, price_basic
    - Use column order: id, transaction, category, price_basic,
      [price layers], price_purchasers

    A NaN value in a price column means no target for that price basis for
    that (id, transaction, category) combination. Currently only
    ``price_basic`` (supply) and ``price_purchasers`` (use) carry non-NaN
    values, but the structure is ready for layer-level targets.

    Typically produced by :func:`~sutlab.io.load_balancing_targets_from_separated_excel`
    or :func:`~sutlab.io.load_balancing_targets_from_combined_excel`
    and attached to a :class:`SUT` via :func:`set_balancing_targets`.

    Parameters
    ----------
    supply : DataFrame
        Target totals for supply transactions. Column order:
        id, transaction, category, price_basic.
    use : DataFrame
        Target totals for use transactions. Column order:
        id, transaction, category, price_basic, [price layers],
        price_purchasers.
    """

    supply: pd.DataFrame
    use: pd.DataFrame

    def write_to_separated_parquet(
        self,
        id_values: list[str | int],
        paths: list[str | Path],
        columns_metadata: SUTColumns,
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_balancing_targets_to_separated_parquet`."""
        from sutlab.io import write_balancing_targets_to_separated_parquet
        write_balancing_targets_to_separated_parquet(self, id_values, paths, columns_metadata, print_paths=print_paths)

    def write_to_combined_parquet(
        self,
        path: str | Path,
        columns_metadata: SUTColumns,
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_balancing_targets_to_combined_parquet`."""
        from sutlab.io import write_balancing_targets_to_combined_parquet
        write_balancing_targets_to_combined_parquet(self, path, columns_metadata, print_paths=print_paths)

    def write_to_separated_csv(
        self,
        id_values: list[str | int],
        paths: list[str | Path],
        columns_metadata: SUTColumns,
        *,
        sep: str = ",",
        encoding: str | None = None,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_balancing_targets_to_separated_csv`."""
        from sutlab.io import write_balancing_targets_to_separated_csv
        write_balancing_targets_to_separated_csv(self, id_values, paths, columns_metadata, sep=sep, encoding=encoding, print_paths=print_paths)

    def write_to_combined_csv(
        self,
        path: str | Path,
        columns_metadata: SUTColumns,
        *,
        sep: str = ",",
        encoding: str | None = None,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_balancing_targets_to_combined_csv`."""
        from sutlab.io import write_balancing_targets_to_combined_csv
        write_balancing_targets_to_combined_csv(self, path, columns_metadata, sep=sep, encoding=encoding, print_paths=print_paths)

    def write_to_separated_excel(
        self,
        id_values: list[str | int],
        paths: list[str | Path],
        columns_metadata: SUTColumns,
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_balancing_targets_to_separated_excel`."""
        from sutlab.io import write_balancing_targets_to_separated_excel
        write_balancing_targets_to_separated_excel(self, id_values, paths, columns_metadata, print_paths=print_paths)

    def write_to_combined_excel(
        self,
        path: str | Path,
        columns_metadata: SUTColumns,
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_balancing_targets_to_combined_excel`."""
        from sutlab.io import write_balancing_targets_to_combined_excel
        write_balancing_targets_to_combined_excel(self, path, columns_metadata, print_paths=print_paths)


@dataclass
class SUT:
    """
    A collection of supply and use tables sharing the same structure and metadata.

    The collection typically holds a time series (e.g. one SUT per year), but
    the id dimension is not required to be temporal. Supply and use are stored
    as long-format DataFrames containing all members of the collection; each
    row belongs to one member identified by the id column
    (``metadata.columns.id``).

    One member of the collection can be designated as the active balancing
    target via :func:`set_balancing_id`. Balancing functions operate on that member
    only; inspection functions span the full collection.

    Parameters
    ----------
    price_basis : {"current_year", "previous_year"}
        The price basis used for valuation across the whole collection.
        ``"current_year"`` means values are in the prices of the reference
        year itself. ``"previous_year"`` means values are revalued at the
        prices of the preceding year, as used for volume calculations.
    supply : DataFrame
        Supply table in long format. Contains an id column, product,
        transaction, category, and the basic-prices column specified in
        ``metadata.columns.price_basic``. Supply is valued at basic prices
        only — price layers are a use-side concept. Columns should be
        ordered: id, product, transaction, category, then price columns.
        This is not enforced but recommended for readability.
    use : DataFrame
        Use table in long format. Contains an id column, product, transaction,
        category, and all price columns specified in ``metadata.columns``
        (basic, price layers, purchasers). Columns should be ordered: id,
        product, transaction, category, then price columns. This is not
        enforced but recommended for readability.
    balancing_id : str, int, or None
        The id value of the member currently being balanced. Set via
        :func:`set_balancing_id`. ``None`` if no member is designated as active.
    balancing_targets : BalancingTargets or None
        Target column totals for the current balancing round. Set via
        :func:`set_balancing_targets`. ``None`` if no targets have been loaded.
    balancing_config : BalancingConfig or None
        Configuration for balancing functions: tolerances and locked cells.
        Set via :func:`set_balancing_config`. ``None`` if no configuration
        has been loaded.
    metadata : SUTMetadata or None
        Column specifications and optional classification tables. Required by
        functions that need to look up labels or validate codes. If ``None``,
        only functions that operate purely on the data arrays can be used.
    """

    price_basis: Literal["current_year", "previous_year"]
    supply: pd.DataFrame
    use: pd.DataFrame
    balancing_id: str | int | None = None
    balancing_targets: BalancingTargets | None = None
    balancing_config: BalancingConfig | None = None
    metadata: SUTMetadata | None = None

    # ------------------------------------------------------------------
    # Methods delegating to module-level functions
    # ------------------------------------------------------------------

    def set_balancing_id(self, balancing_id: str | int) -> SUT:
        """Delegates to :func:`set_balancing_id`."""
        return set_balancing_id(self, balancing_id)

    def set_balancing_targets(self, targets: BalancingTargets) -> SUT:
        """Delegates to :func:`set_balancing_targets`."""
        return set_balancing_targets(self, targets)

    def set_balancing_config(self, config: BalancingConfig) -> SUT:
        """Delegates to :func:`set_balancing_config`."""
        return set_balancing_config(self, config)

    def set_metadata(self, metadata: SUTMetadata) -> SUT:
        """Delegates to :func:`set_metadata`."""
        return set_metadata(self, metadata)

    def filter_rows(
        self,
        *,
        ids: str | int | Iterable[str | int] | None = None,
        products: str | list[str] | None = None,
        transactions: str | list[str] | None = None,
        categories: str | list[str] | None = None,
        table: str | None = None,
    ) -> SUT:
        """Delegates to :func:`filter_rows`."""
        return filter_rows(self, ids=ids, products=products, transactions=transactions, categories=categories, table=table)

    def get_ids(self) -> pd.DataFrame:
        """Delegates to :func:`get_ids`."""
        return get_ids(self)

    def get_product_codes(self, products: str | list[str] | None = None) -> pd.DataFrame:
        """Delegates to :func:`get_product_codes`."""
        return get_product_codes(self, products=products)

    def get_transaction_codes(self, transactions: str | list[str] | None = None) -> pd.DataFrame:
        """Delegates to :func:`get_transaction_codes`."""
        return get_transaction_codes(self, transactions=transactions)

    def get_industry_codes(self, industries: str | list[str] | None = None) -> pd.DataFrame:
        """Delegates to :func:`get_industry_codes`."""
        return get_industry_codes(self, industries=industries)

    def get_individual_consumption_codes(self, categories: str | list[str] | None = None) -> pd.DataFrame:
        """Delegates to :func:`get_individual_consumption_codes`."""
        return get_individual_consumption_codes(self, categories=categories)

    def get_collective_consumption_codes(self, categories: str | list[str] | None = None) -> pd.DataFrame:
        """Delegates to :func:`get_collective_consumption_codes`."""
        return get_collective_consumption_codes(self, categories=categories)

    def compute_price_layer_rates(
        self,
        aggregation_level: Literal["product", "transaction", "category"],
    ) -> pd.DataFrame:
        """Delegates to :func:`~sutlab.derive.compute_price_layer_rates`."""
        from sutlab.derive import compute_price_layer_rates
        return compute_price_layer_rates(self, aggregation_level)

    def compute_totals(
        self,
        dimensions: str | list[str],
        *,
        use_price_columns: str | list[str] | None = None,
    ) -> pd.DataFrame:
        """Delegates to :func:`~sutlab.derive.compute_totals`."""
        from sutlab.derive import compute_totals
        return compute_totals(self, dimensions, use_price_columns=use_price_columns)

    def inspect_products(
        self,
        products: str | list[str],
        ids=None,
        sort_id=None,
    ) -> ProductInspection:
        """Delegates to :func:`~sutlab.inspect.inspect_products`."""
        from sutlab.inspect import inspect_products
        return inspect_products(self, products, ids=ids, sort_id=sort_id)

    def inspect_industries(
        self,
        industries: str | list[str],
        ids=None,
        sort_id=None,
    ) -> IndustryInspection:
        """Delegates to :func:`~sutlab.inspect.inspect_industries`."""
        from sutlab.inspect import inspect_industries
        return inspect_industries(self, industries, ids=ids, sort_id=sort_id)

    def inspect_final_uses(
        self,
        transactions: str | list[str],
        *,
        categories: str | list[str] | None = None,
        ids=None,
        sort_id=None,
    ) -> FinalUseInspection:
        """Delegates to :func:`~sutlab.inspect.inspect_final_uses`."""
        from sutlab.inspect import inspect_final_uses
        return inspect_final_uses(self, transactions, categories=categories, ids=ids, sort_id=sort_id)

    def inspect_unbalanced_products(
        self,
        products: str | list[str] | None = None,
        sort: bool = False,
        tolerance: float = 1,
    ) -> UnbalancedProductsInspection:
        """Delegates to :func:`~sutlab.inspect.inspect_unbalanced_products`."""
        from sutlab.inspect import inspect_unbalanced_products
        return inspect_unbalanced_products(self, products, sort=sort, tolerance=tolerance)

    def balance_columns(
        self,
        transactions: str | list[str] | None = None,
        categories: str | list[str] | None = None,
        adjust_products: str | list[str] | None = None,
    ) -> SUT:
        """Delegates to :func:`~sutlab.balancing.balance_columns`."""
        from sutlab.balancing import balance_columns
        return balance_columns(self, transactions=transactions, categories=categories, adjust_products=adjust_products)

    def balance_products_use(
        self,
        products: str | list[str] | None = None,
        adjust_transactions: str | list[str] | None = None,
        adjust_categories: str | list[str] | None = None,
    ) -> SUT:
        """Delegates to :func:`~sutlab.balancing.balance_products_use`."""
        from sutlab.balancing import balance_products_use
        return balance_products_use(self, products=products, adjust_transactions=adjust_transactions, adjust_categories=adjust_categories)

    def filter_free_cells(self, *, table: str | None = None) -> SUT:
        """Delegates to :func:`~sutlab.balancing.filter_free_cells`."""
        from sutlab.balancing import filter_free_cells
        return filter_free_cells(self, table=table)

    def resolve_target_tolerances(self) -> SUT:
        """Delegates to :func:`~sutlab.balancing.resolve_target_tolerances`."""
        from sutlab.balancing import resolve_target_tolerances
        return resolve_target_tolerances(self)

    def inspect_unbalanced_targets(
        self,
        transactions: str | list[str] | None = None,
        categories: str | list[str] | None = None,
        sort: bool = False,
    ) -> UnbalancedTargetsInspection:
        """Delegates to :func:`~sutlab.inspect.inspect_unbalanced_targets`."""
        from sutlab.inspect import inspect_unbalanced_targets
        return inspect_unbalanced_targets(self, transactions=transactions, categories=categories, sort=sort)

    def inspect_sut_comparison(
        self,
        before: SUT,
        *,
        ids: str | int | Iterable[str | int] | None = None,
        products: str | list[str] | None = None,
        transactions: str | list[str] | None = None,
        categories: str | list[str] | None = None,
        diff_tolerance: float = 0,
        rel_tolerance: float = 0,
        filter_nan_as_zero: bool = False,
        sort: bool = False,
        compare_dimensions: str | list[str] | None = None,
    ) -> SUTComparisonInspection:
        """Delegates to :func:`~sutlab.inspect.inspect_sut_comparison`."""
        from sutlab.inspect import inspect_sut_comparison
        return inspect_sut_comparison(
            before, self,
            ids=ids, products=products, transactions=transactions, categories=categories,
            diff_tolerance=diff_tolerance, rel_tolerance=rel_tolerance,
            filter_nan_as_zero=filter_nan_as_zero, sort=sort,
            compare_dimensions=compare_dimensions,
        )

    def adjust_add_sut(self, adjustments: SUT) -> SUT:
        """Delegates to :func:`~sutlab.adjust.adjust_add_sut`."""
        from sutlab.adjust import adjust_add_sut
        return adjust_add_sut(self, adjustments)

    def write_to_separated_parquet(
        self,
        id_values: list[str | int],
        paths: list[str | Path],
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_sut_to_separated_parquet`."""
        from sutlab.io import write_sut_to_separated_parquet
        write_sut_to_separated_parquet(self, id_values, paths, print_paths=print_paths)

    def write_to_combined_parquet(
        self,
        path: str | Path,
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_sut_to_combined_parquet`."""
        from sutlab.io import write_sut_to_combined_parquet
        write_sut_to_combined_parquet(self, path, print_paths=print_paths)

    def write_to_separated_csv(
        self,
        id_values: list[str | int],
        paths: list[str | Path],
        *,
        sep: str = ",",
        encoding: str | None = None,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_sut_to_separated_csv`."""
        from sutlab.io import write_sut_to_separated_csv
        write_sut_to_separated_csv(self, id_values, paths, sep=sep, encoding=encoding, print_paths=print_paths)

    def write_to_combined_csv(
        self,
        path: str | Path,
        *,
        sep: str = ",",
        encoding: str | None = None,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_sut_to_combined_csv`."""
        from sutlab.io import write_sut_to_combined_csv
        write_sut_to_combined_csv(self, path, sep=sep, encoding=encoding, print_paths=print_paths)

    def write_to_separated_excel(
        self,
        id_values: list[str | int],
        paths: list[str | Path],
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_sut_to_separated_excel`."""
        from sutlab.io import write_sut_to_separated_excel
        write_sut_to_separated_excel(self, id_values, paths, print_paths=print_paths)

    def write_to_combined_excel(
        self,
        path: str | Path,
        *,
        print_paths: bool = False,
    ) -> None:
        """Delegates to :func:`~sutlab.io.write_sut_to_combined_excel`."""
        from sutlab.io import write_sut_to_combined_excel
        write_sut_to_combined_excel(self, path, print_paths=print_paths)


def set_balancing_id(sut: SUT, balancing_id: str | int) -> SUT:
    """
    Return a new SUT with ``balancing_id`` set to the given id value.

    The original SUT is not modified. Balancing functions will operate only
    on rows where the id column matches ``balancing_id``; inspection functions
    span the full collection.

    Parameters
    ----------
    sut : SUT
        The SUT collection to update.
    balancing_id : str or int
        The id value to set as the active balancing target. Must exist in
        the supply table's id column.

    Returns
    -------
    SUT
        A new SUT with ``balancing_id`` set. The underlying data is shared
        with the original (not copied).

    Raises
    ------
    ValueError
        If ``sut.metadata`` is None — it is needed to identify the id column.
    ValueError
        If ``balancing_id`` is not found in the supply table.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call mark_for_balancing. "
            "Provide a SUTMetadata with a SUTColumns.id column name."
        )

    id_col = sut.metadata.columns.id
    available_ids = sorted(sut.supply[id_col].unique())

    if balancing_id not in available_ids:
        available_str = ", ".join(str(x) for x in available_ids)
        raise ValueError(
            f"ID '{balancing_id}' not found in supply table. "
            f"Available IDs: {available_str}"
        )

    return replace(sut, balancing_id=balancing_id)


def set_balancing_targets(sut: SUT, targets: BalancingTargets) -> SUT:
    """
    Return a new SUT with ``balancing_targets`` set to the given targets.

    The original SUT is not modified. Validates that the targets DataFrames
    contain the minimum required columns.

    Parameters
    ----------
    sut : SUT
        The SUT collection to update.
    targets : BalancingTargets
        Target column totals to attach. Supply and use DataFrames must use the
        same concrete column names as the SUT data, as defined in
        ``sut.metadata.columns``.

    Returns
    -------
    SUT
        A new SUT with ``balancing_targets`` set. The underlying data is
        shared with the original (not copied).

    Raises
    ------
    TypeError
        If ``targets`` is not a ``BalancingTargets`` instance.
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``targets.supply`` is missing any of: id, transaction, category,
        price_basic columns.
    ValueError
        If ``targets.use`` is missing any of: id, transaction, category,
        price_purchasers columns.
    """
    if not isinstance(targets, BalancingTargets):
        raise TypeError(
            f"targets must be a BalancingTargets instance, got {type(targets).__name__}."
        )

    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call set_balancing_targets. "
            "Provide a SUTMetadata with column name mappings."
        )

    cols = sut.metadata.columns

    supply_required = [cols.id, cols.transaction, cols.category, cols.price_basic]
    supply_missing = [c for c in supply_required if c not in targets.supply.columns]
    if supply_missing:
        missing_str = ", ".join(f"'{c}'" for c in supply_missing)
        present_str = ", ".join(f"'{c}'" for c in targets.supply.columns)
        raise ValueError(
            f"targets.supply is missing required columns: {missing_str}. "
            f"Found: {present_str}"
        )

    use_required = [cols.id, cols.transaction, cols.category, cols.price_purchasers]
    use_missing = [c for c in use_required if c not in targets.use.columns]
    if use_missing:
        missing_str = ", ".join(f"'{c}'" for c in use_missing)
        present_str = ", ".join(f"'{c}'" for c in targets.use.columns)
        raise ValueError(
            f"targets.use is missing required columns: {missing_str}. "
            f"Found: {present_str}"
        )

    return replace(sut, balancing_targets=targets)


def set_balancing_config(sut: SUT, config: BalancingConfig) -> SUT:
    """
    Return a new SUT with ``balancing_config`` set to the given configuration.

    The original SUT is not modified.

    Parameters
    ----------
    sut : SUT
        The SUT collection to update.
    config : BalancingConfig
        Balancing configuration to attach, containing tolerances and locked
        cells.

    Returns
    -------
    SUT
        A new SUT with ``balancing_config`` set. The underlying data is
        shared with the original (not copied).

    Raises
    ------
    TypeError
        If ``config`` is not a ``BalancingConfig`` instance.
    """
    if not isinstance(config, BalancingConfig):
        raise TypeError(
            f"config must be a BalancingConfig instance, got {type(config).__name__}."
        )

    return replace(sut, balancing_config=config)


def set_metadata(sut: SUT, metadata: SUTMetadata) -> SUT:
    """
    Return a new SUT with ``metadata`` set to the given value.

    The original SUT is not modified.

    Parameters
    ----------
    sut : SUT
        The SUT collection to update.
    metadata : SUTMetadata
        Metadata to attach, containing column name mappings and optional
        classification tables.

    Returns
    -------
    SUT
        A new SUT with ``metadata`` set. The underlying data is shared with
        the original (not copied).

    Raises
    ------
    TypeError
        If ``metadata`` is not a ``SUTMetadata`` instance.
    """
    if not isinstance(metadata, SUTMetadata):
        raise TypeError(
            f"metadata must be a SUTMetadata instance, got {type(metadata).__name__}."
        )

    return replace(sut, metadata=metadata)


# ---------------------------------------------------------------------------
# Product selection helpers
# ---------------------------------------------------------------------------


def _natural_sort_key(s: str) -> list:
    """Split a string into alternating text and integer parts for natural ordering.

    This makes embedded digit runs compare numerically rather than
    lexically, so ``"V9100" < "V10100"`` (9 < 10) rather than
    ``"V9100" > "V10100"`` ("9" > "1").

    Examples
    --------
    >>> _natural_sort_key("V9100")
    ['V', 9100, '']
    >>> _natural_sort_key("V10100")
    ['V', 10100, '']
    """
    parts = re.split(r"(\d+)", s)
    return [int(p) if p.isdigit() else p for p in parts]


def _code_matches_pattern(
    code: str,
    pattern: str,
    precomputed_sort_key: list | None = None,
) -> bool:
    """Return True if code matches a single positive pattern (exact, wildcard, or range).

    precomputed_sort_key, if provided, is the cached result of
    ``_natural_sort_key(code)``. Pass it when matching many codes against the
    same range pattern to avoid redundant ``re.split`` calls.
    """
    if "*" in pattern:
        return code.startswith(pattern.rstrip("*"))
    elif ":" in pattern:
        lo, hi = pattern.split(":", 1)
        key = precomputed_sort_key if precomputed_sort_key is not None else _natural_sort_key(code)
        return _natural_sort_key(lo) <= key <= _natural_sort_key(hi)
    else:
        return code == pattern


def _match_codes(codes: list[str], patterns: list[str]) -> list[str]:
    """Return the subset of codes that match the given patterns.

    Each pattern is one of:

    - **Exact**: plain string, matched by equality.
    - **Wildcard**: contains ``*``, matched by the prefix before the ``*``.
    - **Range**: contains ``:``, matched if the code falls between the two
      bounds (inclusive) using natural sort order.
    - **Negation**: starts with ``~``, followed by any of the above. Codes
      matching a negation pattern are excluded from the result.

    Negation is applied after positive matching. If only negation patterns
    are given, the starting set is all codes.

    Each code appears at most once in the result. Order follows the order
    of codes in the input.

    Parameters
    ----------
    codes : list of str
        The candidate codes to test (typically the unique codes present in
        the data).
    patterns : list of str
        One or more patterns as described above.

    Returns
    -------
    list of str
        Codes from ``codes`` that survive both the positive and negative passes.
    """
    positive_patterns = [p for p in patterns if not p.startswith("~")]
    negative_patterns = [p[1:] for p in patterns if p.startswith("~")]

    # Pre-compute natural sort keys once if any range pattern is present.
    # Without this, _natural_sort_key (which calls re.split) would be called
    # once per code per range pattern — O(N_codes × N_range_patterns) splits.
    all_active_patterns = positive_patterns + negative_patterns
    if any(":" in p for p in all_active_patterns):
        code_sort_keys: dict[str, list] = {code: _natural_sort_key(code) for code in codes}
    else:
        code_sort_keys = {}

    # Positive pass: match any positive pattern.
    # If there are no positive patterns but there are negation patterns,
    # start from all codes (negation-only means "everything except ...").
    # If patterns is empty, return nothing.
    if positive_patterns:
        candidates = [
            code for code in codes
            if any(_code_matches_pattern(code, p, code_sort_keys.get(code)) for p in positive_patterns)
        ]
    elif negative_patterns:
        candidates = list(codes)
    else:
        return []

    # Negative pass: remove codes matching any negation pattern
    if negative_patterns:
        excluded = {
            code for code in candidates
            if any(_code_matches_pattern(code, p, code_sort_keys.get(code)) for p in negative_patterns)
        }
        candidates = [code for code in candidates if code not in excluded]

    return candidates


def _filter_sut_by_column(sut: SUT, column_name: str, patterns: str | list[str]) -> SUT:
    """Filter supply and use to rows where column_name matches any pattern.

    Caller is responsible for metadata validation. NaN values in the column
    are silently excluded (they match no pattern).
    """
    if isinstance(patterns, str):
        patterns = [patterns]

    supply_codes = sut.supply[column_name].dropna().unique().tolist()
    use_codes = sut.use[column_name].dropna().unique().tolist()
    all_unique_codes = list(set(supply_codes) | set(use_codes))

    matched_codes = _match_codes(all_unique_codes, patterns)

    filtered_supply = sut.supply[sut.supply[column_name].isin(matched_codes)]
    filtered_use = sut.use[sut.use[column_name].isin(matched_codes)]

    return replace(sut, supply=filtered_supply, use=filtered_use)


def _filter_sut_by_ids(sut: SUT, ids: str | int | Iterable[str | int]) -> SUT:
    """Filter supply and use to rows matching the given id values or patterns.

    Handles int/str type conversion so integer id columns (e.g. years) work
    alongside string patterns. Caller is responsible for metadata validation.
    """
    if isinstance(ids, (str, int)):
        ids = [ids]
    else:
        ids = list(ids)

    id_col = sut.metadata.columns.id

    ids_as_str = [str(v) for v in ids]
    supply_codes = [str(v) for v in sut.supply[id_col].unique()]
    use_codes = [str(v) for v in sut.use[id_col].unique()]
    all_unique_codes = list(set(supply_codes) | set(use_codes))

    matched_codes = _match_codes(all_unique_codes, ids_as_str)

    filtered_supply = sut.supply[sut.supply[id_col].astype(str).isin(matched_codes)]
    filtered_use = sut.use[sut.use[id_col].astype(str).isin(matched_codes)]

    return replace(sut, supply=filtered_supply, use=filtered_use)


def filter_rows(
    sut: SUT,
    *,
    ids: str | int | Iterable[str | int] | None = None,
    products: str | list[str] | None = None,
    transactions: str | list[str] | None = None,
    categories: str | list[str] | None = None,
    table: str | None = None,
) -> SUT:
    """Return a new SUT containing only the rows matching the given criteria.

    All arguments except ``sut`` are optional, but at least one of ``ids``,
    ``products``, ``transactions``, or ``categories`` must be provided.
    Filters are applied with AND logic — each argument narrows the result
    further.

    Parameters
    ----------
    sut : SUT
        The SUT collection to filter.
    ids : str, int, iterable of str or int, or None
        Filter by collection member id. Accepts a single value, a list, or
        any iterable including ``range``. Each entry is one of:

        - **Exact value**: e.g. ``2019`` or ``"Q1"``.
        - **Wildcard**: contains ``*``, e.g. ``"201*"``.
        - **Range**: contains ``:``, e.g. ``"2015:2019"``
          (inclusive, natural sort order).
        - **Negation**: starts with ``~``, e.g. ``"~2019"`` excludes that id.

        ``range(2015, 2020)`` is equivalent to ``[2015, 2016, 2017, 2018, 2019]``.
    products : str, list of str, or None
        Filter by product code. Each entry is one of:

        - **Exact code**: e.g. ``"V10100"``.
        - **Wildcard**: contains ``*``, e.g. ``"V10*"``.
        - **Range**: contains ``:``, e.g. ``"V10100:V20300"``
          (inclusive, natural sort order).
        - **Negation**: starts with ``~``, e.g. ``"~V10*"`` excludes all V10
          codes. If only negation patterns are given, the starting set is all
          codes in the data.

    transactions : str, list of str, or None
        Filter by transaction code. Same pattern syntax as ``products``.

        Note: each transaction code belongs to either supply or use, not
        both. Filtering by a supply transaction code will produce an empty
        use table and vice versa.
    categories : str, list of str, or None
        Filter by category code. Same pattern syntax as ``products``.

        Rows with no category (imports, exports, investment) have a NaN
        category value and are excluded when filtering by category.
    table : str or None, optional
        Which table to filter. ``"supply"`` filters only ``sut.supply``;
        ``"use"`` filters only ``sut.use``; ``None`` (default) filters both.

    Returns
    -------
    SUT
        A new SUT with the selected table(s) filtered to matching rows.
        ``balancing_id`` is set to ``None`` — balancing a sub-SUT is not
        supported. ``price_basis`` and ``metadata`` are carried over
        unchanged. If no rows match, the result contains empty DataFrames.

    Raises
    ------
    ValueError
        If all of ``ids``, ``products``, ``transactions``, and ``categories``
        are ``None``.
    ValueError
        If ``table`` is not ``None``, ``"supply"``, or ``"use"``.
    ValueError
        If ``sut.metadata`` is ``None`` — it is needed to identify the
        relevant columns.
    """
    if ids is None and products is None and transactions is None and categories is None:
        raise ValueError(
            "At least one of ids, products, transactions, or categories must be provided."
        )

    if table is not None and table not in ("supply", "use"):
        raise ValueError(
            f"table must be 'supply', 'use', or None. Got: {repr(table)}"
        )

    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call filter_rows. "
            "Provide a SUTMetadata with column name mappings."
        )

    original_supply = sut.supply
    original_use = sut.use

    cols = sut.metadata.columns
    result = sut

    if ids is not None:
        result = _filter_sut_by_ids(result, ids)
    if products is not None:
        result = _filter_sut_by_column(result, cols.product, products)
    if transactions is not None:
        result = _filter_sut_by_column(result, cols.transaction, transactions)
    if categories is not None:
        result = _filter_sut_by_column(result, cols.category, categories)

    if table == "supply":
        result = replace(result, use=original_use)
    elif table == "use":
        result = replace(result, supply=original_supply)

    return replace(result, balancing_id=None)


# ---------------------------------------------------------------------------
# Code lookup functions
# ---------------------------------------------------------------------------


def _unique_column_values(sut: SUT, column_name: str) -> pd.DataFrame:
    """Return a sorted single-column DataFrame of unique non-null values from supply and use."""
    supply_vals = sut.supply[column_name].dropna().unique().tolist()
    use_vals = sut.use[column_name].dropna().unique().tolist()
    all_vals = list(set(supply_vals) | set(use_vals))
    return pd.DataFrame({column_name: all_vals}).sort_values(column_name).reset_index(drop=True)


def _add_txt_column(
    codes_df: pd.DataFrame,
    classification_df: pd.DataFrame | None,
    key_col: str,
) -> pd.DataFrame:
    """Left-join the ``_txt`` label column from ``classification_df`` if available.

    If ``classification_df`` is ``None`` or does not contain a ``{key_col}_txt``
    column, ``codes_df`` is returned unchanged.
    """
    if classification_df is None:
        return codes_df
    txt_col = f"{key_col}_txt"
    if txt_col not in classification_df.columns:
        return codes_df
    labels = classification_df[[key_col, txt_col]].drop_duplicates(subset=key_col)
    return codes_df.merge(labels, on=key_col, how="left")


def get_product_codes(
    sut: SUT,
    products: str | list[str] | None = None,
) -> pd.DataFrame:
    """Return the unique product codes present in the data.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    products : str, list of str, or None
        Optional filter. Each entry is one of:

        - **Exact code**: e.g. ``"V10100"``.
        - **Wildcard**: contains ``*``, e.g. ``"V10*"``.
        - **Range**: contains ``:``, e.g. ``"V10100:V20300"``
          (inclusive, natural sort order).
        - **Negation**: starts with ``~``, e.g. ``"~V10*"`` excludes all
          V10 codes. If only negation patterns are given, the starting set
          is all codes in the data.

        When ``None`` (default), all codes are returned.

    Returns
    -------
    pd.DataFrame
        DataFrame named after the product column in ``sut``, containing the
        matching product codes sorted in ascending order with a clean integer
        index. If ``sut.metadata.classifications.products`` is present, a
        second column ``{product_col}_txt`` with the product label is included.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_product_codes. "
            "Provide a SUTMetadata with column name mappings."
        )
    prod_col = sut.metadata.columns.product
    result = _unique_column_values(sut, prod_col)
    if products is not None:
        patterns = [products] if isinstance(products, str) else products
        matched = _match_codes(result[prod_col].tolist(), patterns)
        result = result[result[prod_col].isin(matched)].reset_index(drop=True)
    if sut.metadata.classifications is not None:
        result = _add_txt_column(result, sut.metadata.classifications.products, prod_col)
    return result


def get_transaction_codes(
    sut: SUT,
    transactions: str | list[str] | None = None,
) -> pd.DataFrame:
    """Return the unique transaction codes present in the data.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    transactions : str, list of str, or None
        Optional filter. Same pattern syntax as ``products`` in
        :func:`get_product_codes`. When ``None`` (default), all codes are
        returned.

    Returns
    -------
    pd.DataFrame
        DataFrame named after the transaction column in ``sut``, containing
        the matching transaction codes sorted in ascending order with a clean
        integer index. If ``sut.metadata.classifications.transactions`` is
        present, a second column ``{transaction_col}_txt`` with the transaction
        label is included.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_transaction_codes. "
            "Provide a SUTMetadata with column name mappings."
        )
    trans_col = sut.metadata.columns.transaction
    result = _unique_column_values(sut, trans_col)
    if transactions is not None:
        patterns = [transactions] if isinstance(transactions, str) else transactions
        matched = _match_codes(result[trans_col].tolist(), patterns)
        result = result[result[trans_col].isin(matched)].reset_index(drop=True)
    if sut.metadata.classifications is not None:
        result = _add_txt_column(result, sut.metadata.classifications.transactions, trans_col)
    return result


def _category_codes_for_esa(sut: SUT, esa_codes: list[str]) -> pd.DataFrame:
    """Return sorted unique category codes from rows whose transaction maps to any of the given ESA codes."""
    trans_df = sut.metadata.classifications.transactions
    trans_col = sut.metadata.columns.transaction
    matching_trans = trans_df[trans_df["esa_code"].isin(esa_codes)][trans_col].tolist()

    cat_col = sut.metadata.columns.category

    supply_cats = sut.supply[sut.supply[trans_col].isin(matching_trans)][cat_col].dropna().unique().tolist()
    use_cats = sut.use[sut.use[trans_col].isin(matching_trans)][cat_col].dropna().unique().tolist()
    all_cats = list(set(supply_cats) | set(use_cats))

    return pd.DataFrame({cat_col: all_cats}).sort_values(cat_col).reset_index(drop=True)


def _require_transaction_classifications(sut: SUT, function_name: str) -> None:
    """Raise ValueError if transaction classifications with esa_code are not available."""
    if sut.metadata is None:
        raise ValueError(
            f"sut.metadata is required to call {function_name}. "
            "Provide a SUTMetadata with column name mappings."
        )
    if (
        sut.metadata.classifications is None
        or sut.metadata.classifications.transactions is None
    ):
        raise ValueError(
            f"sut.metadata.classifications.transactions is required to call {function_name}. "
            "Load a classifications file with a 'transactions' sheet including an 'esa_code' column."
        )


def get_industry_codes(
    sut: SUT,
    industries: str | list[str] | None = None,
) -> pd.DataFrame:
    """Return the unique industry codes present in the data.

    Industry codes are the category codes from output (P1) and intermediate
    consumption (P2) rows.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    industries : str, list of str, or None
        Optional filter. Same pattern syntax as ``products`` in
        :func:`get_product_codes`. When ``None`` (default), all codes are
        returned.

    Returns
    -------
    pd.DataFrame
        DataFrame named after the category column in ``sut``, containing the
        matching industry codes, sorted in ascending order with a clean integer
        index. If ``sut.metadata.classifications.industries`` is present, a
        second column ``{category_col}_txt`` with the industry label is included.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.metadata.classifications.transactions``
        is ``None``.
    """
    _require_transaction_classifications(sut, "get_industry_codes")
    cat_col = sut.metadata.columns.category
    result = _category_codes_for_esa(sut, ["P1", "P2"])
    if industries is not None:
        patterns = [industries] if isinstance(industries, str) else industries
        matched = _match_codes(result[cat_col].tolist(), patterns)
        result = result[result[cat_col].isin(matched)].reset_index(drop=True)
    result = _add_txt_column(result, sut.metadata.classifications.industries, cat_col)
    return result


def get_individual_consumption_codes(
    sut: SUT,
    categories: str | list[str] | None = None,
) -> pd.DataFrame:
    """Return the unique individual consumption function codes present in the data.

    Individual consumption codes are the category codes from rows with ESA
    transaction P31 (Individual consumption expenditure).

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    categories : str, list of str, or None
        Optional filter. Same pattern syntax as ``products`` in
        :func:`get_product_codes`. When ``None`` (default), all codes are
        returned.

    Returns
    -------
    pd.DataFrame
        DataFrame named after the category column in ``sut``, containing the
        matching individual consumption codes, sorted in ascending order with a
        clean integer index. If
        ``sut.metadata.classifications.individual_consumption`` is present, a
        second column ``{category_col}_txt`` with the label is included.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.metadata.classifications.transactions``
        is ``None``.
    """
    _require_transaction_classifications(sut, "get_individual_consumption_codes")
    cat_col = sut.metadata.columns.category
    result = _category_codes_for_esa(sut, ["P31"])
    if categories is not None:
        patterns = [categories] if isinstance(categories, str) else categories
        matched = _match_codes(result[cat_col].tolist(), patterns)
        result = result[result[cat_col].isin(matched)].reset_index(drop=True)
    result = _add_txt_column(result, sut.metadata.classifications.individual_consumption, cat_col)
    return result


def get_collective_consumption_codes(
    sut: SUT,
    categories: str | list[str] | None = None,
) -> pd.DataFrame:
    """Return the unique collective consumption function codes present in the data.

    Collective consumption codes are the category codes from rows with ESA
    transaction P32 (Collective consumption expenditure).

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.
    categories : str, list of str, or None
        Optional filter. Same pattern syntax as ``products`` in
        :func:`get_product_codes`. When ``None`` (default), all codes are
        returned.

    Returns
    -------
    pd.DataFrame
        DataFrame named after the category column in ``sut``, containing the
        matching collective consumption codes, sorted in ascending order with a
        clean integer index. If
        ``sut.metadata.classifications.collective_consumption`` is present, a
        second column ``{category_col}_txt`` with the label is included.

    Raises
    ------
    ValueError
        If ``sut.metadata`` or ``sut.metadata.classifications.transactions``
        is ``None``.
    """
    _require_transaction_classifications(sut, "get_collective_consumption_codes")
    cat_col = sut.metadata.columns.category
    result = _category_codes_for_esa(sut, ["P32"])
    if categories is not None:
        patterns = [categories] if isinstance(categories, str) else categories
        matched = _match_codes(result[cat_col].tolist(), patterns)
        result = result[result[cat_col].isin(matched)].reset_index(drop=True)
    result = _add_txt_column(result, sut.metadata.classifications.collective_consumption, cat_col)
    return result


def get_ids(sut: SUT) -> pd.DataFrame:
    """Return the unique id values present in the data.

    Parameters
    ----------
    sut : SUT
        The SUT collection to inspect.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame named after the id column in ``sut``,
        containing the unique id values from supply and use combined,
        sorted in ascending order with a clean integer index.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call get_ids. "
            "Provide a SUTMetadata with column name mappings."
        )
    return _unique_column_values(sut, sut.metadata.columns.id)


# ---------------------------------------------------------------------------
# Attach free-function docstrings to SUT methods so that
# `?sut.method` in Jupyter shows the full documentation.
# ---------------------------------------------------------------------------

SUT.set_balancing_id.__doc__ = set_balancing_id.__doc__
SUT.set_balancing_targets.__doc__ = set_balancing_targets.__doc__
SUT.set_balancing_config.__doc__ = set_balancing_config.__doc__
SUT.filter_rows.__doc__ = filter_rows.__doc__
SUT.get_ids.__doc__ = get_ids.__doc__
SUT.get_product_codes.__doc__ = get_product_codes.__doc__
SUT.get_transaction_codes.__doc__ = get_transaction_codes.__doc__
SUT.get_industry_codes.__doc__ = get_industry_codes.__doc__
SUT.get_individual_consumption_codes.__doc__ = get_individual_consumption_codes.__doc__
SUT.get_collective_consumption_codes.__doc__ = get_collective_consumption_codes.__doc__

