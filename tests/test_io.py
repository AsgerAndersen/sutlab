"""
Tests for I/O functions in sutlab.io.
"""

import re
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
# Helpers for writing minimal Excel files in tests
# ---------------------------------------------------------------------------

def write_columns_file(tmp_path: Path, rows: list[dict]) -> Path:
    """Write a columns Excel file from a list of row dicts and return its path."""
    path = tmp_path / "columns.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def write_classifications_file(
    tmp_path: Path, sheets: dict[str, pd.DataFrame]
) -> Path:
    """Write a multi-sheet classifications Excel file and return its path."""
    path = tmp_path / "classifications.xlsx"
    with pd.ExcelWriter(path) as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


def minimal_columns_rows() -> list[dict]:
    """Return a minimal valid set of column rows covering all required roles."""
    return [
        {"column": "year",  "role": "id"},
        {"column": "nrnr",  "role": "product"},
        {"column": "trans", "role": "transaction"},
        {"column": "brch",  "role": "category"},
        {"column": "bas",   "role": "price_basic"},
        {"column": "koeb",  "role": "price_purchasers"},
    ]


def minimal_transactions_df() -> pd.DataFrame:
    """Return a minimal valid transactions DataFrame with all required columns."""
    return pd.DataFrame({
        "code":  ["0100", "0700", "2000"],
        "name":  ["Output", "Imports", "Intermediate"],
        "table": ["supply", "supply", "use"],
    })


# ---------------------------------------------------------------------------
# Tests for load_metadata_columns_from_excel
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
        assert result.trade_margins == "ava"
        assert result.vat == "moms"

    def test_absent_optional_fields_are_none(self):
        result = load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.wholesale_margins is None
        assert result.retail_margins is None
        assert result.transport_margins is None
        assert result.product_taxes is None
        assert result.product_subsidies is None
        assert result.product_taxes_less_subsidies is None

    def test_integer_looking_column_name_read_as_string(self, tmp_path):
        rows = minimal_columns_rows()
        rows[0]["column"] = 2021  # year column as integer in Excel
        path = write_columns_file(tmp_path, rows)
        result = load_metadata_columns_from_excel(path)
        assert result.id == "2021"
        assert isinstance(result.id, str)

    def test_strips_whitespace_from_role(self, tmp_path):
        rows = minimal_columns_rows()
        rows[1]["role"] = "  product  "  # whitespace around role
        path = write_columns_file(tmp_path, rows)
        result = load_metadata_columns_from_excel(path)
        assert result.product == "nrnr"

    def test_strips_whitespace_from_column(self, tmp_path):
        rows = minimal_columns_rows()
        rows[1]["column"] = "  nrnr  "  # whitespace around column name
        path = write_columns_file(tmp_path, rows)
        result = load_metadata_columns_from_excel(path)
        assert result.product == "nrnr"

    def test_error_missing_role_header(self, tmp_path):
        path = tmp_path / "columns.xlsx"
        pd.DataFrame({"column": ["nrnr"], "rol": ["product"]}).to_excel(
            path, index=False
        )
        with pytest.raises(ValueError, match="'role'"):
            load_metadata_columns_from_excel(path)

    def test_error_missing_column_header(self, tmp_path):
        path = tmp_path / "columns.xlsx"
        pd.DataFrame({"col": ["nrnr"], "role": ["product"]}).to_excel(
            path, index=False
        )
        with pytest.raises(ValueError, match="'column'"):
            load_metadata_columns_from_excel(path)

    def test_error_unknown_role(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "x", "role": "made_up_role"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="made_up_role"):
            load_metadata_columns_from_excel(path)

    def test_error_unknown_role_lists_known_roles(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "x", "role": "made_up_role"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="price_basic"):
            load_metadata_columns_from_excel(path)

    def test_error_duplicate_role(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "other_year", "role": "id"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="'id'"):
            load_metadata_columns_from_excel(path)

    def test_error_duplicate_column_name(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "year", "role": "trade_margins"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="'year'"):
            load_metadata_columns_from_excel(path)

    def test_error_missing_required_role(self, tmp_path):
        rows = [r for r in minimal_columns_rows() if r["role"] != "id"]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="'id'"):
            load_metadata_columns_from_excel(path)

    def test_error_message_lists_all_missing_required_roles(self, tmp_path):
        # Only price_basic and price_purchasers present — four roles missing
        rows = [
            {"column": "bas",  "role": "price_basic"},
            {"column": "koeb", "role": "price_purchasers"},
        ]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError) as exc_info:
            load_metadata_columns_from_excel(path)
        message = str(exc_info.value)
        assert "id" in message
        assert "product" in message
        assert "transaction" in message
        assert "category" in message


# ---------------------------------------------------------------------------
# Tests for load_metadata_classifications_from_excel
# ---------------------------------------------------------------------------

