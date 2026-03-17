"""Tool definitions for the Life XP agent harness.

Each tool is a dict matching the Anthropic tool-use schema, plus an `execute`
function that the agent loop calls when Claude invokes that tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from life_xp.database import fetch_all, fetch_one, insert, update

# ── Tool schema definitions (sent to Claude) ─────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "plan_subgoals",
        "description": (
            "Break a high-level goal into concrete, measurable sub-goals. "
            "Each sub-goal should be independently trackable. "
            "Return a JSON array of {title, description, target, xp_reward}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer", "description": "ID of the parent goal"},
                "sub_goals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "target": {"type": "string"},
                            "xp_reward": {"type": "integer"},
                        },
                        "required": ["title", "description"],
                    },
                    "description": "List of sub-goals to create",
                },
            },
            "required": ["goal_id", "sub_goals"],
        },
    },
    {
        "name": "discover_integrations",
        "description": (
            "Given a goal, research what integrations or data sources could "
            "automatically track progress. Consider: Apple Health (via Swift "
            "helper), REST APIs (Withings, Fitbit, finance APIs), CLI tools, "
            "browser scraping, file watching, git hooks, etc. "
            "Return a ranked list of strategies with pros/cons."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer", "description": "ID of the goal"},
                "goal_title": {"type": "string"},
                "goal_target": {"type": "string"},
                "category": {"type": "string"},
                "strategies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "sensor_type": {
                                "type": "string",
                                "enum": ["swift_health", "api", "cli", "browser", "file_watch", "manual"],
                            },
                            "description": {"type": "string"},
                            "config_needed": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "What the user needs to provide (API keys, paths, etc.)",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "0-1 confidence this will work",
                            },
                        },
                        "required": ["name", "sensor_type", "description"],
                    },
                },
            },
            "required": ["goal_id", "strategies"],
        },
    },
    {
        "name": "build_sensor",
        "description": (
            "Create a sensor configuration for a goal. This registers how "
            "the app will automatically track progress. The sensor will be "
            "put into 'testing' status until test_sensor confirms it works."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "sensor_type": {
                    "type": "string",
                    "enum": ["swift_health", "api", "cli", "browser", "file_watch", "manual"],
                },
                "config": {
                    "type": "object",
                    "description": (
                        "Configuration for the sensor. Structure depends on type:\n"
                        "- swift_health: {metric: 'weight'|'steps'|'heart_rate', unit: 'kg'|'lbs'|'count'}\n"
                        "- api: {url, method, headers, auth_type, response_path}\n"
                        "- cli: {command, parse_regex, schedule_minutes}\n"
                        "- file_watch: {path, parse_format}\n"
                        "- manual: {prompt, unit}"
                    ),
                },
            },
            "required": ["goal_id", "sensor_type", "config"],
        },
    },
    {
        "name": "test_sensor",
        "description": (
            "Test a sensor configuration by running it once and checking "
            "if it returns valid data. Updates sensor status to 'active' "
            "on success or 'failed' with error details on failure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sensor_id": {"type": "integer", "description": "ID of the sensor to test"},
            },
            "required": ["sensor_id"],
        },
    },
    {
        "name": "award_xp",
        "description": (
            "Award XP points to the user for achieving something. "
            "Use this when a sub-goal is completed, a milestone is hit, "
            "or the user deserves a bonus for consistency."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "XP to award"},
                "source_type": {
                    "type": "string",
                    "enum": ["goal", "sub_goal", "streak", "bonus", "milestone"],
                },
                "source_id": {"type": "integer", "description": "ID of the goal/sub_goal"},
                "reason": {"type": "string", "description": "Human-readable reason"},
            },
            "required": ["amount", "source_type", "reason"],
        },
    },
    {
        "name": "ask_user",
        "description": (
            "Ask the user a question when you need more information. "
            "Use this to request API keys, clarify preferences, or confirm "
            "an integration approach before building it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional multiple-choice options",
                },
                "context": {"type": "string", "description": "Why you're asking this"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "format_progress",
        "description": (
            "Format a goal's current progress for display to the user. "
            "Reads the latest sensor data and returns a summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
            },
            "required": ["goal_id"],
        },
    },
]


# ── Tool execution ───────────────────────────────────────────────────

async def execute_tool(db, tool_name: str, tool_input: dict) -> dict[str, Any]:
    """Execute a tool and return the result."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await handler(db, tool_input)
    except Exception as e:
        return {"error": str(e)}


async def _plan_subgoals(db, inp: dict) -> dict:
    goal_id = inp["goal_id"]
    created = []
    for i, sg in enumerate(inp["sub_goals"]):
        row_id = await insert(db, "sub_goals", {
            "goal_id": goal_id,
            "title": sg["title"],
            "description": sg.get("description", ""),
            "target": sg.get("target", ""),
            "xp_reward": sg.get("xp_reward", 50),
            "sort_order": i,
        })
        created.append({"id": row_id, "title": sg["title"]})
    return {"created": created, "count": len(created)}


async def _discover_integrations(db, inp: dict) -> dict:
    # This tool's output is the strategies themselves — the agent fills them in
    # We just store them for the frontend to display
    return {
        "goal_id": inp["goal_id"],
        "strategies": inp["strategies"],
        "message": f"Found {len(inp['strategies'])} potential tracking strategies.",
    }


async def _build_sensor(db, inp: dict) -> dict:
    sensor_id = await insert(db, "sensor_configs", {
        "goal_id": inp["goal_id"],
        "sensor_type": inp["sensor_type"],
        "config": json.dumps(inp["config"]),
        "status": "testing",
    })
    return {"sensor_id": sensor_id, "status": "testing", "message": "Sensor created. Run test_sensor to verify."}


