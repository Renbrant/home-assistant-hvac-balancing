# HVAC Field History Baseline

This dataset documents the production Home Assistant
history used for the controller calibration work tracked
in GitHub Issue #6.

## Collection period

- Start: `2026-08-12 00:00:00 America/Denver`
- End: `2026-08-18 14:03:58 America/Denver`
- Start UTC: `2026-08-12T06:00:00.000Z`
- End UTC: `2026-08-18T20:03:58.374Z`

## Collection method

Data was retrieved through the Home Assistant REST History API.

The complete Home Assistant Recorder database was not copied
or committed.

Only project-related entity history is written to this dataset.

## Files

### `normalized/states.csv`

State history for temperatures, temperature deltas, Base P,
Adaptive I, PI targets and effective booster commands.

### `normalized/adaptive-controller.csv`

Adaptive controller state plus diagnostic attributes:

- `base_speed`
- `control_direction`
- `directional_error`
- `reference_error`
- `last_evaluation`

### `normalized/pi-target.csv`

Final PI target plus Base P and Adaptive I components.

### `normalized/climate.csv`

Nest HVAC mode, `hvac_action`, temperatures, targets and fan mode.

### `normalized/power-1min.csv`

One-minute summaries of recorded AC and furnace/airflow
power state changes.

These averages are arithmetic summaries of recorded state-change
observations and are not time-weighted energy integration.

### `entity-summary.csv`

Coverage and record counts for every collected entity.

### `manifest.json`

Machine-readable collection metadata, validation results,
query configuration and SHA-256 fingerprints of each temporary
History API response.

## Data validity

Base P and room thermal-response measurements can be analyzed
directly from this baseline.

Adaptive I results should also be interpreted together with
Issue #3, which investigates possible unintended adaptive resets.

## Related issues

- #3 - Adaptive I reset behavior
- #4 - HEAT_COOL idle Base P behavior
- #5 - climate trigger / Nest release behavior
- #6 - Base P / Adaptive I calibration

## Coverage

- `sensor.kitchen_temp_temperature`: 506 records
- `sensor.bed_1_temp_temperature`: 491 records
- `sensor.bed_2_temp_temperature`: 464 records
- `sensor.bed_3_temp_temperature`: 483 records
- `sensor.bed_1_temperature_delta`: 988 records
- `sensor.bed_2_temperature_delta`: 961 records
- `sensor.bed_3_temperature_delta`: 980 records
- `sensor.bed_1_booster_target_speed`: 313 records
- `sensor.bed_2_booster_target_speed`: 386 records
- `sensor.bed_3_booster_target_speed`: 304 records
- `sensor.bed_1_booster_effective_percentage`: 449 records
- `sensor.bed_2_booster_effective_percentage`: 516 records
- `sensor.bed_3_booster_effective_percentage`: 388 records
- `sensor.kitchen_temperature`: 246 records
- `sensor.bed_1_booster_adaptive_boost`: 128 records
- `sensor.bed_2_booster_adaptive_boost`: 137 records
- `sensor.bed_3_booster_adaptive_boost`: 85 records
- `sensor.bed_1_booster_pi_target_speed`: 434 records
- `sensor.bed_2_booster_pi_target_speed`: 516 records
- `sensor.bed_3_booster_pi_target_speed`: 382 records
- `climate.kitchen`: 759 records
- `sensor.ac_power_total`: 18,829 records
- `sensor.furnace_power_total`: 15,511 records
