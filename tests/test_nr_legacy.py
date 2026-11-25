"""
Tests for the legacy Statistics Denmark fixed-width format in sutlab.nr_legacy.
"""

from pathlib import Path

import pandas as pd
import pytest

from sutlab.nr_legacy import (
    load_sut_from_separated_nr_legacy_fwf,
    make_final_annual_sut_paths,
    write_sut_to_separated_nr_legacy_fwf,
)
from sutlab.sut import SUT, SUTClassifications, SUTColumns, SUTMetadata


# ---------------------------------------------------------------------------
# Tests for load_sut_from_separated_nr_legacy_fwf
# ---------------------------------------------------------------------------


def _fwf_line(product, transaction, category, values, trailer=""):
    """Build one line of the legacy fixed-width format.

    Positions: product 0-7, transaction 16-20, category 30-36, then six
    16-character right-aligned value fields from position 44. Values given as
    None are left blank. Anything in ``trailer`` is put after position 140.
    """
    line = product.ljust(16) + transaction.ljust(14) + category.ljust(14)
    for value in values:
        text = "" if value is None else str(value)
        line += text.rjust(16)
    if trailer:
        line = line.ljust(140) + trailer
    return line


FWF_COLUMNS = SUTColumns(
    id="year",
    product="nrnr",
    transaction="trans",
    category="brch",
    price_basic="bas",
    price_purchasers="koeb",
    wholesale_margins="eng",
    retail_margins="det",
    product_taxes_less_subsidies="afg",
    vat="moms",
)

FWF_LINES = [
    # supply rows: only a basic price value
    _fwf_line("A000001", "0100", "100010", [100]),
    _fwf_line("A000001", "0700", "", [50], trailer="   F.....F "),
    # use rows: all six values; trailing flags/timestamp must be ignored
    _fwf_line("A000001", "2000", "100010", [80, 5, 3, -2, 4, 90],
              trailer="    RBJ    ...F     21-01-2022 11:35"),
    _fwf_line("A000001", "3110", "01120", [40, 0, 0, 0, 10, 50]),
    _fwf_line("B000002", "6001", "", [20, 1, 0, 0, 0, 21]),
]


def _fwf_metadata(columns: SUTColumns = FWF_COLUMNS) -> SUTMetadata:
    transactions = pd.DataFrame({
        "trans": ["0100", "0700", "2000", "3110", "6001"],
        "trans_txt": ["Output", "Imports", "Intermediate", "Household", "Exports"],
        "table": ["supply", "supply", "use", "use", "use"],
        "esa_code": ["P1", "P7", "P2", "P31", "P6"],
    })
    return SUTMetadata(
        columns=columns,
        classifications=SUTClassifications(transactions=transactions),
    )


def _write_fwf(path: Path, lines: list[str], encoding: str = "cp1252") -> Path:
    path.write_bytes(("\n".join(lines) + "\n").encode(encoding))
    return path