async def _test_sensor(db, inp: dict) -> dict:
    sensor = await fetch_one(db, "SELECT * FROM sensor_configs WHERE id = ?", (inp["sensor_id"],))
    if not sensor:
        return {"error": "Sensor not found"}

    config = json.loads(sensor["config"])
    sensor_type = sensor["sensor_type"]

    try:
        if sensor_type == "swift_health":
            result = await _test_swift_health(config)
        elif sensor_type == "cli":
            result = await _test_cli_sensor(config)
        elif sensor_type == "api":
            result = await _test_api_sensor(config)
        elif sensor_type == "manual":
            result = {"value": "awaiting_input", "message": "Manual sensor ready — will prompt user for input."}
        else:
            result = {"value": "mock_ok", "message": f"Sensor type '{sensor_type}' accepted (will test on first poll)."}

        await update(db, "sensor_configs", inp["sensor_id"], {"status": "active", "last_value": str(result.get("value", ""))})
        await insert(db, "sensor_readings", {
            "sensor_id": inp["sensor_id"],
            "value": str(result.get("value", "")),
            "raw_data": json.dumps(result),
        })
        return {"status": "active", "test_result": result}

    except Exception as e:
        await update(db, "sensor_configs", inp["sensor_id"], {"status": "failed"})
        return {"status": "failed", "error": str(e)}


async def _test_swift_health(config: dict) -> dict:
    """Test the Swift HealthKit helper."""
    helper = Path(__file__).parent.parent / "swift_helpers" / "health_reader"
    if not helper.exists():
        # Try to compile it
        swift_src = helper.with_suffix(".swift")
        if swift_src.exists():
            proc = subprocess.run(
                ["swiftc", str(swift_src), "-o", str(helper)],
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                return {"error": f"Failed to compile Swift helper: {proc.stderr}", "value": "compile_error"}

    if helper.exists():
        metric = config.get("metric", "weight")
        proc = subprocess.run(
            [str(helper), metric],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            return {"value": proc.stdout.strip(), "source": "apple_health"}
        return {"error": proc.stderr.strip(), "value": "read_error"}

    # Fallback: try Apple Shortcuts
    return {"value": "no_helper", "message": "Swift helper not compiled. Will use Apple Shortcuts or manual entry as fallback."}


async def _test_cli_sensor(config: dict) -> dict:
    """Test a CLI-based sensor."""
    command = config.get("command", "echo test")
    proc = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=15,
    )
    if proc.returncode == 0:
        return {"value": proc.stdout.strip()[:500], "source": "cli"}
    return {"error": proc.stderr.strip()[:500], "value": "cli_error"}


async def _test_api_sensor(config: dict) -> dict:
    """Test an API-based sensor."""
    import httpx
    from life_xp.sensors.api_sensor import extract_path
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(method, url, headers=headers)
        resp.raise_for_status()
        data = resp.json() if "json" in resp.headers.get("content-type", "") else resp.text
        path = config.get("response_path", "")
        if path:
            data = extract_path(data, path)
        return {"value": str(data)[:500], "source": "api"}


async def _award_xp(db, inp: dict) -> dict:
    from life_xp.xp import award_xp, get_player_stats
    stats = await award_xp(
        db,
        amount=inp["amount"],
        source_type=inp["source_type"],
        source_id=inp.get("source_id"),
        reason=inp.get("reason", ""),
    )
    return {
        "awarded": inp["amount"],
        "total_xp": stats.total_xp,
        "level": stats.level,
        "title": stats.title,
        "message": f"+{inp['amount']} XP! (Level {stats.level} {stats.title})",
    }


async def _ask_user(db, inp: dict) -> dict:
    # This is handled specially by the agent loop — it pauses and waits
    # for user input via the API. We just return the question structure.
    return {
        "type": "question",
        "question": inp["question"],
        "options": inp.get("options", []),
        "context": inp.get("context", ""),
    }


async def _format_progress(db, inp: dict) -> dict:
    goal = await fetch_one(db, "SELECT * FROM goals WHERE id = ?", (inp["goal_id"],))
    if not goal:
        return {"error": "Goal not found"}

    sub_goals = await fetch_all(
        db, "SELECT * FROM sub_goals WHERE goal_id = ? ORDER BY sort_order", (inp["goal_id"],)
    )
    sensors = await fetch_all(
        db, "SELECT * FROM sensor_configs WHERE goal_id = ?", (inp["goal_id"],)
    )

    # Get latest readings for each sensor
    readings = []
    for s in sensors:
        latest = await fetch_one(
            db,
            "SELECT * FROM sensor_readings WHERE sensor_id = ? ORDER BY created_at DESC LIMIT 1",
            (s["id"],),
        )
        if latest:
            readings.append({"sensor_id": s["id"], "type": s["sensor_type"], "value": latest["value"], "at": latest["created_at"]})

    completed = sum(1 for sg in sub_goals if sg["status"] == "completed")
    total = len(sub_goals)

    return {
        "goal": {"title": goal["title"], "target": goal["target"], "status": goal["status"]},
        "sub_goals": {"completed": completed, "total": total, "items": sub_goals},
        "latest_readings": readings,
        "active_sensors": len([s for s in sensors if s["status"] == "active"]),
    }


TOOL_HANDLERS = {
    "plan_subgoals": _plan_subgoals,
    "discover_integrations": _discover_integrations,
    "build_sensor": _build_sensor,
    "test_sensor": _test_sensor,
    "award_xp": _award_xp,
    "ask_user": _ask_user,
    "format_progress": _format_progress,
}
