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
    from life_xp.engine import update_goal_progress, check_habit, get_goal, complete_goal

    if event.goal_id and event.value is not None:
        goal = get_goal(event.goal_id)
        if goal and goal["status"] != "active":
            return

        result = update_goal_progress(event.goal_id, event.value)

        if result.get("completed"):
            from life_xp.notifications import notify
            notify(
                title="🎯 Goal Complete!",
                message=f"{event.message} — +{result['xp_awarded']} XP!",
            )
        elif goal and not goal.get("target_value"):
            _try_llm_completion(goal, event)

    if event.habit_id:
        check_habit(event.habit_id)

    conn = get_connection()
    conn.execute(
        "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
        (event.sensor_type, json.dumps(event.raw_data, default=str)),
    )
    conn.commit()
    conn.close()


def _try_llm_completion(goal: dict, event: SensorEvent):
    """Use LLM to evaluate whether a qualitative goal is complete based on sensor data."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system="You evaluate whether a goal has been completed based on sensor data. Reply with ONLY a JSON object: {\"completed\": true/false, \"reason\": \"brief explanation\"}",
            messages=[{
                "role": "user",
                "content": f'Goal: "{goal["title"]}"\nDescription: {goal.get("description", "none")}\n\nSensor detected: {event.message}\nRaw data summary: {json.dumps(event.raw_data, default=str)[:500]}\n\nHas this goal been completed?',
            }],
        )

        response = msg.content[0].text.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(response)

        if result.get("completed"):
            from life_xp.engine import complete_goal
            from life_xp.notifications import notify

            completion = complete_goal(goal["id"])
            log.info(f"LLM auto-completed goal '{goal['title']}': {result.get('reason')}")
            notify(
                title="🎯 Goal Complete!",
                message=f"{goal['title']} — +{completion['xp_awarded']} XP! ({result.get('reason', '')})",
            )
    except Exception as e:
        log.error(f"LLM goal evaluation failed: {e}")
