# Issue #23 — Central Assist threshold: Speed 10

**Decision date:** 2026-08-22  
**Tracking issue:** #23

## Production observation

The central HVAC blower was remaining active for longer periods than desired and its acoustic impact was noticeably greater than the local bedroom booster fans.

The previous v0.2 parity behavior requested Central Assist when any zone reached a final PI target of Speed 8 or higher.

## Decision

Raise the default Central Assist activation threshold from:

```text
Speed 8
```

to:

```text
Speed 10
```

The intended actuator hierarchy is now:

```text
Speed 0-8  -> local booster only
Speed 10   -> local booster at maximum demand + Central Assist
```

Central Assist is therefore reserved as a last-stage airflow reinforcement when at least one zone has reached maximum local booster demand.

## Deliberately unchanged behavior

This tuning step does not change:

- Base P thresholds or hysteresis
- Adaptive I behavior
- maximum booster speed
- five-minute Central Assist release grace
- Central Assist operation while thermostat mode remains `cool`, including `hvac_action: idle`
- Nest fan-timer adapter behavior

## Validation intent

After deployment, compare central blower runtime, acoustic comfort, and room convergence against the pre-change baseline. If excessive blower runtime remains, evaluate `idle`-period Central Assist behavior separately rather than combining that change with this threshold adjustment.
