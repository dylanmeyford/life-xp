"""Apple Health step counter sensor (macOS only)."""

import subprocess
import platform
import json

from life_xp.sensors.base import Sensor, SensorEvent, SensorRegistry


@SensorRegistry.register
class StepsSensor(Sensor):
    """Reads step count from Apple Health via shortcuts/AppleScript."""

    sensor_type = "steps"

    def is_available(self) -> bool:
        return platform.system() == "Darwin"

    def check(self, config: dict) -> list[SensorEvent]:
        steps = self._get_steps()
        if steps is None:
            return []

        events = []
        goal_id = config.get("goal_id")
        target = config.get("target", 10000)

        if steps >= target:
            events.append(SensorEvent(
                sensor_type="steps",
                goal_id=goal_id,
                habit_id=config.get("habit_id"),
                value=steps,
                message=f"You hit {steps:,} steps today!",
                raw_data={"steps": steps, "target": target},
            ))

        return events

    def _get_steps(self) -> int | None:
        """Try to get today's step count from Apple Health via Shortcuts."""
        # Method 1: Via Shortcuts app (requires a shortcut named "Get Steps")
        try:
            result = subprocess.run(
                ["shortcuts", "run", "Get Steps"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        # Method 2: Check if there's a health export file
        # Users can export Apple Health data to ~/.life-xp/health/
        import os
        from pathlib import Path
        health_dir = Path.home() / ".life-xp" / "health"
        if health_dir.exists():
            today_file = health_dir / "steps.json"
            if today_file.exists():
                try:
                    data = json.loads(today_file.read_text())
                    return int(data.get("steps", 0))
                except (json.JSONDecodeError, ValueError):
                    pass

        return None
