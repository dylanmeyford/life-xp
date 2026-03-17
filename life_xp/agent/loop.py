"""Agent loop — the brain of Life XP.

Uses Claude's tool-use API to autonomously plan goals, discover integrations,
build sensors, and award XP. The agent is invoked when:
  1. A user creates a new goal (onboarding flow)
  2. A user sends a chat message
  3. A sensor produces a new reading (background check)
  4. A scheduled tick fires (periodic review)
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from life_xp.agent.tools import TOOL_DEFINITIONS, execute_tool
from life_xp.database import fetch_all, fetch_one, insert

MODEL = os.environ.get("LIFE_XP_MODEL", "claude-sonnet-4-20250514")

SYSTEM_PROMPT = """\
You are the Life XP Coach — an AI agent that helps users gamify their real life.

Your job is to:
1. Break down vague goals into concrete, measurable sub-goals
2. Figure out the BEST way to automatically track each goal
3. Build and test integrations (sensors) so tracking is hands-free
4. Award XP as the user makes progress
5. Keep the user motivated with encouragement and insights

INTEGRATION DISCOVERY STRATEGY:
When a user sets a goal, think about how to track it automatically:
- Health goals (weight, steps, exercise): Try Apple HealthKit via the Swift helper first,
  then Withings/Fitbit APIs, then manual entry as fallback
- Finance goals: Check for bank APIs, Plaid, CSV imports, or manual entry
- Learning goals: Track via git commits, course platform APIs, or study timer CLIs
- Productivity goals: Screen time APIs, app usage tracking, calendar integration
- Custom goals: Ask the user how they currently track it, then automate that

SENSOR RULES:
- Each goal may have EXACTLY ONE sensor. Never create multiple sensors for the same goal.
- Use build_sensor only when a goal has no sensor yet.
- Use replace_sensor to swap a goal's existing sensor for a different one (deletes old + creates new).
- Use delete_sensor to remove a sensor without replacement (e.g. broken or no longer needed).
- If build_sensor returns an error saying a sensor already exists, use replace_sensor instead.
- Always test new sensors with test_sensor after building or replacing.

IMPORTANT RULES:
- Always use plan_subgoals first to break down a new goal
- Then use discover_integrations to find tracking options
- Present the best strategy to the user via ask_user before building
- Always test sensors with test_sensor before activating them
- Award small XP (10-25) for completing setup steps
- Award larger XP (50-200) for achieving sub-goals
- Be encouraging but not annoying
- If something fails, explain why and try an alternative approach

GUIDING THE USER THROUGH SETUP:
- You are a coach, NOT an API client. Never make raw HTTP/API calls yourself.
- When a user needs to set up an integration (get API keys, test endpoints, etc.),
  walk them through it step by step with clear instructions.
- Provide ready-to-use curl commands or code snippets the user can copy and run.
  Always wrap these in fenced code blocks (```bash, ```json, etc.) so they render
  nicely in the chat UI.
- Example: instead of calling the Fitbit API yourself, show the user:
  ```bash
  curl -X GET "https://api.fitbit.com/1/user/-/profile.json" \
    -H "Authorization: Bearer YOUR_TOKEN"
  ```
- When explaining config values or JSON structures, use fenced code blocks too.
- Keep instructions concise — one step at a time, not a wall of text.

TOKEN & AUTH LIFECYCLE:
- API sensors with expiring tokens (OAuth, JWT, custom) are refreshed automatically.
- The system supports these auth_type values for API sensors:
  • "oauth" — uses refresh_token to get new access tokens (Fitbit, Withings, etc.)
  • "jwt" — re-authenticates using client credentials or a custom refresh endpoint
  • "api_key" — static keys that don't expire, no refresh needed
  • "custom" — configurable refresh via token_url and refresh_body
- When building API sensors, always set auth_type and include token_url + credentials
  so the system can refresh tokens automatically.
- If a sensor shows "error: 401", automatic refresh failed. Suggest re-authentication.
- You do NOT need to handle token refresh yourself — the system does it automatically.

