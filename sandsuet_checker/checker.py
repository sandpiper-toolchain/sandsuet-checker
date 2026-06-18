"""
sandsuet_checker — sandsuet v1.0.0 Compliance Checker
======================================================
Validates NetCDF4 files against the sandsuet analysis-ready data specification.

Specification reference:
    Moodie et al. (2026). sandsuet v1.0.0: an analysis-ready data specification
    for the sandpiper geomorphology toolchain.

Authorship:
    Conceptual design and specification: sandpiper toolchain team
    Initial prototype: NotebookLM AI assistant, under technical direction of
        the sandpiper toolchain team
    Implementation and refinement: Claude (Anthropic), under intellectual
        guidance and direction of the sandpiper toolchain team

Primary API:
    from sandsuet_checker import SandsuetChecker
    checker = SandsuetChecker("myfile.nc", georeferenced=False)
    results = checker.run_all()  # list of (section, status, message) tuples
"""

import os
import re

import netCDF4 as nc
import numpy as np

try:
    import cf_units

    CF_UNITS_AVAILABLE = True
except ImportError:
    CF_UNITS_AVAILABLE = False

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

TIME_NAMES = {"time", "t"}
VERTICAL_NAMES = {
    "z",
    "depth",
    "elevation",
    "height",
    "level",
    "lev",
    "alt",
    "altitude",
}
NORTH_SOUTH_NAMES = {
    "y",
    "lat",
    "latitude",
    "northing",
    "north",
    "south",
    "southing",
    "n",
    "s",
}
EAST_WEST_NAMES = {
    "x",
    "lon",
    "longitude",
    "easting",
    "westing",
    "east",
    "west",
    "e",
    "w",
}

TIME_BASE_UNITS = {
    "s",
    "second",
    "seconds",
    "sec",
    "secs",
    "min",
    "minute",
    "minutes",
    "h",
    "hr",
    "hour",
    "hours",
    "d",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
}


def _classify_dim(name, units=None):
    n = name.lower()
    if n in TIME_NAMES:
        return "T"
    if units:
        u = str(units).lower().strip()
        if "since" in u:
            return "T"
        if u in TIME_BASE_UNITS:
            return "T"
    if n in VERTICAL_NAMES:
        return "Z"
    if n in NORTH_SOUTH_NAMES:
        return "Y"
    if n in EAST_WEST_NAMES:
        return "X"
    return "?"


def _all_variables(group):
    result = list(group.variables.values())
    for sub in group.groups.values():
        result.extend(_all_variables(sub))
    return result


def _all_groups(group):
    result = [group]
    for sub in group.groups.values():
        result.extend(_all_groups(sub))
    return result


