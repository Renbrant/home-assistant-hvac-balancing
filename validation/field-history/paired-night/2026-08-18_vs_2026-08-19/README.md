# First production v0.2 paired-night validation

This directory contains the official normalized datasets for the first matched production comparison between the legacy v0.1.3 controller and the Python v0.2 controller.

## Matched windows

| Dataset | Local window | UTC window |
|---|---|---|
| PRE v0.1.3 | 2026-08-18 23:00 to 2026-08-19 09:30 America/Denver | 2026-08-19T05:00:00Z to 2026-08-19T15:30:00Z |
| POST v0.2 | 2026-08-19 23:00 to 2026-08-20 09:30 America/Denver | 2026-08-20T05:00:00Z to 2026-08-20T15:30:00Z |

Both windows are exactly 10.5 hours.

## Provenance

The source data came from the Home Assistant REST History API. Raw API JSON is intentionally **not committed**.

Source integrity is preserved by SHA-256:

- PRE: `D18AE992F9E88FCE3E75B075B5E1983799B60655367753E8A21F4E67A68B7A9E`
- POST: `EADB1FA86B2604B93EFA39FB25ADAEF8654390FD6625C4BDFD44D5BE3245A589`

Home Assistant version: `2026.8.2`

Timezone: `America/Denver`

## Normalization

Normalizer: `analysis/normalize_hvac_history.py`

Normalizer version: `1.0.1`

The normalization process:

- accepts the Home Assistant History API list-of-lists response;
- reconstructs omitted entity IDs from group context;
- removes duplicate identical history records;
- establishes an exact start-window seed from the latest known state;
- clamps the seed timestamp to the exact comparison-window start;
- excludes source events outside the requested window;
- records source and generated-file hashes in each manifest.

## Analyzer

Reference analyzer: `analysis/analyze_hvac_baseline.py`

Analysis methodology version: `1.1.0`

Booster activity is defined as `effective_percentage > 0`. The logical `fan.*` state is not used as the authoritative booster-activity definition.

## Dataset layout

    2026-08-18_vs_2026-08-19/
    ├── README.md
    ├── pre-v0.1.3/
    │   ├── manifest.json
    │   └── normalized/
    │       ├── states.csv
    │       ├── climate.csv
    │       └── adaptive-controller.csv
    └── post-v0.2/
        ├── manifest.json
        └── normalized/
            ├── states.csv
            ├── climate.csv
            └── adaptive-controller.csv

## Interpretation status

The normalized datasets are immutable comparison evidence.

The final paired-night interpretation is kept separate from the dataset itself so analyzer-output semantics can be validated before conclusions are published. In particular, whole-window directional statistics and HVAC-active directional statistics must not be treated as interchangeable.

No Home Assistant configuration or HVAC controller parameter was changed while creating these datasets.
