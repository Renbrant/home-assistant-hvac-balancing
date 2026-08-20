# CURRENT PRODUCTION BASELINE - v0.2.0-beta.9

> Current field calibration should use post-cutover v0.2 Production data.
> Pre-v0.1.3 Adaptive reset data remains useful as historical defect evidence.

---

# HVAC Balancing Calibration Methodology

## Purpose

This document defines the repeatable engineering methodology used to evaluate,
calibrate, and validate the Home Assistant bedroom HVAC balancing controller.

The objective is not to force every bedroom temperature delta to zero at any
cost.

The controller must balance:

- bedroom thermal consistency;
- response speed;
- booster fan noise;
- booster duty cycle;
- central blower usage;
- HVAC energy consumption;
- controller stability.

Production parameters should be changed only when measured field behavior
supports the change.

---

## 1. Separate reliability defects from calibration

Before tuning controller parameters, implementation defects must be separated
from calibration questions.

The current investigation distinguishes:

- Issue #3 - possible unintended Adaptive I resets;
- Issue #4 - Base P direction during `heat_cool` idle operation;
- Issue #5 - climate triggers and Nest fan-release behavior;
- Issue #6 - Base P and Adaptive I field-data calibration.

A controller coefficient should not be changed to compensate for a software
defect.

Adaptive I history must not be treated as representative of the intended
algorithm while unexpected resets remain unresolved.

Base P and physical room-response behavior can still be analyzed independently.

---

## 2. Production data acquisition

Historical data is collected from the production Home Assistant instance using
the Home Assistant REST History API.

Only HVAC-balancing entities are requested.

The extraction process must not:

- stop Home Assistant Recorder;
- modify Home Assistant state;
- change HVAC controller configuration;
- copy the complete Home Assistant SQLite database;
- commit unrelated household history;
- persist Home Assistant access tokens;
- commit secrets.

Every baseline should record:

- collection start;
- collection end;
- timezone;
- Home Assistant version;
- requested entities;
- record counts;
- validation status;
- extraction provenance.

---

## 3. Immutable baseline

Calibration begins from a fixed historical dataset.

The first formal baseline covers:

```text
2026-08-12 00:00 America/Denver
through
2026-08-18 14:03 America/Denver
```

The dataset is stored under:

```text
validation/field-history/2026-08-12_to_2026-08-18/
```

Historical source data should not be modified because a later analysis produces
an unexpected result.

If extraction or normalization changes materially, create a new documented
dataset or explicitly version the transformation.

---

## 4. Home Assistant history is event-based

Home Assistant history primarily records state changes.

It is not a uniform one-row-per-minute time series.

Therefore, statistics such as:

- percentage of time;
- average command;
- error distribution;
- actuator saturation;

must not be calculated by simply counting CSV rows.

One value may remain unchanged for hours with only one history entry while
another sensor creates many entries during the same interval.

---

## 5. One-minute reconstruction

The analysis reconstructs event history onto a regular one-minute timeline.

For each entity:

1. events are ordered chronologically;
2. the latest known state is retained;
3. that state is carried forward until the next change;
4. the value active at each one-minute timestamp is reconstructed.

This produces an approximately time-weighted representation of controller
behavior.

The first formal analysis covers approximately:

```text
158.07 hours
```

using:

```text
1-minute resolution
```

---

## 6. Raw signed room delta

The raw bedroom temperature delta is:

```text
bedroom_temperature - kitchen_temperature
```

A positive delta means the bedroom is warmer than the Kitchen reference.

A negative delta means the bedroom is cooler than the Kitchen reference.

The signed value is retained for physical thermal analysis.

---

## 7. Directional controller error

Controller demand must consider the active HVAC direction.

### Cooling

```text
directional_error =
    bedroom_temperature
    -
    kitchen_temperature
```

Negative values are clamped to zero for controller-demand analysis.

### Heating

```text
directional_error =
    kitchen_temperature
    -
    bedroom_temperature
```

Negative values are also clamped to zero.

### Heat/Cool mode

When thermostat mode is `heat_cool`:

- `hvac_action = cooling` uses the cooling direction;
- `hvac_action = heating` uses the heating direction.

