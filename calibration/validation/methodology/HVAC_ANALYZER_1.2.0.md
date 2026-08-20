# HVAC Analyzer Methodology Addendum — 1.2.0

This addendum extends the field-calibration methodology in
`calibration/validation/methodology/HVAC_CALIBRATION_METHODOLOGY.md`.

It is additive. Existing analysis methodology 1.0.0 and 1.1.0 metrics retain
their established definitions.

## Purpose

Analysis methodology 1.2.0 makes HVAC-active directional statistics an explicit
part of the analyzer JSON contract.

The change exists to prevent two different thermal contexts from being treated
as interchangeable:

- whole monitored window;
- periods where `hvac_action` is `cooling` or `heating`.

Before 1.2.0, HVAC-active error bands were already calculated, but summary
statistics such as mean and P90 were exposed only for the whole reconstructed
window. Temporary comparison scripts therefore had to calculate HVAC-active
summary statistics externally.

Version 1.2.0 removes that ambiguity.

## Analyzer

Reference implementation:

`calibration/analysis/analyze_hvac_baseline.py`

Analysis methodology version:

`1.2.0`

Validated implementation commit:

`9c08e095693ffc922ab97ff524e309257c3cc172`

## Existing whole-window contract

The existing block remains unchanged:

`beds.<bed>.directional`

It describes all reconstructed samples for which directional error can be
calculated and contains:

- `mean`;
- `median`;
- `p90`;
- `maximum`;
- `mean_absolute_room_delta`.

These values must continue to be described as whole-window statistics.

## New HVAC-active contract

Version 1.2.0 adds:

`beds.<bed>.directional_hvac_active`

A sample belongs to this context only when:

- `hvac_action = cooling`; or
- `hvac_action = heating`.

Directional error itself continues to use the direction rules already defined
in the main calibration methodology.

The block contains:

- `mean`;
- `median`;
- `p90`;
- `maximum`;
- `mean_absolute_room_delta`.

No idle sample is included in this block.

## Relationship to HVAC-active error bands

The existing:

`beds.<bed>.bands.hvac_active`

continues to provide the distribution across the defined directional-error
bands for the same HVAC-active sample context.

Therefore the HVAC-active summary statistics and HVAC-active bands can now be
reported together without an external calculation script.

## Paired-night regression contract

The first production v0.2 paired-night datasets are stored under:

`calibration/validation/field-history/paired-night/2026-08-18_vs_2026-08-19/`

For those datasets, analyzer 1.2.0 reproduces the previously validated
HVAC-active directional statistics:

| Bedroom | PRE mean | POST mean | PRE P90 | POST P90 |
|---|---:|---:|---:|---:|
| Bed 1 | 2.05°F | 1.67°F | 2.30°F | 2.00°F |
| Bed 2 | 2.43°F | 1.82°F | 3.08°F | 2.36°F |
| Bed 3 | 3.16°F | 1.97°F | 3.40°F | 3.20°F |

These values are regression evidence for the new output context; they are not
new controller tuning targets.

## Semantic separation rule

Reports must explicitly name the context of thermal summary statistics.

Use terms such as:

- `whole-window directional mean`;
- `HVAC-active directional mean`;
- `HVAC-active directional P90`.

Do not label a whole-window value simply as an HVAC-active value or compare the
two as though they were generated from the same sample population.

## Booster metrics remain unchanged

Analysis methodology 1.2.0 does not alter the booster activity definitions
introduced in 1.1.0.

In particular:

- booster active remains `effective_percentage > 0`;
- logical `fan.*` state remains non-authoritative for booster runtime;
- active modulation remains a positive-to-different-positive transition;
- `active_modulation_changes` remains a whole-window count;
- `active_modulation_changes_per_hvac_hour` retains its HVAC-scoped numerator;
- equivalent full-speed hours remain a command/workload proxy, not measured
  electrical energy.

## Comparability

Version 1.2.0 is additive. It does not intentionally change established 1.0.0
or 1.1.0 calculations.

The August 12–18 historical baseline remains the long-window regression
reference, while the paired-night dataset provides a short matched-window
regression reference for the explicit HVAC-active summary contract.

Any future change that alters directional-error sample selection or an existing
metric definition must increment the analysis methodology version again and
must document whether prior reports remain directly comparable.
