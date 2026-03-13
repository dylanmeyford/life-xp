"""LLM coaching engine — uses Claude API for goal decomposition and proactive nudges."""

import json
import os
import logging
from datetime import date, datetime

import anthropic

from life_xp.database import get_connection
from life_xp.xp import get_stats

log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("LIFE_XP_MODEL", "claude-sonnet-4-20250514")


def _get_client() -> anthropic.Anthropic:
    key = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY environment variable."
        )
    return anthropic.Anthropic(api_key=key)


def _get_user_context() -> dict:
    """Build context about the user's current state for the LLM."""
    from life_xp.engine import list_goals, list_habits, list_daily_tasks

    stats = get_stats()
    goals = list_goals("active")
    habits = list_habits()
    today_tasks = list_daily_tasks()

    return {
        "level": stats.level,
        "title": stats.title,
        "total_xp": stats.total_xp,
        "active_goals": [
            {
                "id": g["id"],
                "title": g["title"],
                "description": g.get("description", ""),
                "category": g.get("category_name", ""),
                "goal_type": g.get("goal_type", "manual"),
                "target_value": g.get("target_value"),
                "current_value": g.get("current_value"),
                "unit": g.get("unit"),
                "recurrence": g.get("recurrence"),
            }
            for g in goals[:20]
        ],
        "habits": [
            {
                "id": h["id"],
                "title": h["title"],
                "streak": h.get("streak", 0),
                "done_today": h.get("done_today", False),
                "frequency": h["frequency"],
            }
            for h in habits
        ],
        "today_tasks": [
            {
                "id": t["id"],
                "title": t["title"],
                "status": t["status"],
                "goal_title": t.get("goal_title", ""),
            }
            for t in today_tasks
        ],
        "date": date.today().isoformat(),
        "day_of_week": date.today().strftime("%A"),
    }


SYSTEM_PROMPT = """You are an encouraging life coach and personal productivity assistant embedded in a gamified life-tracking app called Life XP. The user earns XP for completing goals, habits, and daily tasks.

Your role:
- Help break down vague or qualitative goals into specific, actionable daily tasks
- Generate motivating daily plans based on the user's active goals and habits
- Evaluate self-reported progress on qualitative goals
- Send encouraging but concise nudges

Always respond in JSON format when asked for structured output. Be concise, warm, and action-oriented. Use the user's current level, streaks, and progress to personalize encouragement."""


async def decompose_goal(goal: dict, user_context: dict | None = None) -> list[dict]:
    """Break a qualitative or complex goal into daily actionable tasks."""
    if user_context is None:
        user_context = _get_user_context()

    client = _get_client()
    prompt = f"""The user has set this goal:
Title: {goal['title']}
Description: {goal.get('description', '')}
Category: {goal.get('category_name', goal.get('category', ''))}
Type: {goal.get('goal_type', 'qualitative')}
Recurrence: {goal.get('recurrence', 'none')}

User context:
{json.dumps(user_context, indent=2)}

Generate 3-5 specific, actionable daily tasks that would help progress this goal TODAY.
Each task should be completable in a single sitting.

Respond with a JSON array of objects with "title", "description", and "xp_reward" (10-50 based on difficulty) fields. Only output the JSON array, nothing else."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = message.content[0].text.strip()
        # Handle potential markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError) as e:
        log.error(f"Failed to parse LLM response for goal decomposition: {e}")
        return []


async def generate_daily_plan(
    goals: list[dict] | None = None,
    habits: list[dict] | None = None,
) -> list[dict]:
    """Generate today's priority tasks across all active goals."""
    user_context = _get_user_context()
    if goals is None:
        goals = user_context["active_goals"]
    if habits is None:
        habits = user_context["habits"]

    client = _get_client()
    prompt = f"""Generate a daily plan for the user based on their active goals and habits.

User context:
{json.dumps(user_context, indent=2)}

Create 3-7 specific daily tasks that would make today productive across their goals.
Prioritize goals that are recurring or have upcoming deadlines.
Don't duplicate habits (they have their own tracking).

Respond with a JSON array of objects with:
- "title": short actionable task
- "description": one sentence context
- "goal_id": the goal ID this relates to (or null for general tasks)
- "xp_reward": 10-50 based on difficulty

Only output the JSON array, nothing else."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError) as e:
        log.error(f"Failed to parse daily plan: {e}")
        return []


async def evaluate_progress(goal: dict, user_message: str) -> dict:
    """User reports what they did; LLM evaluates if goal was progressed."""
    user_context = _get_user_context()
    client = _get_client()

    prompt = f"""The user is reporting progress on this goal:
Title: {goal['title']}
Description: {goal.get('description', '')}
Type: {goal.get('goal_type', 'qualitative')}

Their report: "{user_message}"

Evaluate:
1. Did they make meaningful progress? (true/false)
2. How much XP should they earn? (0-100 based on effort)
3. A brief encouraging response (1-2 sentences)
4. Suggested next step (1 sentence)

Respond with a JSON object with fields: "progressed" (bool), "xp_award" (int), "response" (string), "next_step" (string). Only output the JSON object."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError) as e:
        log.error(f"Failed to parse progress evaluation: {e}")
        return {"progressed": False, "xp_award": 0, "response": "Thanks for the update!", "next_step": ""}


async def generate_nudge(time_of_day: str = "afternoon") -> str | None:
    """Generate a proactive motivational nudge based on today's progress."""
    user_context = _get_user_context()

    # Don't nudge if no goals/habits
    if not user_context["active_goals"] and not user_context["habits"]:
        return None

    client = _get_client()

    tasks_done = sum(1 for t in user_context["today_tasks"] if t["status"] == "done")
    tasks_total = len(user_context["today_tasks"])
    habits_done = sum(1 for h in user_context["habits"] if h["done_today"])
    habits_total = len(user_context["habits"])

    prompt = f"""Generate a short, motivating notification for the user.

Time: {time_of_day} ({user_context['day_of_week']})
Level: {user_context['level']} ({user_context['title']})
Today's tasks: {tasks_done}/{tasks_total} completed
Habits done: {habits_done}/{habits_total}

{"They've been productive!" if tasks_done > tasks_total / 2 else "They could use some motivation."}

Write ONE short notification message (under 100 characters). Be encouraging but not annoying.
Output just the message string, no quotes, no JSON."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=100,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip().strip('"')
    return text if text else None


async def coaching_reply(session_id: int, user_message: str) -> str:
    """Handle a coaching chat reply (for notification quick-replies)."""
    conn = get_connection()

    # Get session context
    session = conn.execute(
        "SELECT * FROM coaching_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not session:
        conn.close()
        return "I couldn't find that conversation. Try starting a new one!"

    # Get message history
    messages = conn.execute(
        "SELECT role, content FROM coaching_messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()

    # Save user message
    conn.execute(
        "INSERT INTO coaching_messages (session_id, role, content) VALUES (?, 'user', ?)",
        (session_id, user_message),
    )
    conn.commit()

    # Build conversation for Claude
    conversation = [{"role": m["role"], "content": m["content"]} for m in messages]
    conversation.append({"role": "user", "content": user_message})

    # Get goal context if this session is tied to a goal
    goal_context = ""
    if session["goal_id"]:
        goal = conn.execute("SELECT * FROM goals WHERE id = ?", (session["goal_id"],)).fetchone()
        if goal:
            goal_context = f"\nThis conversation is about the goal: {goal['title']}\n"

    conn.close()

    client = _get_client()
    user_context = _get_user_context()

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT + goal_context + f"\nUser context:\n{json.dumps(user_context)}",
        messages=conversation,
    )

    reply = message.content[0].text.strip()

    # Save assistant reply
    conn = get_connection()
    conn.execute(
        "INSERT INTO coaching_messages (session_id, role, content) VALUES (?, 'assistant', ?)",
        (session_id, reply),
    )
    conn.commit()
    conn.close()

    return reply


def create_coaching_session(goal_id: int | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO coaching_sessions (goal_id) VALUES (?)", (goal_id,)
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id
