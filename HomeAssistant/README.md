# Home Assistant Installation

This directory contains the Home Assistant configuration used by the **Home Assistant HVAC Balancing** project.

> **Current version: v1.2.0 — Active PI-Lite Thermal Balancing**
> The current controller is operational and is being field-tested primarily during summer / cooling conditions.

Version 1.2 keeps the three-bedroom architecture introduced in v1.1 and adds an adaptive PI-lite control layer so the system can react not only to the current room-temperature imbalance, but also to **how quickly that imbalance is improving**.

The controller now uses:

```text
Base P
Temperature-driven proportional command

        +

Adaptive I
Performance-driven correction

        =

Final PI Target
```

The local bedroom boosters remain the primary balancing actuators. The Nest central blower is now used as a **second-stage assist** only when stronger whole-system circulation is justified.

---

# Configuration Files

The Home Assistant implementation is divided into three files:

| File | Purpose |
|---|---|
| `templates.yaml` | Temperature deltas, Base P, Adaptive I, PI targets, and effective fan percentages |
| `automation.yaml` | Commands the three booster fans and controls second-stage Nest circulation |
| `dashboard.yaml` | Live monitoring, Plotly historical visualization, diagnostics, and tuning |

The files are intended to be used together. In particular, **v1.2 `automation.yaml` depends on the new PI-target entities created by v1.2 `templates.yaml`**.

---

# What Changed from v1.1

Version 1.2 introduces several important behavioral changes:

- Added an independent adaptive correction for Bed 1, Bed 2, and Bed 3
- Added approximately 20-minute performance-evaluation windows
- Added `reference_error` and `last_evaluation` diagnostics
- Added persistent control-direction tracking
- Added final PI-target sensors for all three bedrooms
- Balancing can continue between active HVAC cycles while the thermostat remains in `COOL` or `HEAT`
- In `HEAT_COOL`, the last active heating/cooling direction is retained while HVAC is temporarily idle
- The Nest central blower is no longer requested at Base Speed 4
- Central circulation is now a second-stage assist starting at **PI Target 8 or higher**
- The five-minute circulation-release logic now uses the final PI targets
- Monitoring was redesigned around stacked Plotly graphs with a common time axis
- AC electrical power and indoor blower / airflow power can be displayed directly
- Effective booster percentage is graphed historically for all three rooms

---

# Requirements

## Required for the Controller

- Home Assistant
- Nest thermostat integrated with Home Assistant
- Dedicated temperature sensors for Kitchen, Bed 1, Bed 2, and Bed 3
- Three smart HVAC register booster fans
- Booster `fan` entities exposed to Home Assistant
- Xtend Tuya for the booster model used in this installation

## Required for the Current Dashboard

The current monitoring interface uses custom Lovelace cards:

- `plotly-graph-card`
- `multiple-entity-row`
- `card-mod`

Older diagnostic cards in the repository may also use:

- `apexcharts-card`

The dashboard is **not required** for the control logic itself.

## Optional Power Monitoring

The dashboard can display real HVAC electrical consumption using:

```text
sensor.ac_power_total
sensor.furnace_power_total
```

These sensors are diagnostic only. The PI controller does not require them to operate.

---

# Before Installing

Before replacing or merging any YAML:

1. Back up the current Home Assistant configuration.
2. Confirm the entity IDs used by your installation.
3. Install and test the three booster `fan` entities independently.
4. Confirm all four temperature sensors report plausible values.
5. Replace / merge `templates.yaml` before enabling the v1.2 automation.
6. Do not run the v1.2 automation against the old v1.1 templates.

If your entity IDs differ from those documented below, update the YAML before enabling the controller.

---

# Default Entity Mapping

## Thermostat

```text
climate.kitchen
```

## Temperature Sensors

