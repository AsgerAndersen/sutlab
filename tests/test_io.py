"""
Tests for I/O functions in sutlab.io.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from sutlab.io import (
    _load_metadata_classifications_from_excel,
    _load_metadata_columns_from_excel,
    load_balancing_config_from_excel,
    load_balancing_targets_from_excel,
    load_metadata_from_excel,
    load_sut_from_parquet,
)
from sutlab.sut import (
    BalancingConfig,
    BalancingTargets,
    Locks,
    SUT,
    SUTClassifications,
    SUTColumns,
    SUTMetadata,
    TargetTolerances,
)


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


def minimal_columns() -> SUTColumns:
    """Return a SUTColumns matching minimal_columns_rows()."""
    return SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
    )


def minimal_transactions_df() -> pd.DataFrame:
    """Return a minimal valid transactions DataFrame with all required columns."""
    return pd.DataFrame({
        "trans":     ["0100",   "0700", "2000"],
        "trans_txt": ["Output", "Imports", "Intermediate"],
        "table":     ["supply", "supply", "use"],
        "esa_code":  ["P1",     "P7",    "P2"],
    })


# ---------------------------------------------------------------------------
# Tests for _load_metadata_columns_from_excel
# ---------------------------------------------------------------------------

class TestLoadMetadataColumnsFromExcel:

    def test_returns_sut_columns(self):
        result = _load_metadata_columns_from_excel(COLUMNS_FILE)
        assert isinstance(result, SUTColumns)

    def test_required_fields_loaded_correctly(self):
        result = _load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.id == "year"
        assert result.product == "nrnr"
        assert result.transaction == "trans"
        assert result.category == "brch"
        assert result.price_basic == "bas"
        assert result.price_purchasers == "koeb"

    def test_optional_fields_loaded_correctly(self):
        result = _load_metadata_columns_from_excel(COLUMNS_FILE)
        assert result.trade_margins == "ava"
        assert result.vat == "moms"

    def test_absent_optional_fields_are_none(self):
        result = _load_metadata_columns_from_excel(COLUMNS_FILE)
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
        result = _load_metadata_columns_from_excel(path)
        assert result.id == "2021"
        assert isinstance(result.id, str)

    def test_strips_whitespace_from_role(self, tmp_path):
        rows = minimal_columns_rows()
        rows[1]["role"] = "  product  "  # whitespace around role
        path = write_columns_file(tmp_path, rows)
        result = _load_metadata_columns_from_excel(path)
        assert result.product == "nrnr"

    def test_strips_whitespace_from_column(self, tmp_path):
        rows = minimal_columns_rows()
        rows[1]["column"] = "  nrnr  "  # whitespace around column name
        path = write_columns_file(tmp_path, rows)
        result = _load_metadata_columns_from_excel(path)
        assert result.product == "nrnr"

    def test_error_missing_role_header(self, tmp_path):
        path = tmp_path / "columns.xlsx"
        pd.DataFrame({"column": ["nrnr"], "rol": ["product"]}).to_excel(
            path, index=False
        )
        with pytest.raises(ValueError, match="'role'"):
            _load_metadata_columns_from_excel(path)

    def test_error_missing_column_header(self, tmp_path):
        path = tmp_path / "columns.xlsx"
        pd.DataFrame({"col": ["nrnr"], "role": ["product"]}).to_excel(
            path, index=False
        )
        with pytest.raises(ValueError, match="'column'"):
            _load_metadata_columns_from_excel(path)

    def test_error_unknown_role(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "x", "role": "made_up_role"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="made_up_role"):
            _load_metadata_columns_from_excel(path)

    def test_error_unknown_role_lists_known_roles(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "x", "role": "made_up_role"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="price_basic"):
            _load_metadata_columns_from_excel(path)

    def test_error_duplicate_role(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "other_year", "role": "id"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="'id'"):
            _load_metadata_columns_from_excel(path)

    def test_error_duplicate_column_name(self, tmp_path):
        rows = minimal_columns_rows() + [{"column": "year", "role": "trade_margins"}]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="'year'"):
            _load_metadata_columns_from_excel(path)

    def test_error_missing_required_role(self, tmp_path):
        rows = [r for r in minimal_columns_rows() if r["role"] != "id"]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError, match="'id'"):
            _load_metadata_columns_from_excel(path)

    def test_error_message_lists_all_missing_required_roles(self, tmp_path):
        # Only price_basic and price_purchasers present — four roles missing
        rows = [
            {"column": "bas",  "role": "price_basic"},
            {"column": "koeb", "role": "price_purchasers"},
        ]
        path = write_columns_file(tmp_path, rows)
        with pytest.raises(ValueError) as exc_info:
            _load_metadata_columns_from_excel(path)
        message = str(exc_info.value)
        assert "id" in message
        assert "product" in message
        assert "transaction" in message
        assert "category" in message


# ---------------------------------------------------------------------------
# Tests for _load_metadata_classifications_from_excel
# ---------------------------------------------------------------------------

class TestLoadMetadataClassificationsFromExcel:

    def test_returns_sut_classifications(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        assert isinstance(result, SUTClassifications)

    def test_classification_names_loaded(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        assert result.classification_names is not None
        assert "dimension" in result.classification_names.columns
        assert "classification" in result.classification_names.columns

    def test_products_loaded(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        assert result.products is not None
        assert set(result.products["nrnr"]) == {"A", "B", "C", "T"}

    def test_transactions_loaded_with_required_columns(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        assert result.transactions is not None
        assert "trans" in result.transactions.columns
        assert "trans_txt" in result.transactions.columns
        assert "table" in result.transactions.columns
        assert "esa_code" in result.transactions.columns

    def test_transactions_esa_code_values_are_valid(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        valid = {"D2121", "P1", "P2", "P3", "P31", "P32", "P51g", "P52", "P53", "P6", "P7"}
        assert set(result.transactions["esa_code"]).issubset(valid)

    def test_transactions_table_values_are_supply_or_use(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        assert set(result.transactions["table"]).issubset({"supply", "use"})

    def test_supply_transaction_codes_correct(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        supply_codes = set(
            result.transactions.loc[
                result.transactions["table"] == "supply", "trans"
            ]
        )
        assert supply_codes == {"0100", "0700"}

    def test_industries_loaded(self):
        result = _load_metadata_classifications_from_excel(CLASSIFICATIONS_FILE, minimal_columns())
        assert result.industries is not None
        assert set(result.industries["brch"]) == {"X", "Y", "Z"}

    def test_absent_sheet_gives_none(self, tmp_path):
        # File with only transactions — everything else should be None
        path = write_classifications_file(
            tmp_path, {"transactions": minimal_transactions_df()}
        )
        result = _load_metadata_classifications_from_excel(path, minimal_columns())
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
        result = _load_metadata_classifications_from_excel(path, minimal_columns())
        assert result.transactions is not None

    def test_extra_columns_in_sheet_are_ignored(self, tmp_path):
        # Extra columns beyond the required ones are silently dropped
        products = pd.DataFrame({
            "nrnr": ["A"], "nrnr_txt": ["Product A"], "extra_col": [99]
        })
        path = write_classifications_file(tmp_path, {"transactions": minimal_transactions_df(), "products": products})
        result = _load_metadata_classifications_from_excel(path, minimal_columns())
        assert "extra_col" not in result.products.columns
        assert list(result.products.columns) == ["nrnr", "nrnr_txt"]

    def test_strips_whitespace_from_all_sheets(self, tmp_path):
        transactions = pd.DataFrame({
            "trans":     ["  0100  "],
            "trans_txt": ["  Output  "],
            "table":     ["  supply  "],
            "esa_code":  ["  P1  "],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        result = _load_metadata_classifications_from_excel(path, minimal_columns())
        assert result.transactions["trans"].iloc[0] == "0100"
        assert result.transactions["table"].iloc[0] == "supply"

    def test_error_transactions_missing_table_column(self, tmp_path):
        transactions = pd.DataFrame({"trans": ["0100"], "trans_txt": ["Output"]})
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'table'"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_invalid_table_value(self, tmp_path):
        transactions = pd.DataFrame({
            "trans":     ["0100",   "2000"],
            "trans_txt": ["Output", "Intermediate"],
            "table":     ["supply", "wrong"],
            "esa_code":  ["P1",     "P2"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'wrong'"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_invalid_table_value_lists_valid_values(self, tmp_path):
        transactions = pd.DataFrame({
            "trans":     ["0100"],
            "trans_txt": ["Output"],
            "table":     ["typo"],
            "esa_code":  ["P1"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="supply"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_transactions_missing_esa_code_column(self, tmp_path):
        transactions = pd.DataFrame({
            "trans":     ["0100"],
            "trans_txt": ["Output"],
            "table":     ["supply"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'esa_code'"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_invalid_esa_code_value(self, tmp_path):
        transactions = pd.DataFrame({
            "trans":     ["0100"],
            "trans_txt": ["Output"],
            "table":     ["supply"],
            "esa_code":  ["WRONG"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="'WRONG'"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_invalid_esa_code_lists_valid_values(self, tmp_path):
        transactions = pd.DataFrame({
            "trans":     ["0100"],
            "trans_txt": ["Output"],
            "table":     ["supply"],
            "esa_code":  ["WRONG"],
        })
        path = write_classifications_file(tmp_path, {"transactions": transactions})
        with pytest.raises(ValueError, match="P1"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_sheet_missing_required_column(self, tmp_path):
        path = write_classifications_file(tmp_path, {
            "products": pd.DataFrame({"nrnr": ["A"]}),  # missing 'nrnr_txt'
        })
        with pytest.raises(ValueError, match="'nrnr_txt'"):
            _load_metadata_classifications_from_excel(path, minimal_columns())

    def test_error_message_names_the_offending_sheet(self, tmp_path):
        path = write_classifications_file(tmp_path, {
            "products": pd.DataFrame({"nrnr": ["A"]}),  # missing 'nrnr_txt'
        })
        with pytest.raises(ValueError, match="'products'"):
            _load_metadata_classifications_from_excel(path, minimal_columns())


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
            {"products": pd.DataFrame({"nrnr": ["A"], "nrnr_txt": ["Product A"]})},
        )
        with pytest.raises(ValueError, match="'transactions'"):
            load_metadata_from_excel(COLUMNS_FILE, classifications_path)

    def test_error_for_missing_transactions_sheet_mentions_file(self, tmp_path):
        classifications_path = write_classifications_file(
            tmp_path,
            {"products": pd.DataFrame({"nrnr": ["A"], "nrnr_txt": ["Product A"]})},
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
# Tests for load_balancing_targets_from_excel
# ---------------------------------------------------------------------------

TARGETS_FILE = FIXTURES / "ta_targets_2021.xlsx"


def write_targets_file(tmp_path: Path, rows: list[dict], filename="targets.xlsx") -> Path:
    """Write a targets Excel file from a list of row dicts and return its path."""
    path = tmp_path / filename
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


NAN = float("nan")


def minimal_targets_rows() -> list[dict]:
    """Minimal valid targets: one supply row and one use row.

    Mirrors the fixture metadata columns: trans, brch, bas, ava, moms, koeb.
    Supply rows have bas non-NaN; use rows have koeb non-NaN.
    """
    return [
        {"trans": "0100", "brch": "X",  "bas": 202, "ava": NAN, "moms": NAN, "koeb": NAN},
        {"trans": "2000", "brch": "X",  "bas": NAN, "ava": NAN, "moms": NAN, "koeb":  64},
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

    def test_supply_column_order(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert list(result.supply.columns) == ["year", "trans", "brch", "bas"]

    def test_use_column_order(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert list(result.use.columns) == ["year", "trans", "brch", "bas", "ava", "moms", "koeb"]

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

    def test_price_columns_are_numeric(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert pd.api.types.is_numeric_dtype(result.supply["bas"])
        assert pd.api.types.is_numeric_dtype(result.use["koeb"])

    def test_supply_target_values_correct(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        supply_0100_x = result.supply[
            (result.supply["trans"] == "0100") & (result.supply["brch"] == "X")
        ]["bas"].iloc[0]
        assert supply_0100_x == 202

    def test_use_target_values_correct(self, metadata):
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        use_2000_x = result.use[
            (result.use["trans"] == "2000") & (result.use["brch"] == "X")
        ]["koeb"].iloc[0]
        assert use_2000_x == 64

    def test_supply_nontargeted_price_columns_are_nan(self, metadata):
        # Supply rows: only bas carries a target; ava, moms, koeb are not in supply output
        # (supply output is id, trans, brch, bas only — layers are excluded)
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        assert "ava" not in result.supply.columns
        assert "koeb" not in result.supply.columns

    def test_use_nontargeted_price_columns_are_nan(self, metadata):
        # Use rows: only koeb carries a target; bas, ava, moms are NaN in the fixture
        result = load_balancing_targets_from_excel([2021], [TARGETS_FILE], metadata)
        use_2000_x = result.use[
            (result.use["trans"] == "2000") & (result.use["brch"] == "X")
        ]
        assert pd.isna(use_2000_x["bas"].iloc[0])
        assert pd.isna(use_2000_x["ava"].iloc[0])

    def test_error_mismatched_lengths(self, metadata):
        with pytest.raises(ValueError, match="same length"):
            load_balancing_targets_from_excel([2021, 2022], [TARGETS_FILE], metadata)

    def test_error_when_classifications_absent(self, metadata):
        bare_metadata = SUTMetadata(columns=metadata.columns)
        with pytest.raises(ValueError, match="transactions"):
            load_balancing_targets_from_excel([2021], [TARGETS_FILE], bare_metadata)

    def test_error_missing_required_column(self, tmp_path, metadata):
        # File missing brch (category column)
        path = write_targets_file(tmp_path, [
            {"trans": "0100", "bas": 202, "ava": NAN, "moms": NAN, "koeb": NAN}
        ])
        with pytest.raises(ValueError, match="brch"):
            load_balancing_targets_from_excel([2021], [path], metadata)

    def test_error_missing_price_column(self, tmp_path, metadata):
        # File missing koeb (price_purchasers column)
        path = write_targets_file(tmp_path, [
            {"trans": "0100", "brch": "X", "bas": 202, "ava": NAN, "moms": NAN}
        ])
        with pytest.raises(ValueError, match="koeb"):
            load_balancing_targets_from_excel([2021], [path], metadata)

    def test_error_unknown_transaction_code(self, tmp_path, metadata):
        rows = minimal_targets_rows() + [
            {"trans": "ZZZZ", "brch": "X", "bas": NAN, "ava": NAN, "moms": NAN, "koeb": 10}
        ]
        path = write_targets_file(tmp_path, rows)
        with pytest.raises(ValueError, match="ZZZZ"):
            load_balancing_targets_from_excel([2021], [path], metadata)


# ---------------------------------------------------------------------------
# Tests for load_balancing_config_from_excel
# ---------------------------------------------------------------------------

TOLERANCES_FILE = FIXTURES / "ta_tolerances.xlsx"
LOCKS_FILE = FIXTURES / "balancing_locks.xlsx"


def write_tolerances_file(
    tmp_path: Path, sheets: dict[str, pd.DataFrame], filename="tolerances.xlsx"
) -> Path:
    """Write a tolerances Excel file from a dict of sheet DataFrames."""
    path = tmp_path / filename
    with pd.ExcelWriter(path) as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


def write_locks_file(
    tmp_path: Path, sheets: dict[str, pd.DataFrame], filename="locks.xlsx"
) -> Path:
    """Write a locks Excel file from a dict of sheet DataFrames."""
    path = tmp_path / filename
    with pd.ExcelWriter(path) as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


class TestLoadBalancingConfigFromExcel:

    @pytest.fixture
    def metadata(self):
        return load_metadata_from_excel(COLUMNS_FILE, CLASSIFICATIONS_FILE)

    # --- return types ---

    def test_returns_balancing_config(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert isinstance(result, BalancingConfig)

    def test_tolerances_only_locks_is_none(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert result.locks is None

    def test_locks_only_tolerances_is_none(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, locks_path=LOCKS_FILE
        )
        assert result.target_tolerances is None

    def test_both_paths_both_fields_populated(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE, locks_path=LOCKS_FILE
        )
        assert result.target_tolerances is not None
        assert result.locks is not None

    def test_error_if_no_paths_provided(self, metadata):
        with pytest.raises(ValueError, match="tolerances_path"):
            load_balancing_config_from_excel(metadata)

    # --- tolerances ---

    def test_tolerances_returns_target_tolerances(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert isinstance(result.target_tolerances, TargetTolerances)

    def test_tolerances_trans_loaded(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert result.target_tolerances.transactions is not None
        assert set(result.target_tolerances.transactions["trans"]) == {
            "0100", "0700", "2000", "3110", "3200", "5139", "5200", "6001"
        }

    def test_tolerances_trans_cat_loaded(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert result.target_tolerances.categories is not None
        assert len(result.target_tolerances.categories) == 3

    def test_tolerances_trans_rel_abs_are_numeric(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert pd.api.types.is_numeric_dtype(result.target_tolerances.transactions["rel"])
        assert pd.api.types.is_numeric_dtype(result.target_tolerances.transactions["abs"])

    def test_tolerances_trans_cat_rel_abs_are_numeric(self, metadata):
        result = load_balancing_config_from_excel(
            metadata, tolerances_path=TOLERANCES_FILE
        )
        assert pd.api.types.is_numeric_dtype(result.target_tolerances.categories["rel"])
        assert pd.api.types.is_numeric_dtype(result.target_tolerances.categories["abs"])

    def test_tolerances_absent_sheet_gives_none(self, tmp_path, metadata):
        # File with only transactions sheet — trans_cat should be None
        trans_df = pd.DataFrame({
            "trans": ["0100"], "rel": [0.02], "abs": [5.0]
        })
        path = write_tolerances_file(tmp_path, {"transactions": trans_df})
        result = load_balancing_config_from_excel(metadata, tolerances_path=path)
        assert result.target_tolerances.transactions is not None
        assert result.target_tolerances.categories is None

    def test_tolerances_strips_whitespace(self, tmp_path, metadata):
        trans_df = pd.DataFrame({
            "trans": ["  0100  "], "rel": ["0.02"], "abs": ["5.0"]
        })
        path = write_tolerances_file(tmp_path, {"transactions": trans_df})
        result = load_balancing_config_from_excel(metadata, tolerances_path=path)
        assert result.target_tolerances.transactions["trans"].iloc[0] == "0100"

    def test_tolerances_error_missing_column(self, tmp_path, metadata):
        # Missing 'abs' column
        trans_df = pd.DataFrame({"trans": ["0100"], "rel": [0.02]})
        path = write_tolerances_file(tmp_path, {"transactions": trans_df})
        with pytest.raises(ValueError, match="'abs'"):
            load_balancing_config_from_excel(metadata, tolerances_path=path)

    def test_tolerances_error_mentions_sheet_name(self, tmp_path, metadata):
        trans_df = pd.DataFrame({"trans": ["0100"], "rel": [0.02]})
        path = write_tolerances_file(tmp_path, {"transactions": trans_df})
        with pytest.raises(ValueError, match="'transactions'"):
            load_balancing_config_from_excel(metadata, tolerances_path=path)

    # --- locks ---

    def test_locks_returns_locks(self, metadata):
        result = load_balancing_config_from_excel(metadata, locks_path=LOCKS_FILE)
        assert isinstance(result.locks, Locks)

    def test_locks_products_loaded(self, metadata):
        result = load_balancing_config_from_excel(metadata, locks_path=LOCKS_FILE)
        assert result.locks.products is not None
        assert list(result.locks.products["nrnr"]) == ["C"]

    def test_locks_trans_loaded(self, metadata):
        result = load_balancing_config_from_excel(metadata, locks_path=LOCKS_FILE)
        assert result.locks.transactions is not None
        assert set(result.locks.transactions["trans"]) == {"3200", "6001"}

    def test_locks_absent_sheets_are_none(self, metadata):
        # Fixture has only products and trans sheets — trans_cat and cells absent
        result = load_balancing_config_from_excel(metadata, locks_path=LOCKS_FILE)
        assert result.locks.categories is None
        assert result.locks.cells is None

    def test_locks_all_sheets_loaded(self, tmp_path, metadata):
        products_df = pd.DataFrame({"nrnr": ["A"]})
        trans_df = pd.DataFrame({"trans": ["2000"]})
        trans_cat_df = pd.DataFrame({"trans": ["3110"], "brch": ["HH"]})
        cells_df = pd.DataFrame({"nrnr": ["B"], "trans": ["2000"], "brch": ["X"]})
        path = write_locks_file(tmp_path, {
            "products": products_df,
            "transactions": trans_df,
            "categories": trans_cat_df,
            "cells": cells_df,
        })
        result = load_balancing_config_from_excel(metadata, locks_path=path)
        assert result.locks.products is not None
        assert result.locks.transactions is not None
        assert result.locks.categories is not None
        assert result.locks.cells is not None

    def test_locks_strips_whitespace(self, tmp_path, metadata):
        products_df = pd.DataFrame({"nrnr": ["  C  "]})
        path = write_locks_file(tmp_path, {"products": products_df})
        result = load_balancing_config_from_excel(metadata, locks_path=path)
        assert result.locks.products["nrnr"].iloc[0] == "C"

    def test_locks_error_missing_column(self, tmp_path, metadata):
        # products sheet with wrong column name
        products_df = pd.DataFrame({"wrong_col": ["C"]})
        path = write_locks_file(tmp_path, {"products": products_df})
        with pytest.raises(ValueError, match="'nrnr'"):
            load_balancing_config_from_excel(metadata, locks_path=path)

    def test_locks_error_mentions_sheet_name(self, tmp_path, metadata):
        products_df = pd.DataFrame({"wrong_col": ["C"]})
        path = write_locks_file(tmp_path, {"products": products_df})
        with pytest.raises(ValueError, match="'products'"):
            load_balancing_config_from_excel(metadata, locks_path=path)

    def test_locks_unknown_sheets_ignored(self, tmp_path, metadata):
        products_df = pd.DataFrame({"nrnr": ["C"]})
        path = write_locks_file(tmp_path, {
            "products": products_df,
            "unknown_sheet": pd.DataFrame({"x": [1]}),
        })
        result = load_balancing_config_from_excel(metadata, locks_path=path)
        assert result.locks.products is not None

    def test_locks_price_layers_loaded(self, tmp_path, metadata):
        price_layers_df = pd.DataFrame({"price_layer": ["ava"]})
        path = write_locks_file(tmp_path, {"price_layers": price_layers_df})
        result = load_balancing_config_from_excel(metadata, locks_path=path)
        assert result.locks.price_layers is not None
        assert list(result.locks.price_layers["price_layer"]) == ["ava"]

    def test_locks_price_layers_absent_is_none(self, metadata):
        # Fixture file has no price_layers sheet
        result = load_balancing_config_from_excel(metadata, locks_path=LOCKS_FILE)
        assert result.locks.price_layers is None

    def test_locks_price_layers_multiple_values(self, tmp_path, metadata):
        price_layers_df = pd.DataFrame({"price_layer": ["ava", "moms"]})
        path = write_locks_file(tmp_path, {"price_layers": price_layers_df})
        result = load_balancing_config_from_excel(metadata, locks_path=path)
        assert set(result.locks.price_layers["price_layer"]) == {"ava", "moms"}

    def test_locks_price_layers_error_unknown_column_name(self, tmp_path, metadata):
        # "bad_col" is not a known price layer column name in the metadata
        price_layers_df = pd.DataFrame({"price_layer": ["bad_col"]})
        path = write_locks_file(tmp_path, {"price_layers": price_layers_df})
        with pytest.raises(ValueError, match="'bad_col'"):
            load_balancing_config_from_excel(metadata, locks_path=path)

    def test_locks_price_layers_error_mentions_known_columns(self, tmp_path, metadata):
        price_layers_df = pd.DataFrame({"price_layer": ["bad_col"]})
        path = write_locks_file(tmp_path, {"price_layers": price_layers_df})
        with pytest.raises(ValueError, match="ava"):
            load_balancing_config_from_excel(metadata, locks_path=path)

    def test_locks_price_layers_error_missing_price_layer_column(self, tmp_path, metadata):
        # Sheet exists but uses wrong column header
        price_layers_df = pd.DataFrame({"wrong_col": ["ava"]})
        path = write_locks_file(tmp_path, {"price_layers": price_layers_df})
        with pytest.raises(ValueError, match="'price_layer'"):
            load_balancing_config_from_excel(metadata, locks_path=path)
