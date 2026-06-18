"""
Fetch a sandsuet-compliant sample dataset from Zenodo and run the compliance checker
on it.

Dataset: TDB-12-1 topography and experiment control sandsuet - sample
DOI:     https://doi.org/10.5281/zenodo.19076639

A 200x200x200 datacube from a fan-delta experiment at Tulane University:
200 hours of runtime over a 1m x 1m domain at 5mm resolution.

Requirements:
    pip install pooch sandsuet-checker
"""

import pooch

from sandsuet_checker import SandsuetChecker
from sandsuet_checker.cli import format_report

SAMPLE_FILE = pooch.retrieve(
    url="doi:10.5281/zenodo.19076639/tdb12-sample.nc",
    known_hash="md5:21f7dec09dbeca3aaf1738b320e2294c",
    progressbar=True,
)

checker = SandsuetChecker(SAMPLE_FILE)
results = checker.run_all()
print(format_report(SAMPLE_FILE, results, use_color=True))
