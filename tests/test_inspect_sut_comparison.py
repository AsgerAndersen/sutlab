"""
Tests for inspect_sut_comparison.
"""

import pytest
import pandas as pd
import numpy as np

from sutlab.sut import SUT, SUTColumns, SUTMetadata, SUTClassifications, BalancingTargets
from sutlab.inspect import (
    inspect_sut_comparison,
    SUTComparisonInspection,
    SUTComparisonData,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
#
# Two ids: 2021 and 2022.
# Products: A, B, C.
# Supply transactions: P1. Use transactions: P2.
# Price layers: ava (wholesale_margins), moms (vat).
#
# before SUT:
#   supply: A/P1/X bas=100, B/P1/X bas=50, C/P1/X bas=80
#   use:    A/P2/X bas=90 ava=5 moms=9 koeb=104
#           B/P2/X bas=50 ava=3 moms=6 koeb=59
#           C/P2/X bas=70 ava=4 moms=8 koeb=82
#
# after SUT (2021 only changed):
#   supply: A/P1/X bas=110 (+10), B/P1/X bas=50 (unchanged), C/P1/X bas=80 (unchanged)
#   use:    A/P2/X bas=100 (+10) ava=5 (unchanged) moms=10 (+1) koeb=115 (+11)
#           B/P2/X bas=50 (unchanged) ava=3 (unchanged) moms=6 (unchanged) koeb=59 (unchanged)
#           C/P2/X bas=70 (unchanged) ava=4 (unchanged) moms=8 (unchanged) koeb=82 (unchanged)
#
# 2022 rows are identical in before and after (so should not appear in results).
# ---------------------------------------------------------------------------


@pytest.fixture
def cols():
    return SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
        wholesale_margins="ava",
        vat="moms",
    )


@pytest.fixture
def before_supply():
    return pd.DataFrame({
        "year":  [2021, 2021, 2021, 2022, 2022, 2022],
        "nrnr":  ["A",  "B",  "C",  "A",  "B",  "C"],
        "trans": ["P1", "P1", "P1", "P1", "P1", "P1"],
        "brch":  ["X",  "X",  "X",  "X",  "X",  "X"],
        "bas":   [100., 50.,  80.,  100., 50.,  80.],
        "koeb":  [100., 50.,  80.,  100., 50.,  80.],
    })


@pytest.fixture
def before_use():
    return pd.DataFrame({
        "year":  [2021, 2021, 2021, 2022, 2022, 2022],
        "nrnr":  ["A",  "B",  "C",  "A",  "B",  "C"],
        "trans": ["P2", "P2", "P2", "P2", "P2", "P2"],
        "brch":  ["X",  "X",  "X",  "X",  "X",  "X"],
        "bas":   [90.,  50.,  70.,  90.,  50.,  70.],
        "ava":   [5.,   3.,   4.,   5.,   3.,   4.],
        "moms":  [9.,   6.,   8.,   9.,   6.,   8.],
        "koeb":  [104., 59.,  82.,  104., 59.,  82.],
    })


@pytest.fixture
def after_supply():
    return pd.DataFrame({
        "year":  [2021, 2021, 2021, 2022, 2022, 2022],
        "nrnr":  ["A",  "B",  "C",  "A",  "B",  "C"],
        "trans": ["P1", "P1", "P1", "P1", "P1", "P1"],
        "brch":  ["X",  "X",  "X",  "X",  "X",  "X"],
        "bas":   [110., 50.,  80.,  100., 50.,  80.],   # A/2021 changed
        "koeb":  [110., 50.,  80.,  100., 50.,  80.],
    })


@pytest.fixture
def after_use():
    return pd.DataFrame({
        "year":  [2021, 2021, 2021, 2022, 2022, 2022],
        "nrnr":  ["A",  "B",  "C",  "A",  "B",  "C"],
        "trans": ["P2", "P2", "P2", "P2", "P2", "P2"],
        "brch":  ["X",  "X",  "X",  "X",  "X",  "X"],
        "bas":   [100., 50.,  70.,  90.,  50.,  70.],   # A/2021 changed
        "ava":   [5.,   3.,   4.,   5.,   3.,   4.],
        "moms":  [10.,  6.,   8.,   9.,   6.,   8.],   # A/2021 changed
        "koeb":  [115., 59.,  82.,  104., 59.,  82.],  # A/2021 changed
    })


