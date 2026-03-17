"""XP engine — leveling, rewards, and progression."""

from __future__ import annotations

import math
from dataclasses import dataclass

from life_xp.database import fetch_all, fetch_one, insert

# ── Level curve ──────────────────────────────────────────────────────

BASE_XP = 100
EXPONENT = 1.5

TITLES = [
    (1, "Novice"),
    (5, "Apprentice"),
    (10, "Journeyman"),
    (15, "Adept"),
    (20, "Expert"),
    (30, "Master"),
    (40, "Grandmaster"),
    (50, "Legend"),
    (75, "Mythic"),
    (100, "Ascended"),
]


def xp_for_level(level: int) -> int:
    """Total XP required to reach a given level."""
    return int(BASE_XP * (level ** EXPONENT))


def level_from_xp(total_xp: int) -> int:
    """Current level for a given total XP."""
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def title_for_level(level: int) -> str:
    title = TITLES[0][1]
    for threshold, name in TITLES:
        if level >= threshold:
            title = name
    return title


@dataclass
class PlayerStats:
    total_xp: int
    level: int
    title: str
    xp_current_level: int   # XP earned within current level
    xp_next_level: int      # XP needed for next level
    progress: float         # 0.0 – 1.0 progress to next level


async def get_player_stats(db) -> PlayerStats:
    """Calculate current player stats from XP ledger."""
    row = await fetch_one(db, "SELECT COALESCE(SUM(amount), 0) as total FROM xp_ledger")
    total_xp = row["total"]
    level = level_from_xp(total_xp)
    title = title_for_level(level)
    xp_this = xp_for_level(level)
    xp_next = xp_for_level(level + 1)
    xp_in_level = total_xp - xp_this
    xp_needed = xp_next - xp_this
    progress = xp_in_level / xp_needed if xp_needed > 0 else 1.0

    return PlayerStats(
        total_xp=total_xp,
        level=level,
        title=title,
        xp_current_level=xp_in_level,
        xp_next_level=xp_needed,
        progress=min(1.0, max(0.0, progress)),
    )


async def award_xp(db, amount: int, source_type: str, source_id: int | None = None, reason: str = "") -> PlayerStats:
    """Award XP and return updated stats."""
    await insert(db, "xp_ledger", {
        "amount": amount,
        "source_type": source_type,
        "source_id": source_id,
        "reason": reason,
    })
    return await get_player_stats(db)


async def get_xp_history(db, limit: int = 50) -> list[dict]:
    return await fetch_all(
        db,
        "SELECT * FROM xp_ledger ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
