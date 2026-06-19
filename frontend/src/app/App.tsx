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
import { DashboardScreen } from "../features/dashboard/DashboardScreen";
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
    defaultSpeedModel: "qwen3:8b",
    defaultBalancedModel: "qwen3:30b",
    supportsVisionModels: true,
    recommendedDeckModel: "qwen2.5vl:7b",
    latencyHint: "Local models — zero latency on device, complete data privacy.",
    bestFor: "Local-first, private inference, and zero-key use.",
    speedLabel: "Qwen3 8B",
    balancedLabel: "Qwen3 30B",
    publicReadiness: "Local install required",
    openWeight: true,
    modelPresets: [
      { label: "Qwen3 8B", value: "qwen3:8b", note: "Fast default." },
      { label: "Qwen3 30B", value: "qwen3:30b", note: "Deeper reasoning." },
      { label: "Qwen2.5 VL", value: "qwen2.5vl:7b", note: "Vision · deck image reading." },
      { label: "Llama 3.2", value: "llama3.2:latest", note: "Lightweight CPU fallback." },
    ],
  },
  {
    key: "local_openai",
    label: "Local OpenAI-compatible",
    requiresApiKey: false,
    defaultSpeedModel: "Qwen/Qwen3-8B",
    defaultBalancedModel: "Qwen/Qwen3-30B",
    supportsVisionModels: true,
    recommendedDeckModel: "Qwen/Qwen2.5-VL-7B-Instruct",
    latencyHint: "Open-source models served by vLLM, TGI, LM Studio, or llama.cpp.",
    bestFor: "Fast local GPUs, Hugging Face models, private endpoints.",
    speedLabel: "Qwen3 8B",
    balancedLabel: "Qwen3 30B",
    publicReadiness: "Local endpoint",
    openWeight: true,
    modelPresets: [
      { label: "Qwen3 8B", value: "Qwen/Qwen3-8B", note: "Fast open-weight default." },
      { label: "Qwen3 30B", value: "Qwen/Qwen3-30B-A3B", note: "MoE · better reasoning." },
      { label: "Qwen2.5 VL", value: "Qwen/Qwen2.5-VL-7B-Instruct", note: "Vision · deck image reading." },
      { label: "Llama 4 Scout", value: "meta-llama/Llama-4-Scout-17B-16E", note: "Efficient MoE open-weight." },
    ],
  },
  {
    key: "sift_brain",
    label: "Sift Brain",
    requiresApiKey: false,
    defaultSpeedModel: "sift-brain",
    defaultBalancedModel: "sift-brain",
    supportsVisionModels: false,
    recommendedDeckModel: "",
    latencyHint: "Fine-tuned local adapter served at port 8001. Runs `npm run brain:serve` first.",
    bestFor: "Proprietary Sift intelligence layer — runs your own fine-tuned adapter.",
    speedLabel: "Sift Brain",
    balancedLabel: "Sift Brain",
    publicReadiness: "Neural engine · local port 8001",
    openWeight: true,
    modelPresets: [
      { label: "Sift Brain (latest)", value: "sift-brain", note: "Best adapter by eval score." },
    ],
  },
  {
    key: "open_source",
    label: "Open-source endpoint",
    requiresApiKey: true,
    defaultSpeedModel: "Qwen/Qwen2.5-VL-7B-Instruct",
    defaultBalancedModel: "Qwen/Qwen2.5-VL-7B-Instruct",
    supportsVisionModels: true,
    recommendedDeckModel: "Qwen/Qwen2.5-VL-7B-Instruct",
    latencyHint: "Server-side open-source model endpoint for Qwen, Llama, Gemma, Pixtral, or other OpenAI-compatible deployments.",
    bestFor: "Public demos that need open-source models without making users run local hardware.",
    speedLabel: "Qwen VL",
    balancedLabel: "Qwen VL",
    publicReadiness: "Open-source cloud lane",
    openWeight: true,
    modelPresets: [
      { label: "Qwen2.5 VL", value: "Qwen/Qwen2.5-VL-7B-Instruct", note: "Best open-source deck vision default." },
      { label: "Qwen3 VL", value: "Qwen/Qwen3-VL-8B-Instruct", note: "Newer open-source vision lane when available." },
      { label: "Llama Vision", value: "meta-llama/Llama-3.2-11B-Vision-Instruct", note: "Alternative open-source visual reviewer." },
      { label: "Pixtral", value: "mistralai/Pixtral-12B-2409", note: "Open multimodal deck reader." },
    ],
  },
  {
    key: "vertex",
    label: "Vertex AI Gemini",
    requiresApiKey: false,
    serverConfigured: true,
    defaultSpeedModel: "gemini-2.5-flash",
    defaultBalancedModel: "gemini-2.5-pro",
    supportsVisionModels: true,
    recommendedDeckModel: "gemini-2.5-flash",
    latencyHint: "Google Cloud hosted Gemini path using the Cloud Run service account.",
    bestFor: "Using GCP credits and IAM instead of per-session API keys.",
    speedLabel: "Gemini Flash",
    balancedLabel: "Gemini Pro",
    publicReadiness: "GCP-native lane",
    openWeight: false,
    modelPresets: [
      { label: "Gemini 2.5 Flash", value: "gemini-2.5-flash", note: "Stable low-latency GCP default." },
      { label: "Gemini 2.5 Pro", value: "gemini-2.5-pro", note: "Stable higher-quality GCP default." },
      { label: "Gemini 3 Flash", value: "gemini-3-flash-preview", note: "Latest fast preview lane." },
      { label: "Gemini 3.1 Pro", value: "gemini-3.1-pro-preview", note: "Latest reasoning preview lane." },
    ],
  },
  {
    key: "groq",
    label: "Groq",
    requiresApiKey: true,
    defaultSpeedModel: "meta-llama/llama-4-scout-17b-16e-instruct",
    defaultBalancedModel: "meta-llama/llama-4-maverick-17b-128e-instruct",
    supportsVisionModels: false,
    recommendedDeckModel: "",
    latencyHint: "World’s fastest hosted inference — sub-100 ms TTFT on Llama-4.",
    bestFor: "Low-latency public launch with Llama-4 open-weight models.",
    speedLabel: "Llama-4 Scout",
    balancedLabel: "Llama-4 Maverick",
    publicReadiness: "Recommended hosted default",
    openWeight: true,
    modelPresets: [
      { label: "Llama-4 Scout", value: "meta-llama/llama-4-scout-17b-16e-instruct", note: "Fast 17B MoE." },
      { label: "Llama-4 Maverick", value: "meta-llama/llama-4-maverick-17b-128e-instruct", note: "Higher quality, 128E." },
      { label: "Qwen3 8B", value: "qwen/qwen3-8b", note: "Groq open-weight alternative." },
    ],
  },
  {
    key: "cerebras",
    label: "Cerebras",
    requiresApiKey: true,
    defaultSpeedModel: "qwen-3-8b",
    defaultBalancedModel: "qwen-3-32b",
    supportsVisionModels: false,
    recommendedDeckModel: "",
    latencyHint: "Fastest hosted open-weight throughput — Qwen3 on Cerebras silicon.",
    bestFor: "High-speed expert and evaluation turns on Qwen3.",
    speedLabel: "Qwen3 8B",
    balancedLabel: "Qwen3 32B",
    publicReadiness: "Performance lane",
    openWeight: true,
    modelPresets: [
      { label: "Qwen3 8B", value: "qwen-3-8b", note: "Fast Cerebras lane." },
      { label: "Qwen3 32B", value: "qwen-3-32b", note: "Higher quality Cerebras lane." },
    ],
  },
  {
    key: "openai",
    label: "OpenAI",
    requiresApiKey: true,
    defaultSpeedModel: "gpt-4.1-mini",
    defaultBalancedModel: "gpt-4.1",
    supportsVisionModels: true,
    recommendedDeckModel: "gpt-4.1",
    latencyHint: "Frontier quality for complex synthesis, deck reasoning, and polish.",
    bestFor: "Highest-quality public mode when cost is acceptable.",
    speedLabel: "GPT-4.1 mini",
    balancedLabel: "GPT-4.1",
    publicReadiness: "Frontier quality lane",
    openWeight: false,
    modelPresets: [
      { label: "GPT-4.1 mini", value: "gpt-4.1-mini", note: "Fast and affordable." },
      { label: "GPT-4.1", value: "gpt-4.1", note: "Strongest reasoning." },
      { label: "GPT-4o", value: "gpt-4o", note: "Vision + multimodal." },
    ],
  },
  {
    key: "openrouter",
    label: "OpenRouter",
    requiresApiKey: true,
    defaultSpeedModel: "meta-llama/llama-4-scout",
    defaultBalancedModel: "meta-llama/llama-4-maverick",
    supportsVisionModels: true,
    recommendedDeckModel: "anthropic/claude-sonnet-4-5",
    latencyHint: "Flexible broker for comparing open-weight and closed frontier models.",
    bestFor: "Provider experiments without changing the app.",
    speedLabel: "Llama-4 Scout",
    balancedLabel: "Llama-4 Maverick",
    publicReadiness: "Experiment lane",
    openWeight: true,
    modelPresets: [
      { label: "Llama-4 Scout", value: "meta-llama/llama-4-scout", note: "Fast open-weight via Router." },
      { label: "Llama-4 Maverick", value: "meta-llama/llama-4-maverick", note: "Sharper open-weight via Router." },
      { label: "Qwen3 8B", value: "qwen/qwen3-8b", note: "Lightweight open-weight." },
    ],
  },
  { key: "anthropic", label: "Anthropic", requiresApiKey: true, defaultSpeedModel: "claude-haiku-4-5", defaultBalancedModel: "claude-sonnet-4-5", supportsVisionModels: true, recommendedDeckModel: "claude-sonnet-4-5", latencyHint: "Strong long-form synthesis with hosted API latency.", bestFor: "Careful narrative analysis and investor-style memo work.", speedLabel: "Haiku 4.5", balancedLabel: "Sonnet 4.5", publicReadiness: "Quality lane",
    modelPresets: [
      { label: "Haiku 4.5", value: "claude-haiku-4-5", note: "Fast, affordable." },
      { label: "Sonnet 4.5", value: "claude-sonnet-4-5", note: "Best balance for decks." },
    ],
  },
  { key: "gemini", label: "Gemini", requiresApiKey: true, defaultSpeedModel: "gemini-2.5-flash", defaultBalancedModel: "gemini-2.5-pro", supportsVisionModels: true, recommendedDeckModel: "gemini-2.5-flash", latencyHint: "Fast hosted multimodal fallback for broad consumer access.", bestFor: "Affordable hosted analysis and deck-adjacent workflows.", speedLabel: "Flash", balancedLabel: "Pro", publicReadiness: "Multimodal lane" },
];
const DEFAULT_SETUP_DRAFT: SetupDraft = {
  runtimeKind: "external",
  provider: "groq",
  model: "meta-llama/llama-4-scout-17b-16e-instruct",
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

function isLocalProviderKey(key: string): boolean {
  return key === "ollama" || key === "local_openai";
}

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

  const [authProviders, setAuthProviders] = useState<Array<{ key: string; label: string; configured: boolean }>>([]);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void getAuthSession()
      .then((response) => {
        if (cancelled) {
          return;
        }
        setAdminEnabled(Boolean(response.adminMode));
        setAuthProviders(response.providers || []);
        if (response.error) {
          setAuthError(response.error);
        }
        if (response.user && response.user.clientId) {
          const identity: WorkspaceIdentity = {
            clientId: response.user.clientId,
            displayName: response.user.displayName,
            emailOrHandle: response.user.email,
            accessKey: "oauth-session",
          };
          setStoredIdentity(identity);
          setActiveIdentity(identity);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdminEnabled(false);
          setAuthProviders([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  useEffect(() => {
    void listProviders()
      .then((response) => {
        setProviderOptions(response.providers);
        const hostedDefault = response.providers.find((item) => !isLocalProviderKey(item.key) && item.serverConfigured);
        if (!hostedDefault) {
          return;
        }
        setSetupDraft((current) => {
          const currentProvider = response.providers.find((item) => item.key === current.provider);
          const needsClientKey = Boolean(currentProvider?.requiresApiKey && !currentProvider.serverConfigured);
          if (current.runtimeKind !== "external" || !needsClientKey || current.apiKey.trim()) {
            return current;
          }
          return {
            ...current,
            provider: hostedDefault.key,
            model: hostedDefault.defaultBalancedModel || hostedDefault.defaultSpeedModel || current.model,
          };
        });
      })
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

  const handleContinueWithIdentity = async () => {
    let finalAccessKey = accessKey;
    if (!finalAccessKey || finalAccessKey.length < 8) {
      finalAccessKey = generateAccessKey();
    }
    let finalDisplayName = displayName;
    if (!finalDisplayName.trim() && emailOrHandle.includes("@")) {
      finalDisplayName = emailOrHandle.split("@")[0];
    } else if (!finalDisplayName.trim()) {
      finalDisplayName = emailOrHandle;
    }

    const identity = await createWorkspaceIdentity(finalDisplayName, emailOrHandle, finalAccessKey);
    if (!identity) {
      setSetupError("Enter your email to continue.");
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
    return (
      <div className="loading-screen" role="status" aria-label="Loading Sift">
        <div className="sift-loading-inner">
          <div className="sift-loading-wordmark">
            SIFT<span>.</span>
          </div>
          <div className="sift-loading-bar" aria-hidden="true" />
        </div>
      </div>
    );
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
                emailOrHandle={emailOrHandle}
                onEmailOrHandleChange={setEmailOrHandle}
                onContinue={handleContinueWithIdentity}
                theme={theme}
                onThemeChange={setTheme}
                error={setupError || authError}
                authProviders={authProviders}
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
      <Route path="/dashboard" element={<DashboardScreen />} />
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
