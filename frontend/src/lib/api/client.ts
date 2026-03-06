import type {
  AdminEventsPayload,
  AdminOverview,
  OutlinePayload,
  ResponseProfile,
  SessionListPayload,
  SessionPayload,
  StartSessionPayload,
} from "../../app/types";

const API_BASE = (() => {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (explicit) {
    return explicit;
  }
  const { protocol, hostname, port } = window.location;
  if (port === "5173") {
    return `${protocol}//${hostname}:8000`;
  }
  return "";
})();

type StreamHandlers = {
  onMeta?: (data: Record<string, unknown>) => void;
  onDelta?: (delta: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
};

export async function startSession(payload: Record<string, unknown>): Promise<StartSessionPayload> {
  const response = await fetch(`${API_BASE}/api/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Failed to start session");
  }
  return response.json();
}

export async function listSessions(clientId: string): Promise<SessionListPayload> {
  const response = await fetch(`${API_BASE}/api/session?clientId=${encodeURIComponent(clientId)}`);
  if (!response.ok) {
    throw new Error("Failed to load session list");
  }
  return response.json();
}

export async function getSession(sessionId: string): Promise<SessionPayload> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}`);
  if (!response.ok) {
    throw new Error("Failed to load session");
  }
  return response.json();
}

export async function sendHeartbeat(clientId: string): Promise<void> {
  await fetch(`${API_BASE}/api/client/heartbeat`, {
    method: "POST",
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getOutline(sessionId: string): Promise<OutlinePayload> {
  const response = await fetch(`${API_BASE}/api/outline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId }),
  });
  if (!response.ok) {
    throw new Error("Failed to load outline");
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
  message: string;
  responseProfile: ResponseProfile;
  file?: File | null;
  handlers: StreamHandlers;
}): Promise<void> {
  const form = new FormData();
  form.set("sessionId", args.sessionId);
  form.set("message", args.message);
  form.set("responseProfile", args.responseProfile);
  if (args.file) {
    form.set("file", args.file);
  }

  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    body: form,
  });
  if (!response.ok || !response.body) {
    throw new Error("Failed to stream chat response");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
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
}

export async function getAdminOverview(token: string): Promise<AdminOverview> {
  const response = await fetch(`${API_BASE}/api/admin/overview`, {
    headers: token ? { "x-admin-token": token } : {},
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Admin token required" : "Failed to load admin overview");
  }
  return response.json();
}

export async function getAdminEvents(token: string): Promise<AdminEventsPayload> {
  const response = await fetch(`${API_BASE}/api/admin/events`, {
    headers: token ? { "x-admin-token": token } : {},
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Admin token required" : "Failed to load admin activity");
  }
  return response.json();
}
