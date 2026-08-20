# Validation and Field Calibration

This directory stores the evidence produced by the calibration toolchain: field-validation datasets, calibration methodology, provenance, and validation reports.

It lives under `calibration/` so the complete calibration workflow has one repository home while keeping executable analysis code, analysis-specific tests, and validation evidence clearly separated.

## Structure

- `methodology/` — versioned calibration and analysis methodology.
- `field-history/` — immutable Home Assistant field-history datasets used for reproducible analysis.
- `field-history/paired-night/` — matched PRE/POST field datasets and comparisons.
- `reports/` — generated or curated validation reports that are not tied to one immutable dataset directory.

Executable calibration tools live in `calibration/analysis/` and their analysis-specific regression tests live in `calibration/tests/`.

General software/runtime tests remain in the repository-level `tests/` directory, and general installation, production, architecture, and release documentation remains under `docs/`.

New field-test or calibration evidence must be placed under this `calibration/validation/` tree rather than creating new top-level experiment folders.