@pytest.fixture
def metadata(cols):
    return SUTMetadata(columns=cols)


@pytest.fixture
def before_sut(before_supply, before_use, metadata):
    return SUT(
        price_basis="current_year",
        supply=before_supply,
        use=before_use,
        metadata=metadata,
    )


@pytest.fixture
def after_sut(after_supply, after_use, metadata):
    return SUT(
        price_basis="current_year",
        supply=after_supply,
        use=after_use,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


def test_returns_inspection_type(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result, SUTComparisonInspection)
    assert isinstance(result.data, SUTComparisonData)


def test_supply_only_changed_row_returned(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    supply = result.data.supply
    # Only A/2021/P1/X changed in supply; 2022 rows and B, C are unchanged.
    assert len(supply) == 1
    row = supply.iloc[0]
    assert row["before_bas"] == 100.0
    assert row["after_bas"] == 110.0
    assert row["diff_bas"] == 10.0
    assert pytest.approx(row["rel_bas"]) == 10.0 / 100.0


def test_use_basic_only_changed_row_returned(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    use_basic = result.data.use_basic
    assert len(use_basic) == 1
    row = use_basic.iloc[0]
    assert row["before_bas"] == 90.0
    assert row["after_bas"] == 100.0
    assert row["diff_bas"] == 10.0


def test_use_purchasers_only_changed_row_returned(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    use_purch = result.data.use_purchasers
    assert len(use_purch) == 1
    row = use_purch.iloc[0]
    assert row["before_koeb"] == 104.0
    assert row["after_koeb"] == 115.0
    assert row["diff_koeb"] == 11.0


def test_use_price_layers_only_changed_layer_returned(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=0)
    layers = result.data.use_price_layers
    # Only moms changed for A/2021/P2/X; ava did not change.
    assert len(layers) == 1
    row = layers.iloc[0]
    assert row["before"] == 9.0
    assert row["after"] == 10.0
    assert row["diff"] == 1.0
    assert layers.index.get_level_values("price_layer")[0] == "moms"


def test_unchanged_rows_not_returned(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    supply = result.data.supply
    # 2022 rows are identical — must not appear.
    years = supply.index.get_level_values("year").tolist()
    assert all(y == 2021 for y in years)


# ---------------------------------------------------------------------------
# Tolerance filtering
# ---------------------------------------------------------------------------


def test_diff_tolerance_filters_small_diffs(before_sut, after_sut):
    # diff=10; diff_tolerance=10 means 10 > 10 is False, so diff does not trigger.
    # rel_tolerance=999 ensures rel does not trigger either — row excluded.
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=10, rel_tolerance=999)
    assert len(result.data.supply) == 0


def test_diff_tolerance_keeps_large_diffs(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=9)
    assert len(result.data.supply) == 1


def test_rel_tolerance_filters_small_rel(before_sut, after_sut):
    # diff=10 < diff_tolerance=999 → AND condition fails → row excluded.
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=999, rel_tolerance=0.15)
    assert len(result.data.supply) == 0


def test_both_tolerances_exceeded_keeps_row(before_sut, after_sut):
    # diff=10 > diff_tolerance=5 and rel~0.10 > rel_tolerance=0.05 — both exceeded, row kept.
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=5, rel_tolerance=0.05)
    assert len(result.data.supply) == 1


def test_only_diff_exceeded_excludes_row(before_sut, after_sut):
    # diff=10 > diff_tolerance=9 but rel~0.10 < rel_tolerance=0.20 — AND fails, row excluded.
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=9, rel_tolerance=0.20)
    assert len(result.data.supply) == 0


def test_only_rel_exceeded_excludes_row(before_sut, after_sut):
    # rel~0.10 > rel_tolerance=0.05 but diff=10 < diff_tolerance=999 — AND fails, row excluded.
    result = inspect_sut_comparison(before_sut, after_sut, diff_tolerance=999, rel_tolerance=0.05)
    assert len(result.data.supply) == 0


# ---------------------------------------------------------------------------
# Outer join — rows only in one SUT always included
# ---------------------------------------------------------------------------


def test_row_only_in_before_always_included(before_sut, after_use, cols, metadata):
    # Remove A/2021/P2/X from after_use entirely.
    after_use_missing = after_use[
        ~((after_use["nrnr"] == "A") & (after_use["year"] == 2021))
    ].copy()
    after_sut_missing = SUT(
        price_basis="current_year",
        supply=after_sut_supply(after_use, cols),
        use=after_use_missing,
        metadata=metadata,
    )
    result = inspect_sut_comparison(before_sut, after_sut_missing, diff_tolerance=9999)
    # Row only in before — must appear even with very large tolerance.
    use_basic = result.data.use_basic
    years = use_basic.index.get_level_values("year").tolist()
    nrnrs = use_basic.index.get_level_values("nrnr").tolist()
    assert any(y == 2021 and n == "A" for y, n in zip(years, nrnrs))


def after_sut_supply(after_use, cols):
    """Helper: build a simple supply DataFrame for the outer join test."""
    return pd.DataFrame({
        "year":  [2021, 2021, 2021, 2022, 2022, 2022],
        "nrnr":  ["A",  "B",  "C",  "A",  "B",  "C"],
        "trans": ["P1", "P1", "P1", "P1", "P1", "P1"],
        "brch":  ["X",  "X",  "X",  "X",  "X",  "X"],
        "bas":   [110., 50.,  80.,  100., 50.,  80.],
        "koeb":  [110., 50.,  80.,  100., 50.,  80.],
    })


def test_row_only_in_after_always_included(before_sut, after_supply, after_use, metadata):
    # Add a new row D/2021/P2/X to after_use.
    new_row = pd.DataFrame({
        "year": [2021], "nrnr": ["D"], "trans": ["P2"], "brch": ["X"],
        "bas": [20.], "ava": [1.], "moms": [2.], "koeb": [23.],
    })
    after_use_extra = pd.concat([after_use, new_row], ignore_index=True)
    after_sut_extra = SUT(
        price_basis="current_year",
        supply=after_supply,
        use=after_use_extra,
        metadata=metadata,
    )
    result = inspect_sut_comparison(before_sut, after_sut_extra, diff_tolerance=9999)
    use_basic = result.data.use_basic
    nrnrs = use_basic.index.get_level_values("nrnr").tolist()
    assert "D" in nrnrs


# ---------------------------------------------------------------------------
# Filtering arguments
# ---------------------------------------------------------------------------


def test_filter_by_ids(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut, ids=2022)
    # 2022 has no changes — all tables empty.
    assert len(result.data.supply) == 0
    assert len(result.data.use_basic) == 0


def test_filter_by_products(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut, products="B")
    # B has no changes.
    assert len(result.data.supply) == 0
    assert len(result.data.use_basic) == 0


def test_filter_by_products_keeps_changed(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut, products="A")
    assert len(result.data.supply) == 1


def test_filter_by_transactions(before_sut, after_sut):
    # Filter to P1 (supply transactions) — use tables should be empty.
    result = inspect_sut_comparison(before_sut, after_sut, transactions="P1")
    assert len(result.data.use_basic) == 0
    assert len(result.data.supply) == 1


def test_filter_by_categories(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut, categories="X")
    # X is the only category, so all changes still present.
    assert len(result.data.supply) == 1


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


def test_sort_orders_within_id(cols, metadata):
    # Build before/after where multiple products changed by different amounts.
    supply_before = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "B"],
        "trans": ["P1", "P1"], "brch": ["X", "X"],
        "bas": [100., 50.], "koeb": [100., 50.],
    })
    supply_after = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "B"],
        "trans": ["P1", "P1"], "brch": ["X", "X"],
        "bas": [120., 55.], "koeb": [120., 55.],  # A diff=20, B diff=5
    })
    use_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [80.], "ava": [4.], "moms": [8.], "koeb": [92.],
    })
    sut_before = SUT(price_basis="current_year", supply=supply_before, use=use_df, metadata=metadata)
    sut_after = SUT(price_basis="current_year", supply=supply_after, use=use_df, metadata=metadata)

    result = inspect_sut_comparison(sut_before, sut_after, sort=True)
    supply = result.data.supply
    # A (diff=20) should come before B (diff=5).
    nrnrs = supply.index.get_level_values("nrnr").tolist()
    assert nrnrs.index("A") < nrnrs.index("B")