| Location | Entity |
|---|---|
| Kitchen reference | `sensor.kitchen_temp_temperature` |
| Bed 1 | `sensor.bed_1_temp_temperature` |
| Bed 2 | `sensor.bed_2_temp_temperature` |
| Bed 3 | `sensor.bed_3_temp_temperature` |

## Booster Fans

```text
fan.bed_1_booster
fan.bed_2_booster
fan.bed_3_booster
```

## Optional HVAC Power Sensors

```text
sensor.ac_power_total
sensor.furnace_power_total
```

---

# System Architecture

The v1.2 control architecture is:

```text
                         Nest Thermostat
                               │
                    HVAC mode / hvac_action
                               │
                               ▼
                         Home Assistant
                               │
               ┌───────────────┼───────────────┐
               │               │               │
               ▼               ▼               ▼
             Bed 1           Bed 2           Bed 3
               │               │               │
               ▼               ▼               ▼
        Directional Error Directional Error Directional Error
               │               │               │
               ▼               ▼               ▼
             Base P          Base P          Base P
               │               │               │
               +               +               +
          Adaptive I      Adaptive I      Adaptive I
               │               │               │
               ▼               ▼               ▼
           PI Target       PI Target       PI Target
               │               │               │
               ▼               ▼               ▼
          Effective %     Effective %     Effective %
               │               │               │
               ▼               ▼               ▼
           Booster 1       Booster 2       Booster 3

                   Any final PI Target >= 8
                               │
                               ▼
                    Nest Central Circulation
```

All three bedrooms are controlled independently but share:

- The Kitchen reference temperature
- Thermostat operating direction
- Central Nest circulation decision

---

# Thermostat Operating Direction

The raw bedroom delta is always:

```text
Bedroom Temperature - Kitchen Temperature
```

The controller then converts that raw difference into a **directional control error**.

## COOL Mode

```text
Control Error = Bedroom - Kitchen
```

A bedroom warmer than the Kitchen produces positive balancing demand.

## HEAT Mode

```text
Control Error = Kitchen - Bedroom
```

A bedroom colder than the Kitchen produces positive balancing demand.

## HEAT_COOL Mode

When `hvac_action` is actively:

```text
cooling
```

or:

```text
heating
```

that action establishes the current control direction.

When the thermostat remains in `heat_cool` but `hvac_action` becomes `idle`, v1.2 retains the most recently known heating/cooling direction. This allows thermal balancing to continue between compressor or furnace cycles instead of immediately dropping all balancing demand.

---

# Active Thermal Balancing While HVAC Is Idle

One of the most important v1.2 changes is that balancing is not limited to the moments when the compressor or furnace is actively running.

For example, while the thermostat remains in `COOL` mode:

```text
Bedroom warmer than Kitchen
          │
          ▼
Directional error remains positive
          │
          ▼
PI balancing remains active
          │
          ▼
Bedroom booster may continue running
```

This can redistribute already-conditioned air between HVAC cycles.

The same concept applies in `HEAT` mode with the control direction reversed.

The `hvac_action` state still matters for one specific rule: the **minimum Speed 1 assistance while conditioned air is actively being produced**.

---

# Installing `templates.yaml`

The repository stores the project template definitions in:

```text
templates.yaml
```

A common include structure is:

```yaml
template: !include templates.yaml
```

When using that structure:

> Do not add another top-level `template:` key inside the included `templates.yaml` file.

If your Home Assistant installation already contains template entities, merge the supplied definitions carefully and avoid duplicate `unique_id` values.

After installation, reload template entities if your installation supports it, or restart Home Assistant.

Then confirm all v1.2 calculated entities are available.

---

# Template Entities

## 1. Raw Temperature Delta

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

These sensors always represent:

```text
Bedroom - Kitchen
```

| Raw Delta | Meaning |
|---:|---|
| Positive | Bedroom is warmer than Kitchen |
| 0°F | Bedroom and Kitchen are equal |
| Negative | Bedroom is cooler than Kitchen |

---

# 2. Base P — Proportional Target

