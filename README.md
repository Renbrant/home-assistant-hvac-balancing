# Home Assistant HVAC Balancing

![Home Assistant HVAC Balancing](Photos/home-assistant-hvac-balancing.png)

A smart HVAC room-balancing system built with Home Assistant, temperature sensors, register booster fans and central HVAC blower control.

The goal of this project is to reduce temperature differences between rooms by dynamically controlling airflow instead of relying only on additional heating or cooling cycles.

---

## The Problem

Some rooms in the house consistently become warmer or cooler than others.

The central HVAC thermostat can maintain the temperature around its reference location, but it cannot directly compensate for differences caused by:

- Different duct lengths and airflow
- Room orientation and solar exposure
- Distance from the HVAC system
- Closed bedroom doors
- Different thermal loads
- Uneven supply airflow

In this installation, the bedrooms can drift significantly from the temperature measured near the main living area.

Instead of simply running the compressor longer, this project attempts to redistribute the conditioned air already available in the house.

---

## The Solution

Home Assistant continuously compares the temperature of each bedroom against a reference temperature measured in the Kitchen.

Based on that temperature difference, it controls smart register booster fans installed in the bedrooms.

For small differences, the system can use only the local booster.

For larger differences, Home Assistant also activates the central HVAC blower to increase airflow through the duct system.

The booster speed increases progressively as the temperature imbalance becomes larger.

The existing Nest thermostat continues to control normal heating and cooling.

Home Assistant acts as an additional **airflow-balancing layer**.

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
                               │
                    ┌──────────▼───────────┐
                    │    Home Assistant    │
                    │                      │
                    │  Temperature Delta   │
                    │  Hysteresis          │
                    │  Booster Control     │
                    │  Blower Control      │
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

## Register Booster Fans

Two smart HVAC register booster fans are installed in the bedrooms.

### Bed 1