The current behavior during:

```text
heat_cool + idle
```

is tracked separately in Issue #4.

---

## 8. Three analysis contexts

Thermal performance is evaluated separately in three contexts.

### Total monitored time

Measures overall bedroom-to-reference consistency.

### HVAC actively heating or cooling

Includes only:

```text
hvac_action = cooling
```

or:

```text
hvac_action = heating
```

This isolates periods where conditioned air is actively being generated.

### Bedroom balancing active

Includes periods where effective booster command is greater than zero.

This isolates periods where the balancing controller is actively intervening.

These three contexts must not be mixed.

---

## 9. Baseline error metrics

For every bedroom calculate:

- mean directional error;
- median directional error;
- 90th percentile directional error;
- maximum directional error;
- mean absolute raw room delta.

Error distribution is divided into:

```text
< 1.0°F
1.0 - <1.5°F
1.5 - <2.0°F
2.0 - <2.5°F
2.5 - <3.0°F
>= 3.0°F
```

The distribution is calculated for:

- total monitored time;
- HVAC-active time;
- balancing-active time.

---

## 10. Booster utilization and saturation

For each room reconstruct effective booster command over time.

Measure:

- average effective command;
- active runtime percentage and hours;
- active runtime percentage while HVAC is actively heating or cooling;
- average effective command during HVAC-active time;
- average effective command while the booster is active;
- number of active episodes;
- median, P90, and longest active-episode duration;
- effective-command change count;
- speed-to-speed modulation count while remaining active;
- HVAC-scoped active modulations per HVAC-active hour;
- median time between active modulations over the full monitored window;
- equivalent full-speed hours;
- equivalent full-speed hours during HVAC-active time;
- time at or above 80%;
- time at 100%;
- time at or above 80% while directional error remains at least 2°F.

The combined condition:

```text
booster >= 80%
AND
directional_error >= 2°F
```

is especially important.

Persistent high command with large remaining error may indicate diminishing
returns from additional local booster speed.

Possible causes include:

- duct limitations;
- register restrictions;
- room thermal load;
- insufficient supply airflow;
- limited incremental airflow at high booster RPM;
- need for central blower assistance.

High booster demand does not automatically mean that Base P should become more
aggressive.

---

## 11. Base P response-rate methodology

Each proportional level is evaluated using 20-minute windows.

Candidate windows begin every five minutes.

A window is accepted only when:

1. HVAC remains actively heating or cooling;
2. Base P has the same value at minutes 0, 5, 10, 15 and 20 of the observation window.

The response metric is:

```text
improvement_20m =
    directional_error_at_start
    -
    directional_error_after_20_minutes
```

Interpretation:

```text
positive = error improved
zero     = no measured improvement
negative = error became worse
```

For every Base P level report:

- number of qualifying windows;
- median 20-minute improvement;
- mean 20-minute improvement.

---

## 12. PI Target response-rate methodology

The same process is applied to final PI Target.

A window is accepted only when:

- HVAC remains continuously active;
- PI Target has the same value at minutes 0, 5, 10, 15 and 20.

This prevents improvement from being incorrectly attributed to one level when
the controller changed levels during the observation window.

---

## 13. Sample-size caution

Command levels may have very different numbers of qualifying observations.

A level with two windows must not be treated with the same statistical
confidence as a level with thirty windows.

Small samples are exploratory evidence.

They are not sufficient by themselves for production tuning.

---

## 14. Adaptive I analysis

Adaptive I is evaluated separately from Base P.

Measure:

- time-weighted average contribution;
- maximum contribution;
- percentage of time greater than zero;
- increase transitions;
- decrease transitions;
- transitions directly from a positive value to zero.

---

## 15. Adaptive I reset diagnostic

Every transition matching:

```text
Adaptive I > 0
->
Adaptive I = 0
```

is compared with the nearest `climate.kitchen` event.

The current coincidence window is:

```text
<= 2 seconds
```

A high coincidence rate suggests thermostat state or attribute activity may be
causing Adaptive I to reset.

This is a reliability diagnostic, not a measurement of ideal Adaptive I gain.

Until Issue #3 is understood or corrected, historical Adaptive I behavior must
be treated as contaminated by reset behavior.

