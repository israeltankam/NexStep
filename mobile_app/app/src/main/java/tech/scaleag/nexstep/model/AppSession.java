package tech.scaleag.nexstep.model;

import org.json.JSONException;
import org.json.JSONObject;

import java.time.Instant;

/** Immutable mobile session and user-facing profile. */
public final class AppSession {

    private final String accessToken;
    private final String expiresAt;
    private final JSONObject profile;

    public AppSession(String accessToken, String expiresAt, JSONObject profile) {
        this.accessToken = accessToken;
        this.expiresAt = expiresAt;
        this.profile = profile;
    }

    public static AppSession fromPayload(JSONObject payload) throws JSONException {
        return new AppSession(
            payload.getString("accessToken"),
            payload.getString("expiresAt"),
            payload.getJSONObject("profile")
        );
    }

    public String accessToken() {
        return accessToken;
    }

    public String expiresAt() {
        return expiresAt;
    }

    public JSONObject profile() {
        return profile;
    }

    public String displayName() {
        return profile.optString("displayName", "");
    }

    public String organizationName() {
        return profile.optString("organizationName", "NexStep");
    }

    public String role() {
        return profile.optString("role", "agent");
    }

    public String language() {
        return profile.optString("language", "fr");
    }

    public boolean canViewTeam() {
        return profile.optBoolean("canViewTeam");
    }

    public boolean isGlobalAdmin() {
        return profile.optBoolean("isGlobalAdmin");
    }

    public boolean isAdministrator() {
        return isGlobalAdmin() ||
            "company_admin".equals(role()) ||
            "super_admin".equals(role());
    }

    public boolean isExpired() {
        try {
            return Instant.parse(expiresAt).isBefore(Instant.now());
        } catch (Exception exception) {
            return true;
        }
    }
}