[Amazon product page](https://amzn.to/45ns5bJ)

### Bed 2

[Amazon product page](https://amzn.to/45ns5bJ)

The boosters provide 10 selectable speed levels and are controlled individually by Home Assistant.

---

## Tuya Integration

The booster fans are Tuya-based Wi-Fi devices.

They work normally with the Tuya/Smart Life ecosystem, but during this implementation the **official Home Assistant Tuya integration did not expose the controls required to properly operate this particular booster fan model**.

For this reason, the project uses **Xtend Tuya** instead.

### What is Xtend Tuya?

Xtend Tuya is a custom Home Assistant integration designed to extend the official Tuya integration by exposing entities and capabilities that are missing from the standard integration.

Project repository:

[azerty9971/xtend_tuya on GitHub](https://github.com/azerty9971/xtend_tuya)

Xtend Tuya is not part of Home Assistant Core. It works as an extension around the Tuya integration and uses mechanisms that are not officially supported by the Home Assistant Core project.

In this installation, Xtend Tuya exposed the booster fan controls required by the balancing system.

---

## Xtend Tuya Limitations Observed

At the time this project was implemented in **August 2026**, Xtend Tuya was functional for controlling these boosters, but the integration was not completely reliable in terms of device-state feedback.

The most noticeable issue was that Home Assistant could sometimes display stale information for values such as:

- Current fan speed
- Fan percentage
- Operating/preset mode
- Some Tuya select entities

For example, the physical booster could be operating at Speed 1 while Home Assistant still reported a previously selected higher speed.

Likewise, the physical device and the Tuya application could show the correct operating mode while the corresponding Home Assistant entity still displayed the previous state.

This made the reported state unsuitable as the primary feedback signal for the controller.

However, **command delivery worked reliably for the functions required by this project**.

The following operations were successfully tested:

- Set booster operating mode to `FAN`
- Set fan percentage / booster speed
- Turn the booster ON
- Turn the booster OFF
- Configure a new speed while the booster was OFF
- Turn the booster ON directly at the previously configured speed

This was sufficient for the balancing controller.

---

## Control Strategy: Desired State Instead of Reported State

Because command execution was reliable but status feedback could be stale, the controller does not depend on the booster-reported speed to determine what should happen next.

Instead, Home Assistant calculates the desired state independently.

The controller determines:

1. The current room temperature difference
2. The required booster speed
3. Whether central HVAC circulation is required
4. The command that should be sent to each booster

The booster is then commanded directly to that desired state.

In other words:

**Home Assistant is the source of truth for the requested booster state.**

The reported Tuya state is treated mainly as diagnostic information.

This is also why the system maintains separate calculated entities for the desired booster speeds instead of relying on the percentage or mode reported by the physical fan.

---

## Booster Command Sequence

Testing showed that the boosters accept mode and speed commands even while they are turned off.

This made it possible to prepare the desired state before starting the fan.

The controller therefore uses the following sequence whenever a booster needs to run:

1. Set operating mode to `FAN`
2. Wait briefly for the Tuya device to process the command
3. Set the desired fan percentage
4. Wait briefly again
5. Turn the booster ON

The 10 physical booster speed levels map directly to Home Assistant fan percentages:

| Booster Level | Fan Percentage |
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

Preparing the speed before turning the fan on also prevents the booster from temporarily starting at a previously stored high speed.

If no airflow is required, Home Assistant simply sends an OFF command.

---

## Reliability Strategy

Since Tuya state feedback cannot currently be assumed to be completely reliable for these devices, the automation also periodically re-applies the desired state.

This provides a simple reconciliation mechanism in case of:

- A missed Tuya command
- A temporary cloud/integration communication problem
- A booster reboot
- Home Assistant restart
- Stale device state

The system therefore follows a **desired-state control model** rather than a strict closed-loop controller based on the state reported by the booster itself.

If Xtend Tuya state feedback becomes fully reliable in a future release, the architecture could be expanded to compare commanded and actual booster states and detect failed commands automatically.

---

## Temperature Reference

The Kitchen temperature sensor is used as the reference for room balancing.

Current temperature entities:

| Location | Home Assistant Entity |
|---|---|
| Kitchen | `sensor.kitchen_temp_temperature` |
| Bed 1 | `sensor.bed_1_temp_temperature` |
| Bed 2 | `sensor.bed_2_temp_temperature` |

Using similar dedicated temperature sensors in all three locations provides a better relative comparison than mixing different temperature measurement technologies.

---

## Temperature Delta

Home Assistant calculates a temperature delta for each bedroom.

The basic relationship is:

**Temperature Delta = Bedroom Temperature − Kitchen Temperature**

Therefore:

| Delta | Meaning |
|---:|---|
| Positive | Bedroom is warmer than Kitchen |
| 0°F | Temperatures are equal |
| Negative | Bedroom is cooler than Kitchen |

The controller interprets this delta differently depending on whether the HVAC system is heating or cooling.

During cooling, a bedroom warmer than the Kitchen creates demand.

During heating, a bedroom colder than the Kitchen creates demand.

---

## Current Booster Control Curve

Initial testing used a conservative control curve.

That approach worked, but temperature equalization was too slow and the boosters rarely operated above the lower speeds.

The controller was therefore tuned to use the booster capacity more aggressively.

| Relevant Temperature Difference | Booster Command |
|---:|---:|
| `< 1.5°F` | OFF |
| `1.5 – <2.0°F` | Speed 2 |
| `2.0 – <2.5°F` | Speed 4 |
| `2.5 – <3.0°F` | Speed 6 |
| `3.0 – <3.5°F` | Speed 8 |
| `≥ 3.5°F` | Speed 10 |

This curve allows the system to react substantially faster when a room begins moving away from the reference temperature.

---

## HVAC Active Minimum Speed

When the central HVAC system is actively heating or cooling, both bedroom boosters operate at a minimum of **Speed 1**.

This helps conditioned air reach the bedrooms whenever the HVAC is already operating.

Speed 1 is only a minimum.

If the temperature delta requests a higher speed, the calculated speed always takes priority.

For example:

| HVAC | Calculated Target | Booster Command |
|---|---:|---:|
| Idle | 0 | OFF |
| Cooling | 0 | Speed 1 |
| Heating | 0 | Speed 1 |
| Cooling | Speed 2 | Speed 2 |
| Cooling | Speed 6 | Speed 6 |
| Heating | Speed 10 | Speed 10 |

---

## Central Blower Assistance

The local booster alone is used for smaller temperature differences.

When the imbalance reaches approximately **2°F**, Home Assistant also requests central HVAC circulation.

With the current control curve, this corresponds to **Speed 4 or greater**.

The control strategy therefore becomes:

| Temperature Difference | Action |
|---:|---|
| `< 1.5°F` | No balancing request |
| `1.5°F` | Local booster |
| `2.0°F` | Booster + central blower |
| `2.5°F` | Higher booster speed + central blower |
| `3.0°F` | Higher booster speed + central blower |
| `3.5°F+` | Maximum booster speed + central blower |

This creates two levels of airflow correction:

**Local correction** using the register booster, followed by **whole-system circulation assistance** when the imbalance becomes larger.

---

## Hysteresis

Temperature sensors naturally fluctuate by small amounts.

Without protection, a value moving repeatedly around a threshold could cause commands such as:

`Speed 2 → Speed 4 → Speed 2 → Speed 4`

The controller therefore includes approximately **0.2°F of hysteresis**.

For example, Speed 4 may start when the temperature difference reaches 2.0°F, but it does not immediately fall back to Speed 2 when the temperature drops slightly below 2.0°F.

The temperature must fall farther before the lower speed is selected.

This significantly reduces unnecessary switching and command traffic.

---

## Post-Circulation

When neither bedroom requires central blower assistance anymore, the central fan is not immediately stopped.

The controller maintains circulation for an additional **5 minutes**.

This allows conditioned air already present in the duct system and throughout the house to continue redistributing before circulation stops.

If new demand appears during those five minutes, the pending shutdown is cancelled.

---

## HVAC Integration

The existing Nest thermostat remains responsible for normal HVAC operation.

Home Assistant monitors both the selected HVAC mode and the current `hvac_action`.

The system recognizes actual operating states such as:

- `cooling`
- `heating`
- `idle`

This is also how the controller knows when the HVAC-active minimum booster Speed 1 should be applied.

---

## Energy Considerations

Energy monitoring during development showed that the outdoor AC equipment and the indoor HVAC blower are on different monitored electrical circuits.

In this installation, observed power consumption was roughly in these ranges:

| Operating Component | Observed Power |
|---|---:|
| Central circulation blower | ~200 W |
| Indoor blower during active cooling | ~280 W at one observed point |
| Outdoor AC compressor/condenser | ~2 kW or more |

These measurements are specific to this installation and should not be considered universal HVAC specifications.

They did reveal an important characteristic of this system:

> Moving conditioned air through the house is significantly less energy-intensive than producing additional cooling with the compressor.

This makes intelligent circulation an interesting tool for improving comfort and potentially reducing unnecessary compressor runtime.

---

## Monitoring

A dedicated Home Assistant dashboard was created to observe the behavior of the balancing controller.

The dashboard tracks:

- Bedroom temperature deltas
- Calculated booster speeds
- HVAC operation
- Central blower activity
- Temperature equalization over time

ApexCharts is used for historical visualization.

This has been especially useful for tuning the booster speed curve and determining whether changes actually improve equalization time.

---

## Home Assistant Configuration

The actual YAML configuration is intentionally kept outside this README to keep the project documentation readable.

| File | Purpose |
|---|---|
| [`HomeAssistant/templates.yaml`](HomeAssistant/templates.yaml) | Temperature delta and booster target calculations |
| [`HomeAssistant/automation.yaml`](HomeAssistant/automation.yaml) | Booster and central blower control |
| [`HomeAssistant/dashboard.yaml`](HomeAssistant/dashboard.yaml) | Monitoring dashboard |
| [`HomeAssistant/README.md`](HomeAssistant/README.md) | Installation and configuration notes |

---

## Repository Structure

```text
home-assistant-hvac-balancing/
│
├── README.md
│
├── Photos/
│   └── home-assistant-hvac-balancing.png
│
└── HomeAssistant/
    ├── README.md
    ├── templates.yaml
    ├── automation.yaml
    └── dashboard.yaml
```

---

## Current Status

The system is currently operational and controlling both bedroom boosters.

Current functionality includes:

- Bedroom-to-Kitchen temperature comparison
- Cooling and heating directional logic
- Dynamic 10-level booster control
- Minimum Speed 1 while HVAC is active
- Central HVAC blower assistance
- Hysteresis
- Five-minute post-circulation
- Home Assistant restart recovery
- Periodic command reconciliation
- Historical monitoring using ApexCharts
- Energy monitoring used to help tune the control strategy

The controller continues to be tuned based on real-world temperature and energy data.

---

## Future Development

Future improvements may include room-specific control curves, different heating and cooling profiles, occupancy-aware balancing, outdoor-temperature compensation, automatic tuning based on equalization time, and energy-aware optimization.

One particularly interesting future direction is measuring the relationship between:

**booster speed → airflow improvement → equalization time → central blower runtime → compressor runtime**

This could eventually allow the controller to automatically select the most efficient strategy for each room.

---

## Disclaimer

This project documents a personal Home Assistant HVAC automation system.

HVAC equipment, duct design, blower capacity, static pressure and building characteristics vary significantly between homes.

Register booster fans and changes to airflow distribution should be used carefully.

Do not excessively restrict supply or return airflow, and consult a qualified HVAC professional if system airflow or static pressure is uncertain.

This repository is intended as a reference and experimentation project rather than a universal HVAC configuration.