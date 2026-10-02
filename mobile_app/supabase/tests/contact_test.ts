import { parseContactPayload } from "../functions/nexstep-mobile-api/_shared/contact.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

Deno.test("mobile contact parser normalizes all supported fields", () => {
  const parsed = parseContactPayload({
    fullName: "  Awa Test  ",
    roleTitle: " Manager ",
    phone: "+237 699 000 111",
    email: " AWA@EXAMPLE.TEST ",
    whatsapp: "+237699000111",
    notes: " WhatsApp first ",
  });
  assert(parsed.error === null, "A valid contact was rejected");
  assert(parsed.contact.full_name === "Awa Test", "The name was not trimmed");
  assert(
    parsed.contact.email === "awa@example.test",
    "The email was not normalized",
  );
  assert(
    parsed.contact.phone_normalized === "237699000111",
    "The phone was not normalized",
  );
});

Deno.test("mobile contact parser requires an identity or contact channel", () => {
  const parsed = parseContactPayload({
    roleTitle: "Manager",
    notes: "Unknown name",
  });
  assert(
    parsed.error === "contact_required",
    "An anonymous contact was accepted",
  );
});

Deno.test("mobile contact parser rejects malformed email addresses", () => {
  const parsed = parseContactPayload({
    fullName: "Awa",
    email: "not-an-email",
  });
  assert(
    parsed.error === "invalid_email",
    "A malformed email address was accepted",
  );
});
