import type { SupabaseClient } from "npm:@supabase/supabase-js@2";

export type JsonObject = Record<string, unknown>;

export interface SessionContext {
  db: SupabaseClient;
  sessionId: string;
  organization: JsonObject;
  user: JsonObject;
  orgUser: JsonObject;
}

export interface ApiResult {
  status?: number;
  data?: unknown;
  error?: string;
}

export function text(value: unknown): string {
  return String(value ?? "");
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function newId(): string {
  return crypto.randomUUID();
}
