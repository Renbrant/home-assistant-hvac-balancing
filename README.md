# Home Assistant HVAC Balancing

![Home Assistant HVAC Balancing](Photos/home-assistant-hvac-balancing.png)

A smart HVAC room-balancing system built with **Home Assistant**, independent temperature sensors, smart register booster fans, and central HVAC blower control.

The goal of this project is to reduce temperature differences between rooms by intelligently redistributing conditioned air instead of relying only on additional heating or cooling cycles.

> **Current implementation:** Summer / Cooling Balancing  
> The system has been field-tested and tuned primarily to reduce overheating in the upstairs bedrooms during air-conditioning operation.

---

## The Problem

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

The objective of this project is therefore to improve **air distribution** before asking the HVAC system to produce additional cooling.

---

## The Solution

Home Assistant continuously compares the temperature of each controlled bedroom against a reference temperature measured in the Kitchen.

Based on that temperature difference, the system dynamically controls smart register booster fans installed in the bedroom supply vents.

For smaller temperature differences, only the local booster is used.

For larger differences, Home Assistant can also request operation of the central HVAC blower to increase airflow through the complete duct system.

The booster speed increases progressively as the temperature imbalance becomes larger.

The Nest thermostat continues to control normal heating and cooling.

Home Assistant operates as an additional:

> **Airflow-balancing control layer**

The objective is to improve temperature distribution using airflow whenever possible, potentially reducing the need for additional HVAC cooling cycles.

---

## System Overview

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
                    └───────┬──────┬───────┘
                            │      │
               ┌────────────┘      └────────────┐
               │                                │
        ┌──────▼──────┐                  ┌──────▼──────┐
        │    Bed 1    │                  │    Bed 2    │
        │             │                  │             │
        │ Temp Sensor │                  │ Temp Sensor │
        │ Booster Fan │                  │ Booster Fan │
        └─────────────┘                  └─────────────┘

                    Temperature Reference
                              │
                       ┌──────▼──────┐
                       │   Kitchen   │
                       │ Temp Sensor │
                       └─────────────┘
```

---

# Hardware

## Register Booster Fans

Two smart HVAC register booster fans are currently installed.

The same model is used in:

- Bed 1
- Bed 2

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

The temperature measurements used by the balancing controller come from dedicated **Zigbee 3.0 temperature and humidity sensors**.

**Sensor used in this project:**  
[Zigbee 3.0 Temperature & Humidity Sensor — Amazon](https://amzn.to/4czY3p1)

The same sensor model is currently installed in:

- Kitchen
- Bed 1
- Bed 2

Using the same sensor model in all three locations is intentional.

The controller is primarily interested in the **temperature difference between rooms**, so using consistent measurement hardware improves the quality of the relative temperature comparison.

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

The relatively high temperature accuracy and fast refresh interval are useful for this application because the balancing controller begins reacting to differences as small as approximately **1.5°F** between rooms.

### Home Assistant Entities

| Location | Function | Entity |
|---|---|---|
| Kitchen | Main temperature reference | `sensor.kitchen_temp_temperature` |
| Bed 1 | Upstairs controlled room | `sensor.bed_1_temp_temperature` |
| Bed 2 | Upstairs controlled room | `sensor.bed_2_temp_temperature` |

For example:

```text
Kitchen = 72.0°F
Bed 1   = 73.6°F

