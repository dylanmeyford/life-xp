"""Achievements / Badges system for Life XP."""

from __future__ import annotations

from datetime import datetime

from life_xp.database import fetch_all, fetch_one


# ── Achievement definitions ─────────────────────────────────────────
# key -> (title, description, icon, xp_reward, check_function_name)

ACHIEVEMENT_DEFS = [
    # Goal milestones
    ("first_goal",       "First Steps",        "Set your first goal",                              "\U0001F331", 50),
    ("five_goals",       "Ambitious",           "Have 5 active goals at once",                      "\U0001F3AF", 100),
    ("first_complete",   "Mission Complete",    "Complete your first goal",                         "\U00002705", 200),
    ("ten_complete",     "Unstoppable",         "Complete 10 goals",                                "\U0001F525", 500),

    # Streak milestones
    ("streak_3",         "Getting Started",     "Maintain a 3-day streak on any goal",              "\U0001F525", 50),
    ("streak_7",         "Week Warrior",        "Maintain a 7-day streak on any goal",              "\U00002728", 100),
    ("streak_14",        "Fortnight Force",     "Maintain a 14-day streak on any goal",             "\U0001F4AA", 200),
    ("streak_30",        "Monthly Master",      "Maintain a 30-day streak on any goal",             "\U0001F451", 500),
    ("streak_100",       "Centurion",           "Maintain a 100-day streak on any goal",            "\U0001F3C6", 1000),

    # XP milestones
    ("xp_1000",          "Thousandaire",        "Earn 1,000 total XP",                              "\U0001F4B0", 100),
    ("xp_10000",         "XP Hoarder",          "Earn 10,000 total XP",                             "\U0001F48E", 250),
    ("xp_100000",        "XP Titan",            "Earn 100,000 total XP",                            "\U0001F30B", 500),

    # Level milestones
    ("level_5",          "Apprentice Rising",   "Reach level 5",                                    "\U00002B50", 100),
    ("level_10",         "Double Digits",       "Reach level 10",                                   "\U0001F31F", 200),
    ("level_25",         "Quarter Century",     "Reach level 25",                                   "\U0001F320", 500),
    ("level_50",         "Legendary",           "Reach level 50",                                   "\U0001F3C5", 1000),

    # Sensor milestones
    ("first_sensor",     "Plugged In",          "Set up your first auto-tracking sensor",           "\U0001F4E1", 75),
    ("five_sensors",     "Fully Wired",         "Have 5 active sensors",                            "\U0001F916", 200),

    # Quest milestones
    ("first_quest",      "Adventurer",          "Complete your first daily quest",                  "\U00002694\uFE0F", 50),
    ("quest_streak_7",   "Quest Master",        "Complete daily quests 7 days in a row",            "\U0001F5E1\uFE0F", 200),
    ("quest_clean_sweep","Clean Sweep",         "Complete all daily quests in a single day",        "\U0001F9F9", 100),

    # Special
    ("night_owl",        "Night Owl",           "Check in after midnight",                          "\U0001F989", 50),
    ("early_bird",       "Early Bird",          "Check in before 6 AM",                             "\U0001F426", 50),
]


async def ensure_achievement_rows(db):
    """Ensure all achievement definitions exist in the DB."""
    for key, title, desc, icon, xp in ACHIEVEMENT_DEFS:
        existing = await fetch_one(db, "SELECT id FROM achievements WHERE key = ?", (key,))
        if not existing:
            await db.execute(
                "INSERT INTO achievements (key, title, description, icon, xp_reward) VALUES (?, ?, ?, ?, ?)",
                (key, title, desc, icon, xp),
            )
    await db.commit()


async def get_all_achievements(db) -> list[dict]:
    await ensure_achievement_rows(db)
    return await fetch_all(db, "SELECT * FROM achievements ORDER BY unlocked_at IS NULL, unlocked_at DESC")


