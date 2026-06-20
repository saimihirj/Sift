import type {
  AdminEventsPayload,
  AdminOverview,
  AuthSessionPayload,
  EvaluatorAnswerPayload,
  EvaluatorReportPayload,
  OutlinePayload,
  ProviderCatalogPayload,
  ResponseProfile,
  SessionListPayload,
  SessionPayload,
  SessionRuntimePayload,
  StartSessionPayload,
} from "../../app/types";

export const API_BASE = (() => {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (explicit) {
    return explicit;
  }
  return "";
})();

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    if (payload && typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }
  } catch {
    try {
      const text = (await response.text()).trim();
      if (text) {
        return text;
      }
    } catch {
      return fallback;
    }
  }
  return fallback;
}

async function fetchOrExplain(input: RequestInfo | URL, init: RequestInit | undefined, fallback: string): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new Error(`${fallback}. Check that the Sift backend is running and reachable.`);
  }
}

type StreamHandlers = {
  onMeta?: (data: Record<string, unknown>) => void;
  onDelta?: (delta: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
  onAbort?: () => void;
};

/**
 * Create an AbortController bound to a single chat turn.
 * Call .abort() to stop the stream mid-flight. The backend
 * (Uvicorn / Starlette) detects the disconnected client and
 * stops the local inference loop automatically.
 */
export function createChatAbortController(): AbortController {
  return new AbortController();
}

export async function getAuthSession(): Promise<AuthSessionPayload> {
  const response = await fetch(`${API_BASE}/api/auth/session`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to load auth session");
  }
  return response.json();
}

export async function startSession(payload: Record<string, unknown>): Promise<StartSessionPayload> {
  const response = await fetchOrExplain(`${API_BASE}/api/session/start`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, "Failed to start session");
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to start session"));
  }
  return response.json();
}

export async function listSessions(clientId: string): Promise<SessionListPayload> {
  const response = await fetch(`${API_BASE}/api/session`, {
    credentials: "include",
    headers: { "x-sift-client-id": clientId },
  });
  if (!response.ok) {
    throw new Error("Failed to load session list");
  }
  return response.json();
}

export async function getSession(sessionId: string, clientId: string): Promise<SessionPayload> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}`, {
    credentials: "include",
    headers: { "x-sift-client-id": clientId },
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to load session"));
  }
  return response.json();
}

export async function updateSessionRuntime(args: {
  sessionId: string;
  clientId: string;
  provider: string;
  model: string;
}): Promise<SessionRuntimePayload> {
  const response = await fetch(`${API_BASE}/api/session/${args.sessionId}/runtime`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: args.provider, model: args.model, clientId: args.clientId }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to update session runtime"));
  }
  return response.json();
}

export async function clearSessionHistory(clientId: string): Promise<{ ok: boolean; sessionsDeleted: number; turnsDeleted: number; eventsDeleted: number }> {
  const response = await fetch(`${API_BASE}/api/session/clear-history`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clientId }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to clear session history"));
  }
  return response.json();
}

export async function listProviders(): Promise<ProviderCatalogPayload> {
  const response = await fetchOrExplain(`${API_BASE}/api/session/providers`, {
    credentials: "include",
  }, "Failed to load provider catalog");
  if (!response.ok) {
    throw new Error("Failed to load provider catalog");
  }
  return response.json();
}

export async function sendHeartbeat(clientId: string): Promise<void> {
  await fetch(`${API_BASE}/api/client/heartbeat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clientId }),
  });
}