def test_sort_price_layers_within_id_and_layer(cols, metadata):
    # Two products A and B with different moms diffs; ava unchanged.
    use_before = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "B"],
        "trans": ["P2", "P2"], "brch": ["X", "X"],
        "bas": [90., 50.], "ava": [5., 3.], "moms": [9., 6.], "koeb": [104., 59.],
    })
    use_after = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "B"],
        "trans": ["P2", "P2"], "brch": ["X", "X"],
        "bas": [90., 50.], "ava": [5., 3.], "moms": [15., 7.], "koeb": [110., 60.],
        # A moms diff=6, B moms diff=1
    })
    supply_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    sut_before = SUT(price_basis="current_year", supply=supply_df, use=use_before, metadata=metadata)
    sut_after = SUT(price_basis="current_year", supply=supply_df, use=use_after, metadata=metadata)

    result = inspect_sut_comparison(sut_before, sut_after, sort=True, diff_tolerance=0)
    layers = result.data.use_price_layers
    layer_names = layers.index.get_level_values("price_layer").tolist()
    nrnrs = layers.index.get_level_values("nrnr").tolist()

    # Within "moms" layer: A (diff=6) before B (diff=1).
    moms_rows = [(p, n) for p, n in zip(layer_names, nrnrs) if p == "moms"]
    assert moms_rows[0][1] == "A"
    assert moms_rows[1][1] == "B"


