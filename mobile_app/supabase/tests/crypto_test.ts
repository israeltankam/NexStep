import {
  hashPassword,
  hmacHex,
  normalizePin,
  verifyStoredSecret,
} from "../functions/nexstep-mobile-api/_shared/crypto.ts";

const salt = "AAECAwQFBgcICQoLDA0ODw==";
const passwordHash =
  `pbkdf2_sha256$240000$${salt}$9PYOIKtHUqSWr81FZeky5HmzwfJgpn71jhiNQWejO_4=`;
const pinHash =
  `pbkdf2_sha256$240000$${salt}$N_csUt_5FSaRTn7Si53IQUrWc1gpNo31MeqVQljmWUM=`;

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

Deno.test("normalizes PINs like the Python service", () => {
  assert(normalizePin("  AbC123  ") === "abc123", "PIN normalization differs");
});

Deno.test("reproduces the Python HMAC lookup", async () => {
  const lookup = await hmacHex("test-pepper", "1234");
  assert(
    lookup === "997ebdcb6709282e5daccecc2fa603014b0a5aa4b43f0a951e039734e1bb9262",
    "HMAC lookup differs from Python",
  );
});

Deno.test("accepts an existing Python password hash", async () => {
  assert(
    await verifyStoredSecret(
      "Correct Horse",
      passwordHash,
      { normalize: false, pepper: null },
    ),
    "Existing password was rejected",
  );
});

Deno.test("rejects an incorrect password", async () => {
  assert(
    !await verifyStoredSecret(
      "incorrect",
      passwordHash,
      { normalize: false, pepper: null },
    ),
    "Incorrect password was accepted",
  );
});

Deno.test("accepts an existing normalized and peppered PIN", async () => {
  assert(
    await verifyStoredSecret(
      " 1234 ",
      pinHash,
      { normalize: true, pepper: "test-pepper" },
    ),
    "Existing PIN was rejected",
  );
});

Deno.test("rejects a PIN when the server pepper differs", async () => {
  assert(
    !await verifyStoredSecret(
      "1234",
      pinHash,
      { normalize: true, pepper: "wrong-pepper" },
    ),
    "PIN was accepted with the wrong pepper",
  );
});

Deno.test("creates a password hash accepted by its verifier", async () => {
  const generated = await hashPassword("new mobile password");
  assert(
    await verifyStoredSecret(
      "new mobile password",
      generated,
      { normalize: false, pepper: null },
    ),
    "Generated password hash could not be verified",
  );
});
