# HVAC Calibration Workspace

This directory is the single repository home for the HVAC balancing calibration workflow.

It groups the tooling, analysis-specific regression tests, field-validation evidence, methodology, and reports used to evaluate controller behavior from real Home Assistant history.

Production runtime code remains outside this directory under `custom_components/`, and general software/runtime tests remain under the repository-level `tests/` directory.

## End-to-end workflow

The calibration pipeline is:

```text
Home Assistant history
        ↓
normalization
        ↓
versioned analyzer
        ↓
analysis regression tests
        ↓
immutable validation datasets
        ↓
comparison reports
        ↓
evidence-based calibration decision
```

The purpose of this separation is to keep measurement and interpretation reproducible and independent from production controller implementation.

## Directory structure

```text
calibration/
├── README.md
├── analysis/
│   ├── analyze_hvac_baseline.py
│   ├── booster_activity_metrics.py
│   └── normalize_hvac_history.py
├── tests/
│   ├── test_analysis_metrics.py
│   └── test_history_normalizer.py
└── validation/
    ├── README.md
    ├── methodology/
    ├── field-history/
    └── reports/
```

## `analysis/`

### `normalize_hvac_history.py`

Converts raw Home Assistant History API responses into the normalized CSV contract consumed by the analyzer.

Current normalizer version: `1.0.1`.

Important behaviors include:

- accepting Home Assistant list-of-lists history responses;
- reconstructing omitted entity IDs from group context;
- deduplicating identical history records;
- creating an exact start-window seed from the latest known state;
- recording raw-source SHA-256 provenance;
- recording generated-file SHA-256 hashes;
- refusing datasets that cannot provide required start-window seeds.

Raw Home Assistant API JSON is not intended to be committed.

### `analyze_hvac_baseline.py`

Official versioned field-history analyzer.

Current analysis methodology version: `1.2.0`.

It reconstructs a one-minute time series and reports thermal, booster, Adaptive I, response-window, and central-assist metrics.

Two thermal contexts must remain distinct:

- `directional` — whole reconstructed observation window;
- `directional_hvac_active` — only samples where `hvac_action` is `cooling` or `heating`.

Use `--format json` for the machine-readable contract used by regression tests and reports.

### `booster_activity_metrics.py`

Contains the booster activity/workload calculations introduced with analysis methodology 1.1.0.

The authoritative booster-active definition is:

```text
effective_percentage > 0
```

Logical Home Assistant `fan.*` state is not authoritative for calibration runtime.

The module distinguishes:

- active runtime;
- ON/OFF episodes;
- command changes;
- positive-to-positive active speed modulation;
- HVAC-scoped modulation rate;
- equivalent full-speed command hours.

Equivalent full-speed hours are a workload proxy, not measured electrical energy.

## `tests/`

This directory contains tests specifically for the calibration toolchain.

### `test_analysis_metrics.py`

Regression-tests the analyzer contract and booster metrics against the historical field baseline.

It verifies, among other things:

- effective percentage is the authoritative activity signal;
- idle speed changes are excluded from the HVAC-scoped modulation numerator;
- analyzer methodology version and JSON structure;
- explicit HVAC-active directional summary metrics.

### `test_history_normalizer.py`

Tests the raw-history normalization contract, including:

- Home Assistant group-level entity inheritance;
- exact start-window seeding;
- normalized CSV schema;
- manifest counts and hashes;
- failure when a required seed cannot be reconstructed.

These tests are intentionally separate from the root-level `tests/`, which validates the production integration and controller runtime.

## `validation/`

The validation tree stores evidence, not production code.

### `methodology/`

Contains the formal analysis and field-calibration definitions.

The main methodology document is:

`calibration/validation/methodology/HVAC_CALIBRATION_METHODOLOGY.md`

Analyzer-specific methodology additions are versioned separately when necessary, for example:

`calibration/validation/methodology/HVAC_ANALYZER_1.2.0.md`

### `field-history/`

Contains immutable normalized datasets used as reproducible calibration evidence.

The long historical reference baseline is stored under:

`calibration/validation/field-history/2026-08-12_to_2026-08-18/`

Matched before/after datasets are stored under:

`calibration/validation/field-history/paired-night/`

Each dataset should preserve source provenance through its manifest even when raw API JSON is intentionally excluded.

### `reports/`

Contains curated interpretations and before/after comparisons derived from versioned datasets and the official analyzer.

Reports must identify the analyzer/methodology version used and must not silently mix whole-window and HVAC-active statistics.

## Running the historical baseline

From the repository root:

```powershell
py -3 calibration\analysis\analyze_hvac_baseline.py calibration\validation\field-history\2026-08-12_to_2026-08-18
```

Machine-readable output:

```powershell
py -3 calibration\analysis\analyze_hvac_baseline.py calibration\validation\field-history\2026-08-12_to_2026-08-18 --format json
```

## Running calibration regression tests

From the repository root:

```powershell
py -3 -m pytest -q calibration\tests
```

The full repository suite remains:

```powershell
py -3 -m pytest -q
```

## Calibration decision rules

Field evidence is observational rather than laboratory-controlled. A favorable single chart or single night is not sufficient justification for controller tuning.

The expected sequence is:

```text
hypothesis
    → fixed dataset
    → reproducible analysis
    → regression validation
    → repeated comparable observations
    → isolated parameter proposal
    → new validation period
    → keep, revise, or revert
```

Where practical, change only one parameter family at a time.

Do not claim energy savings from booster command workload alone. Energy conclusions require actual comparable electrical data and sufficiently comparable HVAC load.

## Repository boundary

Files belong in this workspace when they exist primarily to answer questions such as:

- How well is the balancing controller performing in real field data?
- How was a historical comparison normalized and reproduced?
- What analysis definitions were used?
- What evidence supports or rejects a calibration change?

Production integration code, Home Assistant runtime behavior, configuration-flow logic, and their general software tests remain outside `calibration/`.
