# Home Assistant Installation

This directory contains the Home Assistant configuration used by the **Home Assistant HVAC Balancing** project.

> **Current version: v1.1.0 — Three-bedroom balancing**

Version 1.1 expands the original two-bedroom controller to support:

- Bed 1
- Bed 2
- Bed 3

All three bedrooms use the same control strategy and are independently balanced against the Kitchen reference temperature.

The implementation is divided into three main configuration files:

| File | Purpose |
|---|---|
| `templates.yaml` | Calculates room temperature deltas, booster target speeds, and effective booster percentages |
| `automation.yaml` | Controls the three bedroom booster fans and Nest central blower |
| `dashboard.yaml` | Provides monitoring, diagnostics, and historical visualization |

The configuration in this repository reflects the working implementation as of **August 2026**.

---

# Requirements

The current implementation requires:

- Home Assistant
- Nest thermostat integrated with Home Assistant
- Dedicated temperature sensors for the Kitchen and three controlled bedrooms
- Three Tuya-based smart HVAC register booster fans
- Xtend Tuya custom integration
- ApexCharts Card for historical dashboard visualization

The compact live-status dashboard also uses:

- Multiple Entity Row

The dashboard components are not required for the controller itself.

The control logic can operate without the monitoring dashboard.

---

# System Architecture

The current v1.1 architecture is:

```text
                    Nest Thermostat
                          │
                          │
                    HVAC Operating State
                          │
                          ▼
                    Home Assistant
                          │
            ┌─────────────┼─────────────┐
            │             │             │
            ▼             ▼             ▼
          Bed 1         Bed 2         Bed 3
         Sensor         Sensor         Sensor
            │             │             │
            ▼             ▼             ▼
          Delta          Delta          Delta
            │             │             │
            ▼             ▼             ▼
          Target         Target         Target
            │             │             │
            ▼             ▼             ▼
       Effective %   Effective %   Effective %
            │             │             │
            ▼             ▼             ▼
        Booster 1     Booster 2     Booster 3

                    Any Target >= 4
                          │
                          ▼
                   Central Blower
```

All three bedroom controllers use the same Kitchen reference.

---

# HVAC Thermostat

The central HVAC system is controlled by a Nest thermostat.

Home Assistant entity:

```text
climate.kitchen
```

The controller uses:

- HVAC mode
- `hvac_action`
- Nest fan control

Relevant `hvac_action` states include:

```text
cooling
heating
idle
```

The Nest thermostat remains responsible for normal HVAC heating and cooling.

Home Assistant adds an independent airflow-balancing layer.

---

# Temperature Sensors

The balancing controller uses dedicated Zigbee temperature sensors.

Current entities:

| Location | Entity |
|---|---|
| Kitchen | `sensor.kitchen_temp_temperature` |
| Bed 1 | `sensor.bed_1_temp_temperature` |
| Bed 2 | `sensor.bed_2_temp_temperature` |
| Bed 3 | `sensor.bed_3_temp_temperature` |

The Kitchen sensor acts as the main temperature reference.

The same sensor model is used in all four locations to improve consistency when comparing relative room temperatures.

The controller does not use the Nest thermostat's internal temperature as the primary balancing reference.

---

# Booster Fans

Three Tuya-based smart register booster fans are installed.

The same booster model is used in all three bedrooms.

Product:

https://amzn.to/45ns5bJ

## Bed 1

```text
fan.bed_1_booster
```

## Bed 2

```text
fan.bed_2_booster
```

## Bed 3

```text
fan.bed_3_booster
```

The boosters support ten physical speed levels.

Home Assistant percentage maps directly to those levels:

| Booster Speed | HA Percentage |
|---:|---:|
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

---

# Tuya and Xtend Tuya

The booster fans are Tuya devices.

During development, the official Home Assistant Tuya integration did not expose all controls required to operate this specific booster model.

For that reason, this installation uses the custom **Xtend Tuya** integration:

https://github.com/azerty9971/xtend_tuya

Xtend Tuya extends the entities and functionality available for some Tuya devices.

---

## Important Xtend Tuya Limitation

At the time of this implementation in August 2026, device-state feedback through Xtend Tuya was not completely reliable for these boosters.

Home Assistant could occasionally display stale values for:

- Fan percentage
- Booster speed
- Operating mode
- Related Tuya select entities

However, the functions required by the controller reliably accepted commands.

