# sutlab — supply and use table library

from sutlab.io import (
    load_metadata_from_excel,
    load_sut_from_separated_parquet,
    load_sut_from_combined_parquet,
    load_sut_from_separated_csv,
    load_sut_from_combined_csv,
    load_sut_from_separated_excel,
    load_sut_from_combined_excel,
    write_sut_to_separated_parquet,
    write_sut_to_combined_parquet,
    write_sut_to_separated_csv,
    write_sut_to_combined_csv,
    write_sut_to_separated_excel,
    write_sut_to_combined_excel,
    load_balancing_targets_from_separated_parquet,
    load_balancing_targets_from_combined_parquet,
    load_balancing_targets_from_separated_csv,
    load_balancing_targets_from_combined_csv,
    load_balancing_targets_from_separated_excel,
    load_balancing_targets_from_combined_excel,
    load_balancing_targets_from_dataframe,
    write_balancing_targets_to_separated_parquet,
    write_balancing_targets_to_combined_parquet,
    write_balancing_targets_to_separated_csv,
    write_balancing_targets_to_combined_csv,
    write_balancing_targets_to_separated_excel,
    write_balancing_targets_to_combined_excel,
    load_balancing_config_from_excel,
    load_sut_from_dataframe,
)
from sutlab.sut import (
    set_balancing_id,
    set_balancing_targets,
    set_balancing_config,
    set_metadata,
    filter_rows,
    get_product_codes,
    get_transaction_codes,
    get_industry_codes,
    get_individual_consumption_codes,
    get_collective_consumption_codes,
    get_ids,
)
from sutlab.inspect import inspect_products, inspect_industries, inspect_final_uses
from sutlab.derive import compute_price_layer_rates
from sutlab.balancing import balance_columns, balance_products_use
from sutlab.adjust import adjust_add_sut
from sutlab.sut import SUT

# Attach free-function docstrings to SUT methods so that
# `?sut.method` in Jupyter shows the full documentation.
SUT.compute_price_layer_rates.__doc__ = compute_price_layer_rates.__doc__
SUT.inspect_products.__doc__ = inspect_products.__doc__
SUT.balance_columns.__doc__ = balance_columns.__doc__
SUT.balance_products_use.__doc__ = balance_products_use.__doc__
SUT.inspect_industries.__doc__ = inspect_industries.__doc__
SUT.inspect_final_uses.__doc__ = inspect_final_uses.__doc__
SUT.adjust_add_sut.__doc__ = adjust_add_sut.__doc__
SUT.write_to_separated_parquet.__doc__ = write_sut_to_separated_parquet.__doc__
SUT.write_to_combined_parquet.__doc__ = write_sut_to_combined_parquet.__doc__
SUT.write_to_separated_csv.__doc__ = write_sut_to_separated_csv.__doc__
SUT.write_to_combined_csv.__doc__ = write_sut_to_combined_csv.__doc__
SUT.write_to_separated_excel.__doc__ = write_sut_to_separated_excel.__doc__
SUT.write_to_combined_excel.__doc__ = write_sut_to_combined_excel.__doc__
