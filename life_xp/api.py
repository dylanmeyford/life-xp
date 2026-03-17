"""FastAPI REST API for Life XP."""

from __future__ import annotations

import base64
import json
import logging
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode, urlparse, parse_qs

import httpx

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

logger = logging.getLogger(__name__)


def _goal_sync_metadata(sensors: list[dict]) -> dict:
    """Return goal-level sync metadata derived from active sensors."""
    auto_sensors = [
        s for s in sensors
        if s.get("status") == "active" and s.get("sensor_type") != "manual"
    ]
    last_runs = [s.get("last_run") for s in auto_sensors if s.get("last_run")]
    return {
        "auto_tracked": bool(auto_sensors),
        "last_synced_at": max(last_runs) if last_runs else None,
    }

# ── Lifespan ──────────────────────────────────────────────────────────

db_conn = None
_scheduler: AsyncIOScheduler | None = None


async def _scheduled_poll():
    """Poll all active sensors — called by the scheduler."""
    if db_conn is None:
        return
    from life_xp.sensors.base import SensorRegistry
    try:
        results = await SensorRegistry.poll_all(db_conn)
        if results:
            logger.info("Scheduled poll: %d sensor(s) updated", len(results))
    except Exception as exc:
        logger.error("Scheduled poll failed: %s", exc)


async def _scheduled_token_refresh():
    """Proactively refresh tokens for API sensors nearing expiration."""
    if db_conn is None:
        return
    from life_xp.token_refresh import refresh_token_for_sensor, token_needs_refresh
    try:
        sensors = await fetch_all(
            db_conn, "SELECT * FROM sensor_configs WHERE status = 'active' AND sensor_type = 'api'"
        )
        for s in sensors:
            config = json.loads(s["config"])
            if token_needs_refresh(config):
                logger.info("Proactively refreshing token for sensor %d", s["id"])
                success = await refresh_token_for_sensor(db_conn, s["id"])
                if not success:
                    logger.warning("Token refresh failed for sensor %d", s["id"])
    except Exception as exc:
        logger.error("Scheduled token refresh failed: %s", exc)


async def _scheduled_streak_decay():
    """Decay broken streaks daily at 1 AM."""
    if db_conn is None:
        return
    try:
        from life_xp.streaks import decay_streaks
        broken = await decay_streaks(db_conn)
        if broken:
            logger.info("Streak decay: %d streak(s) broken", broken)
    except Exception as exc:
        logger.error("Streak decay failed: %s", exc)


async def _scheduled_quest_generation():
    """Pre-generate daily quests at midnight."""
    if db_conn is None:
        return
    try:
        from life_xp.quests import generate_daily_quests
        quests = await generate_daily_quests(db_conn)
        logger.info("Generated %d daily quests", len(quests))
    except Exception as exc:
        logger.error("Quest generation failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_conn, _scheduler
    db_conn = await get_db()
    # Import sensors to register them
    import life_xp.sensors.health
    import life_xp.sensors.cli_sensor
    import life_xp.sensors.api_sensor

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_scheduled_poll, "interval", minutes=60, id="sensor_poll")
    _scheduler.add_job(_scheduled_token_refresh, "interval", minutes=15, id="token_refresh")
    _scheduler.add_job(_scheduled_streak_decay, "cron", hour=1, minute=0, id="streak_decay")
    _scheduler.add_job(_scheduled_quest_generation, "cron", hour=0, minute=5, id="quest_gen")
    _scheduler.start()
    logger.info("Scheduler started — polls:60m, tokens:15m, streaks:daily@1am, quests:daily@midnight")

    yield

    _scheduler.shutdown(wait=False)
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
        result.append({
            **g,
            "sub_goals": sub_goals,
            "sensors": sensors,
            **_goal_sync_metadata(sensors),
        })
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
    goal.update(_goal_sync_metadata(goal["sensors"]))
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

