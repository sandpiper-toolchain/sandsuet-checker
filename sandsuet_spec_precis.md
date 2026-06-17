### Technical Precis: sandsuet v1.0.0 Specification and Compliance Requirements

##### 1\. Project Context and Ecosystem

The *sandsuet* data specification is the interoperability keystone of the *sandpiper* toolchain, a cyberinfrastructure ecosystem designed to accelerate code and data reuse in geomorphology. While the toolchain includes modular components such as *pinion* (experimental motion control), *feeder* (sediment delivery), and *sandplover* (analysis of rivers and deltas), *sandsuet* serves as the standardized interface that allows data to flow seamlessly from acquisition to analysis. Architecturally, *sandsuet* is defined as an **"analysis-ready"** specification. It is explicitly intended for implementation at **Phase 5 (data processing and analysis)** of the research lifecycle. By applying the specification post-quality check but prior to analysis, researchers ensure that their scientific conclusions are derived from the exact same data product that is eventually shared via repositories like Zenodo. This distinguishes *sandsuet* from long-term archival standards (e.g., SEN), which prioritize exhaustive metadata and raw data preservation. *sandsuet* instead prioritizes lightweight accessibility and immediate ingestion by modular software like *sandplover*, which is optimized specifically for *sandsuet*\-compliant data structures.

##### 2\. Core Architecture and Format Fundamentals

The *sandsuet* specification is agnostic regarding the underlying physical storage layer, provided the implementation maintains the required hierarchical and metadata structures. However, NetCDF4 is the recommended format, and the specification essentially defines a constrained subset of the NetCDF4 data model. **High-Level Architecture Rules:**

* **Grid Topology:** All data must be arranged in a rectilinear grid.
* **Coordinate Systems:** Data must be projected. Geographic coordinate systems (latitude/longitude) and unstructured meshes are strictly non-compliant.
* **Identity Mapping:** Dimension names and their corresponding coordinate variables must match exactly.
* **Versioning:** Datasets must adhere to Semantic Versioning (X.Y.Z), with the version indicated in global metadata. The "v" prefix must not be used.
* **Hierarchical Encapsulation:** Data must be organized into a multi-level structure to distinguish primary analysis targets from supporting information.

##### 3\. Data Hierarchy and Grouping Logic

The specification enforces a structural distinction between "Essential Data" (primary variables for reuse) and "Auxiliary Data" (supporting information). **Hierarchical Organization Rules:**

* **Top-Level (Root):** The root of the dataset must contain the Essential Data. These variables **must** possess the maximum number of dimensions found anywhere within the file. If a file contains 4D spatiotemporal data, the 4D variables must reside here.
* **Lower Levels (Groups):** Reserved for Auxiliary Data. This includes variables with lower dimensionality (e.g., 1D time series) or supporting spatial information (e.g., masks) that reference and support the essential variables.
* **Group Naming and Logic:** While group naming is technically arbitrary, descriptive names like `group: meta` are recommended to encapsulate variables such as `water_level`, `sediment_supply_rate`, or `water_supply_rate`.
* **Implementation Note:** Auxiliary data must be structured to provide context to the variables in the root, ensuring the dataset remains a self-describing unit.

##### 4\. Dimensional Hierarchy and Ordering Rules

Variables in a *sandsuet* dataset are restricted to a maximum of four dimensions. A strict dimensional ordering hierarchy must be maintained following the formula:

**Temporal (T) \> Vertical Spatial (Z) \> Horizontal Spatial (H) \> Horizontal Spatial (H)**

| Valid Dimension Combinations | Rank | Description |
| \------ | \------ | \------ |
| T, Z, Y, X | 4D | Spatiotemporal with vertical component (e.g., 3D plume over time) |
| T, Y, X | 3D | Spatiotemporal surface/map view (e.g., delta top) |
| Z, Y, X | 3D | 3D Spatial (e.g., stratigraphic volume) |
| Y, X | 2D | 2D Spatial snapshot |
| T | 1D | Temporal only (Auxiliary, e.g., sea-level time series) |
|  | 0D | Scalar (Auxiliary, e.g., constant forcing value) |

**Constraints on Dimensions:**

* **Omission:** Absent dimensions are simply omitted while preserving the relative hierarchy of the remaining dimensions.
* **Horizontal Order:** The relative ordering of the two horizontal dimensions (e.g., X vs. Y) is not enforced unless the dataset is explicitly georeferenced (see Section 7).
* **Temporal Dimension Naming:** The temporal dimension need not be named "time." Any dimension whose coordinate variable carries a time-based unit (e.g., `"second"`, `"days since 2000-01-01"`) is recognized as temporal.
* **Vertical Spatial Preference:** To ensure consistency in Z-axis monotonicity, the vertical dimension should represent **elevation** rather than depth or travel time.
* **Orthogonality:** All spatial dimensions must be orthogonal to one another. This is assumed to hold for any rectilinear grid and is not computationally verified.

##### 5\. Coordinate Variable Validation Logic

A compliance tool must enforce strict validation on coordinate variables. The following logic defines a compliant coordinate:

