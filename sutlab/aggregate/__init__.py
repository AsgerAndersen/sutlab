# sutlab/aggregate/__init__.py

from sutlab.aggregate._products import aggregate_classification_products
from sutlab.aggregate._transactions import aggregate_classification_transactions
from sutlab.aggregate._industries import aggregate_classification_industries
from sutlab.aggregate._individual_consumption import aggregate_classification_individual_consumption
from sutlab.aggregate._collective_consumption import aggregate_classification_collective_consumption

__all__ = [
    "aggregate_classification_products",
    "aggregate_classification_transactions",
    "aggregate_classification_industries",
    "aggregate_classification_individual_consumption",
    "aggregate_classification_collective_consumption",
]