@app.get("/api/goals/{goal_id}/readings/daily")
async def goal_readings_daily(goal_id: int, days: int = 112):
    """Return one aggregated value per day for all sensors on this goal.
    Takes the last reading of each day (sensors like Fitbit return cumulative totals)."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = await fetch_all(
        db_conn,
        """SELECT date(sr.created_at) as date, sr.value
           FROM sensor_readings sr
           JOIN sensor_configs sc ON sc.id = sr.sensor_id
           WHERE sc.goal_id = ? AND sr.created_at >= ?
           ORDER BY sr.created_at ASC""",
        (goal_id, cutoff),
    )
    # Last value per day (rows are ASC so last write wins)
    by_date: dict[str, str] = {}
    for row in rows:
        by_date[row["date"]] = row["value"]
    return [{"date": k, "value": v} for k, v in sorted(by_date.items())]


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


@app.delete("/api/sensors/{sensor_id}")
async def delete_sensor(sensor_id: int):
    sensor = await fetch_one(db_conn, "SELECT id FROM sensor_configs WHERE id = ?", (sensor_id,))
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    await db_conn.execute("DELETE FROM sensor_configs WHERE id = ?", (sensor_id,))
    await db_conn.commit()
    return {"ok": True}


@app.post("/api/sensors/poll")
async def poll_sensors():
    """Manually trigger all active sensors to poll."""
    from life_xp.sensors.base import SensorRegistry
    results = await SensorRegistry.poll_all(db_conn)
    return {"polled": len(results), "results": results}


@app.post("/api/goals/{goal_id}/sync")
async def sync_goal(goal_id: int):
    """Manually trigger all active sensors for one goal."""
    goal = await fetch_one(db_conn, "SELECT id FROM goals WHERE id = ?", (goal_id,))
    if not goal:
        raise HTTPException(404, "Goal not found")
    from life_xp.sensors.base import SensorRegistry
    results = await SensorRegistry.poll_goal(db_conn, goal_id)
    return {"goal_id": goal_id, "polled": len(results), "results": results}


# ── OAuth ─────────────────────────────────────────────────────────

OAUTH_REDIRECT = "lifexp://oauth/callback"


@app.get("/api/oauth/start/{sensor_id}")
async def oauth_start(sensor_id: int):
    """Return the authorization URL for the sensor's OAuth flow.
    The renderer should open this URL in the system browser via openExternal()."""
    sensor = await fetch_one(db_conn, "SELECT * FROM sensor_configs WHERE id = ?", (sensor_id,))
    if not sensor:
        raise HTTPException(404, "Sensor not found")

    config = json.loads(sensor["config"])
    oauth = config.get("oauth_config", config)  # some sensors store fields at top level

    client_id   = oauth.get("client_id")
    auth_url    = oauth.get("auth_url", "https://www.fitbit.com/oauth2/authorize")
    scope       = oauth.get("scope", "activity")

    if not client_id:
        raise HTTPException(400, "Sensor has no client_id — cannot start OAuth")

    params = {
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  OAUTH_REDIRECT,
        "scope":         scope,
        "state":         str(sensor_id),   # encoded so the callback knows which sensor
    }
    return {"url": f"{auth_url}?{urlencode(params)}", "sensor_id": sensor_id}


class OAuthExchangeRequest(BaseModel):
    url:   str
    code:  str | None = None
    state: str | None = None


@app.post("/api/oauth/exchange")
async def oauth_exchange(req: OAuthExchangeRequest):
    """Exchange an authorization code received via the lifexp:// deep-link for tokens.
    Updates the matching sensor's config with the new Bearer token."""
    # Extract code / state from the full URL if not supplied directly
    code  = req.code
    state = req.state
    if not code and req.url:
        parsed = urlparse(req.url)
        qs     = parse_qs(parsed.query)
        code   = (qs.get("code")  or [None])[0]
        state  = (qs.get("state") or [None])[0]

    if not code:
        raise HTTPException(400, "No authorization code in request")

    # Resolve which sensor is waiting for this callback
    sensor = None
    if state and state.isdigit():
        sensor = await fetch_one(db_conn, "SELECT * FROM sensor_configs WHERE id = ?", (int(state),))
    if not sensor:
        # Fall back: pick the most recent sensor with oauth_config
        rows = await fetch_all(
            db_conn,
            "SELECT * FROM sensor_configs WHERE config LIKE '%oauth_config%' OR config LIKE '%client_id%' ORDER BY created_at DESC LIMIT 1",
        )
        sensor = rows[0] if rows else None
    if not sensor:
        raise HTTPException(404, "No sensor found for OAuth callback")

    config      = json.loads(sensor["config"])
    oauth       = config.get("oauth_config", config)
    client_id   = oauth.get("client_id")   or config.get("client_id")
    client_secret = oauth.get("client_secret") or config.get("client_secret")
    token_url   = oauth.get("token_url", "https://api.fitbit.com/oauth2/token")

    if not client_id or not client_secret:
        raise HTTPException(400, "Sensor config missing client_id or client_secret")

    # Exchange code for tokens
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_url,
            headers={
                "Authorization":  f"Basic {credentials}",
                "Content-Type":   "application/x-www-form-urlencoded",
            },
            data={
                "grant_type":   "authorization_code",
                "code":         code,
                "redirect_uri": OAUTH_REDIRECT,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(400, f"Token exchange failed ({resp.status_code}): {resp.text}")

    tokens        = resp.json()
    access_token  = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token:
        raise HTTPException(400, f"No access_token in response: {tokens}")

    # Persist new tokens — update headers, store refresh token, mark active
    new_config = {**config}
    new_config["headers"]       = {"Authorization": f"Bearer {access_token}"}
    new_config["refresh_token"] = refresh_token
    new_config["auth_type"]     = "oauth"
    new_config["token_url"]     = token_url
    new_config["client_id"]     = client_id
    new_config["client_secret"] = client_secret

    expires_in = tokens.get("expires_in")
    if expires_in is not None:
        new_config["token_expires_at"] = time.time() + int(expires_in)

    new_config.pop("oauth_config", None)          # clean up one-time flow data
    new_config.pop("authorization_code", None)

    await update(db_conn, "sensor_configs", sensor["id"], {
        "config": json.dumps(new_config),
        "status": "active",
    })

    logger.info("OAuth exchange complete for sensor %d", sensor["id"])
    return {"ok": True, "sensor_id": sensor["id"], "message": "Connected — sensor is now active"}


# ── Streaks ──────────────────────────────────────────────────────────

@app.get("/api/streaks")
async def list_streaks():
    from life_xp.streaks import get_all_streaks
    return await get_all_streaks(db_conn)


@app.get("/api/streaks/{goal_id}")
async def get_goal_streak(goal_id: int):
    from life_xp.streaks import get_streak
    return await get_streak(db_conn, goal_id)


@app.post("/api/streaks/{goal_id}/checkin")
async def streak_checkin(goal_id: int):
    from life_xp.streaks import checkin
    from life_xp.achievements import check_and_unlock
    result = await checkin(db_conn, goal_id)
    unlocked = await check_and_unlock(db_conn)
    return {**result, "achievements_unlocked": unlocked}


@app.post("/api/streaks/{goal_id}/freeze")
async def streak_freeze(goal_id: int):
    from life_xp.streaks import freeze_streak
    return await freeze_streak(db_conn, goal_id)


# ── Achievements ─────────────────────────────────────────────────────

@app.get("/api/achievements")
async def list_achievements():
    from life_xp.achievements import get_all_achievements
    return await get_all_achievements(db_conn)


@app.post("/api/achievements/check")
async def check_achievements():
    from life_xp.achievements import check_and_unlock
    unlocked = await check_and_unlock(db_conn)
    return {"newly_unlocked": unlocked, "count": len(unlocked)}


# ── Daily Quests ─────────────────────────────────────────────────────

@app.get("/api/quests/daily")
async def daily_quests():
    from life_xp.quests import get_todays_quests
    return await get_todays_quests(db_conn)


@app.post("/api/quests/{quest_id}/complete")
async def quest_complete(quest_id: int):
    from life_xp.quests import complete_quest
    return await complete_quest(db_conn, quest_id)


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
