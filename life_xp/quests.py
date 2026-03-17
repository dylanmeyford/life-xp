"""Daily Quests — AI-generated micro-challenges tied to active goals."""

from __future__ import annotations

import json
import os
import random
from datetime import date, datetime

from life_xp.database import fetch_all, fetch_one, insert


QUESTS_PER_DAY = 3

# ── Fallback quest templates (used when no AI key is configured) ────

TEMPLATES = [
    # Health
    ("Walk {n} extra steps today", "health", [500, 1000, 2000]),
    ("Drink {n} glasses of water", "health", [6, 8, 10]),
    ("Do a {n}-minute stretch session", "health", [5, 10, 15]),
    ("Take a {n}-minute walk outside", "health", [10, 15, 20]),

    # Learning
    ("Read for {n} minutes", "learning", [10, 15, 20, 30]),
    ("Watch a {n}-minute educational video", "learning", [10, 15, 20]),
    ("Write {n} sentences in a journal", "learning", [3, 5, 10]),
    ("Learn {n} new vocabulary words", "learning", [3, 5, 10]),

    # Productivity
    ("Complete {n} tasks from your to-do list", "productivity", [2, 3, 5]),
    ("Focus for {n} minutes without distractions", "productivity", [15, 25, 30, 45]),
    ("Organize one area of your workspace", "productivity", [1]),
    ("Review and plan tomorrow's priorities", "productivity", [1]),

    # Finance
    ("Track all spending today", "finance", [1]),
    ("Skip one unnecessary purchase today", "finance", [1]),
    ("Review your budget for {n} minutes", "finance", [5, 10, 15]),

    # Wellness
    ("Meditate for {n} minutes", "wellness", [5, 10, 15]),
    ("Get to bed {n} minutes earlier than usual", "wellness", [15, 30, 45]),
    ("Take {n} deep breaths between tasks", "wellness", [5, 10]),
    ("No screen time for {n} minutes before bed", "wellness", [15, 30, 60]),

    # General
    ("Do something kind for someone", "general", [1]),
    ("Spend {n} minutes on a hobby", "general", [15, 20, 30]),
    ("Tidy up for {n} minutes", "general", [5, 10, 15]),
]


def _generate_from_templates(goals: list[dict], count: int = QUESTS_PER_DAY) -> list[dict]:
    """Generate quests from templates, prioritizing categories matching active goals."""
    goal_categories = {(g.get("category") or "general").lower() for g in goals}

    # Weight templates by category relevance
    weighted = []
    for template, cat, values in TEMPLATES:
        weight = 3 if cat in goal_categories else 1
        weighted.extend([(template, cat, values)] * weight)

    random.shuffle(weighted)
    seen_templates = set()
    quests = []

    for template, cat, values in weighted:
        if len(quests) >= count:
            break
        if template in seen_templates:
            continue
        seen_templates.add(template)

        n = random.choice(values)
        title = template.format(n=n)
        goal = next((g for g in goals if (g.get("category") or "").lower() == cat), None)

        quests.append({
            "title": title,
            "description": f"Quick challenge in {cat}",
            "xp_reward": random.choice([15, 20, 25, 30, 35]),
            "goal_id": goal["id"] if goal else None,
        })

    return quests