async def unlock(db, key: str) -> dict | None:
    """Unlock an achievement. Returns the achievement if newly unlocked, None if already unlocked."""
    row = await fetch_one(db, "SELECT * FROM achievements WHERE key = ?", (key,))
    if not row:
        return None
    if row["unlocked_at"]:
        return None  # already unlocked

    now = datetime.now().isoformat()
    await db.execute(
        "UPDATE achievements SET unlocked_at = ? WHERE key = ?",
        (now, key),
    )
    await db.commit()
    return dict(await fetch_one(db, "SELECT * FROM achievements WHERE key = ?", (key,)))


async def check_and_unlock(db) -> list[dict]:
    """Check all achievement conditions and unlock any that are met.
    Returns list of newly unlocked achievements."""
    await ensure_achievement_rows(db)
    newly_unlocked = []

    # Goal counts
    active_goals = await fetch_one(db, "SELECT COUNT(*) as c FROM goals WHERE status = 'active'")
    completed_goals = await fetch_one(db, "SELECT COUNT(*) as c FROM goals WHERE status = 'completed'")
    total_goals = await fetch_one(db, "SELECT COUNT(*) as c FROM goals")

    if total_goals["c"] >= 1:
        r = await unlock(db, "first_goal")
        if r: newly_unlocked.append(r)
    if active_goals["c"] >= 5:
        r = await unlock(db, "five_goals")
        if r: newly_unlocked.append(r)
    if completed_goals["c"] >= 1:
        r = await unlock(db, "first_complete")
        if r: newly_unlocked.append(r)
    if completed_goals["c"] >= 10:
        r = await unlock(db, "ten_complete")
        if r: newly_unlocked.append(r)

    # Streak checks
    streaks = await fetch_all(db, "SELECT * FROM streaks")
    max_streak = max((s["current"] for s in streaks), default=0)
    for threshold, key in [(3, "streak_3"), (7, "streak_7"), (14, "streak_14"), (30, "streak_30"), (100, "streak_100")]:
        if max_streak >= threshold:
            r = await unlock(db, key)
            if r: newly_unlocked.append(r)

    # XP checks
    xp_row = await fetch_one(db, "SELECT COALESCE(SUM(amount), 0) as total FROM xp_ledger")
    total_xp = xp_row["total"]
    for threshold, key in [(1000, "xp_1000"), (10000, "xp_10000"), (100000, "xp_100000")]:
        if total_xp >= threshold:
            r = await unlock(db, key)
            if r: newly_unlocked.append(r)

    # Level checks
    from life_xp.xp import level_from_xp
    level = level_from_xp(total_xp)
    for threshold, key in [(5, "level_5"), (10, "level_10"), (25, "level_25"), (50, "level_50")]:
        if level >= threshold:
            r = await unlock(db, key)
            if r: newly_unlocked.append(r)

    # Sensor checks
    active_sensors = await fetch_one(
        db, "SELECT COUNT(*) as c FROM sensor_configs WHERE status = 'active'"
    )
    if active_sensors["c"] >= 1:
        r = await unlock(db, "first_sensor")
        if r: newly_unlocked.append(r)
    if active_sensors["c"] >= 5:
        r = await unlock(db, "five_sensors")
        if r: newly_unlocked.append(r)

    # Quest checks
    completed_quests = await fetch_one(
        db, "SELECT COUNT(*) as c FROM daily_quests WHERE status = 'completed'"
    )
    if completed_quests["c"] >= 1:
        r = await unlock(db, "first_quest")
        if r: newly_unlocked.append(r)

    # Time-based checks
    hour = datetime.now().hour
    if hour >= 0 and hour < 5:
        r = await unlock(db, "night_owl")
        if r: newly_unlocked.append(r)
    if hour >= 4 and hour < 6:
        r = await unlock(db, "early_bird")
        if r: newly_unlocked.append(r)

    # Award XP for newly unlocked achievements
    if newly_unlocked:
        from life_xp.xp import award_xp
        for ach in newly_unlocked:
            await award_xp(db, ach["xp_reward"], "achievement", ach["id"], f"Achievement: {ach['title']}")

    return newly_unlocked
