"""
Inspection functions for supply and use tables.
"""

from sutlab.inspect._products import (
    inspect_products,
    ProductInspection,
    ProductInspectionData,
)
from sutlab.inspect._industries import (
    inspect_industries,
    IndustryInspection,
    IndustryInspectionData,
)
from sutlab.inspect._final_uses import (
    inspect_final_uses,
    FinalUseInspection,
    FinalUseInspectionData,
)
from sutlab.inspect._product_imbalances import (
    inspect_unbalanced_products,
    UnbalancedProductsInspection,
    UnbalancedProductsData,
)
from sutlab.inspect._style import (
    _format_number,
    _format_percentage,
    _apply_balance_style,
    _build_balance_row_css,
    _style_detail_table,
    _style_final_use_use_table,
    _style_final_use_use_categories_table,
    _style_final_use_use_products_table,
    _style_final_use_price_layers_table,
    _DATA_COLORS,
    _INDEX_COLORS,
    _LAYER_PALETTES,
)

__all__ = [
    "inspect_products",
    "ProductInspection",
    "ProductInspectionData",
    "inspect_industries",
    "IndustryInspection",
    "IndustryInspectionData",
    "inspect_final_uses",
    "FinalUseInspection",
    "FinalUseInspectionData",
    "inspect_unbalanced_products",
    "UnbalancedProductsInspection",
    "UnbalancedProductsData",
]