Temperature Delta = +1.6°F
```

That difference is already sufficient to generate a balancing request under the current summer control strategy.

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

The screenshot above shows the entities exposed in Home Assistant for the booster fan through Xtend Tuya.

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

For example, the physical booster could be operating at Speed 1 while Home Assistant still displayed a previously selected higher speed.

The physical booster and Tuya application could show the correct state while Home Assistant continued showing an older value.

However, **command delivery worked reliably for the operations required by this project**.

The following commands were successfully tested:

- Set booster operating mode to `FAN`
- Set fan percentage
- Turn booster ON
- Turn booster OFF
- Configure a new speed while the fan is OFF
- Start directly at the previously configured speed

This was sufficient to implement the balancing controller.

---

## Desired-State Control

Because commands were reliable while device feedback could remain stale, the controller does not depend on the reported fan state to decide what should happen next.

Instead:

> **Home Assistant is the source of truth for the requested booster state.**

Home Assistant independently calculates:

1. Current room temperature imbalance
2. Required booster speed
3. Whether central circulation is required
4. Which commands must be sent to each booster

The reported Tuya state is treated primarily as diagnostic information.

This is why the system maintains separate calculated target-speed sensors instead of using the speed reported by the physical device as the control input.

---

## Booster Command Sequence

Testing showed that the boosters accept operating-mode and speed commands while powered OFF.

The controller takes advantage of that behavior.

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

This prevents the booster from briefly starting at a previously stored higher speed.

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

When no airflow is required, Home Assistant sends an OFF command.

---

# Temperature Sensing

## Temperature Reference

The dedicated Kitchen Zigbee temperature sensor is used as the main reference for balancing.

The controller compares each bedroom against this sensor rather than using the Nest thermostat's internal temperature as the primary room-balancing measurement.

This keeps the Kitchen, Bed 1, and Bed 2 comparisons based on the same sensor model and measurement technology.

---

## Temperature Delta

Home Assistant calculates a raw temperature delta for each bedroom:

**Bedroom Temperature − Kitchen Temperature**

Therefore:

| Raw Delta | Meaning |
|---:|---|
| Positive | Bedroom is warmer than Kitchen |
| 0°F | Temperatures are equal |
| Negative | Bedroom is cooler than Kitchen |

Template entities:

```text
sensor.bed_1_temperature_delta
sensor.bed_2_temperature_delta
```

During summer cooling, a positive bedroom delta indicates that the bedroom is warmer than the Kitchen and therefore may require additional airflow.

---

## Heating Direction

The underlying template architecture already contains directional logic for heating.

During heating, a colder bedroom can generate balancing demand by reversing the interpretation of the temperature difference.

However:

> **The heating strategy has not yet been field-tested or seasonally tuned.**

The current production behavior documented in this repository is based primarily on summer cooling operation.

Winter balancing is planned as the next major project phase.

---

# Current Summer Control Strategy

## Booster Speed Curve

The first version of the controller used a relatively conservative booster-speed curve.

Real-world testing showed that room equalization was too slow and that the booster fans rarely used their available airflow capacity.

The control curve was therefore made more aggressive.

The current summer curve is:

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

## HVAC-Active Minimum Speed

When the HVAC is actively cooling, both upstairs boosters operate at a minimum of:

> **Speed 1**

This improves airflow to the bedrooms whenever conditioned air is already being produced.

The Speed 1 rule is only a minimum.

A higher calculated target always takes priority.

| HVAC State | Calculated Target | Effective Booster Command |
|---|---:|---:|
| Idle | 0 | OFF |
| Cooling | 0 | Speed 1 |
| Cooling | Speed 2 | Speed 2 |
| Cooling | Speed 4 | Speed 4 |
| Cooling | Speed 8 | Speed 8 |
| Cooling | Speed 10 | Speed 10 |

Conceptually:

```text
Effective Target =
max(Calculated Target, HVAC Minimum)
```

where the HVAC minimum is Speed 1 while active cooling is occurring.

---

## Central Blower Assistance

Small temperature differences are handled locally by the booster fan.

When the calculated booster target reaches:

> **Speed 4 or greater**

Home Assistant also requests central HVAC blower circulation.

With the current curve, this corresponds to approximately:

> **2.0°F of directional temperature imbalance**

The strategy is therefore:

| Temperature Difference | Action |
|---:|---|
| `< 1.5°F` | No balancing demand |
| `1.5°F` | Local booster |
| `2.0°F` | Booster + central blower |
| `2.5°F` | Higher booster speed + central blower |
| `3.0°F` | Higher booster speed + central blower |
| `3.5°F+` | Maximum booster speed + central blower |

This creates two levels of correction:

**Local airflow correction**

followed by:

**Local booster + whole-system circulation**

when a larger imbalance exists.

---

## Hysteresis

Temperature sensors naturally fluctuate.

Without hysteresis, a temperature repeatedly crossing a threshold could generate rapid commands such as:

```text
Speed 2
Speed 4
Speed 2
Speed 4
Speed 2
```

The controller therefore uses approximately:

> **0.2°F hysteresis**

For example:

```text
Speed 4 starts around 2.0°F
```

but it does not immediately return to Speed 2 when the temperature drops slightly below 2.0°F.

The difference must fall to approximately:

```text
1.8°F
```

before the controller reduces the level.

Equivalent hysteresis is used throughout the speed curve.

---

## Five-Minute Post-Circulation

When neither bedroom requires central blower assistance anymore, circulation is not stopped immediately.

The controller waits:

> **5 minutes**

and then checks the current demand again.

Conceptually:

```text
Both bedrooms below central blower threshold
                    │
                    ▼
               Wait 5 minutes
                    │
                    ▼
              Re-check demand
                    │
            ┌───────┴───────┐
            │               │
       Demand returned   Still below
            │               │
            ▼               ▼
       Keep blower      Stop independent
        running         Nest circulation
