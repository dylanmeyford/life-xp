"""Git activity sensor — tracks commits and contributions."""

import subprocess
from datetime import date

from life_xp.sensors.base import Sensor, SensorEvent, SensorRegistry


@SensorRegistry.register
class GitSensor(Sensor):
    """Detects git commits made today across configured repositories."""

    sensor_type = "git"

    def is_available(self) -> bool:
        try:
            subprocess.run(["git", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def check(self, config: dict) -> list[SensorEvent]:
        repo_path = config.get("repo_path", ".")
        min_commits = config.get("min_commits", 1)

        count = self._count_today_commits(repo_path)
        if count >= min_commits:
            return [SensorEvent(
                sensor_type="git",
                goal_id=config.get("goal_id"),
                habit_id=config.get("habit_id"),
                value=count,
                message=f"Made {count} commit(s) today!",
                raw_data={"commits": count, "repo": repo_path},
            )]
        return []

    def _count_today_commits(self, repo_path: str) -> int:
        today = date.today().isoformat()
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "log", "--oneline", f"--since={today}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return len(result.stdout.strip().splitlines())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return 0