The original temperature-driven controller remains in v1.2 as the proportional component.

Entities:

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

These entity names are retained for compatibility, but in v1.2 they should be interpreted as:

> **Base P**

## Base P Curve

| Directional Error | Base P |
|---:|---:|
| `< 1.5°F` | 0 |
| `1.5 – <2.0°F` | 2 |
| `2.0 – <2.5°F` | 4 |
| `2.5 – <3.0°F` | 6 |
| `3.0 – <3.5°F` | 8 |
| `≥ 3.5°F` | 10 |

Examples:

```text
1.7°F → Base P 2
2.2°F → Base P 4
2.7°F → Base P 6
3.2°F → Base P 8
3.5°F → Base P 10
```

---

# Base P Hysteresis

The proportional controller uses approximately:

> **0.2°F hysteresis**

when reducing demand.

| Rising Threshold | Base P | Falling Threshold |
|---:|---:|---:|
| 1.5°F | 2 | ≤ 1.3°F → 0 |
| 2.0°F | 4 | ≤ 1.8°F → 2 |
| 2.5°F | 6 | ≤ 2.3°F → 4 |
| 3.0°F | 8 | ≤ 2.8°F → 6 |
| 3.5°F | 10 | ≤ 3.3°F → 8 |

This prevents small sensor fluctuations from repeatedly changing fan speed around a threshold.

---

# 3. Adaptive I — PI-Lite Correction

Each bedroom has an independent adaptive correction:

```text
sensor.bed_1_booster_adaptive_boost
sensor.bed_2_booster_adaptive_boost
sensor.bed_3_booster_adaptive_boost
```

The adaptive controller observes whether the temperature imbalance is actually improving at an acceptable rate.

The adaptive logic wakes approximately every:

> **5 minutes**

but normally changes its correction only after an observation window of approximately:

> **20 minutes**

Each room tracks diagnostic information including:

```text
directional_error
reference_error
last_evaluation
control_direction
```

The dashboard exposes `reference_error` and `last_evaluation` directly so the PI behavior can be monitored without opening template diagnostics.

---

# Adaptive Evaluation Logic

At the beginning of an evaluation window, the controller stores a reference error.

After approximately 20 minutes:

```text
Improvement = Reference Error - Current Error
```

The adaptive response is:

| Improvement during the evaluation window | Adaptive I response |
|---:|---|
| `< 0.2°F` | Increase Adaptive I by 1 |
| `0.2 – <0.5°F` | Hold Adaptive I |
| `≥ 0.5°F` | Reduce Adaptive I by 1 |

Example — insufficient improvement:

```text
Reference Error = 3.0°F
Current Error   = 2.9°F
Improvement     = 0.1°F

Adaptive I → +1 step
```

Example — strong improvement:

```text
Reference Error = 3.0°F
Current Error   = 2.4°F
Improvement     = 0.6°F

Adaptive I → -1 step
```

This means the controller can progressively increase local airflow when a room is not equalizing fast enough, even if the raw temperature difference itself has not crossed the next Base P threshold.

---

# Adaptive Reset and Unwind Rules

The adaptive term does not accumulate indefinitely.

It is reset, limited, or unwound when appropriate, including when:

- Thermostat control direction changes
- A required temperature sensor becomes unavailable
- Directional error reaches approximately **1.3°F or less**
- Base P already equals Speed 10 and there is no remaining headroom
- Directional error is roughly **1.3°F to 1.5°F**, where Adaptive I unwinds one step per evaluation instead of continuing to accumulate

---

# Anti-Windup

The controller never allows the adaptive term to push the final command above Speed 10.

Conceptually:

```text
Adaptive Headroom = 10 - Base P
```

Therefore, if:

```text
Base P = 8
```

Adaptive I can contribute at most:

```text
2
```

before the final command reaches Speed 10.

---

# 4. Final PI Target

The final speed target is:

