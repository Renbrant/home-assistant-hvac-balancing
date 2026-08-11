# Home Assistant HVAC Balancing

![Home Assistant HVAC Balancing](Photos/home-assistant-hvac-balancing.png)

A smart HVAC room-balancing system built with **Home Assistant**, independent temperature sensors, smart register booster fans, and central HVAC blower control.

The goal of this project is to reduce temperature differences between rooms by intelligently redistributing conditioned air instead of relying only on additional heating or cooling cycles.

> **Current version: v1.1.0 — Three-bedroom balancing**<br>
> The system is currently field-tested and tuned primarily for summer / cooling operation.

---

# Version 1.1.0

Version **v1.1.0** expands the original two-bedroom controller to support a third independently controlled bedroom while preserving the same control strategy introduced in v1.0.

## What's New in v1.1.0

- Added Bed 3 Zigbee temperature monitoring
- Added a third smart register booster fan
- Added Bed 3 raw temperature-delta calculation
- Added Bed 3 calculated booster target speed
- Added Bed 3 effective booster percentage
- Extended the main automation from two to three bedroom boosters
- Added Bed 3 to the central Nest blower demand logic
- Added Bed 3 to the five-minute post-circulation re-check
- Added Bed 3 to restart and hourly desired-state reconciliation
- Expanded dashboard monitoring for three bedrooms
- Added effective-percentage sensors for all three bedrooms so the final intended fan command can be monitored directly

## What Remains Unchanged

The core v1.0 strategy is preserved:

- Kitchen remains the room-balancing temperature reference
- Each bedroom is controlled independently
- Booster speed is determined from directional temperature error
- A 0.2°F hysteresis prevents rapid speed oscillation
- Active HVAC operation imposes a minimum booster Speed 1
- Speed 4 or higher requests central Nest blower circulation
- Independent central circulation is released only after a five-minute delay when all bedroom demands remain below the threshold
- Home Assistant remains the source of truth for the desired booster state because Xtend Tuya feedback can be stale

## Version History

| Version | Description |
|---|---|
| **v1.0.0** | Initial production controller with Bed 1 and Bed 2 balancing |
| **v1.1.0** | Adds Bed 3 and expands the existing control architecture to three independently controlled bedrooms |

---

# The Problem

Some rooms in the house consistently become warmer or cooler than others.

A central thermostat can maintain the temperature near its own reference location, but it cannot directly compensate for differences caused by factors such as:

- Different duct lengths and airflow
- Distance from the HVAC system
- Room orientation and solar exposure
- Exterior walls and windows
- Different thermal loads
- Closed bedroom doors
- Uneven supply airflow
- Different return-air paths

In this installation, the upstairs bedrooms can become significantly warmer than the Kitchen and main living areas during summer.

Simply lowering the thermostat setpoint would increase compressor runtime and may overcool other areas of the house.

The objective is therefore to improve **air distribution** before asking the HVAC system to produce additional cooling.

---

# The Solution

Home Assistant continuously compares the temperature of each controlled bedroom against a dedicated reference temperature sensor in the Kitchen.

Based on that temperature difference, the system dynamically controls smart register booster fans installed in the bedroom supply vents.

For smaller temperature differences, only the local bedroom booster is used.

For larger differences, Home Assistant can also request operation of the central HVAC blower to increase airflow through the complete duct system.

The Nest thermostat continues to control normal heating and cooling.

Home Assistant operates as an additional:

> **Airflow-balancing control layer**

The objective is to improve temperature distribution using airflow whenever possible, potentially reducing the need for additional HVAC cooling cycles.

---

# System Overview

```text
                    ┌──────────────────────┐
                    │    Nest Thermostat   │
                    │                      │
                    │ Heating / Cooling    │
                    │ Central Blower       │
                    └──────────┬───────────┘
                               │
                               │ HVAC State
                               │
                    ┌──────────▼───────────┐
                    │    Home Assistant    │
                    │                      │
                    │ Temperature Delta    │
                    │ Hysteresis           │
                    │ Booster Control      │
                    │ Blower Control       │
                    └──────┬──────┬───────┘
                           │      │
                ┌──────────┘      └──────────┐
                │                            │
         ┌──────▼──────┐              ┌──────▼──────┐
         │    Bed 1    │              │    Bed 2    │
         │ Temp Sensor │              │ Temp Sensor │
         │ Booster Fan │              │ Booster Fan │
         └─────────────┘              └─────────────┘
                           │
                    ┌──────▼──────┐
                    │    Bed 3    │
                    │ Temp Sensor │
                    │ Booster Fan │
                    └─────────────┘

                    Temperature Reference
                              │
                       ┌──────▼──────┐
                       │   Kitchen   │
                       │ Temp Sensor │
                       └─────────────┘
```

