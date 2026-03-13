"""Finance sensor — monitors transactions from CSV exports or directories."""

import csv
import json
from datetime import date, datetime
from pathlib import Path

from life_xp.sensors.base import Sensor, SensorEvent, SensorRegistry


@SensorRegistry.register
class TransactionSensor(Sensor):
    """Watches for transactions matching keywords (e.g. grocery store visits)."""

    sensor_type = "transactions"

    def is_available(self) -> bool:
        # Available if the transactions directory exists
        tx_dir = Path.home() / ".life-xp" / "transactions"
        return tx_dir.exists()

    def check(self, config: dict) -> list[SensorEvent]:
        keywords = config.get("keywords", [])
        if not keywords:
            return []

        tx_dir = Path.home() / ".life-xp" / "transactions"
        if not tx_dir.exists():
            return []

        events = []
        today = date.today().isoformat()

        # Check CSV files for matching transactions
        for csv_file in tx_dir.glob("*.csv"):
            matches = self._search_csv(csv_file, keywords, today)
            for match in matches:
                events.append(SensorEvent(
                    sensor_type="transactions",
                    goal_id=config.get("goal_id"),
                    habit_id=config.get("habit_id"),
                    value=1,
                    message=f"Transaction detected: {match['description']}",
                    raw_data=match,
                ))

        # Check JSON transaction files
        for json_file in tx_dir.glob("*.json"):
            matches = self._search_json(json_file, keywords, today)
            for match in matches:
                events.append(SensorEvent(
                    sensor_type="transactions",
                    goal_id=config.get("goal_id"),
                    habit_id=config.get("habit_id"),
                    value=1,
                    message=f"Transaction detected: {match['description']}",
                    raw_data=match,
                ))

        return events

    def _search_csv(self, path: Path, keywords: list[str], today: str) -> list[dict]:
        matches = []
        try:
            with open(path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    desc = row.get("description", row.get("Description", "")).lower()
                    tx_date = row.get("date", row.get("Date", ""))
                    if tx_date[:10] == today:
                        for kw in keywords:
                            if kw.lower() in desc:
                                matches.append({"description": desc, "date": tx_date, "keyword": kw})
                                break
        except Exception:
            pass
        return matches

    def _search_json(self, path: Path, keywords: list[str], today: str) -> list[dict]:
        matches = []
        try:
            data = json.loads(path.read_text())
            transactions = data if isinstance(data, list) else data.get("transactions", [])
            for tx in transactions:
                desc = tx.get("description", "").lower()
                tx_date = tx.get("date", "")
                if tx_date[:10] == today:
                    for kw in keywords:
                        if kw.lower() in desc:
                            matches.append({"description": desc, "date": tx_date, "keyword": kw})
                            break
        except Exception:
            pass
        return matches
