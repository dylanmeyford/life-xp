"""XP and leveling system."""

import math
from dataclasses import dataclass

from life_xp.database import get_connection

# XP curve: each level requires more XP than the last
# Level 1: 0 XP, Level 2: 100 XP, Level 10: ~3000 XP, Level 50: ~62,500 XP
BASE_XP = 100
EXPONENT = 1.5


@dataclass
class PlayerStats:
    total_xp: int
    level: int
    xp_in_level: int
    xp_for_next: int
    progress_pct: float
    title: str


TITLES = {
    1: "Novice",
    5: "Apprentice",
    10: "Journeyman",
    15: "Adept",
    20: "Expert",
    25: "Veteran",
    30: "Master",
    40: "Grandmaster",
    50: "Legend",
    60: "Mythic",
    75: "Transcendent",
    100: "Ascended",
}


def xp_for_level(level: int) -> int:
    """Total XP required to reach a given level."""
    if level <= 1:
        return 0
    return int(BASE_XP * ((level - 1) ** EXPONENT))


def level_from_xp(total_xp: int) -> int:
    """Calculate level from total XP."""
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def get_title(level: int) -> str:
    """Get the title for a given level."""
    title = "Novice"
    for threshold, t in sorted(TITLES.items()):
        if level >= threshold:
            title = t
    return title


def get_stats() -> PlayerStats:
    """Get current player stats."""
    conn = get_connection()
    row = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM xp_ledger").fetchone()
    total_xp = row["total"]
    conn.close()

    level = level_from_xp(total_xp)
    current_level_xp = xp_for_level(level)
    next_level_xp = xp_for_level(level + 1)
    xp_in_level = total_xp - current_level_xp
    xp_for_next = next_level_xp - current_level_xp
    progress_pct = (xp_in_level / xp_for_next * 100) if xp_for_next > 0 else 100

    return PlayerStats(
        total_xp=total_xp,
        level=level,
        xp_in_level=xp_in_level,
        xp_for_next=xp_for_next,
        progress_pct=progress_pct,
        title=get_title(level),
    )


def award_xp(amount: int, source_type: str, source_id: int | None = None, description: str = "") -> PlayerStats:
    """Award XP and return updated stats. Returns stats after the award."""
    old_stats = get_stats()

    conn = get_connection()
    conn.execute(
        "INSERT INTO xp_ledger (amount, source_type, source_id, description) VALUES (?, ?, ?, ?)",
        (amount, source_type, source_id, description),
    )
    conn.commit()
    conn.close()

    new_stats = get_stats()

    if new_stats.level > old_stats.level:
        from life_xp.notifications import notify
        notify(
            title="⬆️ LEVEL UP!",
            message=f"You reached Level {new_stats.level} — {new_stats.title}!",
        )

    return new_stats