```text
PI Target = Base P + Adaptive I
```

limited to:

```text
0 ... 10
```

Entities:

```text
sensor.bed_1_booster_pi_target_speed
sensor.bed_2_booster_pi_target_speed
sensor.bed_3_booster_pi_target_speed
```

Example:

```text
Base P      = 6
Adaptive I  = 2
----------------
PI Target   = 8
```

The **PI Target**, rather than Base P alone, is the main target used by the v1.2 automation.

---

# 5. Effective Booster Percentage

The final percentage intended for each physical booster is exposed through:

```text
sensor.bed_1_booster_effective_percentage
sensor.bed_2_booster_effective_percentage
sensor.bed_3_booster_effective_percentage
```

Normal speed-to-percentage mapping is:

| Speed | Percentage |
|---:|---:|
| 0 | 0% |
| 1 | 10% |
| 2 | 20% |
| 3 | 30% |
| 4 | 40% |
| 5 | 50% |
| 6 | 60% |
| 7 | 70% |
| 8 | 80% |
| 9 | 90% |
| 10 | 100% |

## HVAC-Active Minimum Speed

While the HVAC is actively heating or cooling:

```text
hvac_action = heating
```

or:

```text
hvac_action = cooling
```

all three bedroom boosters use a minimum of:

> **Speed 1 / 10%**

Conceptually:

```text
if hvac_action is heating or cooling:
    Effective Speed = max(PI Target, 1)
else:
    Effective Speed = PI Target
```

Important distinction:

> The PI balancing target may remain active while `hvac_action` is idle.

The Speed 1 rule only guarantees minimum airflow while the central HVAC is actively producing conditioned air.

---

# Installing `automation.yaml`

The primary automation is:

> **HVAC - Smart Bedroom Booster Control**

The automation can be installed by:

- Pasting it into the Home Assistant automation editor using **Edit in YAML**
- Merging it into an existing `automations.yaml`
- Using the installation's existing automation include strategy

Before enabling it, verify the entity IDs and confirm the v1.2 PI-target sensors exist.

The automation controls:

```text
Bed 1
Bed 2
Bed 3
```

and is responsible for:

- Reading the final PI target for each room
- Reading the final effective percentage for each room
- Setting booster operating mode
- Setting fan percentage
- Turning each booster ON or OFF independently
- Reacting to HVAC mode and `hvac_action`
- Requesting Nest second-stage circulation when required
- Maintaining the five-minute Nest release delay
- Recovering after Home Assistant restart
- Periodically reconciling desired state

---

# Booster Command Sequence

Testing with the booster model used in this project showed that mode and speed can be configured before the fan is turned on.

The intended command sequence is:

```text
Set FAN preset mode
        │
        ▼
Wait 1 second
        │
        ▼
Set desired percentage
        │
        ▼
Wait 1 second
        │
        ▼
Turn booster ON
```

Home Assistant service sequence:

1. `fan.set_preset_mode`
2. Wait 1 second
3. `fan.set_percentage`
4. Wait 1 second
5. `fan.turn_on`

When no airflow is required:

```text
fan.turn_off
```

is sent.

This ordering helps prevent the booster from briefly starting at an older stored speed.

---

# Xtend Tuya and Desired-State Control

The boosters in this installation are Tuya-based devices.

The official Tuya integration did not expose every control required by this specific model, so the project uses **Xtend Tuya**:

https://github.com/azerty9971/xtend_tuya

At the time of this implementation, command delivery was reliable enough for the required operations, but reported device state could sometimes remain stale.

For that reason:

> **Home Assistant is the source of truth for the desired booster state.**

The automation does not depend on reported fan percentage to decide what should happen next.

It calculates the desired command and sends it explicitly.

Reported Tuya values should therefore be treated primarily as diagnostics.

---

# Central Nest Blower — Second-Stage Assist

Version 1.2 intentionally gives the local booster more opportunity to solve the imbalance before requesting whole-system airflow.

