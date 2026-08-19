"""Structural tests for the HVAC Balancing integration skeleton."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "hvac_balancing"


def load_manifest() -> dict:
    """Load the integration manifest."""

    with (INTEGRATION / "manifest.json").open(
        encoding="utf-8"
    ) as manifest_file:
        return json.load(manifest_file)


def test_required_integration_files_exist() -> None:
    """Verify the minimum Phase 1 integration files exist."""

    required_files = (
        "__init__.py",
        "config_flow.py",
        "configuration.py",
        "const.py",
        "manifest.json",
        "runtime.py",
        "observation.py",
        "sensor.py",
        "binary_sensor.py",
        "strings.json",
        "translations/en.json",
    )

    for relative_path in required_files:
        assert (INTEGRATION / relative_path).is_file(), relative_path


def test_manifest_identity() -> None:
    """Verify the permanent integration identity."""

    manifest = load_manifest()

    assert manifest["domain"] == "hvac_balancing"
    assert manifest["name"] == "HVAC Balancing"
    assert manifest["version"] == "0.2.0-beta.9"


def test_manifest_architecture() -> None:
    """Verify Phase 1 architectural decisions."""

    manifest = load_manifest()

    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["integration_type"] == "service"
    assert manifest["iot_class"] == "calculated"
    assert manifest["requirements"] == []


def test_manifest_distribution_metadata() -> None:
    """Verify metadata needed for future HACS distribution."""

    manifest = load_manifest()

    assert manifest["codeowners"] == ["@Renbrant"]
    assert manifest["documentation"]
    assert manifest["issue_tracker"]
