"""Dynamic loader for user-generated custom sensors."""

import json
import importlib.util
import logging
from pathlib import Path

from life_xp.sensors.base import Sensor, SensorRegistry
from life_xp.database import DATA_DIR

log = logging.getLogger(__name__)

CUSTOM_SENSORS_DIR = DATA_DIR / "custom-sensors"
MANIFEST_PATH = CUSTOM_SENSORS_DIR / "manifest.json"

_loaded_sensors: set[str] = set()


def load_custom_sensors():
    """Load all enabled custom sensors from ~/.life-xp/custom-sensors/.

    Safe to call multiple times — only loads each sensor once.
    """
    if not MANIFEST_PATH.exists():
        return

    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return

    for entry in manifest.get("sensors", []):
        filename = entry.get("filename", "")
        if not entry.get("enabled", True):
            continue
        if filename in _loaded_sensors:
            continue

        sensor_path = CUSTOM_SENSORS_DIR / filename
        if not sensor_path.exists():
            log.warning(f"Custom sensor file not found: {filename}")
            continue

        try:
            _load_sensor_module(sensor_path, entry)
            _loaded_sensors.add(filename)
            log.info(f"Loaded custom sensor: {filename}")
        except Exception as e:
            log.error(f"Failed to load custom sensor {filename}: {e}")


def _load_sensor_module(path: Path, manifest_entry: dict):
    """Dynamically load a sensor module and register its CustomSensor class."""
    module_name = f"life_xp_custom_sensor_{path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Look for CustomSensor class
    sensor_cls = getattr(module, "CustomSensor", None)
    if sensor_cls is None:
        raise ImportError(f"No CustomSensor class in {path}")

    if not issubclass(sensor_cls, Sensor):
        raise ImportError(f"CustomSensor in {path} does not subclass Sensor")

    SensorRegistry.register(sensor_cls)


def list_custom_sensors() -> list[dict]:
    """List all custom sensors with their status."""
    if not MANIFEST_PATH.exists():
        return []

    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    sensors = []
    for entry in manifest.get("sensors", []):
        entry["loaded"] = entry.get("filename", "") in _loaded_sensors
        entry["file_exists"] = (CUSTOM_SENSORS_DIR / entry.get("filename", "")).exists()
        sensors.append(entry)
    return sensors


def disable_custom_sensor(filename: str):
    """Disable a custom sensor by filename."""
    if not MANIFEST_PATH.exists():
        return

    manifest = json.loads(MANIFEST_PATH.read_text())
    for entry in manifest.get("sensors", []):
        if entry.get("filename") == filename:
            entry["enabled"] = False
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    _loaded_sensors.discard(filename)


def enable_custom_sensor(filename: str):
    """Enable a custom sensor by filename."""
    if not MANIFEST_PATH.exists():
        return

    manifest = json.loads(MANIFEST_PATH.read_text())
    for entry in manifest.get("sensors", []):
        if entry.get("filename") == filename:
            entry["enabled"] = True
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
