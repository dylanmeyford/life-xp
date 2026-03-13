"""Agent loop — runs every minute to monitor sensors, generate tasks, and send nudges."""

import asyncio
import logging
from datetime import datetime, date

from life_xp.database import get_connection
from life_xp.engine import (
    list_goals, list_habits, list_daily_tasks,
    create_daily_task, daily_tasks_generated_today,
    queue_notification, get_untracked_goals, mark_sensor_attempted,
)
from life_xp.sensors.base import SensorRegistry
from life_xp.sensors.custom_loader import load_custom_sensors

log = logging.getLogger(__name__)

# Track nudge times to avoid spamming
_last_nudge_hour: int = -1
_last_sensor_build_check: str = ""


async def agent_tick():
    """Single tick of the agent loop. Called every 60 seconds."""
    try:
        # 1. Load custom sensors (idempotent)
        load_custom_sensors()

        # 2. Import and register built-in sensors
        _ensure_sensors_imported()

        # 3. Run all sensors (built-in + custom)
        SensorRegistry.run_all()

        # 4. Morning: generate daily tasks if not yet done
        hour = datetime.now().hour
        if 6 <= hour <= 9 and not daily_tasks_generated_today():
            await _generate_morning_plan()

        # 5. Proactive nudges (max once per 3 hours)
        global _last_nudge_hour
        if hour != _last_nudge_hour and hour in (12, 15, 18, 21):
            _last_nudge_hour = hour
            await _send_nudge(hour)

        # 6. Check for new untracked goals → build custom sensors
        global _last_sensor_build_check
        today = date.today().isoformat()
        if _last_sensor_build_check != today:
            _last_sensor_build_check = today
            await _build_sensors_for_untracked_goals()

        # 7. Check for broken streaks at midnight
        if hour == 0:
            _check_broken_streaks()

        # 8. Check approaching deadlines
        _check_deadlines()

    except Exception as e:
        log.error(f"Agent tick failed: {e}", exc_info=True)


async def _generate_morning_plan():
    """Generate daily tasks using the LLM coach."""
    try:
        from life_xp.coach import generate_daily_plan

        tasks = await generate_daily_plan()
        if not tasks:
            return

        for task in tasks:
            create_daily_task(
                title=task.get("title", ""),
                goal_id=task.get("goal_id"),
                description=task.get("description", ""),
                xp_reward=task.get("xp_reward", 25),
                generated_by="llm",
            )

        queue_notification(
            "coaching",
            "Daily Plan Ready",
            f"You have {len(tasks)} tasks for today. Let's go!",
        )
        log.info(f"Generated {len(tasks)} daily tasks")
    except Exception as e:
        log.error(f"Failed to generate morning plan: {e}")


async def _send_nudge(hour: int):
    """Send a proactive nudge based on time of day."""
    try:
        from life_xp.coach import generate_nudge

        time_labels = {12: "midday", 15: "afternoon", 18: "evening", 21: "night"}
        time_of_day = time_labels.get(hour, "afternoon")

        nudge = await generate_nudge(time_of_day)
        if nudge:
            queue_notification("coaching", "Life XP Coach", nudge)
            log.info(f"Sent {time_of_day} nudge")
    except Exception as e:
        log.error(f"Failed to send nudge: {e}")


async def _build_sensors_for_untracked_goals():
    """Try to build custom sensors for goals that don't have any."""
    try:
        from life_xp.agent.sensor_builder import build_custom_sensor

        untracked = get_untracked_goals()
        for goal in untracked[:3]:  # Max 3 per day to limit API calls
            log.info(f"Attempting to build sensor for: {goal['title']}")
            result = await build_custom_sensor(goal)
            mark_sensor_attempted(goal["id"])

            if result.get("success"):
                queue_notification(
                    "sensor",
                    "New Sensor Created",
                    f"Auto-tracking '{goal['title']}' via: {result['approach']}",
                )
                log.info(f"Built sensor for '{goal['title']}': {result['approach']}")
            else:
                log.info(f"Could not build sensor for '{goal['title']}': {result.get('reason')}")
    except Exception as e:
        log.error(f"Failed to build sensors: {e}")


def _check_broken_streaks():
    """Check for habits whose streaks broke (no check yesterday)."""
    from life_xp.engine import list_habits

    habits = list_habits()
    for h in habits:
        if h.get("streak", 0) > 7 and not h.get("done_today"):
            queue_notification(
                "streak",
                f"Streak Warning: {h['title']}",
                f"Your {h['streak']}-day streak is at risk! Don't forget today.",
            )


def _check_deadlines():
    """Check for goals with approaching deadlines."""
    from life_xp.engine import list_goals
    from datetime import timedelta

    goals = list_goals("active")
    today = date.today()
    tomorrow = (today + timedelta(days=1)).isoformat()

    for g in goals:
        due = g.get("due_date")
        if due and due == tomorrow:
            queue_notification(
                "info",
                "Deadline Tomorrow",
                f"'{g['title']}' is due tomorrow!",
                action_type="open_goal",
                action_data=str(g["id"]),
            )


def _ensure_sensors_imported():
    """Import all built-in sensor modules to register them."""
    try:
        import life_xp.sensors.steps
        import life_xp.sensors.screentime
        import life_xp.sensors.git_sensor
        import life_xp.sensors.finance
        import life_xp.sensors.imessage
    except ImportError as e:
        log.warning(f"Failed to import built-in sensor: {e}")


async def run_agent_loop(interval: int = 60):
    """Main loop — runs agent_tick every `interval` seconds."""
    log.info(f"Agent loop started (interval={interval}s)")
    while True:
        await agent_tick()
        await asyncio.sleep(interval)
