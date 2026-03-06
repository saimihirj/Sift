import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import type {
  AuthProviderOption,
  AuthUser,
  ProviderOption,
  SessionPayload,
  SessionSummary,
  StartSessionPayload,
  ThemeMode,
} from "./types";
import { getAuthSession, getSession, listProviders, listSessions, logoutAuth, postAnalyticsEvent, sendHeartbeat, startSession } from "../lib/api/client";
import { AdminScreen } from "../features/admin/AdminScreen";
import { ChatScreen } from "../features/chat/ChatScreen";
import { EvaluatorReportScreen } from "../features/evaluator/EvaluatorReportScreen";
import { EvaluatorScreen } from "../features/evaluator/EvaluatorScreen";
import { LandingScreen } from "../features/onboarding/LandingScreen";
import { SetupWizard } from "../features/onboarding/SetupWizard";
import { OutlineScreen } from "../features/outline/OutlineScreen";
import { saveSessionCredential } from "../lib/sessionCredentials";

const SESSION_STORAGE_KEY = "vishwakarma-session-id";
const THEME_STORAGE_KEY = "vishwakarma-theme";
const CLIENT_STORAGE_KEY = "vishwakarma-client-id";
const DISPLAY_NAME_STORAGE_KEY = "vishwakarma-display-name";
const DEFAULT_AUTH_PROVIDERS: AuthProviderOption[] = [
  { key: "google", label: "Google", configured: false },
  { key: "apple", label: "Apple", configured: false },
];
const DEFAULT_PROVIDER_OPTIONS: ProviderOption[] = [
  { key: "ollama", label: "Ollama", requiresApiKey: false, defaultSpeedModel: "llama3.2:latest", defaultBalancedModel: "qwen3:4b" },
  { key: "cerebras", label: "Cerebras", requiresApiKey: true, defaultSpeedModel: "llama3.1-8b", defaultBalancedModel: "gpt-oss-120b" },
  { key: "groq", label: "Groq", requiresApiKey: true, defaultSpeedModel: "llama-3.1-8b-instant", defaultBalancedModel: "llama-3.3-70b-versatile" },
  { key: "openai", label: "OpenAI", requiresApiKey: true, defaultSpeedModel: "gpt-4o-mini", defaultBalancedModel: "gpt-4.1" },
  { key: "openrouter", label: "OpenRouter", requiresApiKey: true, defaultSpeedModel: "openai/gpt-4o-mini", defaultBalancedModel: "anthropic/claude-3.5-sonnet" },
  { key: "anthropic", label: "Anthropic", requiresApiKey: true, defaultSpeedModel: "claude-3-5-haiku-latest", defaultBalancedModel: "claude-3-7-sonnet-latest" },
  { key: "gemini", label: "Gemini", requiresApiKey: true, defaultSpeedModel: "gemini-2.0-flash", defaultBalancedModel: "gemini-1.5-pro" },
];

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

function AppBody() {
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [loadingSession, setLoadingSession] = useState(true);
  const [starting, setStarting] = useState(false);
  const [entryScreen, setEntryScreen] = useState<"landing" | "setup">("landing");
  const [providerOptions, setProviderOptions] = useState<ProviderOption[]>(DEFAULT_PROVIDER_OPTIONS);
  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [anonymousClientId] = useState<string>(() => getClientId());
  const [displayName, setDisplayName] = useState<string>(() => localStorage.getItem(DISPLAY_NAME_STORAGE_KEY) ?? "");
  const [theme, setTheme] = useState<ThemeMode>(
    () => (localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null) ?? "dark",
  );
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authProviders, setAuthProviders] = useState<AuthProviderOption[]>(DEFAULT_AUTH_PROVIDERS);
  const [authError, setAuthError] = useState("");
  const [adminEnabled, setAdminEnabled] = useState(false);
  const effectiveClientId = authUser?.clientId || anonymousClientId;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, displayName);
  }, [displayName]);

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
        if (response.user?.displayName) {
          setDisplayName((current) => current || response.user?.displayName || "");
        }
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
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);

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
        localStorage.removeItem(SESSION_STORAGE_KEY);
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
    localStorage.setItem(SESSION_STORAGE_KEY, payload.sessionId);
    setSession(next);
    void listSessions(effectiveClientId)
      .then((response) => setRecentSessions(response.sessions))
      .catch(() => undefined);
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

  const handleStartSession = async (payload: {
    sessionType: "mentor" | "evaluator";
    founderType: string;
    sector: string;
    stage: string;
    mode: "think_it_through" | "quick_stress_test";
    provider: string;
    model: string;
    apiKey: string;
    questionBudget: 10 | 15 | 20;
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
        questionBudget: payload.sessionType === "evaluator" ? payload.questionBudget : undefined,
        provider: payload.provider,
        model: payload.model,
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
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
    setEntryScreen("landing");
    void refreshSessions();
    navigate("/");
  };

  const handleNewSession = () => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
    setEntryScreen("landing");
    void refreshSessions();
    navigate("/");
  };

  const handleOpenSession = async (sessionId: string) => {
    const response = await getSession(sessionId);
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    setSession(response);
    navigate("/");
  };

  const handleSignOut = async () => {
    await logoutAuth();
    setAuthUser(null);
    setAuthError("");
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
                onContinue={() => setEntryScreen("setup")}
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
                onBack={() => setEntryScreen("landing")}
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
