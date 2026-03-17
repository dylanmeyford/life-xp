"""Apple Health sensor via bundled Swift helper."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from life_xp.sensors.base import Sensor, SensorRegistry

SWIFT_HELPER = Path(__file__).parent.parent / "swift_helpers" / "health_reader"


@SensorRegistry.register("swift_health")
class HealthSensor(Sensor):
    """Reads health data via the bundled Swift HealthKit helper binary."""

    async def read(self) -> dict[str, Any]:
        metric = self.config.get("metric", "weight")
        unit = self.config.get("unit", "kg")

        if not SWIFT_HELPER.exists():
            return await self._fallback_shortcuts(metric)

        proc = subprocess.run(
            [str(SWIFT_HELPER), "--metric", metric, "--unit", unit],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            return await self._fallback_shortcuts(metric)

        return {"value": proc.stdout.strip(), "unit": unit, "source": "apple_health"}

    async def _fallback_shortcuts(self, metric: str) -> dict[str, Any]:
        """Fallback: try Apple Shortcuts CLI."""
        shortcut_name = f"Get {metric.replace('_', ' ').title()}"
        try:
            proc = subprocess.run(
                ["shortcuts", "run", shortcut_name],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return {"value": proc.stdout.strip(), "source": "apple_shortcuts"}
        except FileNotFoundError:
            pass

        return {
            "value": "unavailable",
            "source": "none",
            "message": f"Could not read {metric}. Please install the Swift helper or create an Apple Shortcut named '{shortcut_name}'.",
        }
