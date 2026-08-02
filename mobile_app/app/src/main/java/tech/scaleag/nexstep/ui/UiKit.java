package tech.scaleag.nexstep.ui;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import tech.scaleag.nexstep.R;

/** Small native design system shared by every NexStep screen. */
public final class UiKit {

    public static final int GREEN = Color.rgb(22, 131, 92);
    public static final int TEXT = Color.rgb(23, 33, 29);
    public static final int MUTED = Color.rgb(82, 98, 91);
    public static final int BORDER = Color.rgb(216, 225, 220);
    public static final int SURFACE_ALT = Color.rgb(246, 249, 247);

    private UiKit() {
    }

    public static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    public static LinearLayout vertical(Context context) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(context, 20), dp(context, 16), dp(context, 20), dp(context, 24));
        return layout;
    }

    public static ScrollView scroll(Context context, View content) {
        ScrollView scroll = new ScrollView(context);
        scroll.setFillViewport(true);
        scroll.addView(content, new ScrollView.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return scroll;
    }

    public static TextView title(Context context, String value) {
        TextView text = text(context, value, 27, TEXT);
        text.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        text.setPadding(0, 0, 0, dp(context, 8));
        return text;
    }

    public static TextView heading(Context context, String value) {
        TextView text = text(context, value, 20, TEXT);
        text.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        text.setPadding(0, dp(context, 14), 0, dp(context, 8));
        return text;
    }

    public static TextView body(Context context, String value) {
        TextView text = text(context, value, 16, TEXT);
        text.setLineSpacing(dp(context, 3), 1f);
        return text;
    }

    public static TextView caption(Context context, String value) {
        TextView text = text(context, value, 14, MUTED);
        text.setLineSpacing(dp(context, 2), 1f);
        return text;
    }

    private static TextView text(Context context, String value, int size, int color) {
        TextView text = new TextView(context);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(color);
        return text;
    }

    public static EditText input(
        Context context,
        String hint,
        boolean password
    ) {
        EditText input = new EditText(context);
        input.setHint(hint);
        input.setTextSize(16);
        input.setSingleLine(true);
        input.setPadding(dp(context, 12), dp(context, 8), dp(context, 12), dp(context, 8));
        input.setBackground(outline(context, Color.WHITE, BORDER));
        input.setInputType(password
            ? InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
            : InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(context, 52)
        );
        params.bottomMargin = dp(context, 10);
        input.setLayoutParams(params);
        return input;
    }

    public static EditText multiline(Context context, String hint) {
        EditText input = input(context, hint, false);
        input.setSingleLine(false);
        input.setGravity(Gravity.TOP | Gravity.START);
        input.setMinHeight(dp(context, 92));
        input.setLayoutParams(new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return input;
    }

    public static Button primaryButton(Context context, String label) {
        Button button = commandButton(context, label);
        button.setTextColor(Color.WHITE);
        button.setBackground(outline(context, GREEN, GREEN));
        return button;
    }

    public static Button commandButton(Context context, String label) {
        Button button = new Button(context);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(16);
        button.setTextColor(TEXT);
        button.setMinHeight(dp(context, 48));
        button.setBackground(outline(context, Color.WHITE, BORDER));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(context, 50)
        );
        params.bottomMargin = dp(context, 8);
        button.setLayoutParams(params);
        return button;
    }

    public static View divider(Context context) {
        View divider = new View(context);
        divider.setBackgroundColor(BORDER);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(context, 1)
        );
        params.setMargins(0, dp(context, 10), 0, dp(context, 10));
        divider.setLayoutParams(params);
        return divider;
    }

    public static ProgressBar progress(Context context) {
        ProgressBar progress = new ProgressBar(context);
        progress.setIndeterminateTintList(
            android.content.res.ColorStateList.valueOf(GREEN)
        );
        return progress;
    }

    public static TextView urgency(Context context, String color, String label) {
        TextView text = caption(context, label);
        text.setTextColor(Color.WHITE);
        text.setGravity(Gravity.CENTER);
        text.setPadding(dp(context, 9), dp(context, 5), dp(context, 9), dp(context, 5));
        text.setBackground(outline(context, urgencyColor(color), urgencyColor(color)));
        return text;
    }

    public static int urgencyColor(String color) {
        return switch (color) {
            case "red" -> Color.rgb(190, 45, 54);
            case "yellow" -> Color.rgb(190, 137, 0);
            case "green" -> Color.rgb(34, 139, 83);
            case "blue" -> Color.rgb(37, 103, 178);
            default -> Color.rgb(108, 117, 125);
        };
    }

    public static GradientDrawable outline(Context context, int fill, int stroke) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(context, 6));
        drawable.setStroke(dp(context, 1), stroke);
        return drawable;
    }

    public static String urgencyLabel(Context context, String color) {
        return switch (color) {
            case "red" -> context.getString(R.string.urgency_red);
            case "yellow" -> context.getString(R.string.urgency_yellow);
            case "green" -> context.getString(R.string.urgency_green);
            case "blue" -> context.getString(R.string.urgency_blue);
            default -> context.getString(R.string.urgency_gray);
        };
    }
}
