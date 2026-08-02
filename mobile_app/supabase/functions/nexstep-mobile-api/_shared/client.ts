import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2";

function collectKeys(value: unknown, target: Set<string>): void {
  if (typeof value === "string") {
    if (value.startsWith("sb_publishable_") || value.startsWith("eyJ")) {
      target.add(value);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectKeys(item, target));
    return;
  }
  if (value && typeof value === "object") {
    Object.values(value as Record<string, unknown>).forEach((item) => collectKeys(item, target));
  }
}

function firstSecretKey(): string {
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (legacy) return legacy;

  const configured = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (configured) {
    try {
      const candidates = new Set<string>();
      const parsed = JSON.parse(configured);
      const visit = (value: unknown): void => {
        if (typeof value === "string" && (value.startsWith("sb_secret_") || value.startsWith("eyJ"))) {
          candidates.add(value);
        } else if (Array.isArray(value)) {
          value.forEach(visit);
        } else if (value && typeof value === "object") {
          Object.values(value as Record<string, unknown>).forEach(visit);
        }
      };
      visit(parsed);
      const key = candidates.values().next().value;
      if (key) return key;
    } catch {
      // The deployment error below deliberately avoids printing secret content.
    }
  }
  throw new Error("server_secret_key_missing");
}

export function adminClient(): SupabaseClient {
  const projectUrl = Deno.env.get("SUPABASE_URL");
  if (!projectUrl) throw new Error("supabase_url_missing");
  return createClient(projectUrl, firstSecretKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export function validPublishableKey(request: Request): boolean {
  const supplied = request.headers.get("apikey");
  if (!supplied) return false;

  const allowed = new Set<string>();
  const current = Deno.env.get("SUPABASE_PUBLISHABLE_KEYS");
  if (current) {
    try {
      collectKeys(JSON.parse(current), allowed);
    } catch {
      collectKeys(current, allowed);
    }
  }
  const legacy = Deno.env.get("SUPABASE_ANON_KEY");
  if (legacy) allowed.add(legacy);
  return allowed.has(supplied);
}

export function pinPepper(): string {
  const value = Deno.env.get("APP_PIN_PEPPER");
  if (!value) throw new Error("app_pin_pepper_missing");
  return value;
}

export function requireData<T>(
  result: { data: T | null; error: { message: string } | null },
  code = "database_error",
): T {
  if (result.error) throw new Error(code);
  return result.data as T;
}
