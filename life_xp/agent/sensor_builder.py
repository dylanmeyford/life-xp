"""Self-extending sensor system — LLM reasons about and writes custom sensors."""

import ast
import json
import logging
import os
import platform
import shutil
import subprocess
import importlib.util
from pathlib import Path

import anthropic

from life_xp.sensors.base import Sensor, SensorEvent, SensorRegistry
from life_xp.database import get_connection, DATA_DIR

log = logging.getLogger(__name__)

CUSTOM_SENSORS_DIR = DATA_DIR / "custom-sensors"
MANIFEST_PATH = CUSTOM_SENSORS_DIR / "manifest.json"

MODEL = os.environ.get("LIFE_XP_MODEL", "claude-sonnet-4-20250514")


def get_system_capabilities() -> dict:
    """Discover what's available on this machine for tracking goals."""
    caps = {
        "os": platform.system(),
        "os_version": platform.version(),
        "has_applescript": shutil.which("osascript") is not None,
        "has_shortcuts": shutil.which("shortcuts") is not None,
        "has_git": shutil.which("git") is not None,
        "has_sqlite3": shutil.which("sqlite3") is not None,
        "installed_apps": [],
        "available_clis": [],
    }

    # List installed macOS apps
    if platform.system() == "Darwin":
        apps_dir = Path("/Applications")
        if apps_dir.exists():
            caps["installed_apps"] = sorted([
                p.stem for p in apps_dir.glob("*.app")
            ])[:50]

    # Check for common CLIs
    for cli in ["brew", "node", "python3", "swift", "curl", "jq", "defaults"]:
        if shutil.which(cli):
            caps["available_clis"].append(cli)

    # Check for data directories
    caps["has_health_data"] = (DATA_DIR / "health").exists()
    caps["has_transaction_data"] = (DATA_DIR / "transactions").exists()
    caps["has_imessage_db"] = (
        Path.home() / "Library" / "Messages" / "chat.db"
    ).exists()

    return caps


def _load_sensor_examples() -> str:
    """Load existing sensor code as examples for the LLM."""
    base_path = Path(__file__).parent.parent / "sensors"

    examples = []

    # Load base class
    base_file = base_path / "base.py"
    if base_file.exists():
        examples.append(f"# === base.py (Sensor base class) ===\n{base_file.read_text()}")

    # Load one concrete sensor as example
    steps_file = base_path / "steps.py"
    if steps_file.exists():
        examples.append(f"# === steps.py (Example sensor) ===\n{steps_file.read_text()}")

    return "\n\n".join(examples)


async def propose_tracking_strategies(goal: dict) -> dict:
    """Ask the LLM to propose multiple tracking strategies for a goal.

    Instead of auto-selecting one approach, this returns multiple options
    so the user can pick their preferred tracking method.

    Returns:
        dict with "strategies" list and "goal_id"
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"goal_id": goal["id"], "strategies": [], "error": "No API key configured"}

    system_info = get_system_capabilities()
    client = anthropic.Anthropic(api_key=api_key)

    strategy_prompt = f"""I need to track progress on this goal on the user's computer. Think creatively about ALL possible approaches — automated AND manual.

Goal: "{goal['title']}"
Description: {goal.get('description', 'none')}
Category: {goal.get('category_name', '')}
Goal Type: {goal.get('goal_type', 'qualitative')}
Recurrence: {goal.get('recurrence', 'none')}

Available system capabilities:
{json.dumps(system_info, indent=2)}

Propose 2-4 different tracking strategies, from most automated to most manual. Consider:
- AppleScript / CLI automation (fully automatic)
- File system monitoring (semi-automatic)
- Browser-based tools or APIs the user could set up (user-assisted)
- Manual check-in with LLM coaching (fallback)

For each strategy, explain what it does and what the user needs to do (if anything) to set it up.

Respond with a JSON array of strategies:
[
    {{
        "id": 1,
        "label": "Short name (e.g. 'AppleScript Screen Time')",
        "approach": "Detailed description of the strategy",
        "data_source": "applescript|filesystem|cli|database|browser|api|manual",
        "setup_required": "What the user needs to do to enable this (or 'None' if fully automatic)",
        "check_command": "The command or path to check (if applicable)",
        "confidence": 0.0-1.0,
        "automation_level": "automatic|semi-automatic|user-assisted|manual"
    }}
]