---

## 16. Central blower / Nest assist

The current controller requests Nest circulation when any final PI Target
reaches:

```text
PI Target >= 8
```

Central-assist analysis should measure:

- number of `fan_mode=on` episodes;
- approximate runtime;
- percentage of baseline;
- median episode duration;
- P90 episode duration;
- maximum episode duration;
- maximum PI Target around fan start;
- worst bedroom error around fan start.

However, `fan_mode=on` does not prove that:

- the balancing automation initiated the transition;
- airflow increased as intended;
- bedroom convergence improved because of it.

Where possible, assist analysis should also use:

```text
sensor.furnace_power_total
```

and compare error slopes before and after blower activation.

---

## 17. Observational-data limitation

This is field data rather than a controlled laboratory experiment.

Other variables may change simultaneously, including:

- outdoor temperature;
- solar exposure;
- occupancy;
- room doors;
- thermostat target;
- compressor state;
- central blower state;
- booster command;
- internal thermal load.

Correlation must not automatically be interpreted as causation.

Analysis should prefer intervals where the tested control value and HVAC
operating state remain stable.

---

## 18. Room-specific tuning

Bed 1, Bed 2 and Bed 3 initially share controller coefficients.

Room-specific parameters should only be introduced when repeated field data
demonstrates persistent differences in physical response.

One isolated excursion is not sufficient evidence.

---

## 19. Diagnostic hierarchy

When a bedroom remains poorly balanced, investigate in this order:

```text
1. Is the measurement trustworthy?

2. Is controller logic behaving as intended?

3. Is the intended booster command being generated?

4. Is the booster actually operating at that command?

5. Does increased booster speed measurably improve convergence?

6. Is local airflow already saturated?

7. Does central blower assistance improve convergence?

8. Should Base P thresholds change?

9. Should Adaptive I change?

10. Is room-specific tuning justified?
```

This prevents controller gain changes from hiding physical airflow limitations.

---

## 20. Production-change protocol

No production controller parameter should be changed solely because a chart
looks favorable.

The required workflow is:

```text
hypothesis
    ->
baseline
    ->
quantitative evidence
    ->
proposed isolated change
    ->
new observation period
    ->
before/after analysis
    ->
keep, revise, or revert
```

Whenever possible, change only one parameter family at a time.

Avoid simultaneously changing:

- Base P thresholds;
- proportional step sizes;
- Adaptive I interval;
- Adaptive I thresholds;
- Adaptive I gain;
- Nest-assist threshold.

Otherwise causal interpretation becomes difficult.

---

## 21. Before/after validation

After a production tuning change, collect multiple complete HVAC cycles.

Analyze the new period using the same definitions used for the baseline.

Compare:

- mean directional error;
- median directional error;
- P90 directional error;
- maximum directional error;
- time below 1.0°F;
- time below 1.5°F;
- time above 2.0°F;
- time above 3.0°F;
- average booster command;
- active booster runtime;
- active-episode count and duration;
- active speed-modulation count;
- HVAC-scoped active modulations per HVAC-active hour;
- equivalent full-speed hours;
- booster time >=80%;
- booster time at 100%;
- high-command/high-error saturation;
- Adaptive I contribution;
- central blower runtime;
- 20-minute response rate.

A change is successful only if thermal performance improves without unjustified
actuator activity, noise, or energy consumption.

---

## 22. Methodology stability

Analysis rules should be frozen before production parameter proposals are made.

If the methodology changes later, document:

- what changed;
- why it changed;
- whether earlier baselines were recalculated;
- whether results remain directly comparable.

This prevents analytical rules from being changed after seeing which outcome
supports a preferred hypothesis.

---

## 23. First formal baseline

The first formal quantitative execution covers August 12-18, 2026.

Its results are documented in:

```text
validation/field-history/2026-08-12_to_2026-08-18/analysis-summary.md
```

No production tuning change is recommended from the first pass alone.

---

## Related GitHub issues

- #3 - Adaptive I reset behavior
- #4 - HEAT_COOL idle / Base P behavior
- #5 - climate trigger / Nest-release behavior
- #6 - Base P and Adaptive I field-data calibration