Successfully tested operations include:

- Set `FAN` mode
- Set fan percentage
- Turn booster ON
- Turn booster OFF
- Configure a speed while OFF
- Start directly at the configured speed

Because command execution is reliable while feedback may be stale, the project uses a:

> **Desired-state control architecture**

Home Assistant calculates what each booster should be doing and explicitly sends that state.

Reported booster state is treated mainly as diagnostic information.

---

# Configuration Files

## `templates.yaml`

The template configuration creates three groups of calculated sensors.

### Temperature Delta

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

These sensors always represent:

```text
Bedroom Temperature - Kitchen Temperature
```

Therefore:

| Delta | Meaning |
|---:|---|
| Positive | Bedroom is warmer than Kitchen |
| 0°F | Bedroom and Kitchen are equal |
| Negative | Bedroom is cooler than Kitchen |

---

## Booster Target Speed

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

These sensors calculate the temperature-based booster target.

Possible values are:

```text
0
2
4
6
8
10
```

The template logic handles:

- Cooling direction
- Heating direction
- Heat/Cool mode
- Booster speed calculation
- 0.2°F hysteresis

---

## Effective Booster Percentage

Version 1.1 also exposes:

```text
sensor.bed_1_booster_effective_percentage
sensor.bed_2_booster_effective_percentage
sensor.bed_3_booster_effective_percentage
```

These sensors mirror the final booster percentage that the automation intends to use after the HVAC minimum-speed rule is applied.

For example:

| Calculated Target | HVAC Action | Effective Percentage |
|---:|---|---:|
| 0 | idle | 0% |
| 0 | cooling | 10% |
| 0 | heating | 10% |
| 2 | cooling | 20% |
| 4 | cooling | 40% |
| 10 | cooling | 100% |

This distinction is useful for diagnostics.

The calculated target answers:

> Why did the controller select this airflow level?

The effective percentage answers:

> What speed does the automation actually intend to command?

---

# Current Booster Speed Curve

All three bedrooms currently use the same control curve.

| Relevant Temperature Error | Target |
|---:|---:|
| `< 1.5°F` | 0 |
| `1.5 – <2.0°F` | 2 |
| `2.0 – <2.5°F` | 4 |
| `2.5 – <3.0°F` | 6 |
| `3.0 – <3.5°F` | 8 |
| `≥ 3.5°F` | 10 |

Example:

```text
1.7°F → Speed 2
2.2°F → Speed 4
2.7°F → Speed 6
3.2°F → Speed 8
3.5°F → Speed 10
```

---

# Directional Temperature Error

The raw delta is always:

```text
Bedroom - Kitchen
```

However, the target-speed sensors interpret that difference according to the selected HVAC operating mode.

## Cooling

```text
Directional Error =
Bedroom - Kitchen
```

A bedroom warmer than Kitchen creates positive demand.

## Heating

```text
Directional Error =
Kitchen - Bedroom
```

A bedroom colder than Kitchen creates positive demand.

## Heat/Cool Mode

If the Nest is configured as:

```text
heat_cool
```

the current:

```text
hvac_action
```

determines which direction is used.

The template architecture therefore already supports heating direction.

However:

> Heating behavior has not yet been seasonally field-tested or tuned.

The current control thresholds have been validated primarily during summer cooling.

---

# Hysteresis

The template controller uses approximately:

> **0.2°F hysteresis**

This prevents small sensor fluctuations from repeatedly changing booster speeds around a threshold.

Current thresholds:

| Rising Threshold | Target | Falling Threshold |
|---:|---:|---:|
| 1.5°F | Speed 2 | ≤ 1.3°F → OFF |
| 2.0°F | Speed 4 | ≤ 1.8°F → Speed 2 |
| 2.5°F | Speed 6 | ≤ 2.3°F → Speed 4 |
| 3.0°F | Speed 8 | ≤ 2.8°F → Speed 6 |
| 3.5°F | Speed 10 | ≤ 3.3°F → Speed 8 |

Example:

```text
Speed 4 begins at approximately 2.0°F
```

but does not fall to Speed 2 until the error reaches approximately:

```text
1.8°F
```

---

# `automation.yaml`

The primary automation is:

> **HVAC - Smart Bedroom Booster Control**

Version 1.1 controls:

```text
Bed 1
Bed 2
Bed 3
```

Its responsibilities include:

- Reading all three calculated target speeds
- Monitoring `hvac_action`
- Enforcing minimum Speed 1 while HVAC is actively heating or cooling
- Setting booster operating mode
- Setting booster percentage
- Turning each booster ON and OFF independently
- Starting central Nest circulation when any room reaches Speed 4 or higher
- Maintaining a five-minute post-circulation period
- Checking all three rooms before cancelling central circulation
- Recovering after Home Assistant restarts
- Periodically reconciling desired state

---

# Effective Booster Target

The automation distinguishes between:

**Calculated Target**

and:

**Effective Target**

The calculated target comes from room temperature imbalance.

While HVAC is actively heating or cooling:

```text
Effective Target =
max(Calculated Target, 1)
```

Examples:

| Calculated | HVAC Action | Effective |
|---:|---|---:|
| 0 | idle | 0 |
| 0 | cooling | 1 |
| 0 | heating | 1 |
| 2 | cooling | 2 |
| 4 | cooling | 4 |
| 10 | heating | 10 |

Speed 1 is therefore only a minimum airflow-assistance level.

A higher temperature-derived target always has priority.

---

# Booster Command Sequence

When a booster needs to operate, commands are intentionally sent in this order:

```text
Set FAN mode
     │
     ▼
Wait 1 second
     │
     ▼
Set target percentage
     │
     ▼
Wait 1 second
     │
     ▼
Turn booster ON
```

In Home Assistant service terms:

1. `fan.set_preset_mode`
2. Wait 1 second
3. `fan.set_percentage`
4. Wait 1 second
5. `fan.turn_on`

Testing showed that the boosters accept mode and percentage commands while OFF.

This allows the desired speed to be configured before starting the fan.

When no airflow is required:

```text
fan.turn_off
```

is sent.

---

# Central Blower Logic

Central HVAC circulation is requested when **any bedroom** reaches:

> **Speed 4 or greater**

With the current control curve, this corresponds to approximately:

> **2.0°F of directional temperature difference**

Conceptually:

```text
Bed 1 >= S4
      OR
Bed 2 >= S4
      OR
Bed 3 >= S4
       │
       ▼
Central Nest circulation
```

Therefore:

| Condition | Result |
|---|---|
| Target 0 | No local balancing demand |
| Effective S1 | HVAC-active minimum assistance |
| Target S2 | Local bedroom booster only |
| Target S4+ | Bedroom booster + central circulation |

This allows smaller imbalances to be handled locally without unnecessarily running the central blower.

---

# Nest Fan Timer

Central circulation is requested using:

```text
nest.set_fan_timer
```

The current automation requests:

```text
12 hours
```

The 12-hour timer is used as a renewable circulation lease.

It does **not** mean that the controller intentionally wants the blower to run continuously for 12 hours.

While balancing demand exists, the hourly reconciliation refreshes the request.

When balancing demand disappears, the automation explicitly cancels the independent fan request.

---

# Central Blower Post-Run

When all three bedroom targets fall below Speed 4, central circulation is not stopped immediately.

The automation waits:

> **5 minutes**

After the delay, all three calculated target sensors are checked again.

Conceptually:

```text
Bed 1 < S4
   AND
Bed 2 < S4
   AND
Bed 3 < S4
    │
    ▼
Wait 5 minutes
    │
    ▼
Re-check all 3 targets
    │
    ├── Demand returned
    │       │
    │       ▼
    │   Keep blower
    │
    └── Still below S4
            │
            ▼
       Cancel independent
       Nest circulation
```

The automation uses:

```text
mode: restart
```

This is important.

If new demand appears during the five-minute delay, the automation restarts and cancels the pending shutdown.

---

# Automation Triggers

The automation runs when any calculated bedroom target changes:

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

It also runs when the HVAC operating action changes:

```text
climate.kitchen
```

attribute:

```text
hvac_action
```

This is required because starting or stopping active heating/cooling changes the minimum effective booster speed.

The automation also runs:

- When Home Assistant starts
- Once per hour

---

# Hourly Desired-State Reconciliation

Once per hour, the automation re-applies the desired state.

This provides protection against:

- Missed Tuya commands
- Temporary integration issues
- Booster restarts
- Home Assistant restarts
- Stale reported state
- Nest fan timer expiration

The controller does not wait for device feedback to determine the desired state.

Instead:

```text
Calculate desired state
        │
        ▼
Send desired state
        │
        ▼
Repeat periodically
```

