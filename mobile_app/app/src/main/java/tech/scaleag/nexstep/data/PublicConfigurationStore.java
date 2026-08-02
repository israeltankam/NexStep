package tech.scaleag.nexstep.data;

import android.content.Context;
import android.content.SharedPreferences;

import java.net.URI;

import tech.scaleag.nexstep.BuildConfig;

/** Stores only the public Supabase coordinates used by the mobile client. */
public final class PublicConfigurationStore {

    public record Configuration(String projectUrl, String publishableKey) {
    }

    private static final String PREFERENCES = "nexstep_public_configuration";
    private static final String PROJECT_URL = "project_url";
    private static final String PUBLISHABLE_KEY = "publishable_key";

    private final SharedPreferences preferences;

    public PublicConfigurationStore(Context context) {
        preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    /** Returns a complete valid configuration or null when setup is required. */
    public Configuration load() {
        String storedUrl = preferences.getString(PROJECT_URL, "");
        String storedKey = preferences.getString(PUBLISHABLE_KEY, "");
        if (validate(storedUrl, storedKey) == null) {
            return new Configuration(storedUrl.trim(), storedKey.trim());
        }
        if (validate(BuildConfig.SUPABASE_PROJECT_URL, BuildConfig.SUPABASE_PUBLISHABLE_KEY) == null) {
            return new Configuration(
                BuildConfig.SUPABASE_PROJECT_URL.trim(),
                BuildConfig.SUPABASE_PUBLISHABLE_KEY.trim()
            );
        }
        return null;
    }

    public String suggestedUrl() {
        String stored = preferences.getString(PROJECT_URL, "").trim();
        if (!stored.isEmpty()) return stored;
        String builtIn = BuildConfig.SUPABASE_PROJECT_URL.trim();
        return builtIn.contains("your-project") ? "" : builtIn;
    }

    public String suggestedKey() {
        String stored = preferences.getString(PUBLISHABLE_KEY, "").trim();
        if (!stored.isEmpty()) return stored;
        String builtIn = BuildConfig.SUPABASE_PUBLISHABLE_KEY.trim();
        return isPublicKey(builtIn) ? builtIn : "";
    }

    public void save(Configuration configuration) {
        preferences.edit()
            .putString(PROJECT_URL, configuration.projectUrl())
            .putString(PUBLISHABLE_KEY, configuration.publishableKey())
            .apply();
    }

    /** Returns a stable error code, or null when both public values are valid. */
    public static String validate(String rawUrl, String rawKey) {
        String url = rawUrl == null ? "" : rawUrl.trim();
        String key = rawKey == null ? "" : rawKey.trim();
        if (url.isEmpty()) return "configuration_url_required";
        try {
            URI parsed = URI.create(url);
            if (!"https".equalsIgnoreCase(parsed.getScheme()) ||
                parsed.getHost() == null ||
                parsed.getUserInfo() != null ||
                parsed.getQuery() != null ||
                parsed.getFragment() != null ||
                (parsed.getPath() != null && !parsed.getPath().isBlank() && !"/".equals(parsed.getPath()))) {
                return "configuration_url_invalid";
            }
        } catch (IllegalArgumentException exception) {
            return "configuration_url_invalid";
        }
        if (!isPublicKey(key)) return "configuration_key_invalid";
        return null;
    }

    private static boolean isPublicKey(String key) {
        if (key == null || key.length() < 20) return false;
        // Only public formats are accepted. Secret formats deliberately have no accepted prefix.
        return key.startsWith("sb_" + "publishable_") || key.startsWith("eyJ");
    }
}
