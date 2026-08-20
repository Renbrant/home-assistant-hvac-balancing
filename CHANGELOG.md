# Changelog

## v0.2.10 - 2026-08-19

### Distribution

- Added HACS custom-repository support through root hacs.json metadata.
- Added Home Assistant local integration branding.
- Added 256x256 icon.png and 512x512 icon@2x.png brand assets.
- Added direct HACS installation documentation and My Home Assistant shortcut.

### Versioning

- Adopted the pre-1.0 version format without beta suffixes.
- Version identifiers are now synchronized between manifest.json and const.py.
- Added an automated test preventing manifest/runtime version drift.

### Validation

- 182 automated tests pass.
- 22 subtests pass.
- Python compilation passes.
- git diff --check passes.

### Controller

- No HVAC control-policy change from v0.2.0-beta.9.
- The validated Python Production controller, Adaptive I policy, booster actuation, Central Assist ownership, and historical entity compatibility remain unchanged.

### Production status

- v0.2.0-beta.9 remains the currently validated Production installation until the v0.2.10 HACS upgrade is exercised.
- v0.2.10 establishes the HACS distribution path for subsequent installation and upgrade validation.

## v0.2.0-beta.9 - 2026-08-19

### Added

- Python Home Assistant Custom Integration
- Production Config Flow
- cooling-exposure Adaptive I
- per-zone Adaptive deadlines
- physical actuator runtime
- Nest Central Assist ownership
- controller and watchdog diagnostics

### Compatibility

- preserved 15/15 historical calculated sensor IDs
- preserved Recorder history
- zero entity-ID suffix collisions

### Production

- 34/34 integration entities healthy
- booster actuation validated
- Nest Central Assist validated
- Recorder continuity verified 15/15

## v0.1.3

- Fixed unintended Adaptive I resets from climate attribute-only updates.
- Formalized the bedroom controller as cooling-only.

## v0.1.2

- Added PI-lite Adaptive I and second-stage Nest circulation.

## v0.1.1

- Added Bed 3.

## v0.1.0

- Initial Bed 1 and Bed 2 balancing controller.
