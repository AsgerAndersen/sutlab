"""
Tests for I/O functions in sutlab.io.
"""

from pathlib import Path

import pandas as pd
import pytest

from sutlab.io import (
    load_metadata_classifications_from_excel,
    load_metadata_columns_from_excel,
    load_metadata_from_excel,
)
from sutlab.sut import SUTClassifications, SUTColumns, SUTMetadata


FIXTURES = Path(__file__).parent.parent / "data" / "fixtures"
COLUMNS_FILE = FIXTURES / "metadata" / "columns.xlsx"
CLASSIFICATIONS_FILE = FIXTURES / "metadata" / "ta_classifications.xlsx"


# ---------------------------------------------------------------------------
# Helpers for writing bad Excel files in tests
# ---------------------------------------------------------------------------


def write_excel(path, df, sheet_name="Sheet1"):
    """Write a single-sheet Excel file."""
    df.to_excel(path, index=False, sheet_name=sheet_name)


def write_excel_multisheet(path, sheets: dict):
    """Write a multi-sheet Excel file. sheets is {sheet_name: DataFrame}."""
    with pd.ExcelWriter(path) as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)


# ---------------------------------------------------------------------------
# load_metadata_columns_from_excel
# ---------------------------------------------------------------------------


class TestLoadMetadataColumnsFromExcel:

    def test_returns_sut_columns(self):
        result = load_metadata_columns_from_excel(COLUMNS_FILE)
        assert isinstance(result, SUTColumns)

    def test_required_fields_loaded_correctly(self):
        result = load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.id == "year"
        assert result.product == "nrnr"
        assert result.transaction == "trans"
        assert result.category == "brch"
        assert result.price_basic == "bas"
        assert result.price_purchasers == "koeb"

    def test_optional_fields_loaded_correctly(self):
        result = load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.wholesale_margins == "eng"
        assert result.retail_margins == "det"
        assert result.product_taxes_less_subsidies == "afg"
        assert result.vat == "moms"

    def test_absent_optional_fields_are_none(self):
        result = load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.trade_margins is None
        assert result.transport_margins is None
        assert result.product_taxes is None
        assert result.product_subsidies is None

    def test_integer_looking_column_name_read_as_string(self, tmp_path):
        df = pd.DataFrame({
            "column": ["2021", "nrnr", "trans", "brch", "bas", "koeb"],
            "role":   ["id", "product", "transaction", "category", "price_basic", "price_purchasers"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        result = load_metadata_columns_from_excel(path)
        assert result.id == "2021"
        assert isinstance(result.id, str)

    def test_strips_whitespace_from_role(self, tmp_path):
        df = pd.DataFrame({
            "column": ["year", "nrnr", "trans", "brch", "bas", "koeb"],
            "role":   ["id", "product ", "transaction", "category", "price_basic", "price_purchasers"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        result = load_metadata_columns_from_excel(path)
        assert result.product == "nrnr"

    def test_strips_whitespace_from_column(self, tmp_path):
        df = pd.DataFrame({
            "column": ["year", " nrnr", "trans", "brch", "bas", "koeb"],
            "role":   ["id", "product", "transaction", "category", "price_basic", "price_purchasers"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        result = load_metadata_columns_from_excel(path)
        assert result.product == "nrnr"

    def test_error_missing_role_header(self, tmp_path):
        df = pd.DataFrame({"column": ["nrnr"], "rol": ["product"]})
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        with pytest.raises(ValueError, match="'role'"):
            load_metadata_columns_from_excel(path)

    def test_error_missing_column_header(self, tmp_path):
        df = pd.DataFrame({"col": ["nrnr"], "role": ["product"]})
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        with pytest.raises(ValueError, match="'column'"):
            load_metadata_columns_from_excel(path)

    def test_error_unknown_role(self, tmp_path):
        df = pd.DataFrame({
            "column": ["year", "nrnr", "trans", "brch", "bas", "koeb", "xyz"],
            "role":   ["id", "product", "transaction", "category", "price_basic", "price_purchasers", "unknown_role"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        with pytest.raises(ValueError, match="unknown_role"):
            load_metadata_columns_from_excel(path)

    def test_error_duplicate_role(self, tmp_path):
        df = pd.DataFrame({
            "column": ["year", "nrnr", "nrnr2", "trans", "brch", "bas", "koeb"],
            "role":   ["id", "product", "product", "transaction", "category", "price_basic", "price_purchasers"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        with pytest.raises(ValueError, match="'product'.*more than once"):
            load_metadata_columns_from_excel(path)

    def test_error_missing_required_role(self, tmp_path):
        df = pd.DataFrame({
            "column": ["nrnr", "trans", "brch", "bas", "koeb"],
            "role":   ["product", "transaction", "category", "price_basic", "price_purchasers"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        with pytest.raises(ValueError, match="'id'"):
            load_metadata_columns_from_excel(path)

    def test_error_message_lists_all_missing_required_roles(self, tmp_path):
        df = pd.DataFrame({
            "column": ["bas", "koeb"],
            "role":   ["price_basic", "price_purchasers"],
        })
        path = tmp_path / "columns.xlsx"
        write_excel(path, df)
        with pytest.raises(ValueError, match="id") as exc_info:
            load_metadata_columns_from_excel(path)
        message = str(exc_info.value)
        assert "product" in message
        assert "transaction" in message
        assert "category" in message


# ---------------------------------------------------------------------------
# load_metadata_classifications_from_excel
# ---------------------------------------------------------------------------


class TestLoadMetadataClassificationsFromExcel:

    def test_returns_sut_classifications(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert isinstance(result, SUTClassifications)

    def test_classification_names_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.classification_names is not None
        assert list(result.classification_names.columns) == ["dimension", "classification"]

    def test_products_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.products is not None
        assert list(result.products.columns) == ["code", "name"]
        assert set(result.products["code"]) == {"A", "B", "C"}

    def test_transactions_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.transactions is not None
        assert list(result.transactions.columns) == ["code", "name"]

    def test_industries_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.industries is not None
        assert set(result.industries["code"]) == {"X", "Y"}

    def test_missing_sheet_gives_none(self, tmp_path):
        sheets = {
            "products": pd.DataFrame({"code": ["A"], "name": ["Product A"]}),
        }
        path = tmp_path / "classifications.xlsx"
        write_excel_multisheet(path, sheets)
        result = load_metadata_classifications_from_excel(path)
        assert result.transactions is None
        assert result.industries is None
        assert result.classification_names is None

    def test_unknown_sheets_are_ignored(self, tmp_path):
        sheets = {
            "products": pd.DataFrame({"code": ["A"], "name": ["Product A"]}),
            "my_extra_sheet": pd.DataFrame({"foo": [1]}),
        }
        path = tmp_path / "classifications.xlsx"
        write_excel_multisheet(path, sheets)
        result = load_metadata_classifications_from_excel(path)
        assert result.products is not None

    def test_strips_whitespace_from_values(self, tmp_path):
        sheets = {
            "products": pd.DataFrame({"code": [" A "], "name": ["Product A "]}),
        }
        path = tmp_path / "classifications.xlsx"
        write_excel_multisheet(path, sheets)
        result = load_metadata_classifications_from_excel(path)
        assert result.products["code"].iloc[0] == "A"
        assert result.products["name"].iloc[0] == "Product A"

    def test_error_sheet_missing_expected_column(self, tmp_path):
        sheets = {
            "products": pd.DataFrame({"code": ["A"], "naam": ["Product A"]}),
        }
        path = tmp_path / "classifications.xlsx"
        write_excel_multisheet(path, sheets)
        with pytest.raises(ValueError, match="'products'"):
            load_metadata_classifications_from_excel(path)

    def test_error_message_names_missing_column(self, tmp_path):
        sheets = {
            "products": pd.DataFrame({"code": ["A"], "naam": ["Product A"]}),
        }
        path = tmp_path / "classifications.xlsx"
        write_excel_multisheet(path, sheets)
        with pytest.raises(ValueError, match="'name'"):
            load_metadata_classifications_from_excel(path)

    def test_projected_to_expected_columns_only(self, tmp_path):
        sheets = {
            "products": pd.DataFrame({"code": ["A"], "name": ["Product A"], "extra": [99]}),
        }
        path = tmp_path / "classifications.xlsx"
        write_excel_multisheet(path, sheets)
        result = load_metadata_classifications_from_excel(path)
        assert list(result.products.columns) == ["code", "name"]


# ---------------------------------------------------------------------------
# load_metadata_from_excel
# ---------------------------------------------------------------------------


class TestLoadMetadataFromExcel:

    def test_returns_sut_metadata(self):
        result = load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)
        assert isinstance(result, SUTMetadata)

    def test_columns_loaded(self):
        result = load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)
        assert isinstance(result.columns, SUTColumns)
        assert result.columns.id == "year"

    def test_classifications_loaded_when_path_given(self):
        result = load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)
        assert isinstance(result.classifications, SUTClassifications)
        assert result.classifications.products is not None

    def test_classifications_none_when_path_omitted(self):
        result = load_metadata_from_excel(COLUMNS_FILE)
        assert result.classifications is None