class TestLoadMetadataClassificationsFromExcel:

    def test_returns_sut_classifications(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert isinstance(result, SUTClassifications)

    def test_classification_names_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.classification_names is not None
        assert "dimension" in result.classification_names.columns
        assert "classification" in result.classification_names.columns

    def test_products_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.products is not None
        assert set(result.products["code"]) == {"A", "B", "C", "T"}

    def test_transactions_loaded_with_table_column(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.transactions is not None
        assert "code" in result.transactions.columns
        assert "name" in result.transactions.columns
        assert "table" in result.transactions.columns

    def test_transactions_table_values_are_supply_or_use(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert set(result.transactions["table"]).issubset({"supply", "use"})

    def test_supply_transaction_codes_correct(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        supply_codes = set(
            result.transactions.loc[
                result.transactions["table"] == "supply", "code"
            ]
        )
        assert supply_codes == {"0100", "0700"}

    def test_industries_loaded(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.industries is not None
        assert set(result.industries["code"]) == {"X", "Y", "Z"}

    def test_absent_sheet_gives_none(self, tmp_path):
        # File with only transactions — everything else should be None
        path = write_classifications_file(
            tmp_path, {"transactions": minimal_transactions_df()}
        )
        result = load_metadata_classifications_from_excel(path)
        assert result.classification_names is None
        assert result.products is None
        assert result.industries is None
        assert result.individual_consumption is None
        assert result.collective_consumption is None

    def test_unknown_sheets_are_ignored(self, tmp_path):
        path = write_classifications_file(tmp_path, {
            "transactions": minimal_transactions_df(),
            "my_custom_sheet": pd.DataFrame({"x": [1]}),
        })
        result = load_metadata_classifications_from_excel(path)
        assert result.transactions is not None

    def test_extra_columns_in_sheet_are_kept(self, tmp_path):
        # Extra columns beyond the required ones should not be dropped
        products = pd.DataFrame({
            "code": ["A"], "name": ["Product A"], "extra_col": [99]
        })
        path = write_classifications_file(tmp_path, {"transactions": minimal_transactions_df(), "products": products})
        result = load_metadata_classifications_from_excel(path)
        assert "extra_col" in result.products.columns

    def test_strips_whitespace_from_all_sheets(self, tmp_path):
        transactions = pd.DataFrame({
            "code":  ["  0100  "],
            "name":  ["  Output  "],
            "table": ["  supply  "],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        result = load_metadata_classifications_from_excel(path)
        assert result.transactions["code"].iloc[0] == "0100"
        assert result.transactions["table"].iloc[0] == "supply"

    def test_error_transactions_missing_table_column(self, tmp_path):
        transactions = pd.DataFrame({"code": ["0100"], "name": ["Output"]})
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'table'"):
            load_metadata_classifications_from_excel(path)

    def test_error_invalid_table_value(self, tmp_path):
        transactions = pd.DataFrame({
            "code":  ["0100", "2000"],
            "name":  ["Output", "Intermediate"],
            "table": ["supply", "wrong"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'wrong'"):
            load_metadata_classifications_from_excel(path)

    def test_error_invalid_table_value_lists_valid_values(self, tmp_path):
        transactions = pd.DataFrame({
            "code":  ["0100"],
            "name":  ["Output"],
            "table": ["typo"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="supply"):
            load_metadata_classifications_from_excel(path)

    def test_error_sheet_missing_required_column(self, tmp_path):
        path = write_classifications_file(tmp_path, {
            "products": pd.DataFrame({"code": ["A"]}),  # missing 'name'
        })
        with pytest.raises(ValueError, match="'name'"):
            load_metadata_classifications_from_excel(path)

    def test_error_message_names_the_offending_sheet(self, tmp_path):
        path = write_classifications_file(tmp_path, {
            "products": pd.DataFrame({"code": ["A"]}),  # missing 'name'
        })
        with pytest.raises(ValueError, match="'products'"):
            load_metadata_classifications_from_excel(path)


# ---------------------------------------------------------------------------
# Tests for load_metadata_from_excel
# ---------------------------------------------------------------------------

class TestLoadMetadataFromExcel:

    def test_returns_sut_metadata(self):
        result = load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)
        assert isinstance(result, SUTMetadata)

    def test_columns_populated(self):
        result = load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)
        assert isinstance(result.columns, SUTColumns)
        assert result.columns.id == "year"

    def test_classifications_populated(self):
        result = load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)
        assert isinstance(result.classifications, SUTClassifications)
        assert result.classifications.transactions is not None

    def test_error_if_transactions_sheet_absent(self, tmp_path):
        classifications_path = write_classifications_file(
            tmp_path,
            {"products": pd.DataFrame({"code": ["A"], "name": ["Product A"]})},
        )
        with pytest.raises(ValueError, match="'transactions'"):
            load_metadata_from_excel(COLUMNS_FILE, classifications_path)

    def test_error_for_missing_transactions_sheet_mentions_file(self, tmp_path):
        classifications_path = write_classifications_file(
            tmp_path,
            {"products": pd.DataFrame({"code": ["A"], "name": ["Product A"]})},
        )
        with pytest.raises(ValueError, match=re.escape(str(classifications_path))):
            load_metadata_from_excel(COLUMNS_FILE, classifications_path)