Each bedroom has its own temperature sensor, calculated target, effective command, and physical booster.

Any bedroom can independently request central blower assistance when its balancing demand reaches the configured threshold.

---

# Hardware

## Register Booster Fans

Three smart HVAC register booster fans are currently installed.

The same model is used in:

- Bed 1
- Bed 2
- Bed 3

**Product:** [Smart HVAC Register Booster Fan — Amazon](https://amzn.to/45ns5bJ)

The boosters provide **10 selectable speed levels** and can be individually controlled by Home Assistant.

### Booster Fan Photos

<p align="center">
  <img src="Photos/products/61rP3lfUvCL._AC_SL1500_.jpg" width="60%">
</p>

<p align="center">
  <img src="Photos/products/719suP-GdML._AC_SL1500_.jpg" width="41%">
  <img src="Photos/products/71QllN3aedL._AC_SL1500_.jpg" width="41%">
</p>

<p align="center">
  <img src="Photos/products/71U9ywOyj6L._AC_SL1500_.jpg" width="41%">
  <img src="Photos/products/71jVMTwgRZL._AC_SL1500_.jpg" width="41%">
</p>

<p align="center">
  <img src="Photos/products/810lE5zgJHL._AC_SL1500_.jpg" width="41%">
  <img src="Photos/products/81AaMseL5qL._AC_SL1500_.jpg" width="41%">
</p>

---

## Temperature Sensors

Temperature measurements used by the balancing controller come from dedicated **Zigbee 3.0 temperature and humidity sensors**.

**Sensor used in this project:**  
[Zigbee 3.0 Temperature & Humidity Sensor — Amazon](https://amzn.to/4czY3p1)

The same sensor model is currently used in:

- Kitchen
- Bed 1
- Bed 2
- Bed 3

Using the same model in all controlled locations is intentional because the controller is primarily interested in the **temperature difference between rooms**.

### Sensor Specifications

According to the product listing:

| Specification | Value |
|---|---|
| Temperature accuracy | ±0.2°C / ±0.4°F |
| Humidity accuracy | ±2% RH |
| Refresh interval | Approximately 5 seconds |
| Wireless protocol | Zigbee 3.0 |
| Power source | Standard AAA batteries |
| Advertised battery life | Up to 2 years |
| Measurements | Temperature, humidity, dew point and VPD |

### Temperature Entities

| Location | Function | Entity |
|---|---|---|
| Kitchen | Main temperature reference | `sensor.kitchen_temp_temperature` |
| Bed 1 | Controlled bedroom | `sensor.bed_1_temp_temperature` |
| Bed 2 | Controlled bedroom | `sensor.bed_2_temp_temperature` |
| Bed 3 | Controlled bedroom | `sensor.bed_3_temp_temperature` |

---

# Tuya Integration

The booster fans are Tuya-based Wi-Fi devices.

They work normally within the Tuya / Smart Life ecosystem, but during this implementation the **official Home Assistant Tuya integration did not expose the controls required to properly operate this particular booster model**.

For this reason, the project uses **Xtend Tuya**.

## What is Xtend Tuya?

Xtend Tuya is a custom Home Assistant integration designed to extend the official Tuya integration by exposing entities and capabilities that may not otherwise be available for some Tuya devices.

Project repository:

[azerty9971/xtend_tuya on GitHub](https://github.com/azerty9971/xtend_tuya)

Xtend Tuya is not part of Home Assistant Core.

In this installation, it exposed the controls required to operate the register booster fans.

<p align="center">
  <img src="Photos/XTend%20Tuya%20Register%20Booster%20Fan%20integration.png"
       width="100%"
       alt="Xtend Tuya Register Booster Fan integration">
</p>

The required functionality includes:

- Fan power control
- Operating mode
- Speed / percentage control
- Fan entity control

---

## Xtend Tuya Limitations Observed

At the time of implementation in **August 2026**, Xtend Tuya was functional for controlling these boosters, but device-state feedback was not completely reliable.

Home Assistant could occasionally display stale values for items such as:

- Current fan speed
- Fan percentage
- Operating / preset mode
- Some Tuya select entities

The physical booster and Tuya application could show the correct state while Home Assistant continued showing an older value.

However, **command delivery worked reliably for the operations required by this project**.

Successfully tested commands include:

- Set booster operating mode to `FAN`
- Set fan percentage
- Turn booster ON
- Turn booster OFF
- Configure a new speed while the fan is OFF
- Start directly at the configured speed

---

# Desired-State Control

Because commands were reliable while device feedback could remain stale, the controller does not depend on reported fan state to determine what should happen next.

> **Home Assistant is the source of truth for the requested booster state.**

Home Assistant independently calculates:

1. Current room temperature imbalance
2. Required booster target speed
3. Effective fan command after HVAC minimum-speed rules
4. Whether central circulation is required
5. Which commands must be sent to each booster

Reported Tuya state is treated primarily as diagnostic information.

---

## Booster Command Sequence

Testing showed that the boosters accept operating-mode and speed commands while powered OFF.

Whenever a booster needs to operate, Home Assistant uses this sequence:

```text
Set FAN mode
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

This prepares the desired speed before startup and prevents the fan from briefly starting at an older stored value.

The physical fan levels map directly to Home Assistant percentage:

| Booster Level | HA Percentage |
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

If no airflow is required, Home Assistant sends an OFF command.

---

# Temperature Sensing

## Temperature Reference

The dedicated Kitchen Zigbee sensor is used as the main reference for balancing.

The controller compares each bedroom against this sensor rather than using the Nest thermostat's internal temperature as the primary balancing measurement.

This keeps Kitchen, Bed 1, Bed 2, and Bed 3 comparisons based on the same sensor model and measurement technology.

---

## Temperature Delta

Home Assistant calculates a raw temperature delta for each bedroom:

**Bedroom Temperature − Kitchen Temperature**

| Raw Delta | Meaning |
|---:|---|
| Positive | Bedroom is warmer than Kitchen |
| 0°F | Temperatures are equal |
| Negative | Bedroom is cooler than Kitchen |

Template entities:

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

During summer cooling, a positive bedroom delta indicates that the bedroom is warmer than the Kitchen and may require additional airflow.

---

## Directional Error

The raw delta is always:

```text
Bedroom - Kitchen
```

but booster demand depends on HVAC mode.

### Cooling

```text
Directional Error = Bedroom - Kitchen
```

A warmer bedroom creates positive demand.

### Heating

```text
Directional Error = Kitchen - Bedroom
```

A colder bedroom creates positive demand.

### Heat/Cool Auto Mode

When the Nest is in `heat_cool`, `hvac_action` determines which direction is active.

The template architecture therefore already supports directional heating logic, but:

> **Heating behavior has not yet been seasonally field-tested or tuned.**

The current production tuning documented here is based primarily on summer cooling operation.

---

# Calculated and Effective Booster Commands

Version 1.1 exposes two separate concepts for each bedroom.

## Calculated Target Speed

The temperature-derived controller target:

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

Possible values are:

```text
0 / 2 / 4 / 6 / 8 / 10
```

---

## Effective Percentage

The final intended fan percentage after the HVAC-active minimum-speed rule is applied:

```text
sensor.bed_1_booster_effective_percentage
sensor.bed_2_booster_effective_percentage
sensor.bed_3_booster_effective_percentage
```

Examples:

| Calculated Target | HVAC Action | Effective Command |
|---:|---|---:|
| 0 | idle | 0% |
| 0 | cooling | 10% |
| 0 | heating | 10% |
| 2 | cooling | 20% |
| 4 | cooling | 40% |
| 10 | cooling | 100% |

This distinction makes it possible to monitor both **why the controller selected a target** and **what command the automation actually intends to send**.

---

# Current Summer Control Strategy

## Booster Speed Curve

Real-world testing showed that the original conservative controller equalized rooms too slowly, so the control curve was made more aggressive.

The current curve is:

| Directional Temperature Difference | Booster Target |
|---:|---:|
| `< 1.5°F` | OFF |
| `1.5 – <2.0°F` | Speed 2 |
| `2.0 – <2.5°F` | Speed 4 |
| `2.5 – <3.0°F` | Speed 6 |
| `3.0 – <3.5°F` | Speed 8 |
| `≥ 3.5°F` | Speed 10 |

Examples:

```text
ΔT = 1.7°F  → Speed 2
ΔT = 2.2°F  → Speed 4
ΔT = 2.7°F  → Speed 6
ΔT = 3.2°F  → Speed 8
ΔT = 3.5°F  → Speed 10
```

---

## Hysteresis

The controller uses approximately:

> **0.2°F hysteresis**

This prevents rapid speed changes when a temperature difference fluctuates around a threshold.

| Rising Threshold | Target | Falling Threshold |
|---:|---:|---:|
| 1.5°F | Speed 2 | ≤ 1.3°F → OFF |
| 2.0°F | Speed 4 | ≤ 1.8°F → Speed 2 |
| 2.5°F | Speed 6 | ≤ 2.3°F → Speed 4 |
| 3.0°F | Speed 8 | ≤ 2.8°F → Speed 6 |
| 3.5°F | Speed 10 | ≤ 3.3°F → Speed 8 |

---

## HVAC-Active Minimum Speed

When the HVAC is actively heating or cooling, all three bedroom boosters operate at a minimum of:

> **Speed 1**

The Speed 1 rule is only a minimum.

A higher calculated target always takes priority.

Conceptually:

```text
Effective Target = max(Calculated Target, 1)
```

while:

```text
hvac_action = cooling
```

or:

```text
hvac_action = heating
```

When HVAC is idle, the calculated target is used without the Speed 1 minimum.

---

## Central Blower Assistance

Small temperature differences are handled locally by the booster fan.

When **any bedroom** reaches:

> **Speed 4 or greater**

Home Assistant also requests central HVAC blower circulation through the Nest thermostat.

With the current curve, Speed 4 corresponds to approximately:

> **2.0°F of directional temperature imbalance**

Conceptually:

```text
Bed 1 target >= 4
        OR
Bed 2 target >= 4
        OR
Bed 3 target >= 4
        │
        ▼
Request central Nest circulation
```

A 12-hour Nest fan timer is used as a renewable circulation lease.

The hourly reconciliation refreshes it while balancing demand remains present.

---

## Five-Minute Post-Circulation

When all three bedroom calculated targets fall below Speed 4, independent central circulation is not stopped immediately.

The controller waits:

> **5 minutes**

and then performs a live re-check of all three target sensors.

```text
Bed 1 < 4
   AND
Bed 2 < 4
   AND
Bed 3 < 4
    │
    ▼
Wait 5 minutes
    │
    ▼
Re-check all 3 rooms
    │
 ┌──┴──────────────┐
 │                 │
Demand returned   Still below
 │                 │
 ▼                 ▼
Keep blower      Cancel independent
running          Nest circulation
```

The automation uses:

```text
mode: restart
```

so new demand during the five-minute delay cancels the pending shutdown and immediately applies the new desired state.

---

## Automatic Recovery and Reconciliation

The controller reacts immediately when:

- Bed 1 calculated target changes
- Bed 2 calculated target changes
- Bed 3 calculated target changes
- HVAC `hvac_action` changes

It also runs:

- When Home Assistant starts
- Once per hour as a reconciliation cycle

The hourly cycle re-applies desired state and helps recover from:

- Missed Tuya commands
- Temporary integration failure
- Booster reboot
- Home Assistant restart
- Nest fan timer refresh requirements
- Stale device feedback

---

# v1.1 Control Flow

Each bedroom follows the same pipeline:

```text
Bedroom Temperature
        │
        ▼
Raw Temperature Delta
        │
        ▼
Directional Error
        │
        ▼
Calculated Target Speed
        │
        ▼
HVAC Minimum-Speed Rule
        │
        ▼
Effective Percentage
        │
        ▼
Physical Booster Command
```

The three room pipelines operate independently but share the same Kitchen reference and central blower decision.

```text
Kitchen Reference
      │
      ├── Bed 1 → Delta → Target → Effective % → Booster 1
      ├── Bed 2 → Delta → Target → Effective % → Booster 2
      └── Bed 3 → Delta → Target → Effective % → Booster 3
                         │
                         └── Any target >= 4
                                  │
                                  ▼
                           Central Blower
```

---

# Energy Considerations

HVAC electrical consumption was monitored during development.

The installation has separate monitored circuits for:

- Outdoor AC compressor / condenser
- Indoor furnace / blower

Observed values were approximately:

| Operating Component | Observed Power |
|---|---:|
| Central circulation blower | ~200 W |
| Indoor blower during active cooling | ~280 W at one observed operating point |
| Outdoor AC compressor / condenser | ~2 kW or more |

These values are specific to this installation and should not be interpreted as universal HVAC specifications.

They demonstrate an important principle for this project:

> Moving already-conditioned air around the house requires substantially less power than producing additional cooling with the compressor.

---

# Monitoring

A dedicated Home Assistant dashboard is used to observe and tune the controller.

The dashboard monitors:

- HVAC operating state
- Kitchen reference temperature
- Bed 1, Bed 2, and Bed 3 temperatures
- Three bedroom temperature deltas
- Three calculated booster targets
- Three effective booster percentages
- Booster activity
- Central blower activity
- Xtend Tuya raw feedback
- Historical temperature balance
- Historical speed-versus-delta behavior

ApexCharts is used for historical visualization.

---

## Live System Status

The live card is designed to remain compact while showing the most important information for all three rooms.

Each bedroom row can display:

```text
Temperature | ΔT | Effective Speed
```

while the native Nest climate row preserves current HVAC mode, target, measured temperature, and humidity information.

---

## Booster Controller

The **Booster Controller** graph compares calculated target speed against temperature delta.

The controller uses discrete speed steps while the temperature-delta series remains continuous.

For visualization only, small graphical offsets may be used when multiple bedrooms have the same target so the lines do not completely overlap.

Those offsets affect only display position and never change controller values.

---

## Temperature Balance

The **Temperature Balance** graph compares Kitchen with all three controlled bedrooms over time.

The objective is not simply absolute room temperature.

The primary question is whether each bedroom follows the Kitchen reference more closely after airflow correction.

A successful balancing strategy should produce:

> **Smaller temperature differences and shorter periods of significant imbalance.**

---

## Existing Screenshots

The repository includes screenshots captured during development of the controller:

![HVAC Smart Booster - Live Status](Photos/HVAC%20Smart%20Booster%20-%20Live%20Status.png)

![Booster Controller](Photos/Booster%20Controller.png)

![Temperature Balance](Photos/Temperature%20Balance.png)

> Some screenshots were captured during the v1.0 two-bedroom implementation and may not yet visually show Bed 3. The YAML files in `HomeAssistant/` are the authoritative configuration for the current release.

---

# Home Assistant Configuration

The actual Home Assistant YAML configuration is stored separately from this project overview.

| File | Purpose |
|---|---|
| [`HomeAssistant/templates.yaml`](HomeAssistant/templates.yaml) | Temperature delta, target-speed, and effective-percentage template sensors |
| [`HomeAssistant/automation.yaml`](HomeAssistant/automation.yaml) | Three-bedroom booster and central blower control |
| [`HomeAssistant/dashboard.yaml`](HomeAssistant/dashboard.yaml) | Monitoring and diagnostics dashboard |
| [`HomeAssistant/README.md`](HomeAssistant/README.md) | Installation and implementation notes |

---

# Core v1.1 Entities

## Temperature

```text
sensor.kitchen_temp_temperature
sensor.bed_1_temp_temperature
sensor.bed_2_temp_temperature
sensor.bed_3_temp_temperature
```

## Temperature Delta

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
sensor.bed_3_temperature_delta
```

## Calculated Target Speed

```text
sensor.bed_1_booster_target_speed
sensor.bed_2_booster_target_speed
sensor.bed_3_booster_target_speed
```

## Effective Percentage

```text
sensor.bed_1_booster_effective_percentage
sensor.bed_2_booster_effective_percentage
sensor.bed_3_booster_effective_percentage
```

## Booster Fans

```text
fan.bed_1_booster
fan.bed_2_booster
fan.bed_3_booster
```

## Central HVAC

```text
climate.kitchen
```

---

# Repository Structure

```text
home-assistant-hvac-balancing/
│
├── README.md
│
├── Photos/
│   ├── home-assistant-hvac-balancing.png
│   ├── HVAC Smart Booster - Live Status.png
│   ├── Booster Controller.png
│   ├── Temperature Balance.png
│   ├── XTend Tuya Register Booster Fan integration.png
│   │
│   ├── automation/
│   │   ├── 1.png
│   │   ├── 2.png
│   │   ├── 3.png
│   │   └── 4.png
│   │
│   └── products/
│       └── booster product photos
│
└── HomeAssistant/
    ├── README.md
    ├── templates.yaml
    ├── automation.yaml
    └── dashboard.yaml
```

---

# Current Status

The current controller is operational and has been field-tested primarily during **summer cooling conditions**.

This release should be considered:

> **v1.1.0 — Three-bedroom Summer / Cooling Balancing**

The physical balancing system now includes:

```text
Bed 1 Booster
       +
Bed 2 Booster
       +
Bed 3 Booster
       +
Central HVAC blower assistance when required
```

The Kitchen remains the reference temperature.

---

## Current Implementation Checklist

### Summer / Cooling

- [x] Matching Zigbee 3.0 temperature sensors in Kitchen, Bed 1, Bed 2, and Bed 3
- [x] Kitchen reference temperature
- [x] Bed 1 temperature monitoring
- [x] Bed 2 temperature monitoring
- [x] Bed 3 temperature monitoring
- [x] Three bedroom temperature-delta sensors
- [x] Directional cooling/heating error architecture
- [x] Three independent calculated booster targets
- [x] Three effective-percentage monitoring sensors
- [x] Dynamic booster speed control
- [x] Ten-level booster capability
- [x] Summer speed curve tuned from real-world data
- [x] Minimum Speed 1 while HVAC is actively heating or cooling
- [x] Central blower assistance starting at Speed 4
- [x] Bed 3 participation in central blower demand
- [x] 0.2°F hysteresis
- [x] Five-minute post-circulation across all three rooms
- [x] Home Assistant restart recovery
- [x] Hourly desired-state reconciliation
- [x] Xtend Tuya command validation
- [x] Xtend Tuya feedback diagnostics
- [x] ApexCharts historical monitoring
- [x] HVAC electrical monitoring
- [x] Real-world summer operation validated

### Winter / Heating

- [ ] Winter thermal behavior measured
- [ ] Basement temperature monitoring re-established for winter testing
- [ ] Basement temperature imbalance characterized
- [ ] Basement booster evaluated
- [ ] Basement booster installed if required
- [ ] Heating-specific control thresholds validated
- [ ] Heating-specific booster curve tuned
- [ ] Central circulation strategy validated for heating
- [ ] Interaction between upstairs and basement balancing tested
- [ ] Winter energy impact measured
- [ ] Heating configuration field-tested

---

# Future Development

The next major phase is to evolve the current summer controller into a:

> **Season-aware whole-house HVAC balancing system**

Cooling and heating produce different thermal patterns in the house, so the long-term objective is not simply to reuse the summer curve during winter.

Each operating mode should eventually have its own experimentally validated control strategy.

---

## Phase 2 — Winter / Heating Balancing

The expected winter thermal problem is approximately the opposite of summer.

### Summer

```text
Upstairs bedrooms too warm
            │
            ▼
Increase conditioned airflow upstairs
```

### Winter

```text
Basement too cold
        │
        ▼
Increase warm airflow downstairs
```

A possible future architecture is:

```text
                         HVAC MODE
                            │
                 ┌──────────┴──────────┐
                 │                     │
              COOLING               HEATING
                 │                     │
                 ▼                     ▼
       Upstairs balancing       Basement balancing
                 │                     │
          Bed 1 Booster          Basement Booster
          Bed 2 Booster                │
          Bed 3 Booster                │
                 │                     │
                 └──────────┬──────────┘
                            │
                            ▼
                     Central Blower
```

The basement will require dedicated temperature monitoring again before this phase can be characterized and tuned.

---

## Independent Room Control Curves

Version 1.1 intentionally gives Bed 1, Bed 2, and Bed 3 the same control curve.

Future versions may tune each room independently because rooms differ in:

- Duct length
- Register size
- Room volume
- Exterior exposure
- Window area
- Solar load
- Insulation
- Return-air path
- Distance from the blower

Historical performance can then determine whether a specific bedroom benefits from a different response curve.

---

## Command Verification

If future Xtend Tuya versions provide reliable device feedback, the controller could evolve from desired-state control toward automatic command verification.

```text
Desired Speed
      │
      ▼
Send Command
      │
      ▼
Read Device Feedback
      │
   ┌──┴───┐
   │      │
 Match  Mismatch
   │      │
   ▼      ▼
 Done   Retry / Alert
```

This could allow detection of:

- Failed commands
- Offline boosters
- Unexpected mode changes
- Stuck fan states
- Communication failures

---

## Occupancy-Aware Balancing

Room occupancy could eventually become another input to the balancing strategy.

```text
Temperature Demand
        +
HVAC State
        +
Occupancy
        │
        ▼
Airflow Priority
```

This could reduce unnecessary balancing in unused rooms while prioritizing occupied bedrooms.

---

## Nighttime Comfort Profile

Sleeping periods may justify a dedicated control profile with:

- Tighter bedroom temperature tolerance
- More aggressive occupied-bedroom balancing
- Different booster noise limits
- Reduced balancing for unused areas
- Different central blower thresholds

---

## Outdoor Temperature Compensation

Future logic could use outdoor conditions to dynamically modify:

- Booster thresholds
- Maximum booster speed
- Central circulation threshold
- Expected equalization time

A 2°F room difference during mild weather may behave very differently from the same difference during extreme summer heat or winter cold.

---

## Adaptive Controller Tuning

The current thresholds were manually tuned using historical data.

A future version could record each balancing event:

```text
Starting ΔT
Booster speed
Central blower state
Outdoor temperature
HVAC state
Equalization time
Final ΔT
```

Over time, Home Assistant could estimate which airflow strategy produces the best equalization rate for each room.

---

## Equalization Performance Metrics

Future sensors could calculate objective metrics such as:

- Average bedroom ΔT
- Maximum daily ΔT
- Time above 1.5°F imbalance
- Time above 2.0°F imbalance
- Average equalization time
- Booster runtime per room
- Central blower balancing runtime
- Percentage of time within target tolerance

These metrics would make controller versions easier to compare quantitatively.

---

## Energy Optimization

A future controller could combine:

```text
Temperature imbalance
        +
Booster activity
        +
Central blower consumption
        +
Compressor activity
```

with the optimization objective:

> **Maintain acceptable room balance using the least additional energy.**

Possible strategies could include:

- Booster only
- Booster + central blower
- Wait for the next HVAC cycle
- Higher airflow for a shorter period
- Lower airflow for a longer period

---

# Long-Term Goal

The long-term objective is a controller capable of determining:

1. Which rooms are outside the desired thermal balance
2. Whether the HVAC is cooling, heating, or idle
3. Which rooms need additional airflow
4. What booster speed is required
5. Whether central blower assistance is useful
6. When circulation should stop
7. Whether the selected strategy actually reduced the imbalance
8. Whether another strategy could achieve the same comfort using less energy

Conceptually:

```text
Room Temperatures
        +
HVAC Operating State
        +
Outdoor Conditions
        +
Occupancy
        +
Historical Performance
        │
        ▼
   Home Assistant
        │
        ▼
Season-Aware Balancing Strategy
        │
   ┌────┼────┬──────────┐
   ▼    ▼    ▼          ▼
 Bed 1 Bed 2 Bed 3   Basement
   │    │    │          │
   └────┴────┼──────────┘
             │
             ▼
        Central Blower
             │
             ▼
        Measure Result
             │
             ▼
     Optimize Next Decision
```

The v1.1 three-bedroom controller is the current working stage toward that architecture.

---

# Disclaimer

This project documents a personal Home Assistant HVAC automation system.

HVAC equipment, duct design, blower capacity, static pressure, electrical systems, and building characteristics vary significantly between installations.

Register booster fans and changes to airflow distribution should be used carefully.

Avoid significantly restricting supply or return airflow.

Do not close large numbers of supply registers in an attempt to force air toward other rooms.

If system airflow, static pressure, or equipment limitations are uncertain, consult a qualified HVAC professional.

This repository is intended as a reference and experimentation project rather than a universal HVAC configuration.