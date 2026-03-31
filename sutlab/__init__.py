# sutlab — supply and use table library

from sutlab.io import (
    load_metadata_from_excel,
    load_sut_from_parquet,
    load_balancing_targets_from_excel,
    load_balancing_config_from_excel,
)
from sutlab.sut import (
    set_balancing_id,
    set_balancing_targets,
    set_balancing_config,
    get_rows,
    get_product_codes,
    get_transaction_codes,
    get_industry_codes,
    get_individual_consumption_codes,
    get_collective_consumption_codes,
    get_ids,
)
from sutlab.inspect import inspect_products
from sutlab.derive import compute_price_layer_rates
from sutlab.balancing import balance_columns, balance_products_use
from sutlab.sut import SUT

# Attach free-function docstrings to SUT methods so that
# `?sut.method` in Jupyter shows the full documentation.
SUT.compute_price_layer_rates.__doc__ = compute_price_layer_rates.__doc__
SUT.inspect_products.__doc__ = inspect_products.__doc__
SUT.balance_columns.__doc__ = balance_columns.__doc__
SUT.balance_products_use.__doc__ = balance_products_use.__doc__