Nest circulation is requested only when **any final PI target reaches Speed 8 or higher**:

```text
Bed 1 PI Target >= 8
        OR
Bed 2 PI Target >= 8
        OR
Bed 3 PI Target >= 8
        │
        ▼
Request Nest circulation
```

Examples:

```text
Base P 6 + Adaptive I 0 = PI 6 → local booster only
Base P 6 + Adaptive I 1 = PI 7 → local booster only
Base P 6 + Adaptive I 2 = PI 8 → Nest circulation joins
```

A sufficiently large raw imbalance can also produce Base P 8 or 10 immediately, in which case the Nest second-stage assist is requested without waiting for Adaptive I to accumulate.

---

# Nest Fan Timer

Central circulation is requested using the Nest fan timer service used by this installation.

The current controller uses a renewable:

> **12-hour fan timer**

while strong balancing demand remains present.

This should be understood as a renewable circulation request, not as a deliberate instruction to leave the blower running unnecessarily for 12 continuous hours.

The hourly reconciliation can refresh the request when required.

When demand disappears, the controller explicitly releases the independent Nest circulation request after the post-run logic completes.

---

# Five-Minute Nest Release Delay

When all three PI targets fall below Speed 8, independent Nest circulation is not cancelled immediately.

The automation waits:

> **5 minutes**

and then re-checks all three live PI targets.

```text
Bed 1 PI < 8
   AND
Bed 2 PI < 8
   AND
Bed 3 PI < 8
        │
        ▼
Wait 5 minutes
        │
        ▼
Re-check all PI targets
        │
    ┌───┴────────────┐
    │                │
Demand returned      Still all < 8
    │                │
    ▼                ▼
Keep circulation     Cancel independent
                     Nest circulation
```

The automation uses:

```text
mode: restart
```

so new demand during the five-minute delay prevents a stale shutdown decision from being executed.

---

# Automation Triggers and Reconciliation

The v1.2 automation reacts to changes that can alter the desired final state, including:

- Bed 1 PI target
- Bed 2 PI target
- Bed 3 PI target
- Nest `hvac_action`
- Thermostat operating mode

It also runs:

- When Home Assistant starts
- Once per hour for desired-state reconciliation

The periodic reconciliation helps recover from:

- Missed Tuya commands
- Temporary integration issues
- Booster reboot
- Home Assistant restart
- Stale device feedback
- Nest fan timer expiration

Conceptually:

```text
Calculate desired state
        │
        ▼
Send desired state
        │
        ▼
Re-assert periodically
```

---

# Installing the Dashboard

The included:

```text
dashboard.yaml
```

contains the monitoring and diagnostics configuration developed for this project.

The dashboard is optional for control operation but strongly recommended while tuning the PI behavior.

## Current Dashboard Dependencies

The current layout uses:

- `custom:plotly-graph`
- `custom:multiple-entity-row`
- `card-mod`

Make sure these frontend components are installed and loaded before pasting the provided dashboard YAML.

---

# Live Status Table

The compact live-status card places Bed 1, Bed 2, and Bed 3 side by side.

Typical rows are:

```text
Temperature
Delta
Base P
Adaptive I
Ref 20m
Last Eval
PI Target
Fan
```

This makes it possible to see the full controller pipeline at a glance.

The most useful interpretation is:

```text
Delta
  ↓
Base P
  +
Adaptive I
  ↓
PI Target
  ↓
Fan %
```

---

# Plotly Multi-Panel Monitoring

The v1.2 Plotly view uses four vertically stacked graphs sharing the same time axis.

## Graph 1 — HVAC Power

```text
AC power
Airflow / indoor blower power
```

Entities:

```text
sensor.ac_power_total
sensor.furnace_power_total
```

The indoor furnace/blower power is labeled **Airflow** in the dashboard because it is used primarily to show when the indoor circulation system is moving air.