class TestLoadSutFromSeparatedFwf:

    @pytest.fixture
    def metadata(self):
        return _fwf_metadata()

    @pytest.fixture
    def fwf_path(self, tmp_path):
        return _write_fwf(tmp_path / "ta21l", FWF_LINES)

    def test_returns_sut(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        assert isinstance(result, SUT)
        assert result.price_basis == "current_year"

    def test_supply_columns_and_rows(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        assert list(result.supply.columns) == ["year", "nrnr", "trans", "brch", "bas"]
        assert len(result.supply) == 2

    def test_use_columns_in_layer_order(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        assert list(result.use.columns) == [
            "year", "nrnr", "trans", "brch", "bas", "eng", "det", "afg", "moms", "koeb",
        ]
        assert len(result.use) == 3

    def test_values_in_correct_columns(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        row = result.use[
            (result.use["trans"] == "2000") & (result.use["nrnr"] == "A000001")
        ].iloc[0]
        assert row["bas"] == 80
        assert row["eng"] == 5
        assert row["det"] == 3
        assert row["afg"] == -2
        assert row["moms"] == 4
        assert row["koeb"] == 90

    def test_supply_value(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        row = result.supply[result.supply["trans"] == "0100"].iloc[0]
        assert row["bas"] == 100

    def test_codes_are_str_and_keep_leading_zeros(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        assert "0100" in result.supply["trans"].values
        assert "01120" in result.use["brch"].values

    def test_blank_category_is_empty_string(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        imports = result.supply[result.supply["trans"] == "0700"].iloc[0]
        assert imports["brch"] == ""

    def test_price_columns_are_numeric(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        for col in ["bas", "eng", "det", "afg", "moms", "koeb"]:
            assert pd.api.types.is_numeric_dtype(result.use[col])

    def test_id_column_populated(self, metadata, fwf_path):
        result = load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], metadata, "current_year")
        assert (result.supply["year"] == 2021).all()
        assert (result.use["year"] == 2021).all()

    def test_multiple_files_concatenated_and_sorted(self, metadata, tmp_path):
        path_a = _write_fwf(tmp_path / "a", FWF_LINES)
        path_b = _write_fwf(tmp_path / "b", FWF_LINES)
        result = load_sut_from_separated_nr_legacy_fwf(
            [2022, 2021], [path_a, path_b], metadata, "current_year"
        )
        assert set(result.use["year"].unique()) == {2021, 2022}
        assert len(result.use) == 6
        sort_cols = ["year", "nrnr", "trans", "brch"]
        expected = result.use.sort_values(sort_cols).reset_index(drop=True)
        pd.testing.assert_frame_equal(result.use, expected)

    def test_trailing_blank_line_ignored(self, metadata, tmp_path):
        path = tmp_path / "blank"
        path.write_bytes(("\n".join(FWF_LINES) + "\n\n").encode("cp1252"))
        result = load_sut_from_separated_nr_legacy_fwf([2021], [path], metadata, "current_year")
        assert len(result.supply) + len(result.use) == len(FWF_LINES)

    def test_non_utf8_trailer_is_ignored(self, metadata, tmp_path):
        lines = list(FWF_LINES)
        lines[2] = _fwf_line(
            "A000001", "2000", "100010", [80, 5, 3, -2, 4, 90], trailer="   Søren €"
        )
        path = _write_fwf(tmp_path / "cp1252", lines, encoding="cp1252")
        result = load_sut_from_separated_nr_legacy_fwf([2021], [path], metadata, "current_year")
        assert len(result.use) == 3

    def test_print_paths(self, metadata, fwf_path, capsys):
        load_sut_from_separated_nr_legacy_fwf(
            [2021], [fwf_path], metadata, "previous_year", print_paths=True
        )
        out = capsys.readouterr().out
        assert "previous year" in out
        assert str(fwf_path) in out

    def test_error_mismatched_lengths(self, metadata, fwf_path):
        with pytest.raises(ValueError, match="same length"):
            load_sut_from_separated_nr_legacy_fwf([2021, 2022], [fwf_path], metadata, "current_year")

    def test_error_missing_classifications(self, metadata, fwf_path):
        bare = SUTMetadata(columns=metadata.columns)
        with pytest.raises(ValueError, match="transactions"):
            load_sut_from_separated_nr_legacy_fwf([2021], [fwf_path], bare, "current_year")

    def test_error_missing_layer_role(self, fwf_path):
        columns = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
            wholesale_margins="eng", retail_margins="det", vat="moms",
        )
        with pytest.raises(ValueError, match="product_taxes_less_subsidies"):
            load_sut_from_separated_nr_legacy_fwf(
                [2021], [fwf_path], _fwf_metadata(columns), "current_year"
            )

    def test_error_extra_layer_role(self, fwf_path):
        columns = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
            wholesale_margins="eng", retail_margins="det",
            product_taxes_less_subsidies="afg", vat="moms",
            transport_margins="tr",
        )
        with pytest.raises(ValueError, match="transport_margins"):
            load_sut_from_separated_nr_legacy_fwf(
                [2021], [fwf_path], _fwf_metadata(columns), "current_year"
            )

    def test_error_unknown_transaction_code(self, metadata, tmp_path):
        lines = FWF_LINES + [_fwf_line("A000001", "9999", "", [1, 0, 0, 0, 0, 1])]
        path = _write_fwf(tmp_path / "bad", lines)
        with pytest.raises(ValueError, match="9999"):
            load_sut_from_separated_nr_legacy_fwf([2021], [path], metadata, "current_year")


# ---------------------------------------------------------------------------
# Tests for write_sut_to_separated_nr_legacy_fwf
# ---------------------------------------------------------------------------


class TestWriteSutToSeparatedFwf:

    @pytest.fixture
    def metadata(self):
        return _fwf_metadata()

    @pytest.fixture
    def sut(self, metadata, tmp_path):
        path = _write_fwf(tmp_path / "in", FWF_LINES)
        return load_sut_from_separated_nr_legacy_fwf([2021, 2022], [path, path], metadata, "current_year")

    def test_writes_one_file_per_id(self, sut, tmp_path):
        paths = [tmp_path / "a", tmp_path / "b"]
        write_sut_to_separated_nr_legacy_fwf(sut, [2021, 2022], paths)
        assert all(p.exists() for p in paths)

    def test_roundtrip(self, sut, metadata, tmp_path):
        paths = [tmp_path / "a", tmp_path / "b"]
        write_sut_to_separated_nr_legacy_fwf(sut, [2021, 2022], paths)
        result = load_sut_from_separated_nr_legacy_fwf([2021, 2022], paths, metadata, "current_year")
        pd.testing.assert_frame_equal(result.supply, sut.supply)
        pd.testing.assert_frame_equal(result.use, sut.use)

    def test_only_selected_ids_written(self, sut, metadata, tmp_path):
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2022], [path])
        result = load_sut_from_separated_nr_legacy_fwf([2022], [path], metadata, "current_year")
        assert len(result.supply) == 2
        assert len(result.use) == 3

    def test_exact_line_format(self, sut, tmp_path):
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2021], [path])
        lines = path.read_text(encoding="cp1252").split("\n")
        expected = [
            _fwf_line("A000001", "0100", "100010", [100]),
            _fwf_line("A000001", "0700", "", [50]),
            _fwf_line("A000001", "2000", "100010", [80, 5, 3, -2, 4, 90]),
            _fwf_line("A000001", "3110", "01120", [40, 0, 0, 0, 10, 50]),
            _fwf_line("B000002", "6001", "", [20, 1, 0, 0, 0, 21]),
        ]
        assert lines[:-1] == expected
        assert lines[-1] == ""

    def test_supply_line_ends_after_basic_price(self, sut, tmp_path):
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2021], [path])
        supply_line = path.read_text(encoding="cp1252").split("\n")[0]
        assert len(supply_line) == 60

    def test_values_rounded_to_whole_numbers(self, sut, metadata, tmp_path):
        use = sut.use.copy()
        use.loc[use["trans"] == "3110", "bas"] = 40.4
        use.loc[use["trans"] == "3110", "koeb"] = 50.6
        sut = SUT(price_basis="current_year", supply=sut.supply, use=use, metadata=metadata)
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2021], [path])
        result = load_sut_from_separated_nr_legacy_fwf([2021], [path], metadata, "current_year")
        row = result.use[result.use["trans"] == "3110"].iloc[0]
        assert row["bas"] == 40
        assert row["koeb"] == 51

    def test_nan_in_use_row_written_as_zero(self, sut, metadata, tmp_path):
        use = sut.use.copy()
        use.loc[use["trans"] == "3110", "eng"] = float("nan")
        sut = SUT(price_basis="current_year", supply=sut.supply, use=use, metadata=metadata)
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2021], [path])
        result = load_sut_from_separated_nr_legacy_fwf([2021], [path], metadata, "current_year")
        row = result.use[result.use["trans"] == "3110"].iloc[0]
        assert row["eng"] == 0

    def test_rows_sorted_across_supply_and_use(self, sut, tmp_path):
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2021], [path])
        lines = path.read_text(encoding="cp1252").split("\n")[:-1]
        keys = [(l[0:7], l[16:20], l[30:36].strip()) for l in lines]
        assert keys == sorted(keys)

    def test_print_paths(self, sut, tmp_path, capsys):
        path = tmp_path / "a"
        write_sut_to_separated_nr_legacy_fwf(sut, [2021], [path], print_paths=True)
        out = capsys.readouterr().out
        assert "Writing SUT (current year" in out
        assert str(path) in out

    def test_sut_method_delegates(self, sut, metadata, tmp_path):
        path = tmp_path / "a"
        sut.write_to_separated_nr_legacy_fwf([2021], [path])
        result = load_sut_from_separated_nr_legacy_fwf([2021], [path], metadata, "current_year")
        assert len(result.use) == 3

    def test_error_mismatched_lengths(self, sut, tmp_path):
        with pytest.raises(ValueError, match="same length"):
            write_sut_to_separated_nr_legacy_fwf(sut, [2021, 2022], [tmp_path / "a"])

    def test_error_id_not_in_sut(self, sut, tmp_path):
        with pytest.raises(ValueError, match="9999"):
            write_sut_to_separated_nr_legacy_fwf(sut, [9999], [tmp_path / "a"])

    def test_error_missing_metadata(self, sut, tmp_path):
        no_metadata = SUT(price_basis="current_year", supply=sut.supply, use=sut.use)
        with pytest.raises(ValueError, match="metadata"):
            write_sut_to_separated_nr_legacy_fwf(no_metadata, [2021], [tmp_path / "a"])

    def test_error_missing_layer_role(self, sut, tmp_path):
        columns = SUTColumns(
            id="year", product="nrnr", transaction="trans", category="brch",
            price_basic="bas", price_purchasers="koeb",
            wholesale_margins="eng", retail_margins="det", vat="moms",
        )
        bad = SUT(
            price_basis="current_year", supply=sut.supply, use=sut.use,
            metadata=_fwf_metadata(columns),
        )
        with pytest.raises(ValueError, match="product_taxes_less_subsidies"):
            write_sut_to_separated_nr_legacy_fwf(bad, [2021], [tmp_path / "a"])

    def test_error_product_too_long(self, sut, metadata, tmp_path):
        supply = sut.supply.copy()
        supply.loc[supply.index[0], "nrnr"] = "TOOLONG99"
        bad = SUT(price_basis="current_year", supply=supply, use=sut.use, metadata=metadata)
        with pytest.raises(ValueError, match="TOOLONG99"):
            write_sut_to_separated_nr_legacy_fwf(bad, [2021], [tmp_path / "a"])

    def test_error_transaction_too_long(self, sut, metadata, tmp_path):
        supply = sut.supply.copy()
        supply.loc[supply.index[0], "trans"] = "01000"
        bad = SUT(price_basis="current_year", supply=supply, use=sut.use, metadata=metadata)
        with pytest.raises(ValueError, match="01000"):
            write_sut_to_separated_nr_legacy_fwf(bad, [2021], [tmp_path / "a"])

    def test_error_category_too_long(self, sut, metadata, tmp_path):
        use = sut.use.copy()
        use.loc[use.index[0], "brch"] = "1234567"
        bad = SUT(price_basis="current_year", supply=sut.supply, use=use, metadata=metadata)
        with pytest.raises(ValueError, match="1234567"):
            write_sut_to_separated_nr_legacy_fwf(bad, [2021], [tmp_path / "a"])

    def test_error_value_too_wide(self, sut, metadata, tmp_path):
        use = sut.use.copy()
        use.loc[use.index[0], "bas"] = 1e17
        bad = SUT(price_basis="current_year", supply=sut.supply, use=use, metadata=metadata)
        with pytest.raises(ValueError, match="'bas'"):
            write_sut_to_separated_nr_legacy_fwf(bad, [2021], [tmp_path / "a"])



