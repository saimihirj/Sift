import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import type {
  AuthProviderOption,
  AuthUser,
  ProviderOption,
  SessionPayload,
  SessionSummary,
  SetupDraft,
  StartSessionPayload,
  ThemeMode,
} from "./types";
import { clearSessionHistory, getAuthSession, getSession, listProviders, listSessions, logoutAuth, postAnalyticsEvent, sendHeartbeat, startSession } from "../lib/api/client";
import { AdminScreen } from "../features/admin/AdminScreen";
import { ChatScreen } from "../features/chat/ChatScreen";
import { EvaluatorReportScreen } from "../features/evaluator/EvaluatorReportScreen";
import { EvaluatorScreen } from "../features/evaluator/EvaluatorScreen";
import { LandingScreen } from "../features/onboarding/LandingScreen";
import { SetupWizard } from "../features/onboarding/SetupWizard";
import { OutlineScreen } from "../features/outline/OutlineScreen";
import { saveSessionCredential } from "../lib/sessionCredentials";

declare const __APP_BUILD__: string;

const SESSION_STORAGE_KEY = "signal-session-id";
const LEGACY_SESSION_STORAGE_KEY = "vishwakarma-session-id";
const LEGACY_DISPLAY_NAME_STORAGE_KEY = "vishwakarma-display-name";
const THEME_STORAGE_KEY = "vishwakarma-theme";
const CLIENT_STORAGE_KEY = "vishwakarma-client-id";
const APP_BUILD_STORAGE_KEY = "signal-app-build";
const DEFAULT_AUTH_PROVIDERS: AuthProviderOption[] = [
  { key: "google", label: "Google", configured: false },
  { key: "apple", label: "Apple", configured: false },
];
const DEFAULT_PROVIDER_OPTIONS: ProviderOption[] = [
  { key: "ollama", label: "Ollama", requiresApiKey: false, defaultSpeedModel: "llama3.2:latest", defaultBalancedModel: "qwen3:8b" },
  { key: "cerebras", label: "Cerebras", requiresApiKey: true, defaultSpeedModel: "llama3.1-8b", defaultBalancedModel: "gpt-oss-120b" },
  { key: "groq", label: "Groq", requiresApiKey: true, defaultSpeedModel: "llama-3.1-8b-instant", defaultBalancedModel: "llama-3.3-70b-versatile" },
  { key: "openai", label: "OpenAI", requiresApiKey: true, defaultSpeedModel: "gpt-4o-mini", defaultBalancedModel: "gpt-4.1" },
  { key: "openrouter", label: "OpenRouter", requiresApiKey: true, defaultSpeedModel: "openai/gpt-4o-mini", defaultBalancedModel: "anthropic/claude-3.5-sonnet" },
  { key: "anthropic", label: "Anthropic", requiresApiKey: true, defaultSpeedModel: "claude-3-5-haiku-latest", defaultBalancedModel: "claude-3-7-sonnet-latest" },
  { key: "gemini", label: "Gemini", requiresApiKey: true, defaultSpeedModel: "gemini-2.0-flash", defaultBalancedModel: "gemini-1.5-pro" },
];
const DEFAULT_SETUP_DRAFT: SetupDraft = {
  runtimeKind: "local",
  provider: "ollama",
  model: "llama3.2:latest",
  apiKey: "",
  founderType: "founder",
  sector: "saas",
  stage: "idea",
  websiteUrl: "",
  setupContext: "",
  sessionType: "mentor",
  mode: "think_it_through",
};
const LAST_SETUP_STEP = 2;

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

function getStoredSessionId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const activeSessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (activeSessionId) {
    return activeSessionId;
  }
  localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
  sessionStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
  return null;
}

