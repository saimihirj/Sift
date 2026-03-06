"""Pydantic schemas for the FastAPI backend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


FounderType = Literal["student", "professional", "founder", "serial", "unknown"]
Sector = Literal["saas", "d2c", "fintech", "marketplace", "edtech", "healthtech", "deeptech", "unknown"]
Stage = Literal["idea", "pre-revenue", "early-revenue", "growth", "unknown"]
Mode = Literal["think_it_through", "quick_stress_test"]
ResponseProfile = Literal["speed", "balanced"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CoverageItem(BaseModel):
    section: str
    score: int
    label: str


class StartSessionRequest(BaseModel):
    founderType: FounderType = "unknown"
    sector: Sector = "unknown"
    stage: Stage = "unknown"
    mode: Mode = "think_it_through"
    clientId: str | None = None
    displayName: str | None = None


class SessionSummary(BaseModel):
    sessionId: str
    title: str
    subtitle: str
    lastActive: str | None = None
    turnCount: int = 0
    companyName: str = ""
    displayName: str = ""
    sector: str = "unknown"
    stage: str = "unknown"


class SessionResponse(BaseModel):
    sessionId: str
    history: list[ChatTurn]
    state: dict[str, Any]
    chips: list[str]
    responseProfile: ResponseProfile
    coverage: list[CoverageItem]
    nextGap: str
    activeUploads: list[dict[str, Any]] = Field(default_factory=list)


class StartSessionResponse(BaseModel):
    sessionId: str
    openingMessage: str
    state: dict[str, Any]
    chips: list[str]
    responseProfile: ResponseProfile
    coverage: list[CoverageItem]
    nextGap: str
    activeUploads: list[dict[str, Any]] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary] = Field(default_factory=list)


class HeartbeatRequest(BaseModel):
    clientId: str


class HeartbeatResponse(BaseModel):
    ok: bool = True


class OutlineRequest(BaseModel):
    sessionId: str


class OutlineResponse(BaseModel):
    sessionId: str
    markdown: str
    responseProfile: ResponseProfile


class AnalyticsEventRequest(BaseModel):
    eventType: str
    clientId: str = ""
    sessionId: str = ""
    displayName: str = ""
    pathname: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyticsEventResponse(BaseModel):
    ok: bool = True


class AdminOverviewResponse(BaseModel):
    totalSessions: int
    totalTurns: int
    totalEvents: int
    uniqueVisitors: int
    sessionsLast7Days: int
    eventsLast24Hours: int
    outlineOpens: int
    uploads: int
    chatCompletions: int
    averageFirstTokenSeconds: float
    averageTotalSeconds: float
    eventBreakdown: dict[str, int] = Field(default_factory=dict)


class AdminEvent(BaseModel):
    client_id: str = ""
    session_id: str = ""
    display_name: str = ""
    event_type: str
    pathname: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AdminEventsResponse(BaseModel):
    events: list[AdminEvent] = Field(default_factory=list)
    sessions: list[SessionSummary] = Field(default_factory=list)
