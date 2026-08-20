# HVAC Balancing v0.2 Installation

**Current release: v0.2.0-beta.9**

## Safety

> Only one physical HVAC balancing controller may have actuator authority at a time.

## Manual installation

Copy:

```text
custom_components/hvac_balancing
```

to:

```text
/config/custom_components/hvac_balancing
```

Restart Home Assistant and add **HVAC Balancing** under **Settings -> Devices & services**.

Choose **Production Active Control**, configure the thermostat, independent reference sensor, balancing zones and booster fans, then explicitly confirm physical actuation.

## Production mapping used by this project

| Function | Entity |
|---|---|
| Thermostat | `climate.kitchen` |
| Kitchen reference | `sensor.kitchen_temp_temperature` |
| Bed 1 | `sensor.bed_1_temp_temperature` / `fan.bed_1_booster` |
| Bed 2 | `sensor.bed_2_temp_temperature` / `fan.bed_2_booster` |
| Bed 3 | `sensor.bed_3_temp_temperature` / `fan.bed_3_booster` |
| Central Assist | Nest fan timer |

The validated beta.9 Production migration preserved the existing historical calculated sensor IDs.