# ---------------------------------------------------------------------------
# Tests for make_final_annual_sut_paths
# ---------------------------------------------------------------------------


class TestMakeFinalAnnualSutPaths:

    def test_current_year(self):
        paths = make_final_annual_sut_paths([2023], "current_year")
        # Compared as text, since Path comparison ignores case on Windows.
        assert [str(path) for path in paths] == [
            r"\\06kt03\tilanv16\xtrdrv\tilanv24\Afstem23\TA\ta23l"
        ]

    def test_previous_year(self):
        assert make_final_annual_sut_paths([2023], "previous_year") == [
            Path(r"\\06kt03\tilanv16\xtrdrv\tilanv24\Afstem23\TA\ta23f22")
        ]

    def test_multiple_years_keep_order(self):
        paths = make_final_annual_sut_paths([2021, 2019], "current_year", root="y:/")
        assert paths == [
            Path("y:/Afstem21/TA/ta21l"),
            Path("y:/Afstem19/TA/ta19l"),
        ]

    def test_century_boundary_previous_year(self):
        paths = make_final_annual_sut_paths([2000], "previous_year", root="y:/")
        assert paths == [Path("y:/Afstem00/TA/ta00f99")]

    def test_root_as_path(self, tmp_path):
        paths = make_final_annual_sut_paths([2019], "current_year", root=tmp_path)
        assert paths == [tmp_path / "Afstem19" / "TA" / "ta19l"]

    def test_error_invalid_price_basis(self):
        with pytest.raises(ValueError, match="price_basis"):
            make_final_annual_sut_paths([2019], "l")
