# sandsuet-checker

A compliance checker for the **sandsuet v1.0.0** analysis-ready data specification.
sandsuet is the interoperability keystone of the [sandpiper](https://github.com/sandpiper-toolchain) geomorphology toolchain,
defining a constrained NetCDF4 structure that permits greater interoperability for geomorphology research.

## Installation

From the git repository source:

```bash
git clone https://github.com/sandpiper-toolchain/sandsuet-checker
cd sandsuet-checker
pip install .
```

**Dependencies:** `netCDF4`, `numpy`, `cf-units`

## Usage

### Command line

```bash
sandsuet-checker path/to/file.nc
```

Save the report to a file:

```bash
sandsuet-checker path/to/file.nc -o report.txt
```

Enable the N-S-first horizontal dimension check for georeferenced datasets (e.g. UTM coordinates):

```bash
sandsuet-checker path/to/file.nc --georeferenced
```

### Python API

```python
from sandsuet_checker import SandsuetChecker

checker = SandsuetChecker.from_path("path/to/file.nc", georeferenced=False)
results = checker.run_all()

for section, status, message in results:
    print(f"[{status}] {section}: {message}")
```

## Checks performed

| Check | Level | Description |
|-------|-------|-------------|
| Root dimensionality | PASS/FAIL | Essential data in root must have max dimensionality in file |
| Rank limit | PASS/FAIL | No variable may exceed 4 dimensions |
| Identity mapping | PASS/FAIL | Every dimension must have a matching coordinate variable |
| Dimensional ordering | PASS/FAIL | Dimensions must follow T > Z > H ordering |
| Spatial orthogonality | PASS/FAIL | Rectilinear grid assumed orthogonal |
| Spatial uniformity | PASS/FAIL | Spatial coordinates must be uniformly spaced |
| Temporal monotonicity | PASS/FAIL | Time coordinate must be monotonically increasing |
| Monotonicity | PASS/FAIL | All spatial coordinates must be monotonic |
| Projected coordinates | PASS/FAIL | Geographic (lat/lon) coordinates are non-compliant |
| Version metadata | PASS/FAIL | `sandsuet_version` global attribute must be valid semver |
| Attribute presence | PASS/FAIL | All data variables must have `units` and `description`/`long_name` |
| Fill value consistency | PASS/FAIL | Declared `_FillValue` must match values used in data |
| Unit consistency | WARN | Units should be UDUNITS-parseable |
| SVO reference | WARN | `long_name` should reference the Scientific Variables Ontology |
| Z-axis definition | WARN | Vertical axis should be elevation, not depth |
| Fill value presence | WARN | All variables should declare a `_FillValue` |
| N-S first | WARN | (georeferenced only) N-S dimension should precede E-W |

## Example

See `examples/fetch_sample.py` for a self-contained example that downloads a sandsuet-compliant
NetCDF4 file from Zenodo using [pooch](https://www.fatiando.org/pooch/) and runs the checker on it.

To run the example, pip install `sandsuet-checker` with optional dependencies first. This allows
a `tqdm` progress bar.

```bash
pip install sandsuet_checker[examples]
pip install pooch
python examples/fetch_sample.py
```

## Specification

The sandsuet v1.0.0 specification is described in:

> Moodie et al. (2026). *sandsuet v1.0.0: an analysis-ready data specification
> for the sandpiper geomorphology toolchain.*

## Acknowledgements

The sandsuet specification was developed by the sandpiper toolchain team.
The compliance checker was developed collaboratively:

- **Conceptual design and specification:** sandpiper toolchain team
- **Initial prototype:** NotebookLM AI assistant, under technical direction of the sandpiper toolchain team
- **Implementation and refinement:** Claude (Anthropic), under intellectual guidance and direction of the sandpiper toolchain team

## License

[MIT](LICENSE)
