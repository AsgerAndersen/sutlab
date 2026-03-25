"""
Tests for I/O functions in sutlab.io.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from sutlab.io import (
    load_balancing_targets_from_excel,
    load_metadata_classifications_from_excel,
    load_metadata_columns_from_excel,
    load_metadata_from_excel,
    load_sut_from_parquet,
)
from sutlab.sut import BalancingTargets, SUT, SUTClassifications, SUTColumns, SUTMetadata


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
        "code":     ["0100",   "0700", "2000"],
        "name":     ["Output", "Imports", "Intermediate"],
        "table":    ["supply", "supply", "use"],
        "esa_code": ["P1",     "P7",    "P2"],
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

    def test_transactions_loaded_with_required_columns(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        assert result.transactions is not None
        assert "code" in result.transactions.columns
        assert "name" in result.transactions.columns
        assert "table" in result.transactions.columns
        assert "esa_code" in result.transactions.columns

    def test_transactions_esa_code_values_are_valid(self):
        result = load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE)
        valid = {"P1", "P2", "P3", "P31", "P32", "P51g", "P52", "P53", "P6", "P7"}
        assert set(result.transactions["esa_code"]).issubset(valid)

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
            "code":     ["  0100  "],
            "name":     ["  Output  "],
            "table":    ["  supply  "],
            "esa_code": ["  P1  "],
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
            "code":     ["0100",   "2000"],
            "name":     ["Output", "Intermediate"],
            "table":    ["supply", "wrong"],
            "esa_code": ["P1",     "P2"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'wrong'"):
            load_metadata_classifications_from_excel(path)

    def test_error_invalid_table_value_lists_valid_values(self, tmp_path):
        transactions = pd.DataFrame({
            "code":     ["0100"],
            "name":     ["Output"],
            "table":    ["typo"],
            "esa_code": ["P1"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="supply"):
            load_metadata_classifications_from_excel(path)

    def test_error_transactions_missing_esa_code_column(self, tmp_path):
        transactions = pd.DataFrame({
            "code":  ["0100"],
            "name":  ["Output"],
            "table": ["supply"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'esa_code'"):
            load_metadata_classifications_from_excel(path)

    def test_error_invalid_esa_code_value(self, tmp_path):
        transactions = pd.DataFrame({
            "code":     ["0100"],
            "name":     ["Output"],
            "table":    ["supply"],
            "esa_code": ["WRONG"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'WRONG'"):
            load_metadata_classifications_from_excel(path)

    def test_error_invalid_esa_code_lists_valid_values(self, tmp_path):
        transactions = pd.DataFrame({
            "code":     ["0100"],
            "name":     ["Output"],
            "table":    ["supply"],
            "esa_code": ["WRONG"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="P1"):
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


# ---------------------------------------------------------------------------
# Tests for target role in load_metadata_columns_from_excel
# ---------------------------------------------------------------------------

class TestLoadMetadataColumnsTargetRole:

    def test_target_field_loaded_from_fixture(self):
        result = load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.target == "maal"

    def test_target_field_is_none_when_absent(self, tmp_path):
        path = write_columns_file(tmp_path, minimal_columns_rows())
        result = load_metadata_columns_from_excel(path)
        assert result.target is None


# ---------------------------------------------------------------------------
# Tests for load_balancing_targets_from_excel
# ---------------------------------------------------------------------------

TARGETS_FILE = FIXTURES / "ta_targets_2021.xlsx"
TOLERANCES_FILE = FIXTURES / "ta_tolerances.xlsx"


def write_targets_file(tmp_path: Path, rows: list[dict], filename="targets.xlsx") -> Path:
    """Write a targets Excel file from a list of row dicts and return its path."""
    path = tmp_path / filename
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def minimal_targets_rows() -> list[dict]:
    """Minimal valid targets covering one supply and one use row (no id column)."""
    return [
        {"trans": "0100", "brch": "X",  "maal": 202},
        {"trans": "2000", "brch": "X",  "maal": 64},
    ]


class TestLoadBalancingTargetsFromExcel:

    @pytest.fixture
    def metadata(self):
        return load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)

    def test_returns_balancing_targets(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert isinstance(result, BalancingTargets)

    def test_supply_and_use_are_dataframes(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert isinstance(result.supply, pd.DataFrame)
        assert isinstance(result.use, pd.DataFrame)

    def test_supply_contains_only_supply_transactions(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert set(result.supply["trans"].unique()) == {"0100", "0700"}

    def test_use_contains_only_use_transactions(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert set(result.use["trans"].unique()) == {"2000", "3110", "3200", "5139", "5200", "6001"}

    def test_supply_row_count(self, metadata):
        # 0100/X, 0100/Y, 0100/Z, 0700/""
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert len(result.supply) == 4

    def test_use_row_count(self, metadata):
        # 2000/X, 2000/Y, 3110/HH, 3200/GOV, 5139/"", 5200/"", 6001/""
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert len(result.use) == 7

    def test_column_order(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert list(result.supply.columns) == ["year", "trans", "brch", "maal"]
        assert list(result.use.columns) == ["year", "trans", "brch", "maal"]

    def test_id_column_populated(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert (result.supply["year"] == 2021).all()
        assert (result.use["year"] == 2021).all()

    def test_id_value_type_preserved(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert result.supply["year"].iloc[0] == 2021

    def test_string_id_value_preserved(self, metadata):
        result = load_balancing_targets_from_excel(["2021"], [TARGETS_FILE], metadata)
        assert result.supply["year"].iloc[0] == "2021"

    def test_multiple_years_concatenated(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021, 2022], [TARGETS_FILE, TARGETS_FILE], metadata
        )
        assert set(result.supply["year"].unique()) == {2021, 2022}
        assert set(result.use["year"].unique()) == {2021, 2022}
        assert len(result.supply) == 8
        assert len(result.use) == 14

    def test_transaction_codes_preserve_leading_zeros(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert "0100" in result.supply["trans"].values
        assert "0700" in result.supply["trans"].values

    def test_empty_category_filled_with_empty_string(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        imports = result.supply[result.supply["trans"] == "0700"]
        assert imports["brch"].iloc[0] == ""

    def test_target_column_is_numeric(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert pd.api.types.is_numeric_dtype(result.supply["maal"])
        assert pd.api.types.is_numeric_dtype(result.use["maal"])

    def test_target_values_correct(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        supply_0100_x = result.supply[
            (result.supply["trans"] == "0100") & (result.supply["brch"] == "X")
        ]["maal"].iloc[0]
        assert supply_0100_x == 202

    def test_error_mismatched_lengths(self, metadata):
        with pytest.raises(ValueError, match="same length"):
            load_balancing_targets_from_excel([2021, 2022], [TARGETS_FILE], metadata)

    def test_error_when_target_role_not_set(self, metadata):
        bare_columns = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
        )
        bare_metadata = SUTMetadata(columns=bare_columns, classifications=metadata.classifications)
        with pytest.raises(ValueError, match="target"):
            load_balancing_targets_from_excel([2021], [TARGETS_FILE], bare_metadata)

    def test_error_when_classifications_absent(self, metadata):
        bare_metadata = SUTMetadata(columns=metadata.columns)
        with pytest.raises(ValueError, match="transactions"):
            load_balancing_targets_from_excel([2021], [TARGETS_FILE], bare_metadata)

    def test_error_missing_required_column(self, tmp_path, metadata):
        path = write_targets_file(tmp_path, [{"trans": "0100", "maal": 202}])
        with pytest.raises(ValueError, match="brch"):
            load_balancing_targets_from_excel([2021], [path], metadata)

    def test_error_unknown_transaction_code(self, tmp_path, metadata):
        rows = minimal_targets_rows() + [{"trans": "ZZZZ", "brch": "X", "maal": 10}]
        path = write_targets_file(tmp_path, rows)
        with pytest.raises(ValueError, match="ZZZZ"):
            load_balancing_targets_from_excel([2021], [path], metadata)

    def test_tolerances_none_when_path_not_provided(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert result.tolerances_trans is None
        assert result.tolerances_trans_cat is None

    def test_tolerances_loaded_when_path_provided(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=TOLERANCES_FILE
        )
        assert result.tolerances_trans is not None
        assert result.tolerances_trans_cat is not None

    def test_tolerances_trans_has_correct_columns(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=TOLERANCES_FILE
        )
        assert list(result.tolerances_trans.columns) == ["trans", "rel", "abs"]

    def test_tolerances_trans_cat_has_correct_columns(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=TOLERANCES_FILE
        )
        assert list(result.tolerances_trans_cat.columns) == ["trans", "brch", "rel", "abs"]

    def test_tolerances_trans_covers_all_transactions(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=TOLERANCES_FILE
        )
        assert set(result.tolerances_trans["trans"]) == {
            "0100", "0700", "2000", "3110", "3200", "5139", "5200", "6001"
        }

    def test_tolerances_trans_cat_covers_only_some_combinations(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=TOLERANCES_FILE
        )
        assert len(result.tolerances_trans_cat) == 3

    def test_tolerances_numeric_columns(self, metadata):
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=TOLERANCES_FILE
        )
        assert pd.api.types.is_numeric_dtype(result.tolerances_trans["rel"])
        assert pd.api.types.is_numeric_dtype(result.tolerances_trans["abs"])
        assert pd.api.types.is_numeric_dtype(result.tolerances_trans_cat["rel"])
        assert pd.api.types.is_numeric_dtype(result.tolerances_trans_cat["abs"])

    def test_tolerances_trans_cat_none_when_sheet_absent(self, tmp_path, metadata):
        # Write a tolerances file with only the transactions sheet
        path = tmp_path / "tolerances_no_cat.xlsx"
        tol_trans = pd.DataFrame({
            "trans": ["0100", "0700", "2000", "3110", "3200", "5139", "5200", "6001"],
            "rel": [0.02] * 8,
            "abs": [5.0] * 8,
        })
        with pd.ExcelWriter(path) as writer:
            tol_trans.to_excel(writer, sheet_name="transactions", index=False)
        result = load_balancing_targets_from_excel(
            [2021], [TARGETS_FILE], metadata, tolerances_path=path
        )
        assert result.tolerances_trans is not None
        assert result.tolerances_trans_cat is None

    def test_error_tolerances_missing_transactions_sheet(self, tmp_path, metadata):
        path = tmp_path / "bad_tolerances.xlsx"
        pd.DataFrame({"trans": ["0100"], "brch": ["X"], "rel": [0.01], "abs": [3.0]}).to_excel(
            path, sheet_name="categories", index=False
        )
        with pytest.raises(ValueError, match="'transactions'"):
            load_balancing_targets_from_excel(
                [2021], [TARGETS_FILE], metadata, tolerances_path=path
            )

    def test_error_tolerances_trans_missing_column(self, tmp_path, metadata):
        path = tmp_path / "bad_tolerances.xlsx"
        pd.DataFrame({"trans": ["0100"], "rel": [0.02]}).to_excel(  # missing abs
            path, sheet_name="transactions", index=False
        )
        with pytest.raises(ValueError, match="abs"):
            load_balancing_targets_from_excel(
                [2021], [TARGETS_FILE], metadata, tolerances_path=path
            )
