"""Pydantic models for API validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Goals ────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target: str = ""
    category: str = ""


class GoalOut(BaseModel):
    id: int
    title: str
    description: str | None
    target: str | None
    category: str | None
    status: str
    xp_reward: int
    created_at: str
    completed_at: str | None = None
    sub_goals: list[SubGoalOut] = []
    sensors: list[SensorOut] = []


# ── Sub-goals ────────────────────────────────────────────────────────

class SubGoalOut(BaseModel):
    id: int
    goal_id: int
    title: str
    description: str | None
    target: str | None
    status: str
    xp_reward: int
    sort_order: int


# ── Sensors ──────────────────────────────────────────────────────────

class SensorOut(BaseModel):
    id: int
    goal_id: int
    sensor_type: str
    config: str
    status: str
    last_run: str | None = None
    last_value: str | None = None


# ── XP ───────────────────────────────────────────────────────────────

class PlayerStatsOut(BaseModel):
    total_xp: int
    level: int
    title: str
    xp_current_level: int
    xp_next_level: int
    progress: float


class XpEvent(BaseModel):
    id: int
    amount: int
    source_type: str
    source_id: int | None
    reason: str | None
    created_at: str


# ── Agent / Chat ─────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str
    tool_use: str | None = None
    created_at: str | None = None


class ChatRequest(BaseModel):
    message: str
    goal_id: int | None = None


class AgentQuestionOut(BaseModel):
    """When the agent needs user input."""
    question: str
    options: list[str] = []
    goal_id: int | None = None


# ── Settings ─────────────────────────────────────────────────────────

class SettingUpdate(BaseModel):
    key: str
    value: str
