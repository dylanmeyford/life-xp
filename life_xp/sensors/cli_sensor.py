"""CLI-based sensor — runs a shell command and captures output."""

from __future__ import annotations

import re
import subprocess
from typing import Any

from life_xp.sensors.base import Sensor, SensorRegistry


@SensorRegistry.register("cli")
class CLISensor(Sensor):
    """Runs a CLI command and optionally parses output with a regex."""

    async def read(self) -> dict[str, Any]:
        command = self.config.get("command", "echo 0")
        parse_regex = self.config.get("parse_regex", "")

        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
        )
        output = proc.stdout.strip()

        if proc.returncode != 0:
            return {"value": "error", "error": proc.stderr.strip()[:500], "source": "cli"}

        if parse_regex:
            match = re.search(parse_regex, output)
            if match:
                output = match.group(1) if match.groups() else match.group(0)

        return {"value": output[:500], "source": "cli"}
