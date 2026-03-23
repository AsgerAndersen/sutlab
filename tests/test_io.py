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
    load_sut_from_parquet,
)
from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata


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


# ---------------------------------------------------------------------------
# Tests for load_sut_from_parquet
# ---------------------------------------------------------------------------

PARQUET_FILE = FIXTURES / "ta_l_2021.parquet"


class TestLoadSutFromParquet:

    @pytest.fixture
    def metadata(self):
        return load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)

    def test_returns_sut(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert isinstance(result, SUT)

    def test_price_basis_set(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert result.price_basis == "current_year"

    def test_metadata_attached(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert result.metadata is metadata

    def test_balancing_id_is_none(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert result.balancing_id is None

    def test_supply_has_correct_columns(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert list(result.supply.columns) == ["year", "nrnr", "trans", "brch", "bas"]

    def test_use_has_correct_columns(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert list(result.use.columns) == ["year", "nrnr", "trans", "brch", "bas", "ava", "moms", "koeb"]

    def test_supply_contains_only_supply_transactions(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert set(result.supply["trans"].unique()) == {"0100", "0700"}

    def test_use_contains_only_use_transactions(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert set(result.use["trans"].unique()) == {"2000", "3110", "3200", "5139", "5200", "6001"}

    def test_supply_row_count(self, metadata):
        # 5 output rows (A/X, B/X, B/Y, C/Y, T/Z) + 3 import rows = 8
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert len(result.supply) == 8

    def test_use_row_count(self, metadata):
        # 6 intermediate + 3 household + 3 government + 3 gfcf + 3 inventories + 3 exports = 21
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert len(result.use) == 21

    def test_id_column_populated(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert (result.supply["year"] == 2021).all()
        assert (result.use["year"] == 2021).all()

    def test_id_value_type_preserved(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert result.supply["year"].dtype == int or result.supply["year"].iloc[0] == 2021

    def test_string_id_value_preserved(self, metadata):
        result = load_sut_from_parquet(["2021"], [PARQUET_FILE], metadata, "current_year")
        assert result.supply["year"].iloc[0] == "2021"

    def test_product_column_is_str(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert pd.api.types.is_string_dtype(result.supply["nrnr"])
        assert pd.api.types.is_string_dtype(result.use["nrnr"])

    def test_transaction_column_is_str(self, metadata):
        result = load_sut_from_parquet([2021], [PARQUET_FILE], metadata, "current_year")
        assert pd.api.types.is_string_dtype(result.supply["trans"])
        assert pd.api.types.is_string_dtype(result.use["trans"])

    def test_multiple_years_concatenated(self, metadata):
        # Load the same file twice with different id values — simulates two years
        result = load_sut_from_parquet(
            [2021, 2022], [PARQUET_FILE, PARQUET_FILE], metadata, "current_year"
        )
        assert set(result.supply["year"].unique()) == {2021, 2022}
        assert set(result.use["year"].unique()) == {2021, 2022}
        assert len(result.supply) == 16
        assert len(result.use) == 42

    def test_error_mismatched_lengths(self, metadata):
        with pytest.raises(ValueError, match="same length"):
            load_sut_from_parquet([2021, 2022], [PARQUET_FILE], metadata, "current_year")

    def test_error_missing_classifications(self, tmp_path, metadata):
        # metadata without classifications
        bare_metadata = SUTMetadata(columns=metadata.columns)
        with pytest.raises(ValueError, match="transactions"):
            load_sut_from_parquet([2021], [PARQUET_FILE], bare_metadata, "current_year")

    def test_error_unknown_transaction_code(self, tmp_path, metadata):
        # Write a parquet file with an unknown transaction code
        df = pd.read_parquet(PARQUET_FILE)
        df.loc[df["trans"] == "0100", "trans"] = "ZZZZ"
        bad_parquet = tmp_path / "bad.parquet"
        df.to_parquet(bad_parquet, index=False)
        with pytest.raises(ValueError, match="ZZZZ"):
            load_sut_from_parquet([2021], [bad_parquet], metadata, "current_year")

    def test_error_unknown_transaction_code_lists_known_codes(self, tmp_path, metadata):
        df = pd.read_parquet(PARQUET_FILE)
        df.loc[df["trans"] == "0100", "trans"] = "ZZZZ"
        bad_parquet = tmp_path / "bad.parquet"
        df.to_parquet(bad_parquet, index=False)
        with pytest.raises(ValueError, match="0700"):
            load_sut_from_parquet([2021], [bad_parquet], metadata, "current_year")