function setStoredSessionId(sessionId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
  sessionStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
  sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

function clearStoredSessionId(): void {
  if (typeof window === "undefined") {
    return;
  }
  sessionStorage.removeItem(SESSION_STORAGE_KEY);
  localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
  sessionStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
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
  localStorage.removeItem(LEGACY_DISPLAY_NAME_STORAGE_KEY);
  localStorage.setItem(APP_BUILD_STORAGE_KEY, currentBuild);
  return true;
}

function AppBody() {
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [loadingSession, setLoadingSession] = useState(true);
  const [starting, setStarting] = useState(false);
  const [entryScreen, setEntryScreen] = useState<"landing" | "setup">("landing");
  const [setupStep, setSetupStep] = useState(0);
  const [setupDraft, setSetupDraft] = useState<SetupDraft>(DEFAULT_SETUP_DRAFT);
  const [providerOptions, setProviderOptions] = useState<ProviderOption[]>(DEFAULT_PROVIDER_OPTIONS);
  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [anonymousClientId] = useState<string>(() => getClientId());
  const [displayName, setDisplayName] = useState<string>("");
  const [theme, setTheme] = useState<ThemeMode>(
    () => (localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null) ?? "dark",
  );
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authProviders, setAuthProviders] = useState<AuthProviderOption[]>(DEFAULT_AUTH_PROVIDERS);
  const [authError, setAuthError] = useState("");
  const [adminEnabled, setAdminEnabled] = useState(false);
  const effectiveClientId = authUser?.clientId || anonymousClientId;

  useEffect(() => {
    const resetApplied = applyBuildResetIfNeeded();
    if (resetApplied) {
      setSession(null);
      setLoadingSession(false);
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
    localStorage.removeItem(LEGACY_DISPLAY_NAME_STORAGE_KEY);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getAuthSession()
      .then((response) => {
        if (cancelled) {
          return;
        }
        setAuthUser(response.user);
        setAuthProviders(response.providers.length > 0 ? response.providers : DEFAULT_AUTH_PROVIDERS);
        setAuthError(response.error || "");
        setAdminEnabled(Boolean(response.adminMode));
      })
      .catch(() => {
        if (!cancelled) {
          setAuthUser(null);
          setAuthProviders(DEFAULT_AUTH_PROVIDERS);
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
    void listSessions(effectiveClientId)
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
  }, [effectiveClientId]);

  useEffect(() => {
    let cancelled = false;
    const storedSessionId = getStoredSessionId();

    if (!storedSessionId) {
      setLoadingSession(false);
      return () => {
        cancelled = true;
      };
    }

    void getSession(storedSessionId)
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
  }, []);

  useEffect(() => {
    void sendHeartbeat(effectiveClientId).catch(() => undefined);
    const timer = window.setInterval(() => {
      void sendHeartbeat(effectiveClientId).catch(() => undefined);
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [effectiveClientId]);

  useEffect(() => {
    void postAnalyticsEvent({
      eventType: "page_view",
      clientId: effectiveClientId,
      displayName: displayName || authUser?.displayName || "",
      pathname: location.pathname,
    }).catch(() => undefined);
  }, [effectiveClientId, displayName, authUser, location.pathname]);

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
      provider: payload.provider,
      model: payload.model,
      questionBudget: payload.questionBudget,
      websiteUrl: payload.websiteUrl,
      evaluationProgress: payload.evaluationProgress,
      evaluationReport: payload.evaluationReport,
    };
    setStoredSessionId(payload.sessionId);
    setSession(next);
    void listSessions(effectiveClientId)
      .then((response) => setRecentSessions(response.sessions))
      .catch(() => undefined);
    if (payload.sessionType === "evaluator" && payload.evaluationProgress?.completed) {
      navigate(`/evaluate/${payload.sessionId}/report`);
      return;
    }
    navigate("/");
  };

  const refreshSessions = async () => {
    try {
      const response = await listSessions(effectiveClientId);
      setRecentSessions(response.sessions);
    } catch {
      setRecentSessions([]);
    }
  };

  const handleClearHistory = async () => {
    if (!effectiveClientId || clearingHistory) {
      return;
    }
    setClearingHistory(true);
    try {
      await clearSessionHistory(effectiveClientId);
      clearStoredSessionId();
      setSession(null);
      setRecentSessions([]);
      navigate("/", { replace: true });
    } finally {
      setClearingHistory(false);
    }
  };

  const handleStartSession = async (payload: {
    sessionType: "mentor" | "evaluator";
    founderType: string;
    sector: string;
    stage: string;
    mode: "think_it_through" | "quick_stress_test";
    provider: string;
    model: string;
    apiKey: string;
    websiteUrl: string;
    setupContext: string;
  }) => {
    if (!(displayName || authUser?.displayName || "").trim()) {
      return;
    }
    setStarting(true);
    try {
      const response = await startSession({
        founderType: payload.founderType,
        sector: payload.sector,
        stage: payload.stage,
        mode: payload.mode,
        sessionType: payload.sessionType,
        provider: payload.provider,
        model: payload.model,
        apiKey: payload.apiKey.trim(),
        websiteUrl: payload.websiteUrl,
        setupContext: payload.setupContext,
        clientId: effectiveClientId,
        displayName: (displayName || authUser?.displayName || "").trim(),
      });
      if (payload.apiKey.trim()) {
        saveSessionCredential(response.sessionId, {
          provider: payload.provider,
          model: payload.model,
          apiKey: payload.apiKey.trim(),
        });
      }
      hydrateStartedSession(response);
    } finally {
      setStarting(false);
    }
  };

  const handleExitSession = () => {
    clearStoredSessionId();
    setSession(null);
    setEntryScreen("setup");
    setSetupStep(LAST_SETUP_STEP);
    void refreshSessions();
    navigate("/");
  };

  const handleNewSession = () => {
    clearStoredSessionId();
    setSession(null);
    setEntryScreen("setup");
    setSetupStep(LAST_SETUP_STEP);
    void refreshSessions();
    navigate("/");
  };

  const handleOpenSession = async (sessionId: string) => {
    const response = await getSession(sessionId);
    setStoredSessionId(sessionId);
    setSession(response);
    navigate("/");
  };

  const handleSignOut = async () => {
    await logoutAuth();
    setAuthUser(null);
    setAuthError("");
    setDisplayName("");
  };

  if (loadingSession) {
    return <div className="loading-screen">Loading Signal...</div>;
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
              />
            )
          ) : (
            entryScreen === "landing" ? (
              <LandingScreen
                displayName={displayName}
                onDisplayNameChange={setDisplayName}
                onContinue={() => {
                  setEntryScreen("setup");
                  setSetupStep(0);
                }}
                theme={theme}
                onThemeChange={setTheme}
                authUser={authUser}
                authProviders={authProviders}
                authError={authError}
                onSignOut={handleSignOut}
              />
            ) : (
              <SetupWizard
                providerOptions={providerOptions}
                loading={starting}
                step={setupStep}
                draft={setupDraft}
                onStepChange={setSetupStep}
                onDraftChange={setSetupDraft}
                onBack={() => {
                  setDisplayName("");
                  setEntryScreen("landing");
                  setSetupStep(0);
                }}
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
            displayName={displayName}
            clientId={effectiveClientId}
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
