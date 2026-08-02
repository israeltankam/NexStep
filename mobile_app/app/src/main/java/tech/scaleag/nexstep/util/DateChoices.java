package tech.scaleag.nexstep.util;

import java.time.LocalDate;

/** Resolves the same guided due-date choices used by the Streamlit application. */
public final class DateChoices {

    private DateChoices() {
    }

    public static String fromKey(String key, LocalDate customDate) {
        LocalDate today = LocalDate.now();
        return switch (key) {
            case "today" -> today.toString();
            case "tomorrow" -> today.plusDays(1).toString();
            case "3" -> today.plusDays(3).toString();
            case "7" -> today.plusDays(7).toString();
            case "custom" -> customDate == null ? null : customDate.toString();
            default -> null;
        };
    }
}