## Graph 2 — Temperatures

```text
AC / thermostat temperature
Target
Kitchen
Bed 1
Bed 2
Bed 3
```

## Graph 3 — Temperature Delta

```text
Bed 1 ΔT
Bed 2 ΔT
Bed 3 ΔT
```

## Graph 4 — Fan Speed

```text
Bed 1 effective percentage
Bed 2 effective percentage
Bed 3 effective percentage
```

The fan graph uses the actual effective percentage on a 0–100% scale.

Two display variants are currently used:

- Compact 48-hour TV monitoring layout
- Larger full-screen diagnostic layout with a longer history window

---

# Validation Procedure

Validate the installation progressively instead of enabling everything at once.

---

## Step 1 — Verify Raw Temperature Sensors

Confirm these entities are available and plausible:

```text
sensor.kitchen_temp_temperature
sensor.bed_1_temp_temperature
sensor.bed_2_temp_temperature
sensor.bed_3_temp_temperature
```

---

## Step 2 — Verify Raw Temperature Delta

Confirm:

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

follow:

```text
Bedroom - Kitchen
```

Example:

```text
Kitchen = 72.0°F
Bed 2   = 74.2°F

Bed 2 ΔT = +2.2°F
```

---

## Step 3 — Verify Base P

Confirm the proportional curve:

```text
< 1.5°F       → 0
1.5 - <2.0°F  → 2
2.0 - <2.5°F  → 4
2.5 - <3.0°F  → 6
3.0 - <3.5°F  → 8
>= 3.5°F      → 10
```

Remember that falling thresholds include approximately 0.2°F hysteresis.

---

## Step 4 — Verify Adaptive I Diagnostics

Confirm these entities exist:

```text
sensor.bed_1_booster_adaptive_boost
sensor.bed_2_booster_adaptive_boost
sensor.bed_3_booster_adaptive_boost
```

Inspect their attributes and confirm the controller is tracking:

```text
reference_error
last_evaluation
control_direction
```

Do not expect Adaptive I to change immediately. The controller normally requires approximately 20 minutes of meaningful observation before evaluating the response.

---

## Step 5 — Verify PI Target

Confirm:

```text
PI Target = Base P + Adaptive I
```

with a maximum of Speed 10.

Example:

```text
Base P     = 6
Adaptive I = 2
PI Target  = 8
```

---

## Step 6 — Verify Effective Percentage

Confirm the final effective percentage follows the PI Target.

Example:

```text
PI Target 6 → 60%
PI Target 8 → 80%
PI Target 10 → 100%
```

While `hvac_action` is actively `cooling` or `heating`, verify a PI Target of 0 still produces the minimum:

```text
10%
```

---

## Step 7 — Verify Booster Commands

Test each booster independently.

Expected startup sequence:

```text
FAN preset
    ↓
percentage
    ↓
ON
```

When its effective percentage becomes zero, the booster should be commanded OFF.

Because Xtend Tuya feedback can be stale, verify the physical fan as well as the Home Assistant entity when testing.

---

## Step 8 — Verify Active Balancing Between HVAC Cycles

With the thermostat still in `COOL` mode and `hvac_action` temporarily `idle`, create or observe a meaningful positive bedroom imbalance.

Expected behavior:

```text
Thermostat mode = COOL
hvac_action     = idle
Directional error > threshold

→ PI target may remain active
→ booster may continue balancing
```

This is intentional v1.2 behavior.

---

## Step 9 — Verify Nest Second-Stage Assist

Confirm that PI targets below 8 do **not** independently request Nest circulation.

Examples:

```text
PI 4 → booster only
PI 6 → booster only
PI 7 → booster only
```

Then verify that any room reaching:

```text
PI Target >= 8
```

requests central circulation.

Example:

```text
Bed 1 PI = 6
Bed 2 PI = 8
Bed 3 PI = 4

→ Nest circulation requested
```

---

