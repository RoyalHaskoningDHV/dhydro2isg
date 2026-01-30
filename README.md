[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/RoyalHaskoningDHV/dhydro2isg/main?urlpath=%2Fdoc%2Ftree%2Fexamples%2Fdhydro+to+isg.ipynb)

# Dhydro2ISG

**Dhydro2ISG** is a Python package for extracting data from D-Hydro models and converting it into ISG format for groundwater modeling.

The initial version was developed by Haskoning for Waterschap Brabantse Delta and further enhanced by Waterschap Aa & Maas. In 2025, the tool was open-sourced with support from Waterboard De Dommel.

---

## Features

- Export D-Hydro models to ISG format, supporting segments, cross-sections, and water levels at calculation points (time series).
- Read both D-Hydro and ISG formats into a standardized format (STF), which can be edited in GIS and exported to ISG.

---

## ISG Support

The tool generates ISG files without surface-flow routing (ASFR=0). Supported parameters:

| Parameter    | Description                                                      | Source           |
|--------------|------------------------------------------------------------------|------------------|
| Water level  | Water level at the calculation node for the defined period       | D-Hydro model    |
| Bottom level | Bottom level at the calculation node                             | D-Hydro model    |
| Resistance   | River bed resistance at the calculation node (days)              | Manual input     |
| Inf.factor   | Infiltration factor at the calculation node (-)                  | Manual input     |
| mrc          | Manning’s Resistance Coefficient for the cross-section (-)       | Manual input     |

> **Note:** Q-H relationships and structures are not supported.

---

## Notes

- The code has been tested on a limited set of D-Hydro models. Please validate the output before use.
- Tested with D-Hydro versions: XX, XX, 2025.01, and 2025.03.
- If you need additional functionality, create a branch and propose a solution via GitHub.
- For bugs, please create an issue (and, if possible, a proposed fix).
- The tool depends on `hydrolib-core`. Unsupported model versions may cause errors.

---

## Installation & Usage

- Install via pip:

    ```bash
    pip install dhydro2isg
    ```

- Documentation in the example notebook: [examples folder](https://github.com/RoyalHaskoningDHV/dhydro2isg/examples) demonstrates reading a D-Hydro model and exporting to ISG.

---

## Changelog

### Version 1.0.0

- First release
- Minor textual improvements

### Version 0.4.0


- Removed hydrolib-core dependency

### Version 0.3.3

- Published open source under GPL v3 license
- Added pip installation support
- Added example notebooks
- Migrated environment file to `pyproject.toml` and updated dependencies
- Improved aggregation of water levels over defined periods

### Version 0.2.0

- Updated environment and hydrolib-core version (Python < 3.12, tested with 3.11.6)
- Required `pydantic = 1.10` for hydrolib-core compatibility
- New environment file: `environment - new HL.yml`
- Improved snapping of calculation points to waterlines using buffer + spatial join (sjoin), replacing `ckdnearest`
- Added aggregation window option for final calculation period (e.g., "1D" for last day, with "mean" or "min" aggregation)
- Default: 1-day window, mean aggregation

---

## Contact

**Product Owner**
- toine.kerckhoffs@haskoning.com