* **Identity Mapping:** The coordinate variable name must match its dimension name exactly.
* **Spatial Uniformity:** Spatial coordinates (X, Y, Z) must have **uniform spacing**. Spacing is validated with a relative tolerance of 1×10⁻⁴ to accommodate floating-point rounding in generated coordinates.
* **Temporal Spacing:** Temporal coordinates (T) are permitted to have non-uniform spacing.
* **Monotonicity:** All coordinates must be monotonic (strictly increasing or decreasing).
* **Temporal Constraint:** Temporal coordinates must be **monotonically increasing only**.
* **Coordinate Flexibility:** The specification allows multiple coordinate variables to locate variables along the same dimension. For example, if "Sensor 1" and "Sensor 2" record at different intervals (e.g., 5 min vs 20 min), they may have distinct temporal coordinate variables that reference the same absolute time datum.

##### 6\. Metadata and Attribute Requirements

Metadata must provide both semantic context and technical definitions. **Global Attributes:**

* **Mandatory:** `sandsuet_version`. This must be a string in semantic versioning format (e.g., `"1.0.0"`) without the `"v"` prefix.
* **Recommended:** Instrument descriptions, original data source DOIs, and creator information.

**Variable Attributes:**

* **Mandatory on data variables:** `units` and `description`. Coordinate variables (those sharing a name with a dimension) are exempt from the `description`/`long_name` requirement.
* **Units:** Units must be present on all variables. Standard UDUNITS strings (e.g., `"m s-1"`) are preferred but plain-English equivalents (e.g., `"meters per second"`) are accepted; non-standard units produce an advisory warning rather than a failure.
* **Ontology Standards:** The `long_name` attribute on data variables should reference the **Scientific Variables Ontology (SVO)** to ensure machine-readability. Coordinate variables are exempt from this recommendation.
* **Missing Data:** A consistent `_FillValue` must be indicated in the metadata and used for all missing values within a specific variable. While different variables can use different fill values, they must be consistent internally.

##### 7\. Compliance Checker Implementation — `sandsuet_checker.py`

The compliance checker (`sandsuet_checker.py`) is a single-file Python CLI tool implementing the following checks. It requires `netCDF4`, `numpy`, and `cf-units`.

**Usage:**
```
python sandsuet_checker.py <file.nc> [-o report.txt] [--georeferenced]
```

The `--georeferenced` flag enables the N-S-first horizontal dimension check (Section 7c), which is only meaningful for datasets using real-world coordinate systems. For datasets with arbitrary spatial coordinates (e.g., laboratory experiments, model grids without CRS), omit this flag.

###### *Mandatory Schema & Logic (PASS/FAIL)*

* **Root Dimensionality:** Does the root contain variables with the maximum dimensionality found in the file?
* **Rank Limit:** Does any variable exceed four dimensions?
* **Identity Mapping:** Does every dimension have a corresponding coordinate variable with an identical name? (Checked in root and all subgroups.)
* **Dimensional Ordering:** Are dimensions ordered strictly as T > Z > H? (Temporal before vertical before horizontal. Relative order of the two horizontal dims is not enforced here.)
* **Spatial Orthogonality:** Assumed to hold for any rectilinear grid; nominally passed.
* **Strict Spatial Uniformity:** Is the spacing (Δ) constant for all spatial coordinates? (Relative tolerance 1×10⁻⁴.)
* **Temporal Monotonicity:** Are temporal coordinates monotonically increasing?
* **General Monotonicity:** Are all other coordinates monotonic (increasing or decreasing)?
* **Projected Coordinates:** Are coordinates free of geographic (angular/lat-lon) units? Cardinal-direction names (northing, easting, etc.) are recognized as projected and are not flagged. Variables named `latitude` or `longitude` are always flagged regardless of units.
* **Version Metadata:** Is `sandsuet_version` present as a global attribute in valid semver format without a `"v"` prefix?
* **Attribute Presence:** Do all **data variables** have `units` and `description`/`long_name`? (Coordinate variables are exempt from the description requirement.)
* **Internal Fill Value:** Is a consistent `_FillValue` used within each variable as defined in its metadata?
* **Global Unit Consistency:** Are all units parseable by UDUNITS via `cf-units`? Non-standard plain-English units produce a warning rather than a failure.

###### *Best Practice & Recommendation (WARNING)*

* **SVO Reference:** Does the `long_name` attribute on data variables reference the Scientific Variables Ontology? (Coordinate variables are exempt.)
* **Z-Axis Definition:** Is the vertical dimension defined as elevation (recommended for monotonicity)?
* **Fill Value Presence:** Do all variables declare a `_FillValue`?
* **N-S First (georeferenced only):** If `--georeferenced` is passed, is the N-S dimension (Y/Northing) ordered before the E-W dimension (X/Easting)?

##### 8\. Authorship and Attribution

The sandsuet specification was developed by the sandpiper toolchain team (Moodie et al., 2026). The compliance checker was developed collaboratively:

* **Conceptual design and specification:** sandpiper toolchain team
* **Initial prototype:** NotebookLM AI assistant, under technical direction of the sandpiper toolchain team
* **Implementation and refinement:** Claude (Anthropic), under intellectual guidance and direction of the sandpiper toolchain team
