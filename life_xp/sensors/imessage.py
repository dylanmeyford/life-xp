"""iMessage sensor — tracks social interactions via macOS Messages database."""

import sqlite3
import platform
from datetime import date, datetime
from pathlib import Path

from life_xp.sensors.base import Sensor, SensorEvent, SensorRegistry


@SensorRegistry.register
class IMessageSensor(Sensor):
    """Detects iMessage activity for social goal tracking."""

    sensor_type = "imessage"

    def is_available(self) -> bool:
        if platform.system() != "Darwin":
            return False
        db_path = Path.home() / "Library" / "Messages" / "chat.db"
        return db_path.exists()

    def check(self, config: dict) -> list[SensorEvent]:
        min_messages = config.get("min_messages", 1)
        contact = config.get("contact")  # Optional: specific contact

        count = self._count_today_messages(contact)
        if count >= min_messages:
            msg = f"Sent {count} message(s) today"
            if contact:
                msg += f" to {contact}"
            return [SensorEvent(
                sensor_type="imessage",
                goal_id=config.get("goal_id"),
                habit_id=config.get("habit_id"),
                value=count,
                message=msg,
                raw_data={"count": count, "contact": contact},
            )]
        return []

    def _count_today_messages(self, contact: str | None = None) -> int:
        db_path = Path.home() / "Library" / "Messages" / "chat.db"
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            # macOS Messages uses Core Data timestamp (seconds since 2001-01-01)
            epoch_2001 = datetime(2001, 1, 1).timestamp()
            today_start = datetime.combine(date.today(), datetime.min.time()).timestamp()
            core_data_start = int((today_start - epoch_2001) * 1e9)

            query = "SELECT COUNT(*) FROM message WHERE is_from_me = 1 AND date > ?"
            params = [core_data_start]

            if contact:
                query = """
                    SELECT COUNT(*) FROM message m
                    JOIN chat_message_join cmj ON m.rowid = cmj.message_id
                    JOIN chat c ON cmj.chat_id = c.rowid
                    WHERE m.is_from_me = 1 AND m.date > ?
                    AND c.chat_identifier LIKE ?
                """
                params.append(f"%{contact}%")

            row = conn.execute(query, params).fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0
