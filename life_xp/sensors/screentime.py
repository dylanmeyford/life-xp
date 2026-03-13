"""Screen time sensor — tracks app usage via macOS AppleScript."""

import subprocess
import platform

from life_xp.sensors.base import Sensor, SensorEvent, SensorRegistry


@SensorRegistry.register
class ScreenTimeSensor(Sensor):
    """Detects focused app usage for productivity tracking."""

    sensor_type = "screentime"

    def is_available(self) -> bool:
        return platform.system() == "Darwin"

    def check(self, config: dict) -> list[SensorEvent]:
        target_app = config.get("app_name", "")
        min_minutes = config.get("min_minutes", 30)

        active_app = self._get_frontmost_app()
        if not active_app:
            return []

        # This is a simple "is the app currently open" check
        # A more sophisticated version would track cumulative time
        if target_app.lower() in active_app.lower():
            return [SensorEvent(
                sensor_type="screentime",
                goal_id=config.get("goal_id"),
                habit_id=config.get("habit_id"),
                value=1,
                message=f"Using {target_app}",
                raw_data={"app": active_app},
            )]

        return []

    def _get_frontmost_app(self) -> str | None:
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
