type SessionCredential = {
  provider: string;
  model: string;
  apiKey: string;
};

function storageKey(sessionId: string) {
  return `vishwakarma-session-key:${sessionId}`;
}

export function loadSessionCredential(sessionId: string): SessionCredential | null {
  try {
    const raw = sessionStorage.getItem(storageKey(sessionId));
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as SessionCredential;
  } catch {
    return null;
  }
}

export function saveSessionCredential(sessionId: string, credential: SessionCredential | null): void {
  if (!credential || !credential.apiKey.trim()) {
    sessionStorage.removeItem(storageKey(sessionId));
    return;
  }
  sessionStorage.setItem(storageKey(sessionId), JSON.stringify(credential));
}
