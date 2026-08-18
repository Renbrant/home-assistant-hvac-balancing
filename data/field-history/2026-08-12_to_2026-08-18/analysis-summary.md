# August 12-18, 2026 HVAC Baseline Analysis

## Overview

This document records the first formal quantitative analysis of the production
HVAC balancing baseline.

Analysis period:

```text
2026-08-12 00:00 America/Denver
through
2026-08-18 14:03 America/Denver
```

Total analyzed duration:

```text
158.07 hours
```

Reconstructed resolution:

```text
1 minute
```

Methodology:

```text
docs/HVAC_CALIBRATION_METHODOLOGY.md
```

---

## Bed 1

### Directional error

| Metric | Result |
|---|---:|
| Mean | 1.34°F |
| Median | 1.30°F |
| P90 | 2.50°F |
| Maximum | 3.60°F |
| Mean absolute room delta | 1.42°F |

### HVAC-active error distribution

| Band | Time |
|---|---:|
| <1.0°F | 13.4% |
| 1.0-1.5°F | 16.1% |
| 1.5-2.0°F | 25.0% |
| 2.0-2.5°F | 35.4% |
| 2.5-3.0°F | 9.2% |
| >=3.0°F | 0.8% |

### Booster utilization

| Metric | Result |
|---|---:|
| Average effective command | 20.1% |
| Time >=80% | 2.9% |
| Time at 100% | 0.0% |
| >=80% and error >=2°F | 2.9% |
| High-fan observations still >=2°F | 100.0% |

---

## Bed 2

### Directional error

| Metric | Result |
|---|---:|
| Mean | 1.58°F |
| Median | 1.80°F |
| P90 | 3.10°F |
| Maximum | 4.30°F |
| Mean absolute room delta | 1.70°F |

### HVAC-active error distribution

| Band | Time |
|---|---:|
| <1.0°F | 11.1% |
| 1.0-1.5°F | 7.8% |
| 1.5-2.0°F | 12.6% |
| 2.0-2.5°F | 28.2% |
| 2.5-3.0°F | 24.9% |
| >=3.0°F | 15.5% |

### Booster utilization

| Metric | Result |
|---|---:|
| Average effective command | 30.9% |
| Time >=80% | 13.2% |
| Time at 100% | 3.0% |
| >=80% and error >=2°F | 13.2% |
| High-fan observations still >=2°F | 100.0% |

---

## Bed 3

### Directional error

| Metric | Result |
|---|---:|
| Mean | 1.34°F |
| Median | 1.30°F |
| P90 | 3.20°F |
| Maximum | 4.50°F |
| Mean absolute room delta | 1.61°F |

### HVAC-active error distribution

| Band | Time |
|---|---:|
| <1.0°F | 10.1% |
| 1.0-1.5°F | 5.0% |
| 1.5-2.0°F | 11.9% |
| 2.0-2.5°F | 14.8% |
| 2.5-3.0°F | 16.6% |
| >=3.0°F | 41.6% |

### Booster utilization

| Metric | Result |
|---|---:|
| Average effective command | 23.9% |
| Time >=80% | 13.2% |
| Time at 100% | 5.9% |
| >=80% and error >=2°F | 13.2% |
| High-fan observations still >=2°F | 100.0% |

---

## Adaptive I reset evidence

### Bed 1

```text
Time-weighted average: 0.08
Maximum: 3
Time > 0: 6.7%

Increase transitions: 56
Decrease transitions: 49

Positive-to-zero resets: 49
Within 2 seconds of climate.kitchen event: 49

Coincidence: 100.0%
```

### Bed 2

```text
Time-weighted average: 0.06
Maximum: 3
Time > 0: 5.6%

Increase transitions: 60
Decrease transitions: 54

Positive-to-zero resets: 54
Within 2 seconds of climate.kitchen event: 52

Coincidence: 96.3%
```

### Bed 3

```text
Time-weighted average: 0.06
Maximum: 4
Time > 0: 3.9%

Increase transitions: 33
Decrease transitions: 29

Positive-to-zero resets: 29
Within 2 seconds of climate.kitchen event: 29

Coincidence: 100.0%
```

### Interpretation

The temporal correlation is extremely strong.

Nearly every observed transition from a positive Adaptive I value directly to
zero occurred at essentially the same time as a `climate.kitchen` event.

This strongly supports Issue #3.

Adaptive I gain, evaluation interval and thresholds should not be recalibrated
from this baseline as though Adaptive I had been operating normally.

---

## Base P - 20-minute response

Positive values mean directional error decreased.

Only windows with active HVAC and unchanged Base P were accepted.

### Bed 1

| Base P | Windows | Median improvement | Mean improvement |
|---:|---:|---:|---:|
| 0 | 47 | 0.00°F | -0.04°F |
| 2 | 55 | 0.00°F | -0.03°F |
| 4 | 15 | 0.00°F | 0.07°F |
| 6 | 6 | -0.10°F | -0.07°F |

