# Validation and Field Calibration

This directory is the single repository home for field-validation evidence, calibration methodology, historical datasets, and generated validation reports.

## Structure

- `methodology/` — versioned calibration and analysis methodology.
- `field-history/` — immutable Home Assistant field-history datasets used for reproducible analysis.
- `field-history/paired-night/` — matched PRE/POST field datasets and comparisons.
- `reports/` — generated or curated validation reports that are not tied to one immutable dataset directory.

Executable analysis tools remain under `analysis/` and automated software tests remain under `tests/`. General installation, production, architecture, and release documentation remains under `docs/`.

New field-test or calibration evidence must be placed under this `validation/` tree rather than creating new top-level experiment folders.
