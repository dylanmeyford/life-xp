"""Core engine for managing goals, habits, quests, and rewards."""

from datetime import datetime, date, timedelta

from life_xp.database import get_connection
from life_xp.xp import award_xp, get_stats


# ── Goals ──────────────────────────────────────────────────────────────

def create_goal(
    title: str,
    category: str = "Productivity",
    description: str = "",
    xp_reward: int = 100,
    target_value: float | None = None,
    unit: str | None = None,
    parent_id: int | None = None,
    due_date: str | None = None,
) -> int:
    conn = get_connection()
    cat = conn.execute("SELECT id FROM categories WHERE name = ?", (category,)).fetchone()
    cat_id = cat["id"] if cat else None
    cur = conn.execute(
        """INSERT INTO goals (title, description, category_id, parent_id, xp_reward,
           target_value, unit, due_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, cat_id, parent_id, xp_reward, target_value, unit, due_date),
    )
    conn.commit()
    goal_id = cur.lastrowid
    conn.close()
    return goal_id


def update_goal_progress(goal_id: int, value: float) -> dict:
    conn = get_connection()
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        conn.close()
        raise ValueError(f"Goal {goal_id} not found")

    conn.execute(
        "UPDATE goals SET current_value = ?, updated_at = datetime('now') WHERE id = ?",
        (value, goal_id),
    )

    result = {"goal_id": goal_id, "value": value, "completed": False, "xp_awarded": 0}

    if goal["target_value"] and value >= goal["target_value"] and goal["status"] == "active":
        conn.execute(
            "UPDATE goals SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (goal_id,),
        )
        conn.commit()
        conn.close()
        stats = award_xp(goal["xp_reward"], "goal", goal_id, f"Completed: {goal['title']}")
        result["completed"] = True
        result["xp_awarded"] = goal["xp_reward"]
        return result

    conn.commit()
    conn.close()
    return result


def complete_goal(goal_id: int) -> dict:
    conn = get_connection()
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        conn.close()
        raise ValueError(f"Goal {goal_id} not found")
    if goal["status"] != "active":
        conn.close()
        raise ValueError(f"Goal {goal_id} is already {goal['status']}")

    conn.execute(
        "UPDATE goals SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
        (goal_id,),
    )
    conn.commit()
    conn.close()

    stats = award_xp(goal["xp_reward"], "goal", goal_id, f"Completed: {goal['title']}")
    return {"goal_id": goal_id, "xp_awarded": goal["xp_reward"], "stats": stats}


def list_goals(status: str = "active", category: str | None = None) -> list[dict]:
    conn = get_connection()
    query = """
        SELECT g.*, c.name as category_name, c.icon as category_icon, c.color as category_color
        FROM goals g
        LEFT JOIN categories c ON g.category_id = c.id
        WHERE g.status = ?
    """
    params: list = [status]
    if category:
        query += " AND c.name = ?"
        params.append(category)
    query += " ORDER BY g.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_goal(goal_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT g.*, c.name as category_name, c.icon as category_icon
           FROM goals g LEFT JOIN categories c ON g.category_id = c.id
           WHERE g.id = ?""",
        (goal_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sub_goals(parent_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT g.*, c.name as category_name, c.icon as category_icon
           FROM goals g LEFT JOIN categories c ON g.category_id = c.id
           WHERE g.parent_id = ? ORDER BY g.created_at""",
        (parent_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Habits ─────────────────────────────────────────────────────────────

def create_habit(
    title: str,
    category: str = "Productivity",
    description: str = "",
    frequency: str = "daily",
    xp_per_check: int = 25,
) -> int:
    conn = get_connection()
    cat = conn.execute("SELECT id FROM categories WHERE name = ?", (category,)).fetchone()
    cat_id = cat["id"] if cat else None
    cur = conn.execute(
        "INSERT INTO habits (title, description, category_id, frequency, xp_per_check) VALUES (?, ?, ?, ?, ?)",
        (title, description, cat_id, frequency, xp_per_check),
    )
    conn.commit()
    habit_id = cur.lastrowid
    conn.close()
    return habit_id


def check_habit(habit_id: int, check_date: str | None = None) -> dict:
    if check_date is None:
        check_date = date.today().isoformat()

    conn = get_connection()
    habit = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
    if not habit:
        conn.close()
        raise ValueError(f"Habit {habit_id} not found")

    # Check if already checked today
    existing = conn.execute(
        "SELECT id FROM habit_checks WHERE habit_id = ? AND checked_date = ?",
        (habit_id, check_date),
    ).fetchone()
    if existing:
        conn.close()
        return {"already_checked": True, "xp_awarded": 0}

    conn.execute(
        "INSERT INTO habit_checks (habit_id, checked_date) VALUES (?, ?)",
        (habit_id, check_date),
    )
    conn.commit()

    # Calculate streak
    streak = get_habit_streak(habit_id, conn=conn)
    streak_multiplier = 1.0 + (habit["streak_bonus_multiplier"] * min(streak, 30))
    xp = int(habit["xp_per_check"] * streak_multiplier)

    conn.close()

    award_xp(xp, "habit", habit_id, f"Habit: {habit['title']} (streak: {streak})")

    # Streak milestone notifications
    if streak in (7, 14, 30, 50, 100, 365):
        from life_xp.notifications import notify
        bonus = streak * 10
        award_xp(bonus, "streak", habit_id, f"{streak}-day streak: {habit['title']}")
        notify(
            title=f"🔥 {streak}-Day Streak!",
            message=f"{habit['title']} — +{bonus} bonus XP!",
        )

    return {"streak": streak, "xp_awarded": xp, "already_checked": False}


def get_habit_streak(habit_id: int, conn=None) -> int:
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    rows = conn.execute(
        "SELECT checked_date FROM habit_checks WHERE habit_id = ? ORDER BY checked_date DESC",
        (habit_id,),
    ).fetchall()

    if close:
        conn.close()

    if not rows:
        return 0

    streak = 1
    dates = [date.fromisoformat(r["checked_date"]) for r in rows]
    for i in range(len(dates) - 1):
        if (dates[i] - dates[i + 1]).days == 1:
            streak += 1
        else:
            break
    return streak


def list_habits() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT h.*, c.name as category_name, c.icon as category_icon, c.color as category_color
           FROM habits h LEFT JOIN categories c ON h.category_id = c.id
           ORDER BY h.created_at"""
    ).fetchall()
    habits = []
    for r in rows:
        h = dict(r)
        h["streak"] = get_habit_streak(h["id"], conn=conn)
        # Check if done today
        today = date.today().isoformat()
        check = conn.execute(
            "SELECT id FROM habit_checks WHERE habit_id = ? AND checked_date = ?",
            (h["id"], today),
        ).fetchone()
        h["done_today"] = check is not None
        habits.append(h)
    conn.close()
    return habits


def get_habit_history(habit_id: int, days: int = 365) -> list[dict]:
    """Get check history for a habit over the last N days."""
    conn = get_connection()
    start = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT checked_date FROM habit_checks WHERE habit_id = ? AND checked_date >= ? ORDER BY checked_date",
        (habit_id, start),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Quests ─────────────────────────────────────────────────────────────

def create_quest(
    title: str,
    objectives: list[str],
    category: str = "Productivity",
    description: str = "",
    xp_reward: int = 500,
    deadline: str | None = None,
) -> int:
    conn = get_connection()
    cat = conn.execute("SELECT id FROM categories WHERE name = ?", (category,)).fetchone()
    cat_id = cat["id"] if cat else None
    cur = conn.execute(
        "INSERT INTO quests (title, description, category_id, xp_reward, deadline) VALUES (?, ?, ?, ?, ?)",
        (title, description, cat_id, xp_reward, deadline),
    )
    quest_id = cur.lastrowid
    for i, obj in enumerate(objectives):
        conn.execute(
            "INSERT INTO quest_objectives (quest_id, description, sort_order) VALUES (?, ?, ?)",
            (quest_id, obj, i),
        )
    conn.commit()
    conn.close()
    return quest_id


def complete_quest_objective(quest_id: int, objective_id: int) -> dict:
    conn = get_connection()
    conn.execute(
        "UPDATE quest_objectives SET completed = 1 WHERE id = ? AND quest_id = ?",
        (objective_id, quest_id),
    )
    conn.commit()

    # Check if all objectives complete
    remaining = conn.execute(
        "SELECT COUNT(*) as cnt FROM quest_objectives WHERE quest_id = ? AND completed = 0",
        (quest_id,),
    ).fetchone()["cnt"]

    result = {"objective_id": objective_id, "remaining": remaining, "quest_completed": False}

    if remaining == 0:
        quest = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
        conn.execute(
            "UPDATE quests SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (quest_id,),
        )
        conn.commit()
        conn.close()
        award_xp(quest["xp_reward"], "quest", quest_id, f"Quest complete: {quest['title']}")
        result["quest_completed"] = True
        result["xp_awarded"] = quest["xp_reward"]

        from life_xp.notifications import notify
        notify(title="🏆 Quest Complete!", message=f"{quest['title']} — +{quest['xp_reward']} XP!")
    else:
        conn.close()

    return result


def list_quests(status: str = "active") -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT q.*, c.name as category_name, c.icon as category_icon
           FROM quests q LEFT JOIN categories c ON q.category_id = c.id
           WHERE q.status = ? ORDER BY q.created_at DESC""",
        (status,),
    ).fetchall()
    quests = []
    for r in rows:
        q = dict(r)
        objs = conn.execute(
            "SELECT * FROM quest_objectives WHERE quest_id = ? ORDER BY sort_order",
            (q["id"],),
        ).fetchall()
        q["objectives"] = [dict(o) for o in objs]
        q["progress"] = sum(1 for o in objs if o["completed"]) / len(objs) if objs else 0
        quests.append(q)
    conn.close()
    return quests


# ── Rewards ────────────────────────────────────────────────────────────

def create_reward(title: str, xp_cost: int, description: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO rewards (title, description, xp_cost) VALUES (?, ?, ?)",
        (title, description, xp_cost),
    )
    conn.commit()
    reward_id = cur.lastrowid
    conn.close()
    return reward_id


def redeem_reward(reward_id: int) -> dict:
    conn = get_connection()
    reward = conn.execute("SELECT * FROM rewards WHERE id = ?", (reward_id,)).fetchone()
    if not reward:
        conn.close()
        raise ValueError(f"Reward {reward_id} not found")

    stats = get_stats()
    if stats.total_xp < reward["xp_cost"]:
        conn.close()
        raise ValueError(f"Not enough XP! Need {reward['xp_cost']}, have {stats.total_xp}")

    conn.execute(
        "UPDATE rewards SET redeemed_at = datetime('now') WHERE id = ?",
        (reward_id,),
    )
    conn.commit()
    conn.close()

    # Deduct XP
    award_xp(-reward["xp_cost"], "bonus", reward_id, f"Redeemed: {reward['title']}")

    from life_xp.notifications import notify
    notify(title="🎁 Reward Redeemed!", message=f"Enjoy: {reward['title']}")

    return {"reward": reward["title"], "xp_spent": reward["xp_cost"]}


def list_rewards() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM rewards WHERE redeemed_at IS NULL ORDER BY xp_cost"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Categories ─────────────────────────────────────────────────────────

def list_categories() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── XP History ─────────────────────────────────────────────────────────

def get_xp_history(days: int = 30) -> list[dict]:
    conn = get_connection()
    start = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT date(created_at) as day, SUM(amount) as xp
           FROM xp_ledger WHERE created_at >= ? GROUP BY day ORDER BY day""",
        (start,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_xp_by_category() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.name, c.icon, c.color, COALESCE(SUM(xl.amount), 0) as xp
           FROM categories c
           LEFT JOIN goals g ON g.category_id = c.id
           LEFT JOIN xp_ledger xl ON xl.source_type = 'goal' AND xl.source_id = g.id
           GROUP BY c.id ORDER BY xp DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