async def generate_daily_quests(db) -> list[dict]:
    """Generate today's daily quests if they don't exist yet.
    Uses AI if API key is available, otherwise falls back to templates."""
    today = date.today().isoformat()

    # Check if quests already exist for today
    existing = await fetch_all(
        db, "SELECT * FROM daily_quests WHERE quest_date = ? ORDER BY created_at", (today,)
    )
    if existing:
        return existing

    # Expire yesterday's incomplete quests
    await db.execute(
        "UPDATE daily_quests SET status = 'expired' WHERE quest_date < ? AND status = 'active'",
        (today,),
    )
    await db.commit()

    # Get active goals for context
    goals = await fetch_all(db, "SELECT * FROM goals WHERE status = 'active'")

    quests_data = []

    # Try AI generation
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        setting = await fetch_one(db, "SELECT value FROM user_settings WHERE key = 'anthropic_api_key'")
        if setting:
            api_key = setting["value"]

    if api_key and goals:
        try:
            quests_data = await _generate_with_ai(api_key, goals, db)
        except Exception:
            pass

    # Fallback to templates
    if not quests_data:
        quests_data = _generate_from_templates(goals)

    # Insert quests
    created = []
    for q in quests_data[:QUESTS_PER_DAY]:
        row_id = await insert(db, "daily_quests", {
            "title": q["title"],
            "description": q.get("description", ""),
            "xp_reward": q.get("xp_reward", 25),
            "goal_id": q.get("goal_id"),
            "quest_date": today,
        })
        row = await fetch_one(db, "SELECT * FROM daily_quests WHERE id = ?", (row_id,))
        created.append(dict(row))

    return created


async def _generate_with_ai(api_key: str, goals: list[dict], db) -> list[dict]:
    """Use Claude to generate personalized daily quests."""
    import anthropic

    model = os.environ.get("LIFE_XP_MODEL", "claude-sonnet-4-20250514")
    setting = await fetch_one(db, "SELECT value FROM user_settings WHERE key = 'model'")
    if setting:
        model = setting["value"]

    goals_text = "\n".join(
        f"- {g['title']} (target: {g.get('target', 'N/A')}, category: {g.get('category', 'general')})"
        for g in goals
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Generate exactly {QUESTS_PER_DAY} quick daily micro-challenges for someone with these goals:\n"
                f"{goals_text}\n\n"
                "Each quest should be achievable in a single day and take 5-30 minutes.\n"
                "Return ONLY a JSON array with objects having: title, description, xp_reward (15-35).\n"
                "Make them specific, actionable, and encouraging. No markdown, just JSON."
            ),
        }],
    )

    text = response.content[0].text.strip()
    # Extract JSON from response
    if text.startswith("["):
        return json.loads(text)
    # Try to find JSON array in response
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return []


async def get_todays_quests(db) -> list[dict]:
    """Get today's quests, generating them if needed."""
    return await generate_daily_quests(db)


async def complete_quest(db, quest_id: int) -> dict:
    """Mark a quest as completed and award XP."""
    quest = await fetch_one(db, "SELECT * FROM daily_quests WHERE id = ?", (quest_id,))
    if not quest:
        return {"error": "Quest not found"}
    if quest["status"] != "active":
        return {"error": f"Quest is already {quest['status']}"}

    now = datetime.now().isoformat()
    await db.execute(
        "UPDATE daily_quests SET status = 'completed', completed_at = ? WHERE id = ?",
        (now, quest_id),
    )
    await db.commit()

    # Award XP
    from life_xp.xp import award_xp
    stats = await award_xp(db, quest["xp_reward"], "quest", quest_id, f"Quest: {quest['title']}")

    # Check for quest-related achievements
    from life_xp.achievements import check_and_unlock
    unlocked = await check_and_unlock(db)

    # Check if all today's quests are complete
    today = date.today().isoformat()
    remaining = await fetch_one(
        db, "SELECT COUNT(*) as c FROM daily_quests WHERE quest_date = ? AND status = 'active'", (today,)
    )
    all_complete = remaining["c"] == 0

    if all_complete:
        # Bonus XP for clean sweep
        bonus = 50
        await award_xp(db, bonus, "bonus", None, "All daily quests completed!")

    return {
        "quest": dict(quest),
        "xp_awarded": quest["xp_reward"],
        "all_complete": all_complete,
        "bonus_xp": 50 if all_complete else 0,
        "achievements_unlocked": unlocked,
        "stats": {
            "total_xp": stats.total_xp,
            "level": stats.level,
            "title": stats.title,
        },
    }
