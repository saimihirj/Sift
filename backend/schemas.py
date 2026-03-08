"""Pydantic schemas for the FastAPI backend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


FounderType = Literal["student", "professional", "founder", "serial", "unknown"]
Sector = Literal["saas", "d2c", "fintech", "marketplace", "edtech", "healthtech", "deeptech", "unknown"]
Stage = Literal["idea", "pre-revenue", "early-revenue", "growth", "unknown"]
Mode = Literal["think_it_through", "quick_stress_test"]
ResponseProfile = Literal["speed", "balanced"]
SessionType = Literal["mentor", "evaluator"]
Provider = Literal["ollama", "cerebras", "groq", "openai", "openrouter", "anthropic", "gemini"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CoverageItem(BaseModel):
    section: str
    score: int
    label: str


class EvaluationQuestion(BaseModel):
    id: str
    text: str
    baseText: str = ""
    contextHint: str = ""
    contextMode: str = "explore"
    category: str
    weightTier: str


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float


class LensAssessment(BaseModel):
    key: str
    label: str
    status: str
    score: float
    why: str = ""
    evidence: list[str] = Field(default_factory=list)
    improvement: str = ""


class QuestionScore(BaseModel):
    questionId: str
    question: str
    category: str
    score: float
    why: str
    suggestions: list[str] = Field(default_factory=list)


class EvaluationProgress(BaseModel):
    questionBudget: int = 15
    answeredQuestions: int = 0
    questionsAsked: int = 0
    maxQuestions: int = 12
    completed: bool = False
    partial: bool = False
    currentQuestion: EvaluationQuestion | None = None
    currentScore: float = 0.0
    dimensionScores: list[DimensionScore] = Field(default_factory=list)
    website: dict[str, Any] = Field(default_factory=dict)
    lastFeedback: str = ""
    stopReason: str = ""
    canGoDeeper: bool = False


class EvaluationReport(BaseModel):
    overallScore: float
    partial: bool
    answeredQuestions: int
    questionBudget: int
    dimensionScores: list[DimensionScore] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    questions: list[QuestionScore] = Field(default_factory=list)
    summary: str = ""
    verdict: str = ""
    confidence: float = 0.0
    stopReason: str = ""
    coreLenses: list[LensAssessment] = Field(default_factory=list)
    supportingLenses: list[LensAssessment] = Field(default_factory=list)
    missingEvidence: list[str] = Field(default_factory=list)
    nextExperiments: list[str] = Field(default_factory=list)


class StartSessionRequest(BaseModel):
    founderType: FounderType = "unknown"
    sector: Sector = "unknown"
    stage: Stage = "unknown"
    mode: Mode = "think_it_through"
    geography: str = "unspecified"
    sessionType: SessionType = "mentor"
    questionBudget: int | None = None
    provider: Provider = "ollama"
    model: str = ""
    apiKey: str = ""
    websiteUrl: str = ""
    setupContext: str = ""
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
    sessionType: SessionType = "mentor"
    provider: str = "ollama"
    model: str = ""
    questionBudget: int | None = None


class SessionResponse(BaseModel):
    sessionId: str
    history: list[ChatTurn]
    state: dict[str, Any]
    chips: list[str]
    responseProfile: ResponseProfile
    coverage: list[CoverageItem]
    nextGap: str
    activeUploads: list[dict[str, Any]] = Field(default_factory=list)
    sessionType: SessionType = "mentor"
    provider: str = "ollama"
    model: str = ""
    questionBudget: int | None = None
    websiteUrl: str = ""
    evaluationProgress: EvaluationProgress | None = None
    evaluationReport: EvaluationReport | None = None


class StartSessionResponse(BaseModel):
    sessionId: str
    openingMessage: str
    state: dict[str, Any]
    chips: list[str]
    responseProfile: ResponseProfile
    coverage: list[CoverageItem]
    nextGap: str
    activeUploads: list[dict[str, Any]] = Field(default_factory=list)
    sessionType: SessionType = "mentor"
    provider: str = "ollama"
    model: str = ""
    questionBudget: int | None = None
    websiteUrl: str = ""
    evaluationProgress: EvaluationProgress | None = None
    evaluationReport: EvaluationReport | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary] = Field(default_factory=list)


class SessionRuntimeUpdateRequest(BaseModel):
    provider: Provider = "ollama"
    model: str = ""


class SessionRuntimeResponse(BaseModel):
    sessionId: str
    provider: str = "ollama"
    model: str = ""


class ClearHistoryRequest(BaseModel):
    clientId: str = ""


class ClearHistoryResponse(BaseModel):
    ok: bool = True
    sessionsDeleted: int = 0
    turnsDeleted: int = 0
    eventsDeleted: int = 0


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


class EvaluatorAnswerRequest(BaseModel):
    sessionId: str
    answer: str = ""
    apiKey: str = ""


class EvaluatorAnswerResponse(BaseModel):
    sessionId: str
    evaluationProgress: EvaluationProgress
    evaluationReport: EvaluationReport
    reciprocal: str
    question: EvaluationQuestion | None = None
    questionLabel: str = ""
    activeUploads: list[dict[str, Any]] = Field(default_factory=list)
    warning: str = ""


class EvaluatorReportResponse(BaseModel):
    sessionId: str
    evaluationReport: EvaluationReport
    evaluationProgress: EvaluationProgress
    provider: str = "ollama"
    model: str = ""
    websiteUrl: str = ""


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
    evaluatorSessions: int = 0
    evaluatorCompletions: int = 0
    evaluatorCompletionRate: float = 0.0
    averageSuccessScore: float = 0.0
    averageEvaluatorScore: float = 0.0
    websiteFetchFailures: int = 0
    dropOffQuestion: str = ""
    providerBreakdown: dict[str, int] = Field(default_factory=dict)
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
