export type WorkspaceIdentity = {
  displayName: string;
  emailOrHandle: string;
  accessKey: string;
  clientId: string;
};

const KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const ACCESS_KEY_PREFIX = "SF";
const CLIENT_ID_PREFIX = "wk";

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
  return `${ACCESS_KEY_PREFIX}${randomKeyPart(14)}`;
}

export function normalizeAccessKey(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
}

export function normalizeIdentityHandle(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

function base64UrlFromBytes(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  if (typeof btoa === "function") {
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function fallbackDigest(value: string): string {
  let hashOne = 0x811c9dc5;
  let hashTwo = 0x01000193;
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    hashOne ^= code;
    hashOne = Math.imul(hashOne, 0x01000193);
    hashTwo ^= code + index;
    hashTwo = Math.imul(hashTwo, 0x85ebca6b);
  }
  const mixed = [
    hashOne >>> 0,
    hashTwo >>> 0,
    Math.imul(hashOne ^ hashTwo, 0xc2b2ae35) >>> 0,
  ];
  return mixed.map((part) => part.toString(36).padStart(7, "0")).join("").slice(0, 22);
}

function buildLegacyIdentityClientId(emailOrHandle: string, accessKey: string): string {
  const handle = normalizeIdentityHandle(emailOrHandle);
  const key = normalizeAccessKey(accessKey);
  if (!handle || !key) {
    return "";
  }
  return `beta:${handle}:${key}`;
}

export async function buildIdentityClientId(emailOrHandle: string, accessKey: string): Promise<string> {
  const handle = normalizeIdentityHandle(emailOrHandle);
  const key = normalizeAccessKey(accessKey);
  if (!handle || !key) {
    return "";
  }
  if (key.startsWith("SIFT")) {
    return buildLegacyIdentityClientId(handle, key);
  }
  const source = `sift-workspace-v2:${handle}:${key}`;
  if (typeof crypto !== "undefined" && crypto.subtle && typeof TextEncoder !== "undefined") {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(source));
    return `${CLIENT_ID_PREFIX}_${base64UrlFromBytes(new Uint8Array(digest)).slice(0, 22)}`;
  }
  return `${CLIENT_ID_PREFIX}_${fallbackDigest(source)}`;
}

export async function createWorkspaceIdentity(displayName: string, emailOrHandle: string, accessKey: string): Promise<WorkspaceIdentity | null> {
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
    clientId: await buildIdentityClientId(cleanHandle, cleanKey),
  };
}
