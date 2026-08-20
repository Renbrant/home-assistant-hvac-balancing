# HVAC Balancing v0.2 Installation

**Current release: v0.2.10**

## Safety

> Only one physical HVAC balancing controller may have actuator authority at a time.

## Recommended installation: HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Renbrant&repository=home-assistant-hvac-balancing&category=integration)

### Add the custom repository

1. Open **HACS** in Home Assistant.
2. Open **Custom repositories**.
3. Add:

   `https://github.com/Renbrant/home-assistant-hvac-balancing`

4. Select **Integration** as the repository type.
5. Open **HVAC Balancing** in HACS.
6. Download the latest release.
7. Restart Home Assistant.

### Configure HVAC Balancing

After restarting Home Assistant:

1. Open **Settings -> Devices & services**.
2. Select **Add Integration**.
3. Search for **HVAC Balancing**.
4. Complete the configuration flow.

> Only one physical HVAC balancing controller may have actuator authority at a time.

## Manual installation (fallback)

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