# ---------------------------------------------------------------------------
# Column naming
# ---------------------------------------------------------------------------


def test_supply_column_names(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    cols_present = list(result.data.supply.columns)
    assert cols_present == ["before_bas", "after_bas", "diff_bas", "rel_bas"]


def test_use_purchasers_column_names(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    cols_present = list(result.data.use_purchasers.columns)
    assert cols_present == ["before_koeb", "after_koeb", "diff_koeb", "rel_koeb"]


def test_use_price_layers_column_names(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    cols_present = list(result.data.use_price_layers.columns)
    assert cols_present == ["before", "after", "diff", "rel"]


# ---------------------------------------------------------------------------
# Index structure
# ---------------------------------------------------------------------------


def test_supply_index_names_no_labels(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert result.data.supply.index.names == ["year", "nrnr", "trans", "brch"]


def test_use_price_layers_index_has_price_layer_level(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert "price_layer" in result.data.use_price_layers.index.names


# ---------------------------------------------------------------------------
# Text labels from classifications
# ---------------------------------------------------------------------------


@pytest.fixture
def metadata_with_classifications(cols):
    products_df = pd.DataFrame({"nrnr": ["A", "B", "C"], "nrnr_txt": ["Prod A", "Prod B", "Prod C"]})
    transactions_df = pd.DataFrame({
        "trans": ["P1", "P2"], "trans_txt": ["Supply", "Use"],
        "table": ["supply", "use"], "esa_code": ["P1", "P2"],
    })
    industries_df = pd.DataFrame({"brch": ["X"], "brch_txt": ["Industry X"]})
    classifications = SUTClassifications(
        products=products_df,
        transactions=transactions_df,
        industries=industries_df,
    )
    return SUTMetadata(columns=cols, classifications=classifications)


@pytest.fixture
def before_sut_with_labels(before_supply, before_use, metadata_with_classifications):
    return SUT(
        price_basis="current_year",
        supply=before_supply,
        use=before_use,
        metadata=metadata_with_classifications,
    )


@pytest.fixture
def after_sut_with_labels(after_supply, after_use, metadata_with_classifications):
    return SUT(
        price_basis="current_year",
        supply=after_supply,
        use=after_use,
        metadata=metadata_with_classifications,
    )


def test_supply_index_with_labels(before_sut_with_labels, after_sut_with_labels):
    result = inspect_sut_comparison(before_sut_with_labels, after_sut_with_labels)
    expected_names = ["year", "nrnr", "nrnr_txt", "trans", "trans_txt", "brch", "brch_txt"]
    assert result.data.supply.index.names == expected_names


def test_product_label_correct(before_sut_with_labels, after_sut_with_labels):
    result = inspect_sut_comparison(before_sut_with_labels, after_sut_with_labels)
    supply = result.data.supply
    nrnr_txt_vals = supply.index.get_level_values("nrnr_txt").tolist()
    assert nrnr_txt_vals == ["Prod A"]


def test_price_layers_index_with_labels_has_price_layer_last(
    before_sut_with_labels, after_sut_with_labels
):
    result = inspect_sut_comparison(before_sut_with_labels, after_sut_with_labels)
    names = result.data.use_price_layers.index.names
    assert names[-1] == "price_layer"
    assert "nrnr_txt" in names
    assert "trans_txt" in names
    assert "brch_txt" in names


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_raises_when_before_missing_metadata(after_sut):
    sut_no_meta = SUT(price_basis="current_year", supply=pd.DataFrame(), use=pd.DataFrame())
    with pytest.raises(ValueError, match="before.metadata is required"):
        inspect_sut_comparison(sut_no_meta, after_sut)


def test_raises_when_after_missing_metadata(before_sut):
    sut_no_meta = SUT(price_basis="current_year", supply=pd.DataFrame(), use=pd.DataFrame())
    with pytest.raises(ValueError, match="after.metadata is required"):
        inspect_sut_comparison(before_sut, sut_no_meta)


def test_raises_when_column_structures_differ(before_sut, after_use, metadata):
    different_cols = SUTColumns(
        id="year",
        product="nrnr",
        transaction="trans",
        category="brch",
        price_basic="bas",
        price_purchasers="koeb",
        wholesale_margins="eng",   # different from "ava" in before
    )
    different_metadata = SUTMetadata(columns=different_cols)
    after_sut_different = SUT(
        price_basis="current_year",
        supply=pd.DataFrame(),
        use=after_use,
        metadata=different_metadata,
    )
    with pytest.raises(ValueError, match="different column structures"):
        inspect_sut_comparison(before_sut, after_sut_different)


# ---------------------------------------------------------------------------
# Delegate method on SUT
# ---------------------------------------------------------------------------


def test_delegate_method(before_sut, after_sut):
    result = after_sut.inspect_sut_comparison(before_sut)
    assert isinstance(result, SUTComparisonInspection)
    assert len(result.data.supply) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_identical_suts_return_empty_tables(before_sut):
    result = inspect_sut_comparison(before_sut, before_sut)
    assert len(result.data.supply) == 0
    assert len(result.data.use_basic) == 0
    assert len(result.data.use_purchasers) == 0
    assert len(result.data.use_price_layers) == 0


def test_no_price_layers_returns_empty_layers_table(cols, metadata):
    # SUTColumns with no price layer columns mapped.
    cols_no_layers = SUTColumns(
        id="year", product="nrnr", transaction="trans", category="brch",
        price_basic="bas", price_purchasers="koeb",
    )
    meta_no_layers = SUTMetadata(columns=cols_no_layers)
    supply = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    use = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [90.], "koeb": [95.],
    })
    use_after = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [100.], "koeb": [105.],
    })
    sut_a = SUT(price_basis="current_year", supply=supply, use=use, metadata=meta_no_layers)
    sut_b = SUT(price_basis="current_year", supply=supply, use=use_after, metadata=meta_no_layers)
    result = inspect_sut_comparison(sut_a, sut_b)
    assert len(result.data.use_price_layers) == 0


# ---------------------------------------------------------------------------
# filter_nan_as_zero
# ---------------------------------------------------------------------------


def test_filter_nan_as_zero_suppresses_new_zero_row_in_layers(cols, metadata):
    # New product D added in after with 0 in all price layers — should be
    # suppressed when filter_nan_as_zero=True.
    use_before = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [90.], "ava": [5.], "moms": [9.], "koeb": [104.],
    })
    use_after = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "D"], "trans": ["P2", "P2"], "brch": ["X", "X"],
        "bas": [90., 0.], "ava": [5., 0.], "moms": [9., 0.], "koeb": [104., 0.],
    })
    supply_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    sut_a = SUT(price_basis="current_year", supply=supply_df, use=use_before, metadata=metadata)
    sut_b = SUT(price_basis="current_year", supply=supply_df, use=use_after, metadata=metadata)

    result = inspect_sut_comparison(sut_a, sut_b, filter_nan_as_zero=True)
    # D has before=NaN and after=0 for all layers — all suppressed.
    layer_nrnrs = result.data.use_price_layers.index.get_level_values("nrnr").tolist()
    assert "D" not in layer_nrnrs
    # use_basic: D has before=NaN after=0 — suppressed.
    basic_nrnrs = result.data.use_basic.index.get_level_values("nrnr").tolist()
    assert "D" not in basic_nrnrs