---

## 24. Reference analysis implementation

The quantitative methodology has an official versioned implementation:

`analysis/analyze_hvac_baseline.py`

Current analysis methodology version: `1.1.0`.

The analyzer uses only Python standard-library modules and operates on the
normalized field-history datasets stored under `validation/field-history`.

Example execution:

    py -3 analysis\analyze_hvac_baseline.py validation\field-history\2026-08-12_to_2026-08-18

Machine-readable results are available with:

    --format json

The August 12-18, 2026 baseline remains the regression reference. Version 1.1.0
adds booster activity and modulation metrics without changing the established
version 1.0.0 thermal, saturation, response, Adaptive I, or central-assist
metrics.

For the 20-minute Base P and PI Target response analysis, version 1.1.0 retains
the version 1.0.0 rule of checking controller level at minutes 0, 5, 10, 15 and
20. This preserves the original baseline selection rule and keeps before/after
datasets comparable.

---

## 25. Booster activity and modulation metrics (analysis methodology 1.1.0)

Version 1.1.0 adds time-weighted booster activity, episode, workload, and
modulation metrics while preserving all established version 1.0.0 outputs.

### Authoritative activity definition

Booster activity is defined strictly as:

```text
effective_percentage > 0
```

The logical Home Assistant `fan.*` state is not authoritative for calibration
runtime because a fan entity may remain logically `on` while effective
percentage is zero or stale.

### Active runtime

For every room report:

- `active_runtime_pct` - percentage of reconstructed samples with effective
  percentage greater than zero;
- `active_runtime_hours` - corresponding reconstructed active hours;
- `active_runtime_hvac_pct` - percentage of HVAC-active samples where the
  booster effective percentage is greater than zero.

### Command level

Report:

- `average_effective_pct_hvac` - average effective command across HVAC-active
  samples, including zero command;
- `average_pct_while_active` - average effective command only while the booster
  is active.

### Active episodes

An active episode begins on a reconstructed transition from zero to a positive
effective percentage and ends when effective percentage returns to zero.

Report:

- `active_episodes`;
- `median_active_episode_minutes`;
- `p90_active_episode_minutes`;
- `longest_active_episode_minutes`.

Episode duration is approximate to the one-minute reconstruction resolution.

### Command changes and active modulation

A command change is any change in reconstructed effective percentage.

An active modulation is specifically:

```text
previous effective percentage > 0
AND
new effective percentage > 0
AND
new percentage != previous percentage
```

ON/OFF transitions are therefore not active modulations. This distinction is
required when evaluating acoustic busyness: more separate ON/OFF episodes do
not imply more speed-to-speed modulation while a booster is already running.

`active_modulation_changes` counts positive-to-positive changes over the full
monitored window.

`active_modulation_changes_per_hvac_hour` uses a stricter HVAC-scoped numerator:
only positive-to-positive changes whose new reconstructed sample occurs while
`hvac_action` is `cooling` or `heating` are counted, then divided by total
HVAC-active hours in that window.

This definition intentionally differs from the temporary paired-night script
that counted whole-window modulations and divided by HVAC-active hours. The
version 1.1.0 definition removes that numerator/denominator ambiguity.

`median_minutes_between_active_modulations` is explicitly a whole-window cadence
metric based on all active-modulation timestamps. It must not be described as an
HVAC-only interval metric.

### Equivalent full-speed hours

Equivalent full-speed hours are a command/workload proxy:

```text
sum(effective_percentage / 100 * sample_duration_hours)
```

Report both:

- `equivalent_full_speed_hours` over the full monitored window;
- `equivalent_full_speed_hours_hvac` during HVAC-active samples only.

Equivalent full-speed hours are not measured electrical energy. Energy claims
require actual power/energy data and comparable system load.

### Interpretation

Duty cycle, episode cadence, and speed modulation answer different questions:

- duty cycle measures how much time the booster is doing work;
- episode count/duration measures ON/OFF cadence;
- active modulation measures speed changes while already running;
- equivalent full-speed hours estimates commanded airflow workload.

These metrics should be evaluated together rather than using a single activity
number as a proxy for comfort, noise, or energy.
