# Examples

Notebooks that show how `sutlab` is used. They give an overall idea and do not cover every function or option. Start with the first one. The others can be read in any order.

| Notebook | Shows |
|---|---|
| [01_getting_started](01_getting_started.ipynb) | Metadata, loading data, finding codes, selecting rows, writing files |
| [02_inspecting_a_sut](02_inspecting_a_sut.ipynb) | Inspecting products, industries and final uses; display settings; Excel |
| [03_gdp_and_volumes](03_gdp_and_volumes.ipynb) | GDP, contributions to growth, chained volumes |
| [04_balancing](04_balancing.ipynb) | Targets, tolerances, locks, balancing products and columns |
| [05_adjusting_and_comparing](05_adjusting_and_comparing.ipynb) | Adding revisions, comparing two versions |
| [06_aggregating](06_aggregating.ipynb) | Merging products and industries, totals, price layer rates |

## Data

The notebooks use real supply and use tables, which are **not** part of this repository. Copy these files to `docs/examples/data/` before you run them:

- `ta_l_2016.parquet` to `ta_l_2019.parquet` (current prices)
- `ta_d_2016.parquet` to `ta_d_2019.parquet` (previous year's prices)
- `ta_columns.xlsx` and `ta_classifications.xlsx` (metadata)

Files written by the notebooks in this folder end up in `docs/examples/output/`. Git ignores `data/` and `output/`.

The folder `config/` holds invented revisions, tolerances and locks, and is part of the repository.

## Running the notebooks

Open a notebook in VS Code, choose a Python environment as the kernel, and run the cells from the top. The environment needs Python 3.12 or newer and the packages `pandas`, `openpyxl`, `pyarrow`, `jinja2` and `ipykernel`. `sutlab` itself does not need to be installed: the first code cell adds its location to `sys.path`. The project's own environment, created with `uv sync`, also works.

The location is the absolute path `sutlab_folder` in the first code cell. `data/` and `config/` are found from it as well, so a notebook can be copied to another folder and still run. If `sutlab` is moved, change `sutlab_folder` in all the notebooks.

Output files are written to a folder `output/` in the working directory, which is normally the folder of the notebook. Git only ignores the one in `docs/examples/`, so do not commit copies or their outputs, as they contain real figures.

## Clear the outputs before you commit

This repository is public, and the outputs contain real figures. Always clear them before committing:

```
uv run jupyter nbconvert --clear-output --inplace "docs/examples/*.ipynb"
```

Or use *Clear All Outputs* in VS Code. A test checks that there are none:

```
uv run pytest tests/test_example_notebooks.py
```
