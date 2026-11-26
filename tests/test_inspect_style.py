"""
Tests for the theme-independent base styling of inspection tables.

Styled tables must be readable in both light and dark editor themes, so every
Styler is created with black text on a white background (see
``_new_styler`` in ``sutlab/inspect/_style.py``).
"""

import pandas as pd

from sutlab.inspect._style import _new_styler


def _make_df():
    return pd.DataFrame({"value": [1.0, 2.0]}, index=pd.Index(["a", "b"], name="code"))


def test_text_is_black_on_cells_and_headers():
    html = _new_styler(_make_df()).to_html()
    assert " td {\n  color: black;\n}" in html
    assert " th {\n  color: black;\n}" in html


def test_table_rows_and_column_headers_have_white_background():
    html = _new_styler(_make_df()).to_html()
    assert " tr {\n  background-color: white;\n}" in html
    assert " thead th {\n  background-color: white;\n}" in html


def test_cell_background_colours_are_kept():
    styler = _new_styler(_make_df())
    styler = styler.apply(lambda col: ["background-color: #e8f5e9"] * len(col))
    html = styler.to_html()
    assert "background-color: #e8f5e9" in html


def test_cells_themselves_get_no_white_background():
    # A white background on the td/th rules would override the cell colours
    # set by the inspection styling, so it must only be on table/tr/thead th.
    html = _new_styler(_make_df()).to_html()
    assert " td {\n  background-color" not in html
    assert " tbody th {\n  background-color" not in html


def test_excel_export_unaffected(tmp_path):
    # Table styles are HTML-only; writing to Excel must still work.
    path = tmp_path / "out.xlsx"
    _new_styler(_make_df()).to_excel(path)
    assert path.exists()