---

# Installing `templates.yaml`

The repository stores only the templates required for this project.

The expected include structure is:

```yaml
template: !include templates.yaml
```

When using that structure:

> Do not add another `template:` key inside `templates.yaml`.

The provided file itself starts with:

```yaml
- sensor:
```

If an existing installation already has template entities, merge the provided sensor definitions carefully.

Do not create duplicate definitions with the same:

```text
unique_id
```

After installation:

1. Save the YAML
2. Reload Template Entities if available
3. Otherwise restart Home Assistant

Then confirm that all nine calculated entities exist.

### Temperature Delta

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

### Target Speed

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

### Effective Percentage

```text
sensor.bed_1_booster_effective_percentage
sensor.bed_2_booster_effective_percentage
sensor.bed_3_booster_effective_percentage
```

---

# Installing the Automation

The automation can either be:

- Added through the Home Assistant automation UI using **Edit in YAML**
- Merged into an existing `automations.yaml`
- Included using the installation's existing automation include strategy

Before enabling the automation, verify all entity IDs.

The provided v1.1 configuration assumes:

| Function | Entity |
|---|---|
| Nest thermostat | `climate.kitchen` |
| Kitchen temperature | `sensor.kitchen_temp_temperature` |
| Bed 1 temperature | `sensor.bed_1_temp_temperature` |
| Bed 2 temperature | `sensor.bed_2_temp_temperature` |
| Bed 3 temperature | `sensor.bed_3_temp_temperature` |
| Bed 1 booster | `fan.bed_1_booster` |
| Bed 2 booster | `fan.bed_2_booster` |
| Bed 3 booster | `fan.bed_3_booster` |

If another installation uses different entity IDs, update them before enabling the automation.

---

# Installing Xtend Tuya

Xtend Tuya must expose a usable `fan` entity for each booster.

The automation relies primarily on:

```text
fan.set_preset_mode
fan.set_percentage
fan.turn_on
fan.turn_off
```

The physical booster should accept:

```text
preset_mode: FAN
```

The controller does not require the reported Tuya speed state to be accurate.

The `fan` entity is used to send commands.

---

# Installing the Dashboard

The included:

```text
dashboard.yaml
```

contains the monitoring and diagnostics configuration developed for this project.

The dashboard is diagnostic only.

It is **not required for the HVAC balancing automation to operate**.

---

## ApexCharts Card

Historical graphs require:

> **ApexCharts Card**

The dashboard uses ApexCharts to visualize:

- Kitchen temperature
- Bed 1 temperature
- Bed 2 temperature
- Bed 3 temperature
- Temperature deltas
- Calculated target speeds
- Booster activity
- Central Nest blower activity

---

## Multiple Entity Row

The compact live-status card uses:

> **Multiple Entity Row**

This allows each bedroom to display multiple values on a single compact row.

For example:

```text
Bedroom | Temperature | ΔT | Effective %
```

The current compact layout uses icons rather than bedroom names to reduce horizontal space.

---

# Dashboard Monitoring Structure

The v1.1 dashboard is designed to expose several levels of controller behavior.

## Temperature

```text
Kitchen
Bed 1
Bed 2
Bed 3
```

## Temperature Imbalance

```text
Bed 1 ΔT
Bed 2 ΔT
Bed 3 ΔT
```

## Calculated Decision

```text
Bed 1 Target
Bed 2 Target
Bed 3 Target
```

## Effective Command

```text
Bed 1 Effective %
Bed 2 Effective %
Bed 3 Effective %
```

## Physical Device

```text
fan.bed_1_booster
fan.bed_2_booster
fan.bed_3_booster
```

This makes it possible to diagnose:

```text
Temperature
     ↓
Delta
     ↓
Target
     ↓
Effective Command
     ↓
Physical Booster
```

---

# Validation

After installation, validate the system progressively.

Do not begin by testing the entire automation at once.

---

## Step 1 — Temperature Sensors

Confirm:

```text
sensor.kitchen_temp_temperature
sensor.bed_1_temp_temperature
sensor.bed_2_temp_temperature
sensor.bed_3_temp_temperature
```

all provide plausible values.

---

## Step 2 — Temperature Deltas

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

For example:

```text
Kitchen = 72.0°F
Bed 3   = 74.2°F

Bed 3 ΔT = +2.2°F
```

---

