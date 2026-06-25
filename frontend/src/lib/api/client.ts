import type {
  EvaluatorReportPayload,
  SessionPayload,
  StartSessionPayload,
} from "../../app/types";

export const API_BASE = (() => {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (explicit) {
    return explicit.replace(/\/$/, "");
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
      if (text) return text;
    } catch {
      return fallback;
    }
  }
  return fallback;
}

async function fetchOrExplain(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  fallback: string,
): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new Error(`${fallback}. Make sure the Sift backend is running.`);
  }
}

export function createChatAbortController(): AbortController {
  return new AbortController();
}

export async function startSession(
  payload: Record<string, unknown>,
): Promise<StartSessionPayload> {
  const response = await fetchOrExplain(
    `${API_BASE}/api/session/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "include",
    },
    "Could not start session",
  );
  if (!response.ok) {
    const detail = await readApiError(response, "Failed to start session.");
    throw new Error(detail);
  }
  return response.json();
}

export async function getSession(sessionId: string): Promise<SessionPayload> {
  const response = await fetchOrExplain(
    `${API_BASE}/api/session/${sessionId}`,
    { credentials: "include" },
    "Could not load session",
  );
  if (!response.ok) {
    throw new Error("Session not found.");
  }
  return response.json();
}

export async function uploadFile(
  sessionId: string,
  file: File,
  apiKey?: string,
): Promise<{ name: string; docType: string; chunkCount: number }> {
  const form = new FormData();
  form.append("file", file);
  const headers: Record<string, string> = {};
  if (apiKey) headers["X-API-Key"] = apiKey;
  const response = await fetchOrExplain(
    `${API_BASE}/api/session/${sessionId}/upload`,
    { method: "POST", body: form, headers, credentials: "include" },
    "Upload failed",
  );
  if (!response.ok) {
    const detail = await readApiError(response, "Failed to upload file.");
    throw new Error(detail);
  }
  return response.json();
}

export async function runEvaluator(
  sessionId: string,
  apiKey?: string,
): Promise<EvaluatorReportPayload> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) headers["X-API-Key"] = apiKey;
  const response = await fetchOrExplain(
    `${API_BASE}/api/session/${sessionId}/evaluate`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({}),
      credentials: "include",
    },
    "Evaluation failed",
  );
  if (!response.ok) {
    const detail = await readApiError(response, "Failed to run evaluation.");
    throw new Error(detail);
  }
  return response.json();
}

export type StreamHandlers = {
  onDelta?: (delta: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
};

export async function sendChatMessage(
  sessionId: string,
  message: string,
  signal: AbortSignal,
  handlers: StreamHandlers,
  apiKey?: string,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (apiKey) headers["X-API-Key"] = apiKey;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/session/${sessionId}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({ message, stream: true }),
      signal,
      credentials: "include",
    });
  } catch (err: unknown) {
    if ((err as Error).name === "AbortError") return;
    handlers.onError?.("Could not reach the Sift backend.");
    return;
  }

  if (!response.ok) {
    const detail = await readApiError(response, "Chat request failed.");
    handlers.onError?.(detail);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    handlers.onError?.("No response stream.");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    let chunk: ReadableStreamReadResult<Uint8Array>;
    try {
      chunk = await reader.read();
    } catch {
      break;
    }
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith("data:")) continue;
      const raw = trimmed.slice(5).trim();
      if (raw === "[DONE]") {
        handlers.onDone?.({});
        return;
      }
      try {
        const parsed = JSON.parse(raw) as Record<string, unknown>;
        if (parsed.delta && typeof parsed.delta === "string") {
          handlers.onDelta?.(parsed.delta);
        } else if (parsed.done) {
          handlers.onDone?.(parsed);
          return;
        } else if (parsed.error && typeof parsed.error === "string") {
          handlers.onError?.(parsed.error);
          return;
        }
      } catch {
        if (raw) handlers.onDelta?.(raw);
      }
    }
  }
  handlers.onDone?.({});
}

export async function listProviders(): Promise<{
  providers: Array<{ key: string; label: string; requiresApiKey: boolean; serverConfigured?: boolean; defaultBalancedModel: string; defaultSpeedModel: string }>;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/providers`, { credentials: "include" });
    if (!response.ok) return { providers: [] };
    return response.json();
  } catch {
    return { providers: [] };
  }
}
