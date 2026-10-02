import type { JsonObject } from "./types.ts";
import { text } from "./types.ts";

export interface ParsedContact {
  contact: JsonObject;
  error: string | null;
}

const LIMITS: Record<string, number> = {
  fullName: 200,
  roleTitle: 200,
  phone: 80,
  email: 254,
  whatsapp: 80,
  notes: 500,
};

function digitsOnly(value: string): string | null {
  const digits = value.replace(/\D+/g, "");
  return digits || null;
}

/**
 * Normalize the public mobile payload before it reaches PostgreSQL.  The Edge
 * Function uses a service-role client, so validation and organization checks
 * must happen here instead of being delegated to the APK.
 */
export function parseContactPayload(payload: JsonObject): ParsedContact {
  for (const [field, maximum] of Object.entries(LIMITS)) {
    if (text(payload[field]).trim().length > maximum) {
      return { contact: {}, error: "field_too_long" };
    }
  }

  const fullName = text(payload.fullName).trim();
  const roleTitle = text(payload.roleTitle).trim();
  const phone = text(payload.phone).trim();
  const email = text(payload.email).trim().toLocaleLowerCase("en");
  const whatsapp = text(payload.whatsapp).trim();
  const notes = text(payload.notes).trim();
  if (![fullName, phone, email, whatsapp].some(Boolean)) {
    return { contact: {}, error: "contact_required" };
  }
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return { contact: {}, error: "invalid_email" };
  }

  return {
    error: null,
    contact: {
      full_name: fullName || null,
      role_title: roleTitle || null,
      phone_raw: phone || null,
      phone_normalized: digitsOnly(phone),
      email: email || null,
      whatsapp: whatsapp || null,
      channel_notes: notes || null,
    },
  };
}
