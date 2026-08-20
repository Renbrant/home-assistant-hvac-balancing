# HVAC Balancing v0.2 Production Monitoring

**Current Production release: v0.2.0-beta.9**

## Zone metrics

| Metric | Meaning |
|---|---|
| Temperature | Current bedroom temperature |
| Delta | Bedroom minus Kitchen reference |
| Base P | Proportional airflow demand |
| Adaptive I | Performance-driven correction |
| Reference Error | Error captured for the Adaptive episode |
| Improve F/10m | Improvement normalized to effective cooling exposure |
| Adaptive Action | Increase, hold, decrease, reset or observing state |
| Adaptive Window | Effective cooling exposure progress |
| PI Target | Final Base P + Adaptive I target |
| Command | Effective requested booster percentage |
| Physical Fan | Actual Home Assistant fan percentage |

## Improvement Rate

- Below 0.10 F / 10 cooling min: Adaptive I may increase.
- 0.10 to below 0.25: Adaptive I holds.
- 0.25 or higher: Adaptive I may decrease.

Cooling exposure advances only while valid temperatures exist and the HVAC is actually cooling.

## Production soak

Monitor complete cooling cycles, Adaptive decisions, fan command parity, Central Assist ownership/release, watchdog behavior and restart/reload behavior.