def test_filter_nan_as_zero_keeps_new_nonzero_row(cols, metadata):
    # New product D with non-zero layer value — must still appear.
    use_before = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [90.], "ava": [5.], "moms": [9.], "koeb": [104.],
    })
    use_after = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "D"], "trans": ["P2", "P2"], "brch": ["X", "X"],
        "bas": [90., 50.], "ava": [5., 3.], "moms": [9., 6.], "koeb": [104., 59.],
    })
    supply_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    sut_a = SUT(price_basis="current_year", supply=supply_df, use=use_before, metadata=metadata)
    sut_b = SUT(price_basis="current_year", supply=supply_df, use=use_after, metadata=metadata)

    result = inspect_sut_comparison(sut_a, sut_b, filter_nan_as_zero=True)
    layer_nrnrs = result.data.use_price_layers.index.get_level_values("nrnr").tolist()
    assert "D" in layer_nrnrs


def test_filter_nan_as_zero_suppresses_removed_zero_row(cols, metadata):
    # Product D existed in before with 0 value and is absent from after.
    use_before = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "D"], "trans": ["P2", "P2"], "brch": ["X", "X"],
        "bas": [90., 0.], "ava": [5., 0.], "moms": [9., 0.], "koeb": [104., 0.],
    })
    use_after = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [90.], "ava": [5.], "moms": [9.], "koeb": [104.],
    })
    supply_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    sut_a = SUT(price_basis="current_year", supply=supply_df, use=use_before, metadata=metadata)
    sut_b = SUT(price_basis="current_year", supply=supply_df, use=use_after, metadata=metadata)

    result = inspect_sut_comparison(sut_a, sut_b, filter_nan_as_zero=True)
    layer_nrnrs = result.data.use_price_layers.index.get_level_values("nrnr").tolist()
    assert "D" not in layer_nrnrs