export async function postAnalyticsEvent(payload: {
  eventType: string;
  clientId?: string;
  sessionId?: string;
  displayName?: string;
  pathname?: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  await fetch(`${API_BASE}/api/analytics/event`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getOutline(sessionId: string, clientId: string): Promise<OutlinePayload> {
  const response = await fetch(`${API_BASE}/api/outline`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, clientId }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to load outline"));
  }
  return response.json();
}

export async function answerEvaluator(args: {
  sessionId: string;
  clientId: string;
  answer: string;
  evaluatorMode?: string;
  provider?: string;
  model?: string;
  apiKey?: string;
  file?: File | null;
}): Promise<EvaluatorAnswerPayload> {
  const form = new FormData();
  form.set("sessionId", args.sessionId);
  form.set("clientId", args.clientId);
  form.set("answer", args.answer);
  if (args.evaluatorMode) {
    form.set("evaluatorMode", args.evaluatorMode);
  }
  if (args.provider) {
    form.set("provider", args.provider);
  }
  if (args.model) {
    form.set("model", args.model);
  }
  if (args.apiKey) {
    form.set("apiKey", args.apiKey);
  }
  if (args.file) {
    form.set("file", args.file);
  }

  const response = await fetchOrExplain(`${API_BASE}/api/evaluator/answer`, {
    method: "POST",
    credentials: "include",
    body: form,
  }, "Failed to submit evaluator answer");
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to submit evaluator answer"));
  }
  return response.json();
}

export async function getEvaluatorReport(sessionId: string, clientId: string): Promise<EvaluatorReportPayload> {
  const response = await fetch(`${API_BASE}/api/evaluator/${sessionId}/report`, {
    credentials: "include",
    headers: { "x-sift-client-id": clientId },
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to load evaluator report"));
  }
  return response.json();
}

export async function continueEvaluator(sessionId: string, clientId: string): Promise<EvaluatorAnswerPayload> {
  const response = await fetch(`${API_BASE}/api/evaluator/${sessionId}/deeper`, {
    method: "POST",
    credentials: "include",
    headers: { "x-sift-client-id": clientId },
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to continue evaluator"));
  }
  return response.json();
}

function parseEventBlock(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  return { event, data: dataLines.join("\n") };
}

export async function streamChat(args: {
  sessionId: string;
  clientId: string;
  message: string;
  responseProfile: ResponseProfile;
  provider?: string;
  model?: string;
  apiKey?: string;
  helpMode?: string;
  liveWebEnabled?: boolean;
  file?: File | null;
  signal?: AbortSignal;
  handlers: StreamHandlers;
}): Promise<void> {
  const form = new FormData();
  form.set("sessionId", args.sessionId);
  form.set("clientId", args.clientId);
  form.set("message", args.message);
  form.set("responseProfile", args.responseProfile);
  if (args.provider) {
    form.set("provider", args.provider);
  }
  if (args.model) {
    form.set("model", args.model);
  }
  if (args.apiKey) {
    form.set("apiKey", args.apiKey);
  }
  if (args.helpMode) {
    form.set("helpMode", args.helpMode);
  }
  if (typeof args.liveWebEnabled === "boolean") {
    form.set("liveWebEnabled", String(args.liveWebEnabled));
  }
  if (args.file) {
    form.set("file", args.file);
  }

  const response = await fetchOrExplain(`${API_BASE}/api/chat`, {
    method: "POST",
    credentials: "include",
    body: form,
    signal: args.signal,
  }, "Failed to stream chat response");
  if (!response.ok || !response.body) {
    throw new Error(await readApiError(response, "Failed to stream chat response"));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      // Honour an abort signal even between chunk reads.
      if (args.signal?.aborted) {
        await reader.cancel();
        args.handlers.onAbort?.();
        return;
      }

      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        const parsed = parseEventBlock(block.trim());
        if (!parsed) {
          continue;
        }

        const payload = JSON.parse(parsed.data) as Record<string, unknown>;
        if (parsed.event === "meta") {
          args.handlers.onMeta?.(payload);
        }
        if (parsed.event === "delta") {
          args.handlers.onDelta?.((payload.delta as string) ?? "");
        }
        if (parsed.event === "done") {
          args.handlers.onDone?.(payload);
        }
        if (parsed.event === "error") {
          args.handlers.onError?.((payload.message as string) ?? "Unknown stream error");
        }
      }

      if (done) {
        break;
      }
    }
  } catch (err) {
    if (
      err instanceof Error &&
      (err.name === "AbortError" || args.signal?.aborted)
    ) {
      // Clean abort — not an error from the user's perspective.
      args.handlers.onAbort?.();
      return;
    }
    throw err;
  } finally {
    // Release the lock regardless of how we exited.
    try { reader.releaseLock(); } catch { /* ignore */ }
  }
}

export async function getAdminOverview(token: string): Promise<AdminOverview> {
  const response = await fetch(`${API_BASE}/api/admin/overview`, {
    credentials: "include",
    headers: token ? { "x-admin-token": token } : {},
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Admin token required" : "Failed to load admin overview");
  }
  return response.json();
}

export async function getAdminEvents(token: string): Promise<AdminEventsPayload> {
  const response = await fetch(`${API_BASE}/api/admin/events`, {
    credentials: "include",
    headers: token ? { "x-admin-token": token } : {},
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Admin token required" : "Failed to load admin activity");
  }
  return response.json();
}

export async function deleteSession(sessionId: string, token: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/admin/sessions/${sessionId}`, {
    method: "DELETE",
    credentials: "include",
    headers: token ? { "x-admin-token": token } : {},
  });
  if (!response.ok) {
    throw new Error("Failed to delete session");
  }
}

export async function getSessionTranscript(sessionId: string, token: string): Promise<{role: string, content: string}[]> {
  const response = await fetch(`${API_BASE}/api/admin/sessions/${sessionId}/transcript`, {
    credentials: "include",
    headers: token ? { "x-admin-token": token } : {},
  });
  if (!response.ok) {
    throw new Error("Failed to load transcript");
  }
  return response.json();
}