### Bed 2

| Base P | Windows | Median improvement | Mean improvement |
|---:|---:|---:|---:|
| 0 | 32 | 0.00°F | 0.01°F |
| 2 | 1 | -0.60°F | -0.60°F |
| 4 | 7 | 0.00°F | 0.07°F |
| 6 | 10 | 0.00°F | 0.04°F |
| 8 | 2 | 0.15°F | 0.15°F |

The Speed 8 result has only two qualifying windows and should not be treated as
statistically strong.

### Bed 3

| Base P | Windows | Median improvement | Mean improvement |
|---:|---:|---:|---:|
| 0 | 32 | 0.00°F | -0.03°F |
| 2 | 7 | 0.00°F | 0.00°F |
| 4 | 4 | 0.10°F | 0.10°F |
| 6 | 4 | 0.00°F | 0.00°F |
| 8 | 27 | 0.00°F | 0.00°F |
| 10 | 31 | 0.00°F | -0.01°F |

Bed 3 is notable because Base P 8 and Base P 10 have meaningful sample sizes.

Speed 8 has 27 qualifying windows.

Speed 10 has 31 qualifying windows.

Median 20-minute improvement is essentially zero at both levels.

This is evidence of possible diminishing returns from high local booster
command.

It is not yet proof of causality.

---

## Nest / central blower assist

Observed `fan_mode=on` behavior:

```text
Episodes: 45
Approximate runtime: 45.07 hours
Percent of baseline: 28.5%
Median episode: 25.1 minutes
P90 episode: 177.6 minutes
Longest episode: 335.4 minutes

Fan starts with reconstructed maximum PI Target >=8:
60.0%

Median maximum PI Target at fan start:
8

Median worst bedroom directional error at fan start:
3.10°F
```

Only 60% of reconstructed `fan_mode=on` starts occurred with maximum PI Target
of at least 8.

Therefore, fan-mode transitions cannot automatically be attributed to the
balancing controller.

Possible contributors include:

- existing Nest state;
- previously scheduled fan timers;
- climate attribute transitions;
- automation restart behavior;
- behavior investigated in Issue #5.

A dedicated before/after slope comparison is required to measure central blower
benefit.

---

## Engineering conclusions

### Bed 1

Bed 1 has the best controlled high-error tail.

During active HVAC only 0.8% of reconstructed time was at or above 3°F
directional error.

It rarely reaches extreme booster command.

### Bed 2

Bed 2 has the highest typical imbalance.

Key metrics:

```text
Median directional error: 1.80°F
P90: 3.10°F
Maximum: 4.30°F
```

During active HVAC, 15.5% of reconstructed time was at or above 3°F.

Bed 2 requires further investigation.

### Bed 3

Bed 3 has the most severe active-HVAC error tail.

During active HVAC:

```text
41.6%
```

of reconstructed time was at or above 3°F.

Bed 3 also spent:

```text
5.9%
```

of the complete baseline at 100% effective booster command.

Base P 8 and 10 have useful sample counts but essentially no median 20-minute
improvement.

Simply increasing local booster speed further is therefore not the first
solution to test.

### Adaptive I

Adaptive I history is strongly contaminated by reset behavior.

Issue #3 should be treated as a prerequisite to Adaptive I calibration.

### Base P

The first analysis does not justify making the full proportional curve more
aggressive.

High-speed physical response should be investigated first.

### Nest assist

Nest circulation is used substantially, but current data does not establish its
causal thermal benefit.

A dedicated comparison of bedroom error slope before and after blower
activation is required.

---

## Recommended investigation order

```text
1. Resolve or explain Adaptive I resets - Issue #3.

2. Resolve heat_cool idle directional behavior - Issue #4.

3. Resolve broad climate trigger / Nest release behavior - Issue #5.

4. Quantify Bed 3 high-speed diminishing returns.

5. Compare bedroom response before and after central blower assist.

6. Reassess Base P thresholds.

7. Reassess Adaptive I after reset behavior is corrected.

8. Determine whether room-specific tuning is justified.
```

---

## Production recommendation

No production controller parameter should be changed from this first analysis
pass alone.

The baseline has successfully identified where the next engineering work should
focus.

The next phase should remove known control-logic uncertainty before controller
gains are changed.

---

## Reproducible analysis engine

This baseline is reproducible using the versioned analyzer:

`analysis/analyze_hvac_baseline.py`

Analysis methodology version: `1.0.0`.

The analyzer was executed against this August 12-18 dataset and passed
regression checks against the key reference metrics documented in this report,
including bedroom error statistics, Adaptive I reset correlation, Bed 3
high-speed response-window counts, and Nest fan diagnostics.

Future field-history datasets should be analyzed with this same implementation
for before/after comparisons.
