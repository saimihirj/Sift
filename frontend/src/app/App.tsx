import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import type {
  ProviderOption,
  SessionPayload,
  SessionSummary,
  SetupDraft,
  StartSessionPayload,
  ThemeMode,
} from "./types";
import { clearSessionHistory, getAuthSession, getSession, listProviders, listSessions, postAnalyticsEvent, sendHeartbeat, startSession } from "../lib/api/client";
import { AdminScreen } from "../features/admin/AdminScreen";
import { ChatScreen } from "../features/chat/ChatScreen";
import { EvaluatorReportScreen } from "../features/evaluator/EvaluatorReportScreen";
import { EvaluatorScreen } from "../features/evaluator/EvaluatorScreen";
import { ExpertScreen } from "../features/expert/ExpertScreen";
import { LandingScreen } from "../features/onboarding/LandingScreen";
import { SetupWizard } from "../features/onboarding/SetupWizard";
import { OutlineScreen } from "../features/outline/OutlineScreen";
import { saveSessionCredential } from "../lib/sessionCredentials";
import { createWorkspaceIdentity, generateAccessKey, type WorkspaceIdentity } from "../lib/workspaceIdentity";

declare const __APP_BUILD__: string;

const SESSION_STORAGE_KEY = "sift-session-id";
const IDENTITY_STORAGE_KEY = "sift-beta-identity";
const THEME_STORAGE_KEY = "sift-theme";
const CLIENT_STORAGE_KEY = "sift-client-id";
const APP_BUILD_STORAGE_KEY = "sift-app-build";
const DEFAULT_PROVIDER_OPTIONS: ProviderOption[] = [
  {
    key: "ollama",
    label: "Ollama",
    requiresApiKey: false,
    defaultSpeedModel: "llama3.2:latest",
    defaultBalancedModel: "qwen3:8b",
    supportsVisionModels: true,
    recommendedDeckModel: "qwen2.5vl:7b",
    latencyHint: "Best when privacy matters and the user can run local models.",
    bestFor: "Local-first demos, private notes, and zero-key use.",
    speedLabel: "Llama 3.2 fast",
    balancedLabel: "Qwen3 sharper",
    publicReadiness: "Local install required",
    openWeight: true,
  },
  {
    key: "groq",
    label: "Groq",
    requiresApiKey: true,
    defaultSpeedModel: "openai/gpt-oss-20b",
    defaultBalancedModel: "openai/gpt-oss-120b",
    supportsVisionModels: true,
    recommendedDeckModel: "",
    latencyHint: "Very fast hosted open-weight lane for public MVP traffic.",
    bestFor: "Low-latency public launch with GPT-OSS or Llama-class models.",
    speedLabel: "GPT-OSS 20B",
    balancedLabel: "GPT-OSS 120B",
    publicReadiness: "Recommended hosted default",
    openWeight: true,
  },
  {
    key: "cerebras",
    label: "Cerebras",
    requiresApiKey: true,
    defaultSpeedModel: "gpt-oss-120b",
    defaultBalancedModel: "gpt-oss-120b",
    supportsVisionModels: false,
    recommendedDeckModel: "",
    latencyHint: "Fastest hosted open-weight throughput when the account tier supports it.",
    bestFor: "High-speed expert and evaluation turns on GPT-OSS 120B.",
    speedLabel: "GPT-OSS 120B",
    balancedLabel: "GPT-OSS 120B",
    publicReadiness: "Performance lane",
    openWeight: true,
  },
  {
    key: "openai",
    label: "OpenAI",
    requiresApiKey: true,
    defaultSpeedModel: "gpt-5.4-mini",
    defaultBalancedModel: "gpt-5.5",
    supportsVisionModels: true,
    recommendedDeckModel: "gpt-5.5",
    latencyHint: "Frontier quality for complex synthesis, deck reasoning, and polish.",
    bestFor: "Highest-quality public mode when cost is acceptable.",
    speedLabel: "GPT-5.4 mini",
    balancedLabel: "GPT-5.5",
    publicReadiness: "Frontier quality lane",
    openWeight: false,
  },
  {
    key: "openrouter",
    label: "OpenRouter",
    requiresApiKey: true,
    defaultSpeedModel: "openai/gpt-oss-20b",
    defaultBalancedModel: "openai/gpt-oss-120b",
    supportsVisionModels: true,
    recommendedDeckModel: "openai/gpt-5.5",
    latencyHint: "Flexible broker for comparing open-weight and closed frontier models.",
    bestFor: "Provider experiments without changing the app.",
    speedLabel: "GPT-OSS 20B",
    balancedLabel: "GPT-OSS 120B",
    publicReadiness: "Experiment lane",
    openWeight: true,
  },
  { key: "anthropic", label: "Anthropic", requiresApiKey: true, defaultSpeedModel: "claude-3-5-haiku-latest", defaultBalancedModel: "claude-3-7-sonnet-latest", supportsVisionModels: true, recommendedDeckModel: "claude-3-7-sonnet-latest", latencyHint: "Strong long-form synthesis with hosted API latency.", bestFor: "Careful narrative analysis and investor-style memo work.", speedLabel: "Haiku", balancedLabel: "Sonnet", publicReadiness: "Quality lane" },
  { key: "gemini", label: "Gemini", requiresApiKey: true, defaultSpeedModel: "gemini-2.0-flash", defaultBalancedModel: "gemini-1.5-pro", supportsVisionModels: true, recommendedDeckModel: "gemini-2.0-flash", latencyHint: "Fast hosted multimodal fallback for broad consumer access.", bestFor: "Affordable hosted analysis and deck-adjacent workflows.", speedLabel: "Flash", balancedLabel: "Pro", publicReadiness: "Multimodal lane" },
];
const DEFAULT_SETUP_DRAFT: SetupDraft = {
  runtimeKind: "external",
  provider: "groq",
  model: "openai/gpt-oss-20b",
  apiKey: "",
  founderType: "founder",
  sector: "saas",
  stage: "idea",
  geography: "auto",
  websiteUrl: "",
  setupContext: "",
  sessionType: "mentor",
  evaluatorMode: "idea_review",
  mode: "think_it_through",
  helpMode: "coach_me",
  liveWebEnabled: true,
};
function getClientId(): string {
  const existing = localStorage.getItem(CLIENT_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const generated = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `vk-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  localStorage.setItem(CLIENT_STORAGE_KEY, generated);
  return generated;
}

function getStoredIdentity(): WorkspaceIdentity | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = sessionStorage.getItem(IDENTITY_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as WorkspaceIdentity;
    if (!parsed.clientId || !parsed.displayName || !parsed.emailOrHandle || !parsed.accessKey) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function setStoredIdentity(identity: WorkspaceIdentity | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (!identity) {
    sessionStorage.removeItem(IDENTITY_STORAGE_KEY);
    return;
  }
  sessionStorage.setItem(IDENTITY_STORAGE_KEY, JSON.stringify(identity));
}

function getStoredSessionId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const activeSessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (activeSessionId) {
    return activeSessionId;
  }
  return null;
}

function setStoredSessionId(sessionId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

function clearStoredSessionId(): void {
  if (typeof window === "undefined") {
    return;
  }
  sessionStorage.removeItem(SESSION_STORAGE_KEY);
}

function applyBuildResetIfNeeded(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const currentBuild = __APP_BUILD__ || "dev";
  const lastBuild = localStorage.getItem(APP_BUILD_STORAGE_KEY);
  if (lastBuild === currentBuild) {
    return false;
  }
  clearStoredSessionId();
  sessionStorage.removeItem(IDENTITY_STORAGE_KEY);
  localStorage.setItem(APP_BUILD_STORAGE_KEY, currentBuild);
  return true;
}

function AppBody() {
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [loadingSession, setLoadingSession] = useState(true);
  const [starting, setStarting] = useState(false);
  const [setupError, setSetupError] = useState("");
  const [entryScreen, setEntryScreen] = useState<"landing" | "setup">("landing");
  const [setupStep, setSetupStep] = useState(0);
  const [setupDraft, setSetupDraft] = useState<SetupDraft>(DEFAULT_SETUP_DRAFT);
  const [providerOptions, setProviderOptions] = useState<ProviderOption[]>(DEFAULT_PROVIDER_OPTIONS);
  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [deviceClientId] = useState<string>(() => getClientId());
  const [activeIdentity, setActiveIdentity] = useState<WorkspaceIdentity | null>(() => getStoredIdentity());
  const [displayName, setDisplayName] = useState("");
  const [emailOrHandle, setEmailOrHandle] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [theme, setTheme] = useState<ThemeMode>(
    () => (localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null) ?? "dark",
  );
  const [adminEnabled, setAdminEnabled] = useState(false);
  const sessionClientId = activeIdentity?.clientId || "";
  const analyticsClientId = sessionClientId || deviceClientId;
  const effectiveDisplayName = (activeIdentity?.displayName || displayName || "").trim();

  useEffect(() => {
    const resetApplied = applyBuildResetIfNeeded();
    if (resetApplied) {
      setSession(null);
      setLoadingSession(false);
      setSetupError("");
      if (location.pathname !== "/admin") {
        navigate("/", { replace: true });
      }
    }
  }, [location.pathname, navigate]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (activeIdentity && !session) {
      setEntryScreen("setup");
    }
  }, [activeIdentity, session]);

  useEffect(() => {
    let cancelled = false;
    void getAuthSession()
      .then((response) => {
        if (cancelled) {
          return;
        }
        setAdminEnabled(Boolean(response.adminMode));
      })
      .catch(() => {
        if (!cancelled) {
          setAdminEnabled(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  useEffect(() => {
    void listProviders()
      .then((response) => setProviderOptions(response.providers))
      .catch(() => setProviderOptions(DEFAULT_PROVIDER_OPTIONS));
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!sessionClientId) {
      setRecentSessions([]);
      return () => {
        cancelled = true;
      };
    }
    void listSessions(sessionClientId)
      .then((response) => {
        if (!cancelled) {
          setRecentSessions(response.sessions);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRecentSessions([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionClientId]);

  useEffect(() => {
    let cancelled = false;
    const storedSessionId = getStoredSessionId();

    if (!storedSessionId || !sessionClientId) {
      if (!sessionClientId) {
        clearStoredSessionId();
      }
      setLoadingSession(false);
      return () => {
        cancelled = true;
      };
    }

    setLoadingSession(true);
    void getSession(storedSessionId, sessionClientId)
      .then((response) => {
        if (!cancelled) {
          setSession(response);
        }
      })
      .catch(() => {
        clearStoredSessionId();
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingSession(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionClientId]);

  useEffect(() => {
    void sendHeartbeat(analyticsClientId).catch(() => undefined);
    const timer = window.setInterval(() => {
      void sendHeartbeat(analyticsClientId).catch(() => undefined);
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [analyticsClientId]);

  useEffect(() => {
    void postAnalyticsEvent({
      eventType: "page_view",
      clientId: analyticsClientId,
      displayName: effectiveDisplayName,
      pathname: location.pathname,
    }).catch(() => undefined);
  }, [analyticsClientId, effectiveDisplayName, location.pathname]);

  const hydrateStartedSession = (payload: StartSessionPayload) => {
    const next: SessionPayload = {
      sessionId: payload.sessionId,
      history: [{ role: "assistant", content: payload.openingMessage }],
      state: payload.state,
      chips: payload.chips,
      responseProfile: payload.responseProfile,
      coverage: payload.coverage,
      nextGap: payload.nextGap,
      activeUploads: payload.activeUploads,
      sessionType: payload.sessionType,
      evaluatorMode: payload.evaluatorMode,
      provider: payload.provider,
      model: payload.model,
      supportsVision: payload.supportsVision,
      questionBudget: payload.questionBudget,
      websiteUrl: payload.websiteUrl,
      sources: payload.sources,
      confidence: payload.confidence,
      knowledgeLane: payload.knowledgeLane,
      usedLiveWeb: payload.usedLiveWeb,
      followUpMode: payload.followUpMode,
      helpMode: payload.helpMode,
      liveWebEnabled: payload.liveWebEnabled,
      analysisSnapshot: payload.analysisSnapshot,
      runtimeUsage: payload.runtimeUsage,
      evaluationProgress: payload.evaluationProgress,
      evaluationReport: payload.evaluationReport,
      deckEvaluationReport: payload.deckEvaluationReport,
    };
    setStoredSessionId(payload.sessionId);
    setSession(next);
    void listSessions(sessionClientId)
      .then((response) => setRecentSessions(response.sessions))
      .catch(() => undefined);
    if (payload.sessionType === "evaluator" && payload.evaluationProgress?.completed) {
      navigate(`/evaluate/${payload.sessionId}/report`);
      return;
    }
    navigate("/");
  };

  const refreshSessions = async () => {
    if (!sessionClientId) {
      setRecentSessions([]);
      return;
    }
    try {
      const response = await listSessions(sessionClientId);
      setRecentSessions(response.sessions);
    } catch {
      setRecentSessions([]);
    }
  };

  const handleClearHistory = async () => {
    if (!sessionClientId || clearingHistory) {
      return;
    }
    setClearingHistory(true);
    try {
      await clearSessionHistory(sessionClientId);
      clearStoredSessionId();
      setSession(null);
      setRecentSessions([]);
      navigate("/", { replace: true });
    } finally {
      setClearingHistory(false);
    }
  };

  const handleContinueWithIdentity = () => {
    const identity = createWorkspaceIdentity(displayName, emailOrHandle, accessKey);
    if (!identity) {
      setSetupError("Enter your name, email or handle, and a Sift key with at least 8 characters.");
      return;
    }
    setStoredIdentity(identity);
    setActiveIdentity(identity);
    setDisplayName("");
    setEmailOrHandle("");
    setAccessKey("");
    setSetupError("");
    setEntryScreen("setup");
    setSetupStep(0);
    void listSessions(identity.clientId)
      .then((response) => setRecentSessions(response.sessions))
      .catch(() => setRecentSessions([]));
  };

  const handleGenerateAccessKey = () => {
    setAccessKey(generateAccessKey());
    setSetupError("");
  };

  const handleSwitchIdentity = () => {
    clearStoredSessionId();
    setStoredIdentity(null);
    setActiveIdentity(null);
    setDisplayName("");
    setEmailOrHandle("");
    setAccessKey("");
    setSession(null);
    setRecentSessions([]);
    setEntryScreen("landing");
    setSetupStep(0);
    setSetupError("");
    navigate("/", { replace: true });
  };

  const handleStartSession = async (payload: {
    sessionType: "mentor" | "evaluator" | "expert";
    evaluatorMode?: "idea_review" | "deck_review";
    founderType: string;
    sector: string;
    stage: string;
    geography: string;
    mode: "think_it_through" | "quick_stress_test";
    provider: string;
    model: string;
    apiKey: string;
    websiteUrl: string;
    setupContext: string;
    helpMode: "coach_me" | "challenge_me" | "explain_directly";
    liveWebEnabled: boolean;
  }) => {
    if (!sessionClientId || !effectiveDisplayName) {
      setSetupError("Enter your name and Sift key before starting a session.");
      return;
    }
    setSetupError("");
    setStarting(true);
    try {
      const response = await startSession({
        founderType: payload.founderType,
        sector: payload.sector,
        stage: payload.stage,
        mode: payload.mode,
        geography: payload.geography,
        sessionType: payload.sessionType,
        evaluatorMode: payload.evaluatorMode || "idea_review",
        helpMode: payload.helpMode,
        liveWebEnabled: payload.liveWebEnabled,
        provider: payload.provider,
        model: payload.model,
        apiKey: payload.apiKey.trim(),
        websiteUrl: payload.websiteUrl,
        setupContext: payload.setupContext,
        clientId: sessionClientId,
        displayName: effectiveDisplayName,
      });
      if (payload.apiKey.trim()) {
        saveSessionCredential(response.sessionId, {
          provider: payload.provider,
          model: payload.model,
          apiKey: payload.apiKey.trim(),
        });
      }
      hydrateStartedSession(response);
    } catch (error) {
      setSetupError(error instanceof Error ? error.message : "Failed to start session");
    } finally {
      setStarting(false);
    }
  };

  const handleExitSession = () => {
    clearStoredSessionId();
    setSession(null);
    setSetupError("");
    if (sessionClientId) {
      setEntryScreen("setup");
      setSetupStep(0);
    } else {
      setEntryScreen("landing");
      setSetupStep(0);
    }
    void refreshSessions();
    navigate("/");
  };

  const handleNewSession = () => {
    clearStoredSessionId();
    setSession(null);
    setSetupError("");
    if (sessionClientId) {
      setEntryScreen("setup");
      setSetupStep(0);
    } else {
      setEntryScreen("landing");
      setSetupStep(0);
    }
    void refreshSessions();
    navigate("/");
  };

  const handleOpenSession = async (sessionId: string) => {
    if (!sessionClientId) {
      setSetupError("Enter the matching Sift key before opening a saved session.");
      return;
    }
    const response = await getSession(sessionId, sessionClientId);
    setStoredSessionId(sessionId);
    setSession(response);
    navigate("/");
  };

  if (loadingSession) {
    return <div className="loading-screen">Loading Sift...</div>;
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          session ? (
            session.sessionType === "evaluator" ? (
              <EvaluatorScreen
                session={session}
                setSession={(updater) => setSession((previous) => (previous ? updater(previous) : previous))}
                onNewSession={handleNewSession}
                onExitSession={handleExitSession}
                onOpenSession={handleOpenSession}
                onSessionActivity={() => void refreshSessions()}
                onClearHistory={handleClearHistory}
                clearingHistory={clearingHistory}
                recentSessions={recentSessions}
                providerOptions={providerOptions}
                theme={theme}
                onThemeChange={setTheme}
                clientId={sessionClientId}
              />
            ) : session.sessionType === "expert" ? (
              <ExpertScreen
                session={session}
                setSession={(updater) => setSession((previous) => (previous ? updater(previous) : previous))}
                onNewSession={handleNewSession}
                onExitSession={handleExitSession}
                onOpenSession={handleOpenSession}
                onSessionActivity={() => void refreshSessions()}
                onClearHistory={handleClearHistory}
                clearingHistory={clearingHistory}
                recentSessions={recentSessions}
                providerOptions={providerOptions}
                theme={theme}
                onThemeChange={setTheme}
                clientId={sessionClientId}
              />
            ) : (
              <ChatScreen
                session={session}
                setSession={(updater) => setSession((previous) => (previous ? updater(previous) : previous))}
                onNewSession={handleNewSession}
                onExitSession={handleExitSession}
                onOpenSession={handleOpenSession}
                onSessionActivity={() => void refreshSessions()}
                onClearHistory={handleClearHistory}
                clearingHistory={clearingHistory}
                recentSessions={recentSessions}
                providerOptions={providerOptions}
                theme={theme}
                onThemeChange={setTheme}
                clientId={sessionClientId}
              />
            )
          ) : (
            entryScreen === "landing" ? (
              <LandingScreen
                displayName={displayName}
                emailOrHandle={emailOrHandle}
                accessKey={accessKey}
                onDisplayNameChange={setDisplayName}
                onEmailOrHandleChange={setEmailOrHandle}
                onAccessKeyChange={setAccessKey}
                onGenerateAccessKey={handleGenerateAccessKey}
                onContinue={handleContinueWithIdentity}
                theme={theme}
                onThemeChange={setTheme}
                error={setupError}
              />
            ) : (
              <SetupWizard
                providerOptions={providerOptions}
                loading={starting}
                error={setupError}
                canStart={Boolean(sessionClientId && effectiveDisplayName)}
                step={setupStep}
                draft={setupDraft}
                theme={theme}
                onThemeChange={setTheme}
                identityLabel={activeIdentity?.emailOrHandle || ""}
                identityKey={activeIdentity?.accessKey || ""}
                recentSessions={recentSessions}
                onOpenSession={handleOpenSession}
                onSwitchIdentity={handleSwitchIdentity}
                onStepChange={(nextStep) => {
                  setSetupError("");
                  setSetupStep(nextStep);
                }}
                onDraftChange={(updater) => {
                  setSetupError("");
                  setSetupDraft(updater);
                }}
                onBack={handleSwitchIdentity}
                onStart={handleStartSession}
              />
            )
          )
        }
      />
      <Route
        path="/outline/:sessionId"
        element={
          <OutlineScreen
            theme={theme}
            onThemeChange={setTheme}
            onExitSession={handleExitSession}
            displayName={effectiveDisplayName}
            clientId={sessionClientId}
          />
        }
      />
      <Route
        path="/evaluate/:sessionId/report"
        element={
          <EvaluatorReportScreen
            theme={theme}
            onThemeChange={setTheme}
            onExitSession={handleExitSession}
            onResumeSession={handleOpenSession}
            clientId={sessionClientId}
          />
        }
      />
      <Route
        path="/admin"
        element={adminEnabled ? <AdminScreen theme={theme} onThemeChange={setTheme} /> : <Navigate to="/" replace />}
      />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppBody />
    </BrowserRouter>
  );
}
