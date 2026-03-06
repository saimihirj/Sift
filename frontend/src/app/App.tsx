import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import type { SessionPayload, SessionSummary, StartSessionPayload } from "./types";
import { getSession, listSessions, postAnalyticsEvent, sendHeartbeat, startSession } from "../lib/api/client";
import { AdminScreen } from "../features/admin/AdminScreen";
import { ChatScreen } from "../features/chat/ChatScreen";
import { LandingScreen } from "../features/onboarding/LandingScreen";
import { OnboardingCard } from "../features/onboarding/OnboardingCard";
import { OutlineScreen } from "../features/outline/OutlineScreen";

const SESSION_STORAGE_KEY = "vishwakarma-session-id";
const THEME_STORAGE_KEY = "vishwakarma-theme";
const CLIENT_STORAGE_KEY = "vishwakarma-client-id";
const DISPLAY_NAME_STORAGE_KEY = "vishwakarma-display-name";

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
  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [loadingSession, setLoadingSession] = useState(true);
  const [starting, setStarting] = useState(false);
  const [entryScreen, setEntryScreen] = useState<"landing" | "onboarding">("landing");
  const [clientId] = useState<string>(() => getClientId());
  const [displayName, setDisplayName] = useState<string>(() => localStorage.getItem(DISPLAY_NAME_STORAGE_KEY) ?? "");
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (localStorage.getItem(THEME_STORAGE_KEY) as "light" | "dark" | null) ?? "light",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, displayName);
  }, [displayName]);

  useEffect(() => {
    let cancelled = false;
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);

    void listSessions(clientId)
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
  }, [clientId]);

  useEffect(() => {
    void sendHeartbeat(clientId).catch(() => undefined);
    const timer = window.setInterval(() => {
      void sendHeartbeat(clientId).catch(() => undefined);
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [clientId]);

  useEffect(() => {
    void postAnalyticsEvent({
      eventType: "page_view",
      clientId,
      displayName,
      pathname: location.pathname,
    }).catch(() => undefined);
  }, [clientId, displayName, location.pathname]);

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
    };
    localStorage.setItem(SESSION_STORAGE_KEY, payload.sessionId);
    setSession(next);
    navigate("/");
  };

  const refreshSessionList = async () => {
    const response = await listSessions(clientId);
    setRecentSessions(response.sessions);
  };

  const handleResumeSession = async (sessionId: string) => {
    const response = await getSession(sessionId);
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    setSession(response);
    void postAnalyticsEvent({
      eventType: "session_resumed",
      clientId,
      sessionId,
      displayName,
      pathname: "/",
    }).catch(() => undefined);
    navigate("/");
  };

  const handleStart = async (payload: Record<string, unknown>) => {
    if (!displayName.trim()) {
      return;
    }
    setStarting(true);
    try {
      const response = await startSession({ ...payload, clientId, displayName: displayName.trim() });
      hydrateStartedSession(response);
      await refreshSessionList();
    } finally {
      setStarting(false);
    }
  };

  const handleExitSession = () => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
    setEntryScreen("landing");
    navigate("/");
  };

  const handleNewSession = () => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
    setEntryScreen("landing");
    navigate("/");
  };

  if (loadingSession) {
    return <div className="loading-screen">Loading Vishwakarma...</div>;
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          session ? (
            <ChatScreen
              session={session}
              setSession={(updater) => setSession((previous) => (previous ? updater(previous) : previous))}
              recentSessions={recentSessions}
              onOpenSession={handleResumeSession}
              onNewSession={handleNewSession}
              onExitSession={handleExitSession}
              theme={theme}
              onToggleTheme={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
            />
          ) : (
            entryScreen === "landing" ? (
              <LandingScreen
                displayName={displayName}
                onDisplayNameChange={setDisplayName}
                onContinue={() => setEntryScreen("onboarding")}
                recentSessions={recentSessions}
                onResume={handleResumeSession}
              />
            ) : (
              <OnboardingCard
                onStart={handleStart}
                onBackToLanding={() => setEntryScreen("landing")}
                recentSessions={recentSessions}
                onResume={handleResumeSession}
                displayName={displayName}
                loading={starting}
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
            onToggleTheme={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
            onExitSession={handleExitSession}
            displayName={displayName}
            clientId={clientId}
          />
        }
      />
      <Route
        path="/admin"
        element={<AdminScreen theme={theme} onToggleTheme={() => setTheme((current) => (current === "light" ? "dark" : "light"))} />}
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
