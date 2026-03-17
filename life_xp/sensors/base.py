"""Base sensor class and sensor registry."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from life_xp.database import fetch_all, fetch_one, insert, update


class Sensor(ABC):
    """Base class for all sensors."""

    sensor_type: str = "base"

    def __init__(self, sensor_id: int, goal_id: int, config: dict):
        self.sensor_id = sensor_id
        self.goal_id = goal_id
        self.config = config

    @abstractmethod
    async def read(self) -> dict[str, Any]:
        """Take a reading. Must return {"value": ..., ...extra_data}."""
        ...

    async def poll(self, db) -> dict | None:
        """Poll the sensor and store the reading."""
        try:
            result = await self.read()
            value = str(result.get("value", ""))
            await insert(db, "sensor_readings", {
                "sensor_id": self.sensor_id,
                "value": value,
                "raw_data": json.dumps(result),
            })
            await update(db, "sensor_configs", self.sensor_id, {
                "last_run": datetime.now().isoformat(),
                "last_value": value,
            })
            return result
        except Exception as e:
            await update(db, "sensor_configs", self.sensor_id, {
                "last_run": datetime.now().isoformat(),
                "last_value": f"error: {e}",
            })
            return None


class SensorRegistry:
    """Registry of sensor implementations."""

    _types: dict[str, type[Sensor]] = {}

    @classmethod
    def register(cls, sensor_type: str):
        def wrapper(sensor_cls: type[Sensor]):
            cls._types[sensor_type] = sensor_cls
            sensor_cls.sensor_type = sensor_type
            return sensor_cls
        return wrapper

    @classmethod
    def create(cls, sensor_type: str, sensor_id: int, goal_id: int, config: dict) -> Sensor | None:
        sensor_cls = cls._types.get(sensor_type)
        if not sensor_cls:
            return None
        return sensor_cls(sensor_id, goal_id, config)

    @classmethod
    async def poll_all(cls, db) -> list[dict]:
        """Poll all active sensors."""
        sensors = await fetch_all(
            db, "SELECT * FROM sensor_configs WHERE status = 'active'"
        )
        results = []
        for s in sensors:
            config = json.loads(s["config"])
            sensor = cls.create(s["sensor_type"], s["id"], s["goal_id"], config)
            if sensor:
                result = await sensor.poll(db)
                if result:
                    results.append({"sensor_id": s["id"], "goal_id": s["goal_id"], **result})
        return results

    @classmethod
    async def poll_goal(cls, db, goal_id: int) -> list[dict]:
        """Poll all active sensors attached to a specific goal."""
        sensors = await fetch_all(
            db,
            "SELECT * FROM sensor_configs WHERE status = 'active' AND goal_id = ?",
            (goal_id,),
        )
        results = []
        for s in sensors:
            config = json.loads(s["config"])
            sensor = cls.create(s["sensor_type"], s["id"], s["goal_id"], config)
            if sensor:
                result = await sensor.poll(db)
                if result:
                    results.append({"sensor_id": s["id"], "goal_id": s["goal_id"], **result})
        return results
