export type WorkspaceIdentity = {
  displayName: string;
  emailOrHandle: string;
  accessKey: string;
  clientId: string;
};

const KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function randomKeyPart(length: number): string {
  const values = new Uint8Array(length);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(values);
  } else {
    for (let index = 0; index < length; index += 1) {
      values[index] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(values, (value) => KEY_ALPHABET[value % KEY_ALPHABET.length]).join("");
}

export function generateAccessKey(): string {
  return `SIFT-${randomKeyPart(4)}-${randomKeyPart(4)}-${randomKeyPart(4)}`;
}

export function normalizeAccessKey(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
}

export function normalizeIdentityHandle(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

export function buildIdentityClientId(emailOrHandle: string, accessKey: string): string {
  const handle = normalizeIdentityHandle(emailOrHandle);
  const key = normalizeAccessKey(accessKey);
  return handle && key ? `beta:${handle}:${key}` : "";
}

export function createWorkspaceIdentity(displayName: string, emailOrHandle: string, accessKey: string): WorkspaceIdentity | null {
  const cleanName = displayName.trim();
  const cleanHandle = normalizeIdentityHandle(emailOrHandle);
  const cleanKey = normalizeAccessKey(accessKey);
  if (!cleanName || !cleanHandle || cleanKey.length < 8) {
    return null;
  }
  return {
    displayName: cleanName,
    emailOrHandle: cleanHandle,
    accessKey: cleanKey,
    clientId: buildIdentityClientId(cleanHandle, cleanKey),
  };
}
