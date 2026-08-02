package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Color;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import tech.scaleag.nexstep.R;

/** One-time native setup for the two public Supabase client values. */
@SuppressLint("ViewConstructor")
public final class ConfigurationView extends LinearLayout {

    public interface Listener {
        void onConnect(String projectUrl, String publishableKey);

        void onLanguage(String language);
    }

    private final EditText projectUrl;
    private final EditText publishableKey;
    private final TextView error;
    private final Button connect;

    public ConfigurationView(
        Context context,
        String suggestedUrl,
        String suggestedKey,
        Listener listener
    ) {
        super(context);
        setOrientation(VERTICAL);
        setBackgroundColor(Color.WHITE);

        LinearLayout content = UiKit.vertical(context);
        LinearLayout languageRow = new LinearLayout(context);
        languageRow.setGravity(Gravity.END);
        Button french = compactButton(context, "FR");
        Button english = compactButton(context, "EN");
        french.setOnClickListener(view -> listener.onLanguage("fr"));
        english.setOnClickListener(view -> listener.onLanguage("en"));
        languageRow.addView(french);
        languageRow.addView(english);
        content.addView(languageRow);

        ImageView logo = new ImageView(context);
        logo.setImageResource(R.drawable.nexstep_logo);
        logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        logo.setContentDescription(context.getString(R.string.app_name));
        LinearLayout.LayoutParams logoParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            UiKit.dp(context, 90)
        );
        logoParams.setMargins(0, UiKit.dp(context, 14), 0, UiKit.dp(context, 14));
        content.addView(logo, logoParams);

        content.addView(UiKit.title(context, context.getString(R.string.configuration_required)));
        content.addView(UiKit.body(context, context.getString(R.string.configuration_required_detail)));

        error = UiKit.body(context, "");
        error.setTextColor(Color.rgb(190, 45, 54));
        error.setVisibility(GONE);
        content.addView(error);

        projectUrl = UiKit.input(context, context.getString(R.string.configuration_project_url), false);
        projectUrl.setText(suggestedUrl);
        projectUrl.setSingleLine(true);
        publishableKey = UiKit.input(
            context,
            context.getString(R.string.configuration_publishable_key),
            false
        );
        publishableKey.setText(suggestedKey);
        publishableKey.setSingleLine(true);
        content.addView(projectUrl);
        content.addView(publishableKey);
        content.addView(UiKit.caption(context, context.getString(R.string.configuration_key_location)));

        connect = UiKit.primaryButton(context, context.getString(R.string.configuration_connect));
        connect.setOnClickListener(view -> listener.onConnect(
            projectUrl.getText().toString(),
            publishableKey.getText().toString()
        ));
        content.addView(connect);
        content.addView(UiKit.caption(context, context.getString(R.string.configuration_security_note)));
        addView(UiKit.scroll(context, content), new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1f
        ));
    }

    public void setBusy(boolean busy) {
        projectUrl.setEnabled(!busy);
        publishableKey.setEnabled(!busy);
        connect.setEnabled(!busy);
        connect.setText(busy ? R.string.configuration_testing : R.string.configuration_connect);
    }

    public void showError(String message) {
        error.setText(message);
        error.setVisibility(VISIBLE);
        setBusy(false);
    }

    private Button compactButton(Context context, String label) {
        Button button = new Button(context);
        button.setText(label);
        button.setAllCaps(false);
        button.setMinWidth(UiKit.dp(context, 52));
        button.setMinHeight(UiKit.dp(context, 40));
        return button;
    }
}
