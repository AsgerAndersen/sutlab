"""
Helpers shared by test modules.
"""

from sutlab.sut import SUT


def make_previous_sut(
    sut: SUT,
    years=None,
    supply_factor: float = 0.9,
    use_factor: float = 0.95,
) -> SUT:
    """Build a previous-year-price SUT from a current-price SUT for tests.

    Keeps the rows of the given ``years`` and multiplies every price column
    in supply by ``supply_factor`` and every price column in use by
    ``use_factor``. Using different factors for supply and use makes derived
    rows (GVA, imbalances, ...) differ from a simple rescaling of the
    current-price values, which is what chain-linking tests need.

    Parameters
    ----------
    sut : SUT
        Current-price SUT with metadata.
    years : iterable or None
        Id values to keep. ``None`` (default) keeps every id except the
        first, which is what a previous-year-price SUT normally covers.
    supply_factor, use_factor : float
        Scaling factors for the price columns of supply and use.
    """
    cols = sut.metadata.columns
    id_col = cols.id

    if years is None:
        all_ids = sorted(set(sut.supply[id_col]) | set(sut.use[id_col]))
        years = all_ids[1:]
    years = list(years)

    price_columns = [
        cols.price_basic,
        cols.price_purchasers,
        cols.trade_margins,
        cols.wholesale_margins,
        cols.retail_margins,
        cols.transport_margins,
        cols.product_taxes,
        cols.product_subsidies,
        cols.product_taxes_less_subsidies,
        cols.vat,
    ]
    price_columns = [column for column in price_columns if column is not None]

    supply = sut.supply[sut.supply[id_col].isin(years)].copy()
    use = sut.use[sut.use[id_col].isin(years)].copy()

    for column in price_columns:
        if column in supply.columns:
            supply[column] = supply[column] * supply_factor
        if column in use.columns:
            use[column] = use[column] * use_factor

    return SUT(
        price_basis="previous_year",
        supply=supply,
        use=use,
        metadata=sut.metadata,
    )
