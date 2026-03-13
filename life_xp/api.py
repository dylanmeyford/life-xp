"""FastAPI server — REST API for the Life XP frontend."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from life_xp.database import init_db
from life_xp.agent.loop import run_agent_loop

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(run_agent_loop(interval=60))
    log.info("Life XP API started with agent loop")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Life XP", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ─────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    category: str = "Productivity"
    description: str = ""
    xp_reward: int = 100
    target_value: float | None = None
    unit: str | None = None
    parent_id: int | None = None
    due_date: str | None = None
    goal_type: str = "manual"
    recurrence: str | None = None
    llm_context: str | None = None


class HabitCreate(BaseModel):
    title: str
    category: str = "Productivity"
    description: str = ""
    frequency: str = "daily"
    xp_per_check: int = 25


class QuestCreate(BaseModel):
    title: str
    objectives: list[str]
    category: str = "Productivity"
    description: str = ""
    xp_reward: int = 500
    deadline: str | None = None


class RewardCreate(BaseModel):
    title: str
    xp_cost: int
    description: str = ""


class DailyTaskCreate(BaseModel):
    title: str
    goal_id: int | None = None
    description: str = ""
    xp_reward: int = 25


class ProgressUpdate(BaseModel):
    value: float


class CoachDecompose(BaseModel):
    goal_id: int


class CoachEvaluate(BaseModel):
    goal_id: int
    message: str


class CoachReply(BaseModel):
    session_id: int
    message: str


class SensorStrategySelect(BaseModel):
    goal_id: int
    strategy_index: int


class SmartInput(BaseModel):
    text: str


# ── Smart Input (intent parsing + execution) ─────────────────────────

@app.post("/api/input")
async def api_smart_input(body: SmartInput):
    """Parse natural language input, determine intent, and execute the action.

    This is the main entry point for the tray text input. The user types
    anything and the LLM figures out what to do.
    """
    from life_xp.coach import parse_intent, evaluate_progress
    from life_xp.engine import (
        create_goal, create_habit, check_habit, complete_goal,
    )
    from life_xp.xp import award_xp

    result = await parse_intent(body.text)
    intent = result.get("intent", "coaching")
    data = result.get("data", {})
    reply = result.get("reply", "")

    action_result = {}

    if intent == "create_goal":
        goal_id = create_goal(
            title=data.get("title", body.text),
            description=data.get("description", ""),
            category=data.get("category", "Productivity"),
            goal_type=data.get("goal_type", "manual"),
            xp_reward=data.get("xp_reward", 100),
            recurrence=data.get("recurrence"),
            target_value=data.get("target_value"),
            unit=data.get("unit"),
        )
        action_result = {"goal_id": goal_id}

        # If it's a non-manual goal, propose tracking strategies
        if data.get("goal_type", "manual") != "manual":
            from life_xp.engine import get_goal
            from life_xp.agent.sensor_builder import propose_tracking_strategies
            goal = get_goal(goal_id)
            if goal:
                strategies = await propose_tracking_strategies(goal)
                action_result["strategies"] = strategies.get("strategies", [])

    elif intent == "create_habit":
        habit_id = create_habit(
            title=data.get("title", body.text),
            category=data.get("category", "Productivity"),
            frequency=data.get("frequency", "daily"),
            xp_per_check=data.get("xp_per_check", 25),
        )
        action_result = {"habit_id": habit_id}

    elif intent == "check_habit":
        habit_id = data.get("habit_id")
        if habit_id:
            try:
                action_result = check_habit(habit_id)
            except ValueError as e:
                action_result = {"error": str(e)}

    elif intent == "complete_goal":
        goal_id = data.get("goal_id")
        if goal_id:
            try:
                action_result = complete_goal(goal_id)
            except ValueError as e:
                action_result = {"error": str(e)}

    elif intent == "progress_update":
        goal_id = data.get("goal_id")
        if goal_id:
            from life_xp.engine import get_goal
            goal = get_goal(goal_id)
            if goal:
                eval_result = await evaluate_progress(goal, data.get("message", body.text))
                if eval_result.get("progressed") and eval_result.get("xp_award", 0) > 0:
                    award_xp(eval_result["xp_award"], "goal", goal_id, f"Progress: {goal['title']}")
                action_result = eval_result

    # For ask_question and coaching, the reply itself is the result
    elif intent == "ask_question":
        action_result = {"answer": data.get("answer", reply)}

    elif intent == "coaching":
        action_result = {"advice": data.get("advice", reply)}

    return {
        "intent": intent,
        "reply": reply,
        "data": action_result,
    }


# ── Stats ──────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    from life_xp.xp import get_stats as _get_stats
    stats = _get_stats()
    return {
        "total_xp": stats.total_xp,
        "level": stats.level,
        "xp_in_level": stats.xp_in_level,
        "xp_for_next": stats.xp_for_next,
        "progress_pct": stats.progress_pct,
        "title": stats.title,
    }


# ── Goals ──────────────────────────────────────────────────────────────

@app.get("/api/goals")
def api_list_goals(status: str = "active", category: str | None = None):
    from life_xp.engine import list_goals
    return list_goals(status, category)


@app.post("/api/goals")
def api_create_goal(goal: GoalCreate):
    from life_xp.engine import create_goal
    goal_id = create_goal(**goal.model_dump())
    return {"id": goal_id}


@app.get("/api/goals/{goal_id}")
def api_get_goal(goal_id: int):
    from life_xp.engine import get_goal
    goal = get_goal(goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    return goal


@app.put("/api/goals/{goal_id}/complete")
def api_complete_goal(goal_id: int):
    from life_xp.engine import complete_goal
    try:
        return complete_goal(goal_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/goals/{goal_id}/progress")
def api_update_progress(goal_id: int, body: ProgressUpdate):
    from life_xp.engine import update_goal_progress
    try:
        return update_goal_progress(goal_id, body.value)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/goals/{goal_id}/sub-goals")
def api_sub_goals(goal_id: int):
    from life_xp.engine import get_sub_goals
    return get_sub_goals(goal_id)


# ── Habits ─────────────────────────────────────────────────────────────

@app.get("/api/habits")
def api_list_habits():
    from life_xp.engine import list_habits
    return list_habits()


@app.post("/api/habits")
def api_create_habit(habit: HabitCreate):
    from life_xp.engine import create_habit
    habit_id = create_habit(**habit.model_dump())
    return {"id": habit_id}


@app.put("/api/habits/{habit_id}/check")
def api_check_habit(habit_id: int):
    from life_xp.engine import check_habit
    try:
        return check_habit(habit_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/habits/{habit_id}/grid")
def api_habit_grid(habit_id: int, weeks: int = 52):
    from life_xp.engine import get_habit_history
    history = get_habit_history(habit_id, days=weeks * 7)
    checked_dates = [r["checked_date"] for r in history]
    return {"habit_id": habit_id, "weeks": weeks, "checked_dates": checked_dates}


@app.get("/api/habits/overview")
def api_habit_overview(weeks: int = 20):
    from life_xp.database import get_connection
    from datetime import timedelta
    conn = get_connection()
    start = (date.today() - timedelta(days=weeks * 7)).isoformat()
    rows = conn.execute(
        """SELECT checked_date, COUNT(*) as count
           FROM habit_checks WHERE checked_date >= ?
           GROUP BY checked_date ORDER BY checked_date""",
        (start,),
    ).fetchall()
    conn.close()
    return {"weeks": weeks, "data": [dict(r) for r in rows]}


# ── Quests ─────────────────────────────────────────────────────────────

@app.get("/api/quests")
def api_list_quests(status: str = "active"):
    from life_xp.engine import list_quests
    return list_quests(status)


@app.post("/api/quests")
def api_create_quest(quest: QuestCreate):
    from life_xp.engine import create_quest
    quest_id = create_quest(**quest.model_dump())
    return {"id": quest_id}


@app.put("/api/quests/{quest_id}/objectives/{objective_id}/complete")
def api_complete_objective(quest_id: int, objective_id: int):
    from life_xp.engine import complete_quest_objective
    return complete_quest_objective(quest_id, objective_id)


# ── Rewards ────────────────────────────────────────────────────────────

@app.get("/api/rewards")
def api_list_rewards():
    from life_xp.engine import list_rewards
    return list_rewards()


@app.post("/api/rewards")
def api_create_reward(reward: RewardCreate):
    from life_xp.engine import create_reward
    reward_id = create_reward(**reward.model_dump())
    return {"id": reward_id}


@app.put("/api/rewards/{reward_id}/redeem")
def api_redeem_reward(reward_id: int):
    from life_xp.engine import redeem_reward
    try:
        return redeem_reward(reward_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Daily Tasks ────────────────────────────────────────────────────────

@app.get("/api/daily-tasks")
def api_list_daily_tasks(task_date: str | None = None):
    from life_xp.engine import list_daily_tasks
    return list_daily_tasks(task_date)


@app.post("/api/daily-tasks")
def api_create_daily_task(task: DailyTaskCreate):
    from life_xp.engine import create_daily_task
    task_id = create_daily_task(**task.model_dump())
    return {"id": task_id}


@app.put("/api/daily-tasks/{task_id}/complete")
def api_complete_daily_task(task_id: int):
    from life_xp.engine import complete_daily_task
    try:
        return complete_daily_task(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/daily-tasks/{task_id}/skip")
def api_skip_daily_task(task_id: int):
    from life_xp.engine import skip_daily_task
    return skip_daily_task(task_id)


# ── Coaching ───────────────────────────────────────────────────────────

@app.post("/api/coach/decompose")
async def api_coach_decompose(body: CoachDecompose):
    from life_xp.engine import get_goal
    from life_xp.coach import decompose_goal

    goal = get_goal(body.goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")

    tasks = await decompose_goal(goal)
    return {"tasks": tasks}


@app.post("/api/coach/daily-plan")
async def api_coach_daily_plan():
    from life_xp.coach import generate_daily_plan
    tasks = await generate_daily_plan()
    return {"tasks": tasks}


@app.post("/api/coach/evaluate")
async def api_coach_evaluate(body: CoachEvaluate):
    from life_xp.engine import get_goal
    from life_xp.coach import evaluate_progress
    from life_xp.xp import award_xp

    goal = get_goal(body.goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")

    result = await evaluate_progress(goal, body.message)

    if result.get("progressed") and result.get("xp_award", 0) > 0:
        award_xp(result["xp_award"], "goal", body.goal_id, f"Progress: {goal['title']}")

    return result


@app.post("/api/coach/reply")
async def api_coach_reply(body: CoachReply):
    from life_xp.coach import coaching_reply
    reply = await coaching_reply(body.session_id, body.message)
    return {"reply": reply}


# ── Notifications ──────────────────────────────────────────────────────

@app.get("/api/notifications/pending")
def api_pending_notifications():
    from life_xp.engine import get_pending_notifications
    return get_pending_notifications()


@app.put("/api/notifications/{notification_id}/read")
def api_mark_notification_read(notification_id: int):
    from life_xp.engine import mark_notification_read
    mark_notification_read(notification_id)
    return {"ok": True}


@app.put("/api/notifications/read-all")
def api_mark_all_read():
    from life_xp.engine import mark_all_notifications_read
    mark_all_notifications_read()
    return {"ok": True}


# ── Sensors ────────────────────────────────────────────────────────────

@app.get("/api/sensors")
def api_list_sensors():
    from life_xp.sensors.base import SensorRegistry
    from life_xp.sensors.custom_loader import list_custom_sensors

    # Import built-in sensors
    import life_xp.sensors.steps
    import life_xp.sensors.screentime
    import life_xp.sensors.git_sensor
    import life_xp.sensors.finance
    import life_xp.sensors.imessage

    built_in = []
    for name, cls in SensorRegistry.all().items():
        if not name.startswith("custom_"):
            sensor = cls()
            built_in.append({
                "type": name,
                "available": sensor.is_available(),
                "custom": False,
            })

    custom = list_custom_sensors()
    return {"built_in": built_in, "custom": custom}


@app.post("/api/sensors/propose")
async def api_propose_tracking(body: CoachDecompose):
    """Propose multiple tracking strategies for a goal — user picks one."""
    from life_xp.engine import get_goal
    from life_xp.agent.sensor_builder import propose_tracking_strategies

    goal = get_goal(body.goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    return await propose_tracking_strategies(goal)


@app.get("/api/sensors/strategies/{goal_id}")
def api_get_strategies(goal_id: int):
    """Get previously proposed strategies for a goal."""
    from life_xp.database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT strategies_json, selected, selected_index FROM sensor_strategies WHERE goal_id = ?",
        (goal_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "No strategies proposed for this goal")
    return {
        "goal_id": goal_id,
        "strategies": json.loads(row[0]),
        "selected": bool(row[1]),
        "selected_index": row[2],
    }


@app.post("/api/sensors/select")
async def api_select_strategy(body: SensorStrategySelect):
    """User selects their preferred tracking strategy — builds the sensor."""
    from life_xp.agent.sensor_builder import select_tracking_strategy
    result = await select_tracking_strategy(body.goal_id, body.strategy_index)
    return result


@app.post("/api/sensors/run")
def api_run_sensors():
    from life_xp.sensors.base import SensorRegistry
    from life_xp.sensors.custom_loader import load_custom_sensors

    import life_xp.sensors.steps
    import life_xp.sensors.screentime
    import life_xp.sensors.git_sensor
    import life_xp.sensors.finance
    import life_xp.sensors.imessage

    load_custom_sensors()
    SensorRegistry.run_all()
    return {"ok": True}


# ── Categories & History ───────────────────────────────────────────────

@app.get("/api/categories")
def api_categories():
    from life_xp.engine import list_categories
    return list_categories()


@app.get("/api/xp/history")
def api_xp_history(days: int = 30):
    from life_xp.engine import get_xp_history
    return get_xp_history(days)


@app.get("/api/xp/by-category")
def api_xp_by_category():
    from life_xp.engine import get_xp_by_category
    return get_xp_by_category()


# ── Tray Dashboard ────────────────────────────────────────────────────

@app.get("/api/tray")
def api_tray_data():
    """Single endpoint returning everything the tray popover needs."""
    from life_xp.xp import get_stats as _get_stats
    from life_xp.engine import list_goals, list_habits, list_daily_tasks

    stats = _get_stats()
    goals = list_goals("active")
    habits = list_habits()
    tasks = list_daily_tasks()

    tasks_done = sum(1 for t in tasks if t["status"] == "done")

    return {
        "stats": {
            "total_xp": stats.total_xp,
            "level": stats.level,
            "xp_in_level": stats.xp_in_level,
            "xp_for_next": stats.xp_for_next,
            "progress_pct": stats.progress_pct,
            "title": stats.title,
        },
        "goals": [
            {
                "id": g["id"],
                "title": g["title"],
                "category_icon": g.get("category_icon", "⭐"),
                "goal_type": g.get("goal_type", "manual"),
                "progress": (
                    min((g.get("current_value") or 0) / g["target_value"], 1.0)
                    if g.get("target_value")
                    else None
                ),
                "target_value": g.get("target_value"),
                "current_value": g.get("current_value"),
                "unit": g.get("unit"),
                "recurrence": g.get("recurrence"),
            }
            for g in goals[:10]
        ],
        "habits": [
            {
                "id": h["id"],
                "title": h["title"],
                "category_icon": h.get("category_icon", "⭐"),
                "done_today": h.get("done_today", False),
                "streak": h.get("streak", 0),
                "xp_per_check": h["xp_per_check"],
            }
            for h in habits
        ],
        "daily_tasks": {
            "done": tasks_done,
            "total": len(tasks),
            "items": [
                {
                    "id": t["id"],
                    "title": t["title"],
                    "status": t["status"],
                    "xp_reward": t["xp_reward"],
                }
                for t in tasks[:8]
            ],
        },
    }


# ── Health Check ───────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