Always include a "Manual check-in" option as the last strategy (confidence 1.0, automation_level "manual").
Only output the JSON array."""

    strategy_msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system="You are an expert at macOS automation, AppleScript, and local system introspection. You help design creative solutions for tracking real-world activities using computer tools. Think broadly about what's possible.",
        messages=[{"role": "user", "content": strategy_prompt}],
    )

    try:
        text = strategy_msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        strategies = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        log.warning("Failed to parse tracking strategies from LLM")
        strategies = []

    # Always ensure manual fallback exists
    has_manual = any(s.get("automation_level") == "manual" for s in strategies)
    if not has_manual:
        strategies.append({
            "id": len(strategies) + 1,
            "label": "Manual check-in",
            "approach": "You manually mark progress each day. The coaching AI will ask you about your progress and help keep you accountable.",
            "data_source": "manual",
            "setup_required": "None",
            "check_command": "",
            "confidence": 1.0,
            "automation_level": "manual",
        })

    # Store strategies in DB for later selection
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO sensor_strategies (goal_id, strategies_json, selected)
           VALUES (?, ?, 0)""",
        (goal["id"], json.dumps(strategies)),
    )
    conn.commit()
    conn.close()

    log.info(f"Proposed {len(strategies)} tracking strategies for '{goal['title']}'")
    return {"goal_id": goal["id"], "strategies": strategies}


async def select_tracking_strategy(goal_id: int, strategy_index: int) -> dict:
    """User selected a tracking strategy — now build the sensor if needed.

    Args:
        goal_id: The goal to build a sensor for
        strategy_index: Index (0-based) into the proposed strategies list

    Returns:
        dict with "success", "approach", optionally "filename"
    """
    from life_xp.engine import get_goal

    conn = get_connection()
    row = conn.execute(
        "SELECT strategies_json FROM sensor_strategies WHERE goal_id = ?",
        (goal_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"success": False, "reason": "No strategies proposed for this goal"}

    strategies = json.loads(row[0])
    if strategy_index < 0 or strategy_index >= len(strategies):
        return {"success": False, "reason": "Invalid strategy index"}

    strategy = strategies[strategy_index]
    goal = get_goal(goal_id)
    if not goal:
        return {"success": False, "reason": "Goal not found"}

    # Mark the strategy as selected
    conn = get_connection()
    conn.execute(
        "UPDATE sensor_strategies SET selected = 1, selected_index = ? WHERE goal_id = ?",
        (strategy_index, goal_id),
    )
    conn.commit()
    conn.close()

    # If manual, no sensor needed — just update goal context
    if strategy.get("automation_level") == "manual":
        conn = get_connection()
        conn.execute(
            "UPDATE goals SET llm_context = ?, sensor_attempted = 1 WHERE id = ?",
            (f"Tracking: manual check-in. {strategy['approach']}", goal_id),
        )
        conn.commit()
        conn.close()
        return {
            "success": True,
            "approach": strategy["approach"],
            "automation_level": "manual",
        }

    # For automated/semi-automated strategies, build the sensor
    return await _build_sensor_from_strategy(goal, strategy)


async def _build_sensor_from_strategy(goal: dict, strategy: dict) -> dict:
    """Build a custom sensor from a selected strategy."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"success": False, "reason": "No API key configured"}

    sensor_examples = _load_sensor_examples()
    client = anthropic.Anthropic(api_key=api_key)

    code_prompt = f"""Write a Python sensor class that implements the tracking strategy below.

Goal: "{goal['title']}"
Strategy: {strategy['approach']}
Data source: {strategy['data_source']}
Check command: {strategy.get('check_command', '')}

Here are the existing sensor base class and an example sensor for reference:

{sensor_examples}

Requirements:
1. Subclass Sensor from life_xp.sensors.base
2. Set sensor_type = "custom_{{goal_id}}" where goal_id = {goal['id']}
3. Implement is_available() — return True only if the required tools exist
4. Implement check(config) — return a list of SensorEvent when the condition is met
5. Use subprocess with timeout=10 for any shell commands
6. Handle ALL exceptions gracefully (return empty list on error)
7. Do NOT import anything beyond: subprocess, platform, json, os, pathlib, datetime
8. Do NOT make any network requests
9. Do NOT write files outside ~/.life-xp/
10. The class MUST be named CustomSensor

Output ONLY the Python code. No markdown fences, no explanation."""

    code_msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system="You are an expert Python developer writing production sensor code. Write clean, safe, robust code with proper error handling.",
        messages=[{"role": "user", "content": code_prompt}],
    )

    code = code_msg.content[0].text.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1].rsplit("```", 1)[0]

    validation = _validate_sensor_code(code)
    if not validation["safe"]:
        log.warning(f"Generated sensor failed validation: {validation['reason']}")
        return {
            "success": False,
            "reason": f"Generated code failed safety check: {validation['reason']}",
            "approach": strategy["approach"],
        }

    filename = f"goal_{goal['id']}_{_slugify(goal['title'])}.py"
    _save_custom_sensor(goal, code, filename, strategy)

    return {
        "success": True,
        "approach": strategy["approach"],
        "filename": filename,
        "confidence": strategy.get("confidence", 0),
        "automation_level": strategy.get("automation_level", "automatic"),
    }


async def build_custom_sensor(goal: dict) -> dict:
    """Auto-build a sensor (used by agent loop for unattended sensor building).

    For interactive use, prefer propose_tracking_strategies() + select_tracking_strategy().

    Returns:
        dict with "success" (bool), "approach" (str), "filename" (str if success),
        and "needs_user_input" (bool) if strategies should be presented to user.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"success": False, "reason": "No API key configured"}

    # When called from agent loop, propose strategies and queue notification
    # so user can choose from the UI
    result = await propose_tracking_strategies(goal)
    strategies = result.get("strategies", [])

    if not strategies:
        return {"success": False, "reason": "Failed to generate tracking strategies"}

    # Queue a notification asking the user to choose
    from life_xp.engine import queue_notification
    queue_notification(
        title=f"How should I track '{goal['title']}'?",
        message=f"I found {len(strategies)} ways to track this goal. Open the app to choose your preferred method.",
        notification_type="sensor",
        action_type="choose_sensor",
        action_data=json.dumps({"goal_id": goal["id"]}),
    )

    return {
        "success": False,
        "needs_user_input": True,
        "strategies_count": len(strategies),
        "goal_id": goal["id"],
    }


