package tech.scaleag.nexstep.util;

import android.content.Context;
import android.content.res.Configuration;

import java.util.Locale;

/** Applies the user's FR/EN choice before native views are created. */
public final class LanguageManager {

    private static final String PREFERENCES = "nexstep_language";
    private static final String LANGUAGE = "language";

    private LanguageManager() {
    }

    public static Context apply(Context context) {
        String code = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .getString(LANGUAGE, Locale.getDefault().getLanguage());
        return localized(context, "en".equals(code) ? "en" : "fr");
    }

    public static void save(Context context, String language) {
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .edit()
            .putString(LANGUAGE, "en".equals(language) ? "en" : "fr")
            .apply();
    }

    public static String current(Context context) {
        return context.getResources().getConfiguration().getLocales().get(0).getLanguage();
    }

    private static Context localized(Context context, String code) {
        Locale locale = Locale.forLanguageTag(code);
        Locale.setDefault(locale);
        Configuration configuration = new Configuration(context.getResources().getConfiguration());
        configuration.setLocale(locale);
        return context.createConfigurationContext(configuration);
    }
}