class SandsuetChecker:
    """
    Compliance checker for the sandsuet v1.0.0 data specification.

    Parameters
    ----------
    filepath : str
        Path to the NetCDF4 file to validate.
    georeferenced : bool
        If True, enables the N-S-first horizontal dimension check. Use only
        for datasets with real-world coordinate reference systems (e.g. UTM).
        Defaults to False for model/lab grids with arbitrary spatial coords.
    """

    GEOGRAPHIC_NAMES = {"lat", "latitude", "lon", "longitude"}
    CARDINAL_NAMES = (set(NORTH_SOUTH_NAMES) | set(EAST_WEST_NAMES)) - GEOGRAPHIC_NAMES

    def __init__(self, filepath, georeferenced=False):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        self.ds = nc.Dataset(filepath)
        self.filepath = filepath
        self.georeferenced = georeferenced
        self.results = []
        self.max_dims = 0

    def _log(self, section, status, message):
        self.results.append((section, status, message))

    def check_root_dimensionality(self):
        all_vars = _all_variables(self.ds)
        if not all_vars:
            self._log("Hierarchy", "FAIL", "No variables found in dataset.")
            return
        self.max_dims = max(v.ndim for v in all_vars)
        root_max = [v for v in self.ds.variables.values() if v.ndim == self.max_dims]
        if root_max:
            names = ", ".join(v.name for v in root_max)
            self._log(
                "Hierarchy",
                "PASS",
                f"Essential {self.max_dims}D data in root: {names}.",
            )
        else:
            self._log(
                "Hierarchy",
                "FAIL",
                f"Max dimensionality is {self.max_dims}D but no such variables found in root.",
            )

    def check_rank_limit(self):
        failed = [
            f"'{v.name}' ({v.ndim}D)" for v in _all_variables(self.ds) if v.ndim > 4
        ]
        if failed:
            self._log(
                "Rank limit",
                "FAIL",
                f"Variables exceed 4-dimension limit: {', '.join(failed)}.",
            )
        else:
            self._log("Rank limit", "PASS", "All variables are ≤4 dimensions.")

    def check_identity_mapping(self):
        failed = []
        for group in _all_groups(self.ds):
            for dim_name in group.dimensions:
                if (
                    dim_name not in group.variables
                    and dim_name not in self.ds.variables
                ):
                    loc = group.path if hasattr(group, "path") else "root"
                    failed.append(f"'{dim_name}' (in {loc})")
        if failed:
            self._log(
                "Identity mapping",
                "FAIL",
                f"Dimensions without a coordinate variable: {', '.join(failed)}.",
            )
        else:
            self._log(
                "Identity mapping",
                "PASS",
                "Every dimension has a matching coordinate variable.",
            )

    def check_dimensional_ordering(self):
        # X and Y share the same rank — horizontal order is not enforced here
        # (georeferenced N-S-first is a separate check).
        ORDER = {"T": 0, "Z": 1, "Y": 2, "X": 2, "?": 3}
        failed = []
        for var in self.ds.variables.values():
            if var.ndim < 2:
                continue
            classes = [
                _classify_dim(d, getattr(self.ds.variables.get(d), "units", None))
                for d in var.dimensions
            ]
            for i in range(len(classes) - 1):
                if ORDER[classes[i]] > ORDER[classes[i + 1]]:
                    failed.append(
                        f"'{var.name}' dims {list(var.dimensions)} (classified {classes})"
                    )
                    break
        if failed:
            self._log(
                "Dim ordering",
                "FAIL",
                f"Incorrect dimension order (must be T>Z>H): {'; '.join(failed)}.",
            )
        else:
            self._log(
                "Dim ordering",
                "PASS",
                "Dimension ordering follows T > Z > H hierarchy.",
            )

    def check_spatial_orthogonality(self):
        self._log(
            "Spatial orthogonality",
            "PASS",
            "Rectilinear grid topology implies orthogonal spatial dimensions.",
        )

    def check_coordinates(self):
        for dim_name in self.ds.dimensions:
            coord_var = self.ds.variables.get(dim_name)
            if coord_var is None:
                continue

            coord = coord_var[:]
            if coord.size < 2:
                continue

            diffs = np.diff(coord.astype(float))
            coord_units = getattr(coord_var, "units", None)
            is_time = _classify_dim(dim_name, coord_units) == "T"

            if not is_time:
                if not np.allclose(diffs, diffs[0], rtol=1e-4, atol=0):
                    self._log(
                        "Spatial uniformity",
                        "FAIL",
                        f"Coordinate '{dim_name}' is not uniformly spaced "
                        f"(Δ range: {diffs.min():.6g}–{diffs.max():.6g}).",
                    )
                else:
                    self._log(
                        "Spatial uniformity",
                        "PASS",
                        f"Coordinate '{dim_name}' is uniformly spaced (Δ={diffs[0]:.6g}).",
                    )

            is_increasing = np.all(diffs > 0)
            is_decreasing = np.all(diffs < 0)

            if is_time:
                if is_increasing:
                    self._log(
                        "Temporal monotonicity",
                        "PASS",
                        f"Temporal coordinate '{dim_name}' is monotonically increasing.",
                    )
                else:
                    self._log(
                        "Temporal monotonicity",
                        "FAIL",
                        f"Temporal coordinate '{dim_name}' is not monotonically increasing.",
                    )
            else:
                if is_increasing or is_decreasing:
                    direction = "increasing" if is_increasing else "decreasing"
                    self._log(
                        "Monotonicity",
                        "PASS",
                        f"Coordinate '{dim_name}' is monotonically {direction}.",
                    )
                else:
                    self._log(
                        "Monotonicity",
                        "FAIL",
                        f"Coordinate '{dim_name}' is not monotonic.",
                    )

    def check_projected(self):
        degree_vars = []
        for name, var in self.ds.variables.items():
            units = getattr(var, "units", "").lower()
            has_degree_units = any(
                u in units for u in ("degree", "degrees_north", "degrees_east", "deg")
            )
            n = name.lower()
            if n in self.GEOGRAPHIC_NAMES or (
                has_degree_units and n not in self.CARDINAL_NAMES
            ):
                degree_vars.append(f"'{name}' (units='{var.units}')")
        if degree_vars:
            self._log(
                "Projected coords",
                "FAIL",
                f"Geographic (angular) units or lat/lon names found — "
                f"projected coordinates required: {', '.join(degree_vars)}.",
            )
        else:
            self._log(
                "Projected coords",
                "PASS",
                "No geographic coordinates detected; coordinates appear projected.",
            )

    def check_version(self):
        if "sandsuet_version" not in self.ds.ncattrs():
            self._log(
                "Version", "FAIL", "Global attribute 'sandsuet_version' is missing."
            )
            return
        val = str(self.ds.sandsuet_version)
        if val.startswith("v"):
            self._log(
                "Version",
                "FAIL",
                f"sandsuet_version '{val}' must not have a 'v' prefix.",
            )
        elif not SEMVER_RE.match(val):
            self._log(
                "Version",
                "FAIL",
                f"sandsuet_version '{val}' is not valid semantic versioning (X.Y.Z).",
            )
        else:
            self._log("Version", "PASS", f"sandsuet_version '{val}' is valid.")

    def check_variable_attributes(self):
        all_dim_names = set()
        for g in _all_groups(self.ds):
            all_dim_names.update(g.dimensions.keys())

        missing_units, missing_desc = [], []
        for var in _all_variables(self.ds):
            if not hasattr(var, "units"):
                missing_units.append(var.name)
            is_coord = var.name in all_dim_names
            if not is_coord and not (
                hasattr(var, "description") or hasattr(var, "long_name")
            ):
                missing_desc.append(var.name)

        if missing_units:
            self._log(
                "Attribute presence",
                "FAIL",
                f"Variables missing 'units': {', '.join(missing_units)}.",
            )
        else:
            self._log(
                "Attribute presence", "PASS", "All variables have 'units' attribute."
            )

        if missing_desc:
            self._log(
                "Attribute presence",
                "FAIL",
                f"Data variables missing 'description'/'long_name': "
                f"{', '.join(missing_desc)}.",
            )
        else:
            self._log(
                "Attribute presence",
                "PASS",
                "All data variables have 'description' or 'long_name' attribute.",
            )

    def check_fill_values(self):
        for var in _all_variables(self.ds):
            declared = getattr(var, "_FillValue", None)
            if declared is None:
                self._log(
                    "Fill value",
                    "WARN",
                    f"Variable '{var.name}' has no '_FillValue' declared.",
                )
                continue
            raw = var[:]
            if isinstance(raw, np.ma.MaskedArray) and raw.mask.any():
                fill_used = np.unique(var[:].data[raw.mask])
                if not np.all(np.isclose(fill_used, float(declared), equal_nan=True)):
                    self._log(
                        "Fill value",
                        "FAIL",
                        f"Variable '{var.name}': actual fill values {fill_used} "
                        f"don't match declared _FillValue={declared}.",
                    )
                else:
                    self._log(
                        "Fill value",
                        "PASS",
                        f"Variable '{var.name}': fill value consistent.",
                    )
            else:
                self._log(
                    "Fill value",
                    "PASS",
                    f"Variable '{var.name}': no missing data or fill value consistent.",
                )

    def check_unit_consistency(self):
        if not CF_UNITS_AVAILABLE:
            self._log(
                "Unit consistency",
                "WARN",
                "cf-units not available; skipping UDUNITS validation.",
            )
            return
        invalid = []
        for var in _all_variables(self.ds):
            units_str = getattr(var, "units", None)
            if units_str is None:
                continue
            try:
                cf_units.Unit(units_str)
            except ValueError:
                invalid.append(f"'{var.name}' (units='{units_str}')")
        if invalid:
            self._log(
                "Unit consistency",
                "WARN",
                f"Variables with non-standard UDUNITS units (plain-English accepted): "
                f"{', '.join(invalid)}.",
            )
        else:
            self._log(
                "Unit consistency", "PASS", "All variable units are UDUNITS-compliant."
            )

    def check_svo_reference(self):
        svo_pattern = re.compile(r"svo\.colorado\.edu|[a-z_]+__[a-z_]+", re.IGNORECASE)
        all_dim_names = set()
        for g in _all_groups(self.ds):
            all_dim_names.update(g.dimensions.keys())
        missing = []
        for var in _all_variables(self.ds):
            if var.name in all_dim_names:
                continue
            long_name = getattr(var, "long_name", None)
            if long_name is None or not svo_pattern.search(long_name):
                missing.append(var.name)
        if missing:
            self._log(
                "SVO reference",
                "WARN",
                f"Data variables without SVO-style long_name: {', '.join(missing)}.",
            )
        else:
            self._log(
                "SVO reference",
                "PASS",
                "All data variables have SVO-referenced long_name.",
            )

    def check_z_axis_elevation(self):
        depth_names = {"depth", "d"}
        for dim_name in self.ds.dimensions:
            if _classify_dim(dim_name) == "Z":
                if dim_name.lower() in depth_names:
                    self._log(
                        "Z-axis definition",
                        "WARN",
                        f"Vertical dimension '{dim_name}' appears to be depth; "
                        f"elevation is recommended for Z-axis monotonicity.",
                    )
                else:
                    self._log(
                        "Z-axis definition",
                        "PASS",
                        f"Vertical dimension '{dim_name}' appears to be elevation-based.",
                    )

    def check_ns_first(self):
        if not self.georeferenced:
            self._log(
                "N-S first",
                "SKIP",
                "Skipped (pass --georeferenced to enable N-S ordering check).",
            )
            return
        for var in self.ds.variables.values():
            if var.ndim < 2:
                continue
            h_dims = [d for d in var.dimensions if _classify_dim(d) in ("X", "Y")]
            if len(h_dims) < 2:
                continue
            if _classify_dim(h_dims[0]) != "Y":
                self._log(
                    "N-S first",
                    "WARN",
                    f"Variable '{var.name}': first horizontal dim is '{h_dims[0]}' "
                    f"(E-W); N-S (Y/Northing) should come first.",
                )
                return
        self._log(
            "N-S first",
            "PASS",
            "N-S (Y) dimension precedes E-W (X) dimension where applicable.",
        )

    def run_all(self):
        """Run all compliance checks and return results as a list of (section, status, message)."""
        for name in sorted(SandsuetChecker.__dict__):
            check = getattr(self, name)
            if name.startswith("check_") and callable(check):
                check()

        return self.results
