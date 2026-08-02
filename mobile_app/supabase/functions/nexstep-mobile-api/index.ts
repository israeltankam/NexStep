import { authenticate, identifyLogin, login, requestPasswordReset } from "./_shared/auth.ts";
import { adminClient, validPublishableKey } from "./_shared/client.ts";
import {
  actionList,
  backup,
  bootstrap,
  leadBoard,
  nextAction,
  pendingPasswordResets,
} from "./_shared/read.ts";
import type { ApiResult, JsonObject } from "./_shared/types.ts";
import {
  addComment,
  completeAction,
  createLead,
  logout,
  reviewPasswordReset,
  setLanguage,
  transferAction,
} from "./_shared/write.ts";

function response(result: ApiResult): Response {
  const status = result.status ?? (result.error ? 400 : 200);
  return Response.json(
    result.error
      ? { ok: false, error: result.error }
      : { ok: true, data: result.data ?? {} },
    {
      status,
      headers: {
        "cache-control": "no-store",
        "content-type": "application/json; charset=utf-8",
      },
    },
  );
}

Deno.serve(async (request: Request): Promise<Response> => {
    if (request.method !== "POST") {
      return response({ status: 405, error: "method_not_allowed" });
    }
    if (!validPublishableKey(request)) {
      return response({ status: 401, error: "invalid_client_key" });
    }

    try {
      const body = await request.json() as JsonObject;
      const operation = String(body.operation ?? "");
      const payload = (body.payload && typeof body.payload === "object"
        ? body.payload
        : {}) as JsonObject;
      const db = adminClient();

      if (operation === "identify_login") {
        return response(await identifyLogin(db, payload, request));
      }
      if (operation === "login") return response(await login(db, payload, request));
      if (operation === "request_password_reset") {
        return response(await requestPasswordReset(db, payload, request));
      }
      if (operation === "health") return response({ data: { status: "ok" } });

      const context = await authenticate(db, request);
      if (!context) return response({ status: 401, error: "session_expired" });

      switch (operation) {
        case "bootstrap":
          return response(await bootstrap(context));
        case "next_action":
          return response(await nextAction(context));
        case "actions":
          return response(await actionList(context));
        case "lead_board":
          return response(await leadBoard(context, payload));
        case "create_lead":
          return response(await createLead(context, payload));
        case "complete_action":
          return response(await completeAction(context, payload));
        case "transfer_action":
          return response(await transferAction(context, payload));
        case "add_comment":
          return response(await addComment(context, payload));
        case "set_language":
          return response(await setLanguage(context, payload));
        case "pending_password_resets":
          return response(await pendingPasswordResets(context));
        case "review_password_reset":
          return response(await reviewPasswordReset(context, payload));
        case "backup":
          return response(await backup(context, payload));
        case "logout":
          return response(await logout(context));
        default:
          return response({ status: 404, error: "unknown_operation" });
      }
    } catch (error) {
      const code = error instanceof Error ? error.message : "server_error";
      const safeCodes = new Set([
        "too_many_attempts",
        "app_pin_pepper_missing",
        "server_secret_key_missing",
        "supabase_url_missing",
        "database_error",
      ]);
      return response({
        status: code === "too_many_attempts" ? 429 : 500,
        error: safeCodes.has(code) ? code : "server_error",
      });
    }
});
