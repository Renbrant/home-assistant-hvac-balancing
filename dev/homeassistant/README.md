# HVAC Balancing Development Environment

This directory contains development-only Home Assistant infrastructure for
HVAC Balancing v0.2.0.

It is intentionally separate from:

```text
custom_components/hvac_balancing
```

The `custom_components` directory is the distributable integration.

The contents of this `dev` directory are a laboratory and must not be
included in the normal HACS installation.

## Virtual HVAC Test Bench

The Test Bench simulates:

- Kitchen/reference temperature
- Bed 1 temperature
- Bed 2 temperature
- Bed 3 temperature
- Central cooling thermostat
- AC compressor
- Central blower
- Bed 1 booster
- Bed 2 booster
- Bed 3 booster
- sensor availability failures
- actuator availability failures
- repeatable test scenarios

## Repository files

```text
dev/homeassistant/
├── packages/
│   └── hvac_balancing_test_bench.yaml
├── dashboards/
│   └── hvac_balancing_test_bench.yaml
├── configuration_snippet.yaml.example
└── README.md
```

## Intended HA Dev deployment

Repository:

```text
dev/homeassistant/packages/hvac_balancing_test_bench.yaml
```

HA Dev:

```text
/config/packages/hvac_balancing_test_bench.yaml
```

Repository:

```text
dev/homeassistant/dashboards/hvac_balancing_test_bench.yaml
```

HA Dev:

```text
/config/hvac_balancing_test_bench.yaml
```

The keys shown in `configuration_snippet.yaml.example` must be merged into
the existing HA Dev `configuration.yaml`.

Do not overwrite the whole HA configuration file.

## Safety

This Test Bench contains no production entity IDs.

It must remain independent from the production house.

The virtual equipment intentionally uses normal Home Assistant domains:

```text
sensor.*
fan.*
switch.*
climate.*
```

This allows the v0.2 controller to use the same entity interfaces during
simulation that it will use later during shadow and production operation.
