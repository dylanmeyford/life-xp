"""Streak tracking and XP multiplier engine."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from life_xp.database import fetch_all, fetch_one, insert


# ── Multiplier tiers ────────────────────────────────────────────────

MULTIPLIER_TIERS = [
    (100, 5.0),
    (30, 3.0),
    (14, 2.0),
    (7, 1.5),
    (3, 1.25),
    (0, 1.0),
]


def multiplier_for_streak(streak: int) -> float:
    for threshold, mult in MULTIPLIER_TIERS:
        if streak >= threshold:
            return mult
    return 1.0


# ── Streak operations ───────────────────────────────────────────────

async def get_streak(db, goal_id: int) -> dict:
    row = await fetch_one(
        db, "SELECT * FROM streaks WHERE goal_id = ?", (goal_id,)
    )
    if not row:
        return {"goal_id": goal_id, "current": 0, "longest": 0, "last_checkin": None, "multiplier": 1.0, "frozen_until": None}
    return {
        **row,
        "multiplier": multiplier_for_streak(row["current"]),
    }


async def get_all_streaks(db) -> list[dict]:
    rows = await fetch_all(db, "SELECT * FROM streaks ORDER BY current DESC")
    return [{**r, "multiplier": multiplier_for_streak(r["current"])} for r in rows]


async def checkin(db, goal_id: int) -> dict:
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    row = await fetch_one(
        db, "SELECT * FROM streaks WHERE goal_id = ?", (goal_id,)
    )

    if not row:
        # First check-in ever
        await db.execute(
            "INSERT INTO streaks (goal_id, current, longest, last_checkin) VALUES (?, 1, 1, ?)",
            (goal_id, today),
        )
        await db.commit()
        return await get_streak(db, goal_id)

    last = row["last_checkin"]

    if last == today:
        # Already checked in today
        return {**row, "multiplier": multiplier_for_streak(row["current"]), "already": True}

    frozen = row.get("frozen_until")
    is_frozen = frozen and frozen >= today

    if last == yesterday or is_frozen:
        # Continuing streak
        new_current = row["current"] + 1
        new_longest = max(row["longest"], new_current)
    else:
        # Streak broken
        new_current = 1
        new_longest = row["longest"]

    await db.execute(
        "UPDATE streaks SET current = ?, longest = ?, last_checkin = ?, frozen_until = NULL WHERE goal_id = ?",
        (new_current, new_longest, today, goal_id),
    )
    await db.commit()
    return await get_streak(db, goal_id)


async def freeze_streak(db, goal_id: int, days: int = 1) -> dict:
    freeze_until = (date.today() + timedelta(days=days)).isoformat()
    row = await fetch_one(
        db, "SELECT * FROM streaks WHERE goal_id = ?", (goal_id,)
    )
    if not row:
        return {"error": "No streak to freeze"}

    await db.execute(
        "UPDATE streaks SET frozen_until = ? WHERE goal_id = ?",
        (freeze_until, goal_id),
    )
    await db.commit()
    return await get_streak(db, goal_id)


async def decay_streaks(db) -> int:
    """Break streaks that haven't been checked in since yesterday and aren't frozen.
    Called by the scheduler."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    cur = await db.execute(
        """UPDATE streaks SET current = 0
           WHERE last_checkin < ? AND (frozen_until IS NULL OR frozen_until < ?)
           AND current > 0""",
        (yesterday, today),
    )
    await db.commit()
    return cur.rowcount


async def auto_checkin_from_reading(db, goal_id: int):
    """Auto check-in when a sensor reading comes in for today."""
    await checkin(db, goal_id)