You have access to the user's goal data and can read sensor outputs.
Respond conversationally but take actions proactively using your tools.
"""


class AgentLoop:
    """Runs Claude with tool-use in a loop until the agent stops or asks the user."""

    def __init__(self, db):
        self.db = db
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    async def run(
        self,
        user_message: str,
        goal_id: int | None = None,
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        """Run the agent loop. Returns the full message history including agent responses."""

        # Build context about current goals/state
        context = await self._build_context(goal_id)

        # Initialize or continue conversation
        messages = list(conversation_history or [])
        if context:
            # Inject context as a system-adjacent user message if starting fresh
            if not messages:
                messages.append({"role": "user", "content": f"[Current state]\n{context}\n\n{user_message}"})
            else:
                messages.append({"role": "user", "content": user_message})
        else:
            messages.append({"role": "user", "content": user_message})

        # Store user message
        await insert(self.db, "agent_messages", {
            "goal_id": goal_id,
            "role": "user",
            "content": user_message,
        })

        # Agent loop — keep going until Claude stops using tools or asks the user
        max_iterations = 15
        for _ in range(max_iterations):
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # Process response content blocks
            assistant_content = response.content
            text_parts = []
            tool_uses = []
            ask_user_result = None

            for block in assistant_content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_content})

            # Store text response
            if text_parts:
                await insert(self.db, "agent_messages", {
                    "goal_id": goal_id,
                    "role": "assistant",
                    "content": "\n".join(text_parts),
                })

            # If no tool use, we're done
            if not tool_uses:
                break

            # Execute all tool calls and collect results
            tool_results = []
            for tool_use in tool_uses:
                result = await execute_tool(self.db, tool_use.name, tool_use.input)

                # Store tool interaction
                await insert(self.db, "agent_messages", {
                    "goal_id": goal_id,
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_use": json.dumps({"name": tool_use.name, "input": tool_use.input}),
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })

                # If this is an ask_user, we need to pause and wait for user response
                if tool_use.name == "ask_user":
                    ask_user_result = result

            # Add tool results to conversation
            messages.append({"role": "user", "content": tool_results})

            # If agent asked a question, break the loop and return
            # The frontend will show the question and send the answer back
            if ask_user_result:
                break

            # If Claude says stop, stop
            if response.stop_reason == "end_turn":
                break

        return self._extract_response(messages)

    async def _build_context(self, goal_id: int | None) -> str:
        """Build context string about the current state."""
        parts = []

        # Player stats
        from life_xp.xp import get_player_stats
        stats = await get_player_stats(self.db)
        parts.append(f"Player: Level {stats.level} {stats.title} ({stats.total_xp} XP)")

        if goal_id:
            goal = await fetch_one(self.db, "SELECT * FROM goals WHERE id = ?", (goal_id,))
            if goal:
                parts.append(f"\nFocused Goal: {goal['title']} (target: {goal['target']}, status: {goal['status']})")

                sub_goals = await fetch_all(
                    self.db, "SELECT * FROM sub_goals WHERE goal_id = ? ORDER BY sort_order", (goal_id,)
                )
                if sub_goals:
                    parts.append("Sub-goals:")
                    for sg in sub_goals:
                        parts.append(f"  {'[x]' if sg['status'] == 'completed' else '[ ]'} {sg['title']} ({sg['status']})")

                sensors = await fetch_all(
                    self.db, "SELECT * FROM sensor_configs WHERE goal_id = ?", (goal_id,)
                )
                if sensors:
                    parts.append("Sensors:")
                    for s in sensors:
                        parts.append(f"  - {s['sensor_type']} ({s['status']}): last={s['last_value']}")
        else:
            # Show all active goals
            goals = await fetch_all(self.db, "SELECT * FROM goals WHERE status = 'active'")
            if goals:
                parts.append(f"\nActive Goals ({len(goals)}):")
                for g in goals:
                    parts.append(f"  - [{g['id']}] {g['title']} → {g['target']}")

        return "\n".join(parts)

    def _extract_response(self, messages: list[dict]) -> list[dict]:
        """Extract a clean response from the message history for the frontend."""
        result = []
        for msg in messages:
            if msg["role"] == "assistant":
                content = msg["content"]
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "type"):
                            if block.type == "text":
                                result.append({"role": "assistant", "content": block.text})
                            elif block.type == "tool_use":
                                result.append({
                                    "role": "tool_use",
                                    "tool": block.name,
                                    "input": block.input,
                                })
                elif isinstance(content, str):
                    result.append({"role": "assistant", "content": content})
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, str):
                    result.append({"role": "user", "content": content})
                elif isinstance(content, list):
                    # Tool results — check for ask_user questions
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_result":
                            try:
                                data = json.loads(item["content"])
                                if data.get("type") == "question":
                                    result.append({
                                        "role": "question",
                                        "question": data["question"],
                                        "options": data.get("options", []),
                                    })
                            except (json.JSONDecodeError, KeyError):
                                pass
        return result