def _validate_sensor_code(code: str) -> dict:
    """Validate generated sensor code for safety and correctness."""
    # Check syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"safe": False, "reason": f"Syntax error: {e}"}

    # Check for dangerous imports
    dangerous_modules = {"requests", "urllib", "http", "socket", "ftplib", "smtplib", "email"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in dangerous_modules:
                    return {"safe": False, "reason": f"Dangerous import: {alias.name}"}
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in dangerous_modules:
                return {"safe": False, "reason": f"Dangerous import: {node.module}"}

    # Check for dangerous function calls
    dangerous_funcs = {"eval", "exec", "compile", "__import__", "open"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in dangerous_funcs:
                # Allow open() for reading files in ~/.life-xp/
                if node.func.id != "open":
                    return {"safe": False, "reason": f"Dangerous function call: {node.func.id}"}

    # Check that CustomSensor class exists
    has_class = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CustomSensor":
            has_class = True
            break

    if not has_class:
        return {"safe": False, "reason": "No CustomSensor class found"}

    return {"safe": True, "reason": "OK"}


def _save_custom_sensor(goal: dict, code: str, filename: str, strategy: dict):
    """Save the custom sensor code and update the manifest."""
    CUSTOM_SENSORS_DIR.mkdir(parents=True, exist_ok=True)

    # Write the sensor file
    sensor_path = CUSTOM_SENSORS_DIR / filename
    sensor_path.write_text(code)

    # Update manifest
    manifest = _load_manifest()
    manifest["sensors"] = [s for s in manifest.get("sensors", []) if s["filename"] != filename]
    manifest["sensors"].append({
        "filename": filename,
        "goal_id": goal["id"],
        "goal_title": goal["title"],
        "approach": strategy.get("approach", ""),
        "confidence": strategy.get("confidence", 0),
        "enabled": True,
        "created_at": __import__("datetime").datetime.now().isoformat(),
    })
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    # Also create a sensor_config entry in the database
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO sensor_configs (sensor_type, goal_id, config_json, enabled)
           VALUES (?, ?, ?, 1)""",
        (f"custom_{goal['id']}", goal["id"], json.dumps({"filename": filename})),
    )
    conn.commit()
    conn.close()

    log.info(f"Saved custom sensor: {filename} for goal '{goal['title']}'")


def _load_manifest() -> dict:
    """Load the custom sensors manifest."""
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"sensors": []}


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    import re
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", slug).strip("_")[:40]
