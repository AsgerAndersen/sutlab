"""
Tests that the example notebooks in docs/examples contain no outputs.

The notebooks run on real data and the repository is public, so outputs must
be cleared before the notebooks are committed.
"""

import json
from pathlib import Path

import pytest

EXAMPLES_FOLDER = Path(__file__).parent.parent / "docs" / "examples"
NOTEBOOK_PATHS = sorted(EXAMPLES_FOLDER.glob("*.ipynb"))


def test_example_notebooks_exist():
    assert len(NOTEBOOK_PATHS) > 0


@pytest.mark.parametrize("path", NOTEBOOK_PATHS, ids=lambda path: path.name)
def test_example_notebook_has_no_outputs(path):
    notebook = json.loads(path.read_text(encoding="utf-8"))

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        assert cell["outputs"] == [], (
            f"{path.name} contains outputs. Clear them before committing, "
            f"see docs/examples/README.md."
        )
        assert cell["execution_count"] is None, (
            f"{path.name} has been run. Clear the outputs before committing, "
            f"see docs/examples/README.md."
        )