def test_filter_nan_as_zero_false_keeps_zero_nan_rows(cols, metadata):
    # Default behaviour: NaN vs 0 rows are always shown.
    use_before = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [90.], "ava": [5.], "moms": [9.], "koeb": [104.],
    })
    use_after = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "D"], "trans": ["P2", "P2"], "brch": ["X", "X"],
        "bas": [90., 0.], "ava": [5., 0.], "moms": [9., 0.], "koeb": [104., 0.],
    })
    supply_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    sut_a = SUT(price_basis="current_year", supply=supply_df, use=use_before, metadata=metadata)
    sut_b = SUT(price_basis="current_year", supply=supply_df, use=use_after, metadata=metadata)

    result = inspect_sut_comparison(sut_a, sut_b)  # filter_nan_as_zero=False (default)
    layer_nrnrs = result.data.use_price_layers.index.get_level_values("nrnr").tolist()
    assert "D" in layer_nrnrs


def test_filter_nan_as_zero_applies_to_supply(cols, metadata):
    # New supply row with bas=0 — suppressed when filter_nan_as_zero=True.
    supply_before = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [100.], "koeb": [100.],
    })
    supply_after = pd.DataFrame({
        "year": [2021, 2021], "nrnr": ["A", "D"], "trans": ["P1", "P1"], "brch": ["X", "X"],
        "bas": [100., 0.], "koeb": [100., 0.],
    })
    use_df = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P2"], "brch": ["X"],
        "bas": [90.], "ava": [5.], "moms": [9.], "koeb": [104.],
    })
    sut_a = SUT(price_basis="current_year", supply=supply_before, use=use_df, metadata=metadata)
    sut_b = SUT(price_basis="current_year", supply=supply_after, use=use_df, metadata=metadata)

    result = inspect_sut_comparison(sut_a, sut_b, filter_nan_as_zero=True)
    supply_nrnrs = result.data.supply.index.get_level_values("nrnr").tolist()
    assert "D" not in supply_nrnrs


# ---------------------------------------------------------------------------
# Balancing targets comparison
# ---------------------------------------------------------------------------
#
# Targets cover transactions P1 (supply) and P2 (use) for categories X and Y.
# before targets: supply P1/X bas=300, use P2/X bas=200 ava=10 moms=20 koeb=230
# after targets:  supply P1/X bas=310 (+10), use P2/X bas=200 ava=10 moms=25 (+5) koeb=235 (+5)
# P1/Y and P2/Y are identical in before and after (no change).
# ---------------------------------------------------------------------------


@pytest.fixture
def before_targets():
    return BalancingTargets(
        supply=pd.DataFrame({
            "year":  [2021, 2021],
            "trans": ["P1", "P1"],
            "brch":  ["X",  "Y"],
            "bas":   [300., 100.],
        }),
        use=pd.DataFrame({
            "year":  [2021, 2021],
            "trans": ["P2", "P2"],
            "brch":  ["X",  "Y"],
            "bas":   [200., 80.],
            "ava":   [10.,  4.],
            "moms":  [20.,  8.],
            "koeb":  [230., 92.],
        }),
    )


