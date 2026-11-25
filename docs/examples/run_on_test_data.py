"""
Run the example notebooks on local test data.

The notebooks load the final annual SUTs from Statistics Denmark's network
drive. This script makes it possible to test them without access to it:

1. The local parquet files in ``docs/examples/data/`` are written in the legacy
   fixed-width format to a temporary folder with the same structure as the
   network drive.
2. Temporary copies of the notebooks, with the temporary folder as ``root`` in
   ``make_final_annual_sut_paths``, are run. The originals are not changed.
3. The temporary folder is removed.

Usage (from the project root)::

    uv run python docs/examples/run_on_test_data.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXAMPLES_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = EXAMPLES_FOLDER / "data"
SUTLAB_FOLDER = EXAMPLES_FOLDER.parent.parent
sys.path.insert(0, str(SUTLAB_FOLDER))

import sutlab

YEARS = [2016, 2017, 2018, 2019]

# The call that makes the paths in the notebooks starts with this text.
NOTEBOOK_PATHS_TEXT = "make_final_annual_sut_paths(years, "

# Price basis -> prefix of the local parquet files.
PARQUET_PREFIXES = {"current_year": "ta_l", "previous_year": "ta_d"}


def write_legacy_files(root: Path) -> None:
    """Write the local test data below ``root`` as it is stored on the network drive."""
    metadata = sutlab.load_metadata_from_excel(
        DATA_FOLDER / "ta_columns.xlsx",
        DATA_FOLDER / "ta_classifications.xlsx",
    )
    for price_basis, prefix in PARQUET_PREFIXES.items():
        parquet_paths = [DATA_FOLDER / f"{prefix}_{year}.parquet" for year in YEARS]
        sut = sutlab.load_sut_from_separated_parquet(
            YEARS, parquet_paths, metadata, price_basis
        )

        legacy_paths = sutlab.make_final_annual_sut_paths(
            YEARS, price_basis, root=root
        )
        for legacy_path in legacy_paths:
            legacy_path.parent.mkdir(parents=True, exist_ok=True)

        sutlab.write_sut_to_separated_nr_legacy_fwf(sut, YEARS, legacy_paths)


def copy_notebook(path: Path, folder: Path, root: Path) -> Path:
    """Copy a notebook to ``folder``, with the paths below ``root``."""
    notebook = json.loads(path.read_text(encoding="utf-8"))
    new_text = f"{NOTEBOOK_PATHS_TEXT}root={str(root)!r}, price_basis="
    n_replaced = 0
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        for i, line in enumerate(cell["source"]):
            if NOTEBOOK_PATHS_TEXT in line:
                cell["source"][i] = line.replace(NOTEBOOK_PATHS_TEXT, new_text)
                n_replaced += 1
    if n_replaced == 0:
        raise ValueError(
            f"{path.name} must have a line that contains '{NOTEBOOK_PATHS_TEXT}'."
        )
    copy_path = folder / path.name
    copy_path.write_text(json.dumps(notebook), encoding="utf-8")
    return copy_path


def run_notebook(path: Path) -> bool:
    """Run a notebook in its own folder. Print the result, return True if it ran."""
    command = [
        sys.executable, "-m", "nbconvert", "--to", "notebook", "--execute",
        "--output", f"run_{path.name}", path.name,
    ]
    result = subprocess.run(
        command, cwd=path.parent, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode == 0:
        print(f"OK      {path.name}")
        return True
    print(f"FAILED  {path.name}")
    print(result.stderr[-3000:])
    return False


def main() -> int:
    notebook_paths = sorted(EXAMPLES_FOLDER.glob("*.ipynb"))

    with tempfile.TemporaryDirectory() as temporary_folder:
        # The notebook copies are kept apart from the test data.
        root = Path(temporary_folder) / "drive"
        copies_folder = Path(temporary_folder) / "notebooks"
        root.mkdir()
        copies_folder.mkdir()

        print("Writing the test data in the legacy format ...")
        write_legacy_files(root)

        print("Running the notebooks ...")
        results = []
        for path in notebook_paths:
            copy_path = copy_notebook(path, copies_folder, root)
            results.append(run_notebook(copy_path))

    n_failed = results.count(False)
    print(f"{len(results) - n_failed} of {len(results)} notebooks ran without errors.")
    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