## Step 3 — Calculated Targets

Verify the expected curve:

```text
< 1.5°F       → 0
1.5 - <2.0°F  → 2
2.0 - <2.5°F  → 4
2.5 - <3.0°F  → 6
3.0 - <3.5°F  → 8
>= 3.5°F      → 10
```

---

## Step 4 — HVAC Minimum Speed

When:

```text
hvac_action = cooling
```

or:

```text
hvac_action = heating
```

a calculated target of:

```text
0
```

should produce an effective percentage of:

```text
10%
```

corresponding to:

```text
Speed 1
```

---

## Step 5 — Booster Operation

Each booster should independently follow its effective target.

Expected command behavior:

```text
FAN mode
   ↓
percentage
   ↓
ON
```

When target becomes zero while HVAC is not active:

```text
OFF
```

---

## Step 6 — Central Blower

Verify that any bedroom reaching:

```text
Target >= 4
```

can request central Nest circulation.

For example:

```text
Bed 1 = 0
Bed 2 = 2
Bed 3 = 4
```

should result in:

```text
Central circulation requested
```

---

## Step 7 — Five-Minute Post-Circulation

When all three targets become:

```text
< 4
```

the independent Nest fan request should remain active for approximately:

```text
5 minutes
```

before being cancelled.

If any bedroom returns to:

```text
>= 4
```

during that period, the pending shutdown should be cancelled.

---

# Expected Overall Behavior

During summer cooling:

```text
Directional Error < 1.5°F
        │
        ▼
No temperature-derived balancing demand
```

If HVAC is idle:

```text
Target 0
   ↓
Booster OFF
```

If HVAC is actively cooling:

```text
Target 0
   +
HVAC Active
   ↓
Speed 1
```

At:

```text
1.5°F
```

the bedroom receives:

```text
Local booster Speed 2
```

At:

```text
2.0°F
```

the bedroom receives:

```text
Booster Speed 4
       +
Central circulation
```

Higher imbalance produces:

```text
S6 → S8 → S10
```

---

# v1.1 Behavior Summary

All three bedrooms are treated identically.

```text
Bed 1
Temperature → Delta → Target → Effective % → Booster

Bed 2
Temperature → Delta → Target → Effective % → Booster

Bed 3
Temperature → Delta → Target → Effective % → Booster
```

Central circulation is shared:

```text
Any Bedroom Target >= 4
           │
           ▼
     Central Blower
```

Central circulation stops only when:

```text
Bed 1 < 4
   AND
Bed 2 < 4
   AND
Bed 3 < 4
```

for the required post-circulation period.

---

# Important Notes

The configuration in this repository is tuned for a specific house, HVAC system, duct layout, and climate.

The thresholds should not automatically be considered ideal for another home.

Different installations may require adjustments based on:

- Room size
- Duct length
- Duct diameter
- Static pressure
- Booster performance
- HVAC airflow
- Sensor location
- Building insulation
- Solar exposure
- Climate

The monitoring dashboard is particularly useful for making these adjustments based on actual historical behavior.

---

# Winter / Heating

The template architecture already contains directional heating logic.

However, the current controller has been tuned primarily during summer operation.

Winter testing remains a future phase.

The basement temperature sensor previously used during early system observation has been moved to Bed 3 for v1.1.

Therefore, future basement balancing will require dedicated basement temperature monitoring to be established again.

Possible future work includes:

- Basement temperature sensor
- Basement register booster
- Heating-specific speed curve
- Heating-specific blower strategy
- Winter energy analysis
- Seasonal controller profiles

---

# Safety

Register booster fans change airflow distribution through the HVAC system.

Avoid configurations that significantly restrict total system airflow.

Do not close large numbers of supply registers in an attempt to force airflow toward other rooms.

Ensure that return-air paths remain adequate.

HVAC systems differ in:

- Blower capacity
- Static pressure
- Duct design
- Equipment requirements
- Available airflow

If system static pressure, airflow requirements, or equipment limitations are unknown, consult a qualified HVAC professional.

---

# Files

- [`templates.yaml`](templates.yaml) — temperature delta, target-speed, and effective-percentage calculations
- [`automation.yaml`](automation.yaml) — three-bedroom active balancing controller
- [`dashboard.yaml`](dashboard.yaml) — monitoring, diagnostics, and tuning interface

For the complete project description, return to the:

[Main Project README](../README.md)