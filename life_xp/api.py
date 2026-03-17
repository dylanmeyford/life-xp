"""FastAPI REST API for Life XP."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from life_xp.database import fetch_all, fetch_one, get_db, insert, update
from life_xp.models import (
    ChatRequest,
    GoalCreate,
    GoalOut,
    PlayerStatsOut,
    SettingUpdate,
    SubGoalOut,
    SensorOut,
)
from life_xp.xp import get_player_stats, get_xp_history

# ── Lifespan ──────────────────────────────────────────────────────────

db_conn = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_conn
    db_conn = await get_db()
    # Import sensors to register them
    import life_xp.sensors.health
    import life_xp.sensors.cli_sensor
    import life_xp.sensors.api_sensor
    yield
    if db_conn:
        await db_conn.close()


app = FastAPI(title="Life XP", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Player stats ──────────────────────────────────────────────────────

@app.get("/api/stats", response_model=PlayerStatsOut)
async def get_stats():
    stats = await get_player_stats(db_conn)
    return stats


@app.get("/api/xp/history")
async def xp_history(limit: int = 50):
    return await get_xp_history(db_conn, limit)


# ── Goals ─────────────────────────────────────────────────────────────

@app.get("/api/goals")
async def list_goals(status: str = "active"):
    goals = await fetch_all(
        db_conn, "SELECT * FROM goals WHERE status = ? ORDER BY created_at DESC", (status,)
    )
    result = []
    for g in goals:
        sub_goals = await fetch_all(
            db_conn, "SELECT * FROM sub_goals WHERE goal_id = ? ORDER BY sort_order", (g["id"],)
        )
        sensors = await fetch_all(
            db_conn, "SELECT * FROM sensor_configs WHERE goal_id = ?", (g["id"],)
        )
        result.append({**g, "sub_goals": sub_goals, "sensors": sensors})
    return result


@app.post("/api/goals")
async def create_goal(goal: GoalCreate):
    goal_id = await insert(db_conn, "goals", goal.model_dump())
    return {"id": goal_id, "message": "Goal created. Starting agent to plan it out..."}


@app.get("/api/goals/{goal_id}")
async def get_goal(goal_id: int):
    goal = await fetch_one(db_conn, "SELECT * FROM goals WHERE id = ?", (goal_id,))
    if not goal:
        raise HTTPException(404, "Goal not found")
    goal["sub_goals"] = await fetch_all(
        db_conn, "SELECT * FROM sub_goals WHERE goal_id = ? ORDER BY sort_order", (goal_id,)
    )
    goal["sensors"] = await fetch_all(
        db_conn, "SELECT * FROM sensor_configs WHERE goal_id = ?", (goal_id,)
    )
    return goal


@app.patch("/api/goals/{goal_id}")
async def update_goal(goal_id: int, data: dict):
    allowed = {"title", "description", "target", "category", "status"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if not filtered:
        raise HTTPException(400, "No valid fields to update")
    await update(db_conn, "goals", goal_id, filtered)
    return {"ok": True}


# ── Chat / Agent ──────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send a message to the agent. If goal_id is provided, the agent focuses on that goal."""
    from life_xp.agent.loop import AgentLoop

    # Get recent conversation history for this goal
    history_rows = await fetch_all(
        db_conn,
        "SELECT role, content FROM agent_messages WHERE goal_id IS ? ORDER BY created_at DESC LIMIT 20",
        (req.goal_id,),
    )
    # Reverse to chronological order and filter to user/assistant messages
    history = []
    for row in reversed(history_rows):
        if row["role"] in ("user", "assistant"):
            history.append({"role": row["role"], "content": row["content"]})

    agent = AgentLoop(db_conn)
    result = await agent.run(req.message, goal_id=req.goal_id, conversation_history=history[-10:])
    return {"messages": result}


@app.get("/api/chat/history")
async def chat_history(goal_id: int | None = None, limit: int = 50):
    if goal_id is not None:
        rows = await fetch_all(
            db_conn,
            "SELECT * FROM agent_messages WHERE goal_id = ? ORDER BY created_at DESC LIMIT ?",
            (goal_id, limit),
        )
    else:
        rows = await fetch_all(
            db_conn,
            "SELECT * FROM agent_messages ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    return list(reversed(rows))


# ── Sensors ───────────────────────────────────────────────────────────

@app.get("/api/sensors")
async def list_sensors(goal_id: int | None = None):
    if goal_id is not None:
        return await fetch_all(
            db_conn, "SELECT * FROM sensor_configs WHERE goal_id = ?", (goal_id,)
        )
    return await fetch_all(db_conn, "SELECT * FROM sensor_configs")


@app.get("/api/sensors/{sensor_id}/readings")
async def sensor_readings(sensor_id: int, limit: int = 100):
    return await fetch_all(
        db_conn,
        "SELECT * FROM sensor_readings WHERE sensor_id = ? ORDER BY created_at DESC LIMIT ?",
        (sensor_id, limit),
    )


@app.post("/api/sensors/poll")
async def poll_sensors():
    """Manually trigger all active sensors to poll."""
    from life_xp.sensors.base import SensorRegistry
    results = await SensorRegistry.poll_all(db_conn)
    return {"polled": len(results), "results": results}


# ── Settings ──────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    rows = await fetch_all(db_conn, "SELECT * FROM user_settings")
    return {r["key"]: r["value"] for r in rows}


@app.put("/api/settings")
async def update_setting(setting: SettingUpdate):
    await db_conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
        (setting.key, setting.value),
    )
    await db_conn.commit()
    return {"ok": True}