@pytest.fixture
def after_targets():
    return BalancingTargets(
        supply=pd.DataFrame({
            "year":  [2021, 2021],
            "trans": ["P1", "P1"],
            "brch":  ["X",  "Y"],
            "bas":   [310., 100.],  # X changed
        }),
        use=pd.DataFrame({
            "year":  [2021, 2021],
            "trans": ["P2", "P2"],
            "brch":  ["X",  "Y"],
            "bas":   [200., 80.],
            "ava":   [10.,  4.],
            "moms":  [25.,  8.],   # X changed
            "koeb":  [235., 92.],  # X changed
        }),
    )


@pytest.fixture
def before_sut_with_targets(before_supply, before_use, metadata, before_targets):
    return SUT(
        price_basis="current_year",
        supply=before_supply,
        use=before_use,
        metadata=metadata,
        balancing_targets=before_targets,
    )


@pytest.fixture
def after_sut_with_targets(after_supply, after_use, metadata, after_targets):
    return SUT(
        price_basis="current_year",
        supply=after_supply,
        use=after_use,
        metadata=metadata,
        balancing_targets=after_targets,
    )


def test_targets_none_when_before_has_no_targets(before_sut, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut, after_sut_with_targets)
    assert result.data.balancing_targets_supply is None
    assert result.data.balancing_targets_use_basic is None
    assert result.data.balancing_targets_use_purchasers is None
    assert result.data.balancing_targets_use_price_layers is None


def test_targets_none_when_after_has_no_targets(before_sut_with_targets, after_sut):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut)
    assert result.data.balancing_targets_supply is None


