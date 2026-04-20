"""
inspect_unbalanced_products: imbalance table for the active balancing member.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pandas as pd
from pandas.io.formats.style import Styler

from sutlab.sut import SUT, _match_codes, _natural_sort_key
from sutlab.inspect._products import _get_price_layer_columns
from sutlab.inspect._style import _style_imbalances_table, _style_unbalanced_products_summary
from sutlab.inspect._shared import _write_inspection_to_excel
from sutlab.inspect._tables_comparison import TablesComparison, _compute_comparison_table_fields


@dataclass
class UnbalancedProductsData:
    """Raw DataFrames underlying a :class:`UnbalancedProductsInspection`.

    Use this directly for programmatic access. For display in a Jupyter
    notebook, use the corresponding property on
    :class:`UnbalancedProductsInspection` once styling is added.
    """

    imbalances: pd.DataFrame
    summary: pd.DataFrame


@dataclass
class UnbalancedProductsInspection:
    """
    Result of :func:`inspect_unbalanced_products`.

    Raw DataFrames are available under ``result.data``.

    Attributes
    ----------
    imbalances : pd.DataFrame
        One row per product whose supply and use at basic prices differ by
        more than the tolerance threshold.

        Index is the product code column (e.g. ``nrnr``) when no product
        classification is loaded. When a product classification is available,
        the index is a two-level MultiIndex with levels named after the
        product column and its ``_txt`` counterpart
        (e.g. ``nrnr`` and ``nrnr_txt``).

        Columns use the actual data column names from ``SUTColumns``,
        prefixed with ``supply_``, ``use_``, ``diff_``, or ``rel_``:

        - ``supply_{price_basic}`` — total supply for the product at basic
          prices, summed across all transactions and categories in the active
          balancing member.
        - ``use_{price_basic}`` — total use for the product at basic prices.
        - ``diff_{price_basic}`` — ``supply_{price_basic} - use_{price_basic}``.
        - ``rel_{price_basic}`` — ``supply_{price_basic} / use_{price_basic} - 1``.
          ``NaN`` when ``use_{price_basic}`` is zero.
        - One ``use_{layer}`` column per price layer present in the data
          (e.g. ``use_vat``, ``use_transport_margins``), using the actual
          column names from ``SUTColumns``. Each value is the total of that
          layer summed across all use rows for the product in the active
          balancing member. Provided as context for diagnosing the imbalance.
        - ``use_{price_purchasers}`` — total use at purchasers' prices.

    summary : pd.DataFrame
        One row summarising the imbalances table. Index is ``"imbalances"``;
        columns are ``n_unbalanced`` (number of rows in the imbalances table)
        and ``largest_diff`` (the signed diff value whose absolute value
        is largest; ``NaN`` when the imbalances table is empty).
    """

    data: UnbalancedProductsData
    display_unit: float | None = None
    rel_base: int = 100
    decimals: int = 1
    _all_rel: bool = dataclasses.field(default=False, repr=False)

    @property
    def imbalances(self) -> Styler:
        """Styled imbalances table."""
        df = self.data.imbalances
        supply_cols = [c for c in df.columns if c.startswith("supply_")]
        use_cols = [c for c in df.columns if c.startswith("use_")]
        rel_cols = [c for c in df.columns if c.startswith("rel_")]
        rel_col = rel_cols[0] if rel_cols else ""
        return _style_imbalances_table(df, supply_cols, use_cols, rel_col, display_unit=self.display_unit, rel_base=self.rel_base, all_rel=self._all_rel, decimals=self.decimals)

    @property
    def summary(self) -> Styler:
        """Styled summary table."""
        return _style_unbalanced_products_summary(self.data.summary, display_unit=self.display_unit, all_rel=self._all_rel, decimals=self.decimals)

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

    def set_display_unit(self, display_unit: float | None) -> "UnbalancedProductsInspection":
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

    def set_rel_base(self, rel_base: int) -> "UnbalancedProductsInspection":
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

    def set_decimals(self, decimals: int) -> "UnbalancedProductsInspection":
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

    def inspect_tables_comparison(self, other: "UnbalancedProductsInspection") -> TablesComparison:
        """Compare all tables in this inspection with another :class:`UnbalancedProductsInspection`.

        Computes element-wise differences and relative changes between
        corresponding tables. Index alignment uses an outer join.

        Parameters
        ----------
        other : UnbalancedProductsInspection
            The inspection result to compare against.

        Returns
        -------
        TablesComparison
            Contains ``.diff`` and ``.rel`` as
            :class:`UnbalancedProductsInspection` instances.

        Raises
        ------
        TypeError
            If ``other`` is not a :class:`UnbalancedProductsInspection`.
        """
        if not isinstance(other, UnbalancedProductsInspection):
            raise TypeError(
                f"Expected UnbalancedProductsInspection, got {type(other).__name__}."
            )
        diff_fields, rel_fields = _compute_comparison_table_fields(self.data, other.data)
        diff = UnbalancedProductsInspection(
            data=UnbalancedProductsData(**diff_fields),
            display_unit=self.display_unit,
            rel_base=self.rel_base,
            decimals=self.decimals,
        )
        rel = UnbalancedProductsInspection(
            data=UnbalancedProductsData(**rel_fields),
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


def inspect_unbalanced_products(
    sut: SUT,
    products: str | list[str] | None = None,
    sort: bool = False,
    tolerance: float = 1,
) -> UnbalancedProductsInspection:
    """
    Return an imbalances table for products in the active balancing member.

    Only products whose absolute difference between supply and use at basic
    prices exceeds ``tolerance`` are included.

    Parameters
    ----------
    sut : SUT
        The SUT collection. Must have ``balancing_id`` and ``metadata`` set.
    products : str, list of str, or None, optional
        Product codes to check. Accepts the same pattern syntax as
        :func:`~sutlab.sut.filter_rows`: exact codes, wildcards (``*``),
        ranges (``:``), and negation (``~``). ``None`` (the default) checks
        all products present in the balancing member.
    sort : bool, optional
        When ``True``, rows are sorted by the absolute value of
        ``diff_{price_basic}`` in descending order (largest imbalance first).
        Default ``False`` preserves natural sort order of product codes.
    tolerance : float, optional
        Products are considered unbalanced when
        ``abs(supply_{price_basic} - use_{price_basic}) > tolerance``.
        Default ``1``.

    Returns
    -------
    UnbalancedProductsInspection
        A dataclass whose ``.data.imbalances`` is a DataFrame of unbalanced
        products. See :class:`UnbalancedProductsInspection` for the table
        structure.

    Raises
    ------
    ValueError
        If ``sut.metadata`` is ``None``.
    ValueError
        If ``sut.balancing_id`` is ``None``.
    """
    if sut.metadata is None:
        raise ValueError(
            "sut.metadata is required to call inspect_unbalanced_products. "
            "Provide a SUTMetadata with column name mappings."
        )
    if sut.balancing_id is None:
        raise ValueError(
            "sut.balancing_id is not set. Call set_balancing_id first to "
            "identify which member to inspect."
        )

    cols = sut.metadata.columns
    id_col = cols.id
    prod_col = cols.product
    price_basic_col = cols.price_basic
    price_purchasers_col = cols.price_purchasers

    # Derived column names
    supply_basic_name = f"supply_{price_basic_col}"
    use_basic_name = f"use_{price_basic_col}"
    diff_name = f"diff_{price_basic_col}"
    rel_name = f"rel_{price_basic_col}"
    use_purchasers_name = f"use_{price_purchasers_col}"

    # Filter to the active balancing member
    member_supply = sut.supply[sut.supply[id_col] == sut.balancing_id]
    member_use = sut.use[sut.use[id_col] == sut.balancing_id]

    # Resolve which products to check
    supply_codes = member_supply[prod_col].dropna().unique().tolist()
    use_codes = member_use[prod_col].dropna().unique().tolist()
    all_codes = sorted(set(supply_codes) | set(use_codes), key=_natural_sort_key)

    if products is None:
        matched_products = all_codes
    else:
        if isinstance(products, str):
            patterns = [products]
        else:
            patterns = list(products)
        matched_products = _match_codes(all_codes, patterns)

    # Exclude margin products (their supply-use balance is governed differently)
    classifications = sut.metadata.classifications
    if classifications is not None and classifications.margin_products is not None:
        margin_codes = set(classifications.margin_products[prod_col].tolist())
        matched_products = [p for p in matched_products if p not in margin_codes]

    # Restrict both tables to matched products
    matched_supply = member_supply[member_supply[prod_col].isin(matched_products)]
    matched_use = member_use[member_use[prod_col].isin(matched_products)]

    # Sum supply at basic prices per product
    supply_totals = (
        matched_supply
        .groupby(prod_col, dropna=False)[price_basic_col]
        .sum()
        .rename(supply_basic_name)
    )

    # Sum use at basic prices per product
    use_basic_totals = (
        matched_use
        .groupby(prod_col, dropna=False)[price_basic_col]
        .sum()
        .rename(use_basic_name)
    )

    # Sum each price layer per product
    layer_cols = _get_price_layer_columns(cols, member_use)
    layer_totals = {}
    for layer_col in layer_cols:
        layer_totals[f"use_{layer_col}"] = (
            matched_use
            .groupby(prod_col, dropna=False)[layer_col]
            .sum()
        )

    # Sum use at purchasers' prices per product
    use_purchasers_totals = (
        matched_use
        .groupby(prod_col, dropna=False)[price_purchasers_col]
        .sum()
        .rename(use_purchasers_name)
    )

    # Combine into one DataFrame; products missing from supply or use get 0
    result = pd.DataFrame(index=pd.Index(matched_products, name=prod_col))
    result = result.join(supply_totals, how="left").fillna({supply_basic_name: 0.0})
    result = result.join(use_basic_totals, how="left").fillna({use_basic_name: 0.0})

    result[diff_name] = result[supply_basic_name] - result[use_basic_name]
    # Avoid division by zero: use_basic == 0 → NaN
    result[rel_name] = (
        result[supply_basic_name]
        / result[use_basic_name].replace(0, float("nan"))
        - 1
    )

    for use_layer_name, layer_series in layer_totals.items():
        result = result.join(
            layer_series.rename(use_layer_name), how="left"
        ).fillna({use_layer_name: 0.0})

    result = result.join(use_purchasers_totals, how="left").fillna(
        {use_purchasers_name: 0.0}
    )

    # Reorder columns: diff and rel first, then supply, use, price layers, purchasers
    use_layer_names = list(layer_totals.keys())
    col_order = (
        [diff_name, rel_name, supply_basic_name, use_basic_name]
        + use_layer_names
        + [use_purchasers_name]
    )
    result = result[col_order]

    # Keep only products whose imbalance exceeds the tolerance
    result = result[result[diff_name].abs() > tolerance]

    # Optionally sort by absolute imbalance descending
    if sort:
        result = result.sort_values(diff_name, key=lambda s: s.abs(), ascending=False)

    # Attach product labels as a second index level if available
    prod_txt_col = f"{prod_col}_txt"
    has_product_labels = (
        classifications is not None
        and classifications.products is not None
        and prod_txt_col in classifications.products.columns
    )

    if has_product_labels:
        product_names = dict(zip(
            classifications.products[prod_col].astype(str),
            classifications.products[prod_txt_col].astype(str),
        ))
        labels = [product_names.get(code, "") for code in result.index]
        result.index = pd.MultiIndex.from_arrays(
            [result.index, labels],
            names=[prod_col, prod_txt_col],
        )

    # Build summary: one row with n_unbalanced and largest_diff.
    n_unbalanced = len(result)
    if n_unbalanced > 0:
        largest_diff = result[diff_name].loc[result[diff_name].abs().idxmax()]
    else:
        largest_diff = float("nan")
    summary = pd.DataFrame(
        {"n_unbalanced": [n_unbalanced], "largest_diff": [largest_diff]},
        index=pd.Index(["imbalances"], name="table"),
    )

    return UnbalancedProductsInspection(
        data=UnbalancedProductsData(imbalances=result, summary=summary),
    )
