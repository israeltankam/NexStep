const encoder = new TextEncoder();

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_");
}

function base64UrlToBytes(value: string): Uint8Array {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(normalized);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

export function normalizePin(value: unknown): string {
  return String(value ?? "").trim().toLocaleLowerCase();
}

export async function hmacHex(secret: string, value: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return bytesToHex(new Uint8Array(signature));
}

async function pbkdf2(
  secret: string,
  salt: Uint8Array,
  iterations: number,
): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  // Copying fixes the backing type to ArrayBuffer for Web Crypto on Deno 2.
  const stableSalt = Uint8Array.from(salt);
  const result = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: stableSalt, iterations },
    key,
    256,
  );
  return new Uint8Array(result);
}

function timingSafeEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

export async function verifyStoredSecret(
  supplied: string,
  storedHash: string | null,
  options: { normalize: boolean; pepper: string | null },
): Promise<boolean> {
  if (!storedHash) return false;
  const parts = storedHash.split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2_sha256") return false;

  const iterations = Number(parts[1]);
  if (!Number.isInteger(iterations) || iterations < 1) return false;
  try {
    let raw = options.normalize ? normalizePin(supplied) : String(supplied);
    if (options.pepper !== null) raw += options.pepper;
    const actual = await pbkdf2(raw, base64UrlToBytes(parts[2]), iterations);
    return timingSafeEqual(actual, base64UrlToBytes(parts[3]));
  } catch {
    return false;
  }
}

export async function hashPassword(password: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iterations = 240_000;
  const digest = await pbkdf2(password, salt, iterations);
  return [
    "pbkdf2_sha256",
    String(iterations),
    bytesToBase64Url(salt),
    bytesToBase64Url(digest),
  ].join("$");
}

export function randomToken(): string {
  return bytesToBase64Url(crypto.getRandomValues(new Uint8Array(32)));
}