```

This allows conditioned air already present in the duct system to continue redistributing through the house.

The automation uses:

```text
mode: restart
```

so that new demand appearing during the five-minute delay automatically cancels the pending shutdown.

---

## Automatic Recovery and Reconciliation

The controller reacts immediately when:

- Bed 1 calculated target changes
- Bed 2 calculated target changes
- HVAC `hvac_action` changes

It also runs:

- When Home Assistant starts
- Once per hour as a reconciliation cycle

The hourly reconciliation periodically re-applies the desired state.

This helps recover from situations such as:

- Missed Tuya command
- Temporary integration failure
- Booster reboot
- Home Assistant restart
- Nest fan timer refresh requirement
- Stale device feedback

This is another reason the system follows a desired-state control architecture.

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

They did demonstrate an important principle for this project:

> Moving already-conditioned air around the house requires substantially less power than producing additional cooling with the compressor.

This makes intelligent air redistribution an interesting strategy for improving comfort.

---

# Monitoring

A dedicated Home Assistant dashboard was created for observing and tuning the balancing controller.

The dashboard monitors:

- HVAC operating state
- Kitchen temperature
- Bedroom temperatures
- Temperature deltas
- Calculated booster targets
- Booster activity
- Central blower activity
- Xtend Tuya raw feedback
- 24-hour and 48-hour historical behavior

ApexCharts is used for historical visualization.

---

# Real-World System Behavior

The following screenshots show the system operating in the actual Home Assistant installation.

Together, they show three different views of the same controller:

1. What the system is doing now
2. Why the controller selected a particular speed
3. Whether the strategy is improving temperature balance over time

---

## Live System Status

![HVAC Smart Booster - Live Status](Photos/HVAC%20Smart%20Booster%20-%20Live%20Status.png)

The **HVAC Smart Booster - Live Status** card provides a real-time overview of the system.

It displays:

- Nest HVAC state
- `hvac_action`
- Nest blower state
- Kitchen temperature
- Bed 1 temperature
- Bed 1 ΔT
- Bed 1 calculated target
- Bed 1 booster state
- Bed 2 temperature
- Bed 2 ΔT
- Bed 2 calculated target
- Bed 2 booster state

The **Commanded Speed** displayed by the template sensor represents the temperature-based target.

The automation may still impose the HVAC-active minimum Speed 1.

Therefore, a calculated target of:

```text
0
```

can coexist with a physical booster operating at:

```text
Speed 1
```

during active HVAC operation.

That behavior is intentional.

---

## Booster Controller

![Booster Controller](Photos/Booster%20Controller.png)

The **Booster Controller** graph shows the relationship between temperature imbalance and calculated booster speed.

The graph uses two Y axes.

**Left axis**

```text
Booster Speed
0 → 10
```

**Right axis**

```text
Temperature Delta
-5°F → +5°F
```

Bed 1 is represented in yellow.

Bed 2 is represented in orange.

The temperature-delta lines are continuous, while booster commands appear as steps because the controller selects discrete speed levels.

This graph makes it easy to see:

- Speed increases as temperature imbalance increases
- Speed reductions occur only after hysteresis thresholds are crossed
- Both bedrooms are independently controlled

### Visual Separation of Equal Speeds

Both bedrooms can frequently require the same booster speed.

If both series were plotted at exactly the same Y coordinate, one line would completely hide the other.

For visualization only, a small offset is applied:

```text
Bed 1 → -0.12
Bed 2 → +0.12
```

For example:

```text
Actual Bed 1 target = 4
Actual Bed 2 target = 4

