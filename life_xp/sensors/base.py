"""Base sensor framework for reactive goal tracking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import logging

from life_xp.database import get_connection

log = logging.getLogger(__name__)


@dataclass
class SensorEvent:
    sensor_type: str
    goal_id: int | None
    habit_id: int | None
    value: float | None
    message: str
    raw_data: dict


class Sensor(ABC):
    """Base class for all sensors. Sensors poll local data sources and emit events."""

    sensor_type: str = "base"

    @abstractmethod
    def check(self, config: dict) -> list[SensorEvent]:
        """Check the data source and return any events."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this sensor's data source is available on this system."""
        ...


class SensorRegistry:
    """Registry of all available sensors."""

    _sensors: dict[str, type[Sensor]] = {}

    @classmethod
    def register(cls, sensor_class: type[Sensor]):
        cls._sensors[sensor_class.sensor_type] = sensor_class
        return sensor_class

    @classmethod
    def get(cls, sensor_type: str) -> type[Sensor] | None:
        return cls._sensors.get(sensor_type)

    @classmethod
    def available(cls) -> list[str]:
        return [
            name for name, sensor_cls in cls._sensors.items()
            if sensor_cls().is_available()
        ]

    @classmethod
    def all(cls) -> dict[str, type[Sensor]]:
        return dict(cls._sensors)

    @classmethod
    def run_all(cls):
        """Run all configured sensors and process events."""
        conn = get_connection()
        configs = conn.execute(
            "SELECT * FROM sensor_configs WHERE enabled = 1"
        ).fetchall()
        conn.close()

        for config in configs:
            sensor_cls = cls.get(config["sensor_type"])
            if not sensor_cls:
                log.warning(f"Unknown sensor type: {config['sensor_type']}")
                continue

            sensor = sensor_cls()
            if not sensor.is_available():
                continue

            try:
                cfg = json.loads(config["config_json"])
                cfg["goal_id"] = config["goal_id"]
                cfg["habit_id"] = config["habit_id"]
                events = sensor.check(cfg)

                for event in events:
                    _process_event(event)

                # Update last_checked
                conn = get_connection()
                conn.execute(
                    "UPDATE sensor_configs SET last_checked = datetime('now') WHERE id = ?",
                    (config["id"],),
                )
                conn.commit()
                conn.close()

            except Exception as e:
                log.error(f"Sensor {config['sensor_type']} failed: {e}")


def _process_event(event: SensorEvent):
    """Process a sensor event — update goal progress or check habit."""
    from life_xp.engine import update_goal_progress, check_habit

    if event.goal_id and event.value is not None:
        result = update_goal_progress(event.goal_id, event.value)
        if result.get("completed"):
            from life_xp.notifications import notify
            notify(
                title="🎯 Goal Complete!",
                message=f"{event.message} — +{result['xp_awarded']} XP!",
            )

    if event.habit_id:
        check_habit(event.habit_id)

    # Log the event
    conn = get_connection()
    conn.execute(
        "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
        (event.sensor_type, json.dumps(event.raw_data, default=str)),
    )
    conn.commit()
    conn.close()