## Step 10 — Verify Five-Minute Nest Release

When all PI targets fall below 8:

```text
Bed 1 < 8
Bed 2 < 8
Bed 3 < 8
```

verify independent Nest circulation remains active for approximately five minutes before the controller performs its final live re-check.

If any room returns to PI 8 or higher during that delay, the pending release should be cancelled by the restarted automation.

---

## Step 11 — Verify Recovery

Restart Home Assistant or wait for the hourly reconciliation cycle and confirm the desired booster state is re-applied correctly.

The controller should be able to recover from stale Tuya feedback without requiring the reported device state to match first.

---

# Useful Test Scenarios

| Scenario | Expected Result |
|---|---|
| COOL mode, error <1.5°F, HVAC idle | No Base P demand; Adaptive I should eventually unwind/reset as applicable |
| HVAC actively cooling, PI Target 0 | Effective fan minimum = 10% |
| Error 2.2°F, Adaptive I 0 | Base P 4, PI 4, approximately 40%, no Nest assist |
| Error 2.7°F, Adaptive I 0 | Base P 6, PI 6, approximately 60%, no Nest assist |
| Error remains poorly corrected over successive evaluation windows | Adaptive I can increase progressively |
| Base P 6 + Adaptive I 2 | PI 8, approximately 80%, Nest assist requested |
| Base P 10 | PI capped at 10; no adaptive headroom |
| Error ≤ about 1.3°F | Adaptive correction resets / unwinds according to template logic |
| Thermostat direction changes | Adaptive state is reset for the new direction |
| All PI targets <8 for 5 minutes | Independent Nest circulation released after live re-check |

---

# Updating from v1.1 to v1.2

If upgrading an existing v1.1 installation, use this order:

1. Back up the current configuration.
2. Disable the existing v1.1 booster automation.
3. Replace / merge `templates.yaml` with the v1.2 version.
4. Reload templates or restart Home Assistant.
5. Confirm all new Adaptive I and PI-target entities exist.
6. Replace / merge `automation.yaml` with the v1.2 version.
7. Verify entity IDs.
8. Enable the v1.2 automation.
9. Test each booster manually.
10. Validate PI behavior and Nest second-stage assist.
11. Update `dashboard.yaml` if the new monitoring interface is desired.

Do not skip Step 5. The new automation expects:

```text
sensor.bed_1_booster_pi_target_speed
sensor.bed_2_booster_pi_target_speed
sensor.bed_3_booster_pi_target_speed
```

to exist.

---

# Troubleshooting

## Booster Does Not Start

Verify manually that the fan entity accepts:

```text
fan.set_preset_mode
fan.set_percentage
fan.turn_on
```

Confirm the supported preset is:

```text
FAN
```

Also check whether Xtend Tuya reports the device as available.

---

## Booster Starts at the Wrong Speed

Confirm the command order has not been changed.

The percentage should be sent before the final `fan.turn_on` command.

---

## Home Assistant Shows the Wrong Fan Percentage

Xtend Tuya feedback may remain stale even after a successful command.

Use:

```text
sensor.bed_X_booster_effective_percentage
```

as the controller's intended command and verify the physical device when diagnosing command delivery.

---

## Adaptive I Never Changes

Check:

- Required temperature entities are available
- The room has meaningful positive directional error
- The control direction is valid
- Enough time has elapsed for an evaluation window
- `last_evaluation` is updating
- `reference_error` is populated
- Base P is not already at Speed 10

Remember that Adaptive I is intentionally slow compared with Base P.

---

## Adaptive I Keeps Increasing

Check whether the room is actually improving during each evaluation window.

If improvement remains below approximately 0.2°F over 20 minutes, increasing Adaptive I is expected behavior until headroom or other reset conditions are reached.

---

## Nest Circulation Does Not Start at Base P 4 or 6

This is expected in v1.2.

The central blower threshold is now based on the **final PI Target**:

```text
PI Target >= 8
```

not the old v1.1 threshold of Base Target 4.

---

## Booster Continues Running While `hvac_action` Is Idle

This can also be expected in v1.2.

If the thermostat remains in a valid balancing mode and the directional room error still requires correction, PI balancing can continue between active HVAC cycles.

---

## Dashboard Shows No Power History

The power graphs require:

```text
sensor.ac_power_total
sensor.furnace_power_total
```

and those entities must have recorder/history data available for the selected graph period.

The controller itself does not depend on these sensors.

---

# Safety and Tuning Notes

This configuration was tuned for a specific house, HVAC system, duct layout, booster model, and climate.

Do not assume these thresholds are ideal for another installation.

Important variables include:

- Room volume
- Duct length
- Duct diameter
- Supply-register size
- Static pressure
- HVAC blower performance
- Return-air paths
- Sensor placement
- Insulation
- Window area
- Solar exposure
- Outdoor conditions

Register booster fans change airflow distribution through the HVAC system.

Avoid significantly restricting supply or return airflow.

Do not close large numbers of registers in an attempt to force air toward one room.

If airflow requirements, static pressure, or equipment limitations are uncertain, consult a qualified HVAC professional.

---

# Winter / Heating

The v1.2 architecture includes directional heating logic, but the current tuning has been validated primarily during summer / cooling operation.

Heating should be considered a separate tuning phase.

Future winter work may include:

- Dedicated basement temperature monitoring
- Basement booster evaluation
- Heating-specific Base P thresholds
- Heating-specific Adaptive I behavior
- Heating-specific Nest circulation strategy
- Whole-house winter airflow characterization
- Winter energy measurements

---

# v1.2 Behavior Summary

The complete control path for each bedroom is:

```text
Bedroom Temperature
        │
        ▼
Raw Delta
        │
        ▼
Directional Error
        │
        ▼
Base P
        │
        +
Adaptive I
        │
        ▼
PI Target
        │
        ▼
HVAC Active Minimum Rule
        │
        ▼
Effective Percentage
        │
        ▼
Physical Booster
```

The shared second stage is:

```text
Any Bedroom PI Target >= 8
             │
             ▼
       Nest Circulation
```

and release occurs only after:

```text
All PI Targets < 8
        │
        ▼
     5 minutes
        │
        ▼
Live re-check
```

---

# Core v1.2 Entity Reference

## Temperatures

```text
sensor.kitchen_temp_temperature
sensor.bed_1_temp_temperature
sensor.bed_2_temp_temperature
sensor.bed_3_temp_temperature
```

## Raw Delta

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

## Base P

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

## Adaptive I

```text
sensor.bed_1_booster_adaptive_boost
sensor.bed_2_booster_adaptive_boost
sensor.bed_3_booster_adaptive_boost
```

## PI Target

```text
sensor.bed_1_booster_pi_target_speed
sensor.bed_2_booster_pi_target_speed
sensor.bed_3_booster_pi_target_speed
```

## Effective Percentage

```text
sensor.bed_1_booster_effective_percentage
sensor.bed_2_booster_effective_percentage
sensor.bed_3_booster_effective_percentage
```

## Boosters

```text
fan.bed_1_booster
fan.bed_2_booster
fan.bed_3_booster
```

## Central HVAC

```text
climate.kitchen
```

## Optional Power Monitoring

```text
sensor.ac_power_total
sensor.furnace_power_total
```

---

# Files

- [`templates.yaml`](templates.yaml) — Base P, Adaptive I, PI targets, temperature deltas, and effective percentages
- [`automation.yaml`](automation.yaml) — three-bedroom PI balancing and second-stage Nest circulation
- [`dashboard.yaml`](dashboard.yaml) — live status, Plotly monitoring, diagnostics, and tuning

For the project overview, hardware discussion, design rationale, and development roadmap, return to the:

[Main Project README](../README.md)