Displayed Bed 1 position ≈ 3.88
Displayed Bed 2 position ≈ 4.12
```

The actual controller values remain Speed 4.

The offset affects only the graph.

The white horizontal reference line represents:

```text
ΔT = 0°F
```

where bedroom and Kitchen temperature are equal.

---

## Temperature Balance

![Temperature Balance](Photos/Temperature%20Balance.png)

The **Temperature Balance** graph shows the longer-term thermal behavior of the house.

It displays approximately 48 hours of data for:

- Kitchen
- Bed 1
- Bed 2
- Bed 1 ΔT
- Bed 2 ΔT

The temperature data is averaged into 10-minute intervals to make longer-term trends easier to interpret.

The most important objective is not merely absolute room temperature.

The goal is to observe whether the bedroom temperatures follow the Kitchen reference more closely over time.

A successful balancing strategy should produce:

> **Smaller temperature differences and shorter periods of significant imbalance.**

A temperature delta near:

```text
0°F
```

means that the room is closely balanced with the Kitchen.

The graph is also useful for comparing controller revisions.

For example, the current aggressive booster-speed curve can be compared against earlier conservative settings to determine whether temperature differences return toward zero faster.

---

## What the Three Views Show Together

**Live Status**

Shows what the controller is doing right now.

**Booster Controller**

Shows why a particular target speed was selected.

**Temperature Balance**

Shows whether those decisions are actually improving room equalization over time.

Together, these views allow controller tuning to be based on real measured behavior instead of theoretical thresholds alone.

---

# Home Assistant Configuration

The actual Home Assistant YAML configuration is intentionally stored outside this README.

This keeps the project overview readable while allowing the implementation to remain fully documented.

| File | Purpose |
|---|---|
| [`HomeAssistant/templates.yaml`](HomeAssistant/templates.yaml) | Temperature delta and booster target calculations |
| [`HomeAssistant/automation.yaml`](HomeAssistant/automation.yaml) | Booster and central blower control |
| [`HomeAssistant/dashboard.yaml`](HomeAssistant/dashboard.yaml) | Monitoring dashboard |
| [`HomeAssistant/README.md`](HomeAssistant/README.md) | Installation and implementation notes |

---

## Repository Structure

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

The current controller is operational and has been field-tested during **summer cooling conditions**.

This should be considered:

> **Version 1 — Summer / Cooling Balancing**

The primary thermal problem addressed by this version is:

```text
Upstairs bedrooms becoming warmer than the Kitchen
```

The current physical solution is:

```text
Bed 1 Booster
       +
Bed 2 Booster
       +
Central HVAC blower assistance when required
```

The Kitchen is used as the reference temperature.

Real-world testing has already resulted in several controller refinements, including:

- A more aggressive booster-speed curve
- 0.2°F hysteresis
- Minimum Speed 1 during active cooling
- Central circulation beginning at Speed 4
- Five-minute post-circulation
- Periodic state reconciliation
- Desired-state control because of unreliable Tuya feedback

---

## Current Implementation Checklist

### Summer / Cooling

- [x] Matching Zigbee 3.0 temperature sensors in Kitchen, Bed 1 and Bed 2
- [x] Kitchen reference temperature
- [x] Bed 1 temperature monitoring
- [x] Bed 2 temperature monitoring
- [x] Bedroom temperature-delta calculation
- [x] Cooling directional-error calculation
- [x] Dynamic booster speed control
- [x] Ten-level booster capability
- [x] Summer speed curve tuned from real-world data
- [x] Minimum Speed 1 while HVAC is actively cooling
- [x] Central blower assistance starting at Speed 4
- [x] 0.2°F hysteresis
- [x] Five-minute post-circulation
- [x] Home Assistant restart recovery
- [x] Hourly desired-state reconciliation
- [x] Xtend Tuya command validation
- [x] Xtend Tuya feedback diagnostics
- [x] ApexCharts historical monitoring
- [x] HVAC electrical monitoring
- [x] Real-world summer operation validated

### Winter / Heating

- [ ] Winter thermal behavior measured
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

Cooling and heating produce different thermal patterns in the house.

For that reason, the long-term objective is not simply to reuse the summer curve during winter.

Each operating mode should eventually have its own experimentally validated control strategy.

---

## Phase 2 — Winter / Heating Balancing

The winter thermal problem is expected to be almost the opposite of summer.

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
                 │                     │
                 └──────────┬──────────┘
                            │
                            ▼
                     Central Blower
```

---

## Basement Booster

One of the first winter experiments will be evaluating a register booster fan in the basement.

Possible future entity:

```text
fan.basement_booster
```

Possible target sensor:

```text
sensor.basement_booster_target_speed
```

The purpose would be to increase warm supply airflow when the basement becomes significantly colder than the Kitchen reference.

The final decision will be based on winter measurements rather than simply assuming that the summer strategy can be inverted.

---

## Basement Temperature Delta

A future heating controller may use:

```text
Kitchen Temperature - Basement Temperature
```

as the directional heating imbalance.

An initial experimental curve could begin with values similar to the summer controller:

| Heating Difference | Initial Experimental Target |
|---:|---:|
| `< 1.5°F` | OFF |
| `1.5 – <2.0°F` | Speed 2 |
| `2.0 – <2.5°F` | Speed 4 |
| `2.5 – <3.0°F` | Speed 6 |
| `3.0 – <3.5°F` | Speed 8 |
| `≥ 3.5°F` | Speed 10 |

These values are only an initial hypothesis.

The basement may require a completely different curve because of differences in:

- Room volume
- Duct length
- Heat loss
- Supply airflow
- Exterior exposure
- Natural thermal behavior

---

## Separate Cooling and Heating Profiles

The long-term controller should automatically maintain different seasonal behavior.

### Cooling Profile

Optimized for:

- Warm upstairs bedrooms
- Increased bedroom airflow
- Bedroom booster control
- Central circulation for larger upstairs imbalances

### Heating Profile

Optimized for:

- Cold basement conditions
- Increased basement airflow
- Possible basement booster control
- Different central circulation thresholds
- Different speed curves
- Different idle-HVAC behavior

The correct profile should be selected automatically according to HVAC operating mode.

---

## Heating While HVAC Is Idle

One important winter question is whether circulation remains useful when the furnace is not actively producing heat.

When:

```text
hvac_action = heating
```

warm conditioned air is available, so booster assistance has a clear purpose.

When:

```text
hvac_action = idle
```

running a booster or central blower may simply redistribute existing indoor air.

That could still improve temperature equalization, but the effect needs to be measured.

The winter controller may therefore require different behavior depending on whether heating is selected versus actually active.

---

## Independent Room Control Curves

The current bedrooms use the same basic control curve.

Future versions may use room-specific tuning.

Different rooms have different:

- Duct lengths
- Register sizes
- Room volumes
- Exterior exposure
- Window areas
- Solar loads
- Insulation
- Return-air paths
- Distances from the blower

For example:

```text
Bed 1 may respond well to Speed 4
```

while:

```text
Bed 2 may require Speed 6
```

to achieve a similar equalization rate.

The basement may require another completely different curve.

---

## Effective Target Sensors

The current template sensors expose the temperature-derived target.

The automation then applies additional operational rules such as the minimum Speed 1 during active HVAC operation.

Future entities could expose the final effective command directly:

```text
sensor.bed_1_booster_effective_target_speed
sensor.bed_2_booster_effective_target_speed
sensor.basement_booster_effective_target_speed
```

This would make the dashboard show the exact state the automation intends to command after all control rules have been applied.

---

## Command Verification

If future Xtend Tuya versions provide reliable device feedback, the controller could evolve from desired-state control toward command verification.

Conceptually:

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
 Done   Retry
          │
          ▼
        Alert
```

This could allow automatic detection of:

- Failed commands
- Offline boosters
- Unexpected mode changes
- Stuck fan states
- Communication failures

---

## Occupancy-Aware Balancing

Room occupancy could eventually become another input to the balancing strategy.

A room that is empty for several hours may not require the same aggressive correction as an occupied bedroom.

Future decisions could combine:

```text
Temperature demand
        +
HVAC state
        +
Occupancy
```

to determine airflow priority.

---

## Nighttime Comfort Profile

Sleeping periods may justify a dedicated control profile.

Possible nighttime behavior includes:

- Tighter bedroom temperature tolerance
- More aggressive occupied-bedroom balancing
- Different booster noise limits
- Reduced balancing for unused areas
- Different central blower thresholds

The objective would be to prioritize sleeping comfort without unnecessarily forcing every area of the house to exactly the same temperature.

---

## Outdoor Temperature Compensation

The required balancing response may depend on outdoor temperature.

For example, a 2°F room difference during mild weather may behave differently from the same 2°F difference during extreme summer heat.

Future logic could dynamically modify:

- Booster thresholds
- Maximum booster speed
- Central circulation threshold
- Expected equalization time

The same principle could later be applied to extreme winter temperatures.

---

## Adaptive Controller Tuning

The current thresholds were manually tuned using historical data.

A future version could automatically learn how effectively each airflow strategy changes room temperature.

For each balancing event, Home Assistant could record:

```text
Starting ΔT
Booster speed
Central blower state
Outdoor temperature
HVAC state
Equalization time
Final ΔT
```

Over time, the system could estimate relationships such as:

```text
Speed 4
→ average Bed 1 equalization rate
```

or:

```text
Speed 8 + Central Blower
→ average Bed 2 equalization rate
```

The controller could eventually select the lowest airflow level expected to correct the imbalance within an acceptable period.

---

## Equalization Performance Metrics

The project currently relies heavily on historical graph analysis.

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

A future controller could combine temperature and electrical data.

Available information could include:

```text
Temperature imbalance
        +
Booster activity
        +
Central blower consumption
        +
Compressor activity
```

The optimization objective could become:

> **Maintain acceptable room balance using the least additional energy.**

Possible strategies could include:

- Booster only
- Booster + central blower
- Wait for the next HVAC cycle
- Higher airflow for a shorter period
- Lower airflow for a longer period

---

## Seasonal Performance Comparison

Once winter operation is implemented, performance can be evaluated independently for each season.

### Cooling Season

Possible metrics:

- Upstairs ΔT
- Bedroom booster runtime
- Central circulation runtime
- AC compressor runtime
- Equalization time

### Heating Season

Possible metrics:

- Basement ΔT
- Basement booster runtime
- Furnace runtime
- Central circulation runtime
- Equalization time

This will make it possible to determine how well the same overall balancing architecture performs under very different seasonal conditions.

---

## Long-Term Goal

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
   ┌────┼─────────┐
   ▼    ▼         ▼
 Bed 1 Bed 2   Basement
   │    │         │
   └────┼─────────┘
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

The current summer controller is the first working stage toward that architecture.

---

# Disclaimer

This project documents a personal Home Assistant HVAC automation system.

HVAC equipment, duct design, blower capacity, static pressure, electrical systems, and building characteristics vary significantly between installations.

Register booster fans and changes to airflow distribution should be used carefully.

Avoid significantly restricting supply or return airflow.

Do not close large numbers of supply registers in an attempt to force air toward other rooms.

If system airflow, static pressure, or equipment limitations are uncertain, consult a qualified HVAC professional.

This repository is intended as a reference and experimentation project rather than a universal HVAC configuration.