def test_targets_supply_only_changed_row_returned(before_sut_with_targets, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    supply = result.data.balancing_targets_supply
    assert len(supply) == 1
    row = supply.iloc[0]
    assert row["before_bas"] == 300.
    assert row["after_bas"] == 310.
    assert row["diff_bas"] == 10.


def test_targets_use_purchasers_only_changed_row(before_sut_with_targets, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    purch = result.data.balancing_targets_use_purchasers
    assert len(purch) == 1
    row = purch.iloc[0]
    assert row["before_koeb"] == 230.
    assert row["after_koeb"] == 235.
    assert row["diff_koeb"] == 5.


def test_targets_price_layers_only_changed_layer(before_sut_with_targets, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    layers = result.data.balancing_targets_use_price_layers
    # Only moms changed; ava unchanged.
    assert len(layers) == 1
    assert layers.index.get_level_values("price_layer")[0] == "moms"
    assert layers.iloc[0]["diff"] == 5.


def test_targets_index_names(before_sut_with_targets, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    supply = result.data.balancing_targets_supply
    # No product dimension; index is (id, transaction, category).
    assert supply.index.names == ["year", "trans", "brch"]


def test_targets_price_layers_index_has_price_layer_level(
    before_sut_with_targets, after_sut_with_targets
):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    layers = result.data.balancing_targets_use_price_layers
    assert "price_layer" in layers.index.names
    assert "year" in layers.index.names
    assert "nrnr" not in layers.index.names


def test_targets_filter_by_transactions(before_sut_with_targets, after_sut_with_targets):
    # Filter to P2 — supply targets table should be empty.
    result = inspect_sut_comparison(
        before_sut_with_targets, after_sut_with_targets, transactions="P2"
    )
    assert len(result.data.balancing_targets_supply) == 0
    assert len(result.data.balancing_targets_use_purchasers) == 1


def test_targets_unchanged_rows_not_returned(before_sut_with_targets, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    supply = result.data.balancing_targets_supply
    # Y is unchanged — only X should appear.
    cats = supply.index.get_level_values("brch").tolist()
    assert "Y" not in cats


def test_rel_nan_when_before_zero(cols, metadata):
    # before bas = 0, after bas = 10 → rel = NaN (division by zero).
    supply_before = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [0.], "koeb": [0.],
    })
    supply_after = pd.DataFrame({
        "year": [2021], "nrnr": ["A"], "trans": ["P1"], "brch": ["X"],
        "bas": [10.], "koeb": [10.],
    })
    use_df = pd.DataFrame(columns=["year", "nrnr", "trans", "brch", "bas", "ava", "moms", "koeb"])
    sut_a = SUT(price_basis="current_year", supply=supply_before, use=use_df, metadata=metadata)
    sut_b = SUT(price_basis="current_year", supply=supply_after, use=use_df, metadata=metadata)
    result = inspect_sut_comparison(sut_a, sut_b)
    supply = result.data.supply
    assert len(supply) == 1
    assert pd.isna(supply.iloc[0]["rel_bas"])


# ---------------------------------------------------------------------------
# summary field
# ---------------------------------------------------------------------------


def test_summary_is_dataframe(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result.data.summary, pd.DataFrame)


def test_summary_index_name(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert result.data.summary.index.name == "table"


def test_summary_column(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert list(result.data.summary.columns) == ["n_differences"]


def test_summary_sut_rows_present(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    idx = result.data.summary.index.tolist()
    assert "supply" in idx
    assert "use_basic" in idx
    assert "use_purchasers" in idx
    assert "use_price_layers" in idx


def test_summary_correct_counts(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    summary = result.data.summary
    assert summary.loc["supply", "n_differences"] == len(result.data.supply)
    assert summary.loc["use_basic", "n_differences"] == len(result.data.use_basic)
    assert summary.loc["use_purchasers", "n_differences"] == len(result.data.use_purchasers)
    assert summary.loc["use_price_layers", "n_differences"] == len(result.data.use_price_layers)


def test_summary_no_target_rows_when_targets_absent(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    idx = result.data.summary.index.tolist()
    assert "balancing_targets_supply" not in idx
    assert "balancing_targets_use_basic" not in idx
    assert "balancing_targets_use_purchasers" not in idx
    assert "balancing_targets_use_price_layers" not in idx


def test_summary_target_rows_present_when_targets_available(
    before_sut_with_targets, after_sut_with_targets
):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    idx = result.data.summary.index.tolist()
    assert "balancing_targets_supply" in idx
    assert "balancing_targets_use_basic" in idx
    assert "balancing_targets_use_purchasers" in idx
    assert "balancing_targets_use_price_layers" in idx


def test_summary_target_counts_correct(before_sut_with_targets, after_sut_with_targets):
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    summary = result.data.summary
    assert summary.loc["balancing_targets_supply", "n_differences"] == len(result.data.balancing_targets_supply)
    assert summary.loc["balancing_targets_use_price_layers", "n_differences"] == len(result.data.balancing_targets_use_price_layers)


# ---------------------------------------------------------------------------
# Styled properties
# ---------------------------------------------------------------------------


def test_supply_property_returns_styler(before_sut, after_sut):
    from pandas.io.formats.style import Styler
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result.supply, Styler)


def test_use_basic_property_returns_styler(before_sut, after_sut):
    from pandas.io.formats.style import Styler
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result.use_basic, Styler)


def test_use_purchasers_property_returns_styler(before_sut, after_sut):
    from pandas.io.formats.style import Styler
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result.use_purchasers, Styler)


def test_use_price_layers_property_returns_styler(before_sut, after_sut):
    from pandas.io.formats.style import Styler
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result.use_price_layers, Styler)


def test_summary_property_returns_styler(before_sut, after_sut):
    from pandas.io.formats.style import Styler
    result = inspect_sut_comparison(before_sut, after_sut)
    assert isinstance(result.summary, Styler)


def test_styled_properties_handle_empty_tables(before_sut):
    from pandas.io.formats.style import Styler
    # Identical SUTs → all tables empty.
    result = inspect_sut_comparison(before_sut, before_sut)
    assert isinstance(result.supply, Styler)
    assert isinstance(result.use_price_layers, Styler)


def test_targets_styled_properties_return_none_when_absent(before_sut, after_sut):
    result = inspect_sut_comparison(before_sut, after_sut)
    assert result.balancing_targets_supply is None
    assert result.balancing_targets_use_basic is None
    assert result.balancing_targets_use_purchasers is None
    assert result.balancing_targets_use_price_layers is None


def test_targets_styled_properties_return_styler_when_present(
    before_sut_with_targets, after_sut_with_targets
):
    from pandas.io.formats.style import Styler
    result = inspect_sut_comparison(before_sut_with_targets, after_sut_with_targets)
    assert isinstance(result.balancing_targets_supply, Styler)
    assert isinstance(result.balancing_targets_use_basic, Styler)
    assert isinstance(result.balancing_targets_use_purchasers, Styler)
    assert isinstance(result.balancing_targets_use_price_layers, Styler)
