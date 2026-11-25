"""
Run the example notebooks on local test data (Windows only).

The notebooks load the final annual SUTs from Statistics Denmark's network
drive. This script makes it possible to test them without that drive:

1. The local parquet files in ``docs/examples/data/`` are written in the legacy
   fixed-width format to a temporary folder with the same structure as the
   network drive.
2. The temporary folder is mapped to a drive letter with the Windows command
   ``subst``. The letter in the notebooks is used if it is free, otherwise
   another one.
3. Temporary copies of the notebooks are run. The originals are not changed.
4. The mapping and the temporary folder are removed.

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

# The line that sets the drive in the notebooks starts with this text.
NOTEBOOK_DRIVE = "x"
NOTEBOOK_DRIVE_TEXT = f'drive = "{NOTEBOOK_DRIVE}"'

# Price basis -> prefix of the local parquet files.
PARQUET_PREFIXES = {"current_year": "ta_l", "previous_year": "ta_d"}


def is_drive_free(drive: str) -> bool:
    """Return True if no drive, including a disconnected one, has this letter."""
    if Path(f"{drive}:/").exists():
        return False
    # A disconnected network drive does not exist as a path, but is still known
    # to "net use".
    result = subprocess.run(
        ["net", "use", f"{drive}:"], capture_output=True, stdin=subprocess.DEVNULL
    )
    return result.returncode != 0


def choose_drive() -> str:
    """Return the letter used in the notebooks if it is free, otherwise another."""
    candidates = NOTEBOOK_DRIVE + "zywvutsrqponmlkjihgfe"
    for drive in candidates:
        if is_drive_free(drive):
            return drive
    raise RuntimeError("No free drive letter found.")


def write_legacy_files(root: Path, drive: str) -> None:
    """Write the local test data below ``root`` as it is stored on the drive."""
    metadata = sutlab.load_metadata_from_excel(
        DATA_FOLDER / "ta_columns.xlsx",
        DATA_FOLDER / "ta_classifications.xlsx",
    )
    for price_basis, prefix in PARQUET_PREFIXES.items():
        parquet_paths = [DATA_FOLDER / f"{prefix}_{year}.parquet" for year in YEARS]
        sut = sutlab.load_sut_from_separated_parquet(
            YEARS, parquet_paths, metadata, price_basis
        )

        # Same paths as in the notebooks, but with the drive replaced by root.
        legacy_paths = []
        for path in sutlab.make_final_annual_sut_paths(YEARS, drive, price_basis):
            legacy_path = root / path.relative_to(path.anchor)
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_paths.append(legacy_path)

        sutlab.write_sut_to_separated_nr_legacy_fwf(sut, YEARS, legacy_paths)


def copy_notebook(path: Path, folder: Path, drive: str) -> Path:
    """Copy a notebook to ``folder``, with ``drive`` as the drive letter."""
    notebook = json.loads(path.read_text(encoding="utf-8"))
    n_replaced = 0
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        for i, line in enumerate(cell["source"]):
            if line.startswith(NOTEBOOK_DRIVE_TEXT):
                cell["source"][i] = line.replace(
                    NOTEBOOK_DRIVE_TEXT, f'drive = "{drive}"'
                )
                n_replaced += 1
    if n_replaced != 1:
        raise ValueError(
            f"{path.name} must have exactly one line that starts with "
            f"'{NOTEBOOK_DRIVE_TEXT}', found {n_replaced}."
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
    drive = choose_drive()

    with tempfile.TemporaryDirectory() as temporary_folder:
        # The notebook copies are kept apart from the mapped folder.
        root = Path(temporary_folder) / "drive"
        copies_folder = Path(temporary_folder) / "notebooks"
        root.mkdir()
        copies_folder.mkdir()

        print("Writing the test data in the legacy format ...")
        write_legacy_files(root, drive)

        subprocess.run(["subst", f"{drive}:", str(root)], check=True)
        try:
            print(f"Running the notebooks with drive {drive}: ...")
            results = []
            for path in notebook_paths:
                copy_path = copy_notebook(path, copies_folder, drive)
                results.append(run_notebook(copy_path))
        finally:
            subprocess.run(["subst", f"{drive}:", "/D"], check=True)

    n_failed = results.count(False)
    print(f"{len(results) - n_failed} of {len(results)} notebooks ran without errors.")
    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
