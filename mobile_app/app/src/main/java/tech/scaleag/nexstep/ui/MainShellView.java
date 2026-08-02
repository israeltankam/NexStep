package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;

/** Persistent native header, navigation, and screen host. */
@SuppressLint("ViewConstructor")
public final class MainShellView extends LinearLayout {

    public interface Listener {
        void onLogout();

        void onLanguage(String language);
    }

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final JSONObject bootstrap;
    private final FrameLayout content;

    public MainShellView(
        Context context,
        NexStepApiClient api,
        AppSession session,
        JSONObject bootstrap,
        Listener listener
    ) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        this.bootstrap = bootstrap;
        setOrientation(VERTICAL);
        setBackgroundColor(android.graphics.Color.WHITE);

        addView(header(listener));
        content = new FrameLayout(context);
        addView(content, new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1f
        ));
        addView(navigation());
        showNextAction();
    }

    private View header(Listener listener) {
        LinearLayout container = new LinearLayout(context);
        container.setOrientation(VERTICAL);
        container.setBackgroundColor(UiKit.SURFACE_ALT);

        LinearLayout header = new LinearLayout(context);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(
            UiKit.dp(context, 14),
            UiKit.dp(context, 6),
            UiKit.dp(context, 8),
            UiKit.dp(context, 2)
        );

        ImageView logo = new ImageView(context);
        logo.setImageResource(R.drawable.nexstep_logo);
        logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        logo.setContentDescription(context.getString(R.string.app_name));
        header.addView(logo, new LayoutParams(UiKit.dp(context, 105), UiKit.dp(context, 42)));
        header.addView(new View(context), new LayoutParams(0, UiKit.dp(context, 1), 1f));

        ImageView scaleLogo = new ImageView(context);
        scaleLogo.setImageResource(R.drawable.scaleag_logo);
        scaleLogo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        scaleLogo.setContentDescription(context.getString(R.string.open_scale_ag));
        scaleLogo.setOnClickListener(view -> context.startActivity(
            new Intent(Intent.ACTION_VIEW, Uri.parse("https://scale-ag.tech/"))
        ));
        header.addView(scaleLogo, new LayoutParams(UiKit.dp(context, 46), UiKit.dp(context, 38)));

        Button language = new Button(context);
        language.setText("en".equals(session.language()) ? "FR" : "EN");
        language.setContentDescription(context.getString(R.string.change_language));
        language.setOnClickListener(view ->
            listener.onLanguage("en".equals(session.language()) ? "fr" : "en")
        );
        header.addView(language, new LayoutParams(UiKit.dp(context, 48), UiKit.dp(context, 42)));

        Button logout = new Button(context);
        logout.setText("⎋");
        logout.setTextSize(22);
        logout.setContentDescription(context.getString(R.string.logout));
        logout.setOnClickListener(view -> listener.onLogout());
        header.addView(logout, new LayoutParams(UiKit.dp(context, 48), UiKit.dp(context, 42)));
        container.addView(header);

        LinearLayout identity = new LinearLayout(context);
        identity.setOrientation(VERTICAL);
        identity.setPadding(
            UiKit.dp(context, 16),
            0,
            UiKit.dp(context, 16),
            UiKit.dp(context, 8)
        );
        TextView name = UiKit.body(context, session.displayName());
        name.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        identity.addView(name);
        identity.addView(UiKit.caption(context, session.organizationName()));
        container.addView(identity);
        return container;
    }

    private View navigation() {
        HorizontalScrollView scroll = new HorizontalScrollView(context);
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout navigation = new LinearLayout(context);
        navigation.setPadding(
            UiKit.dp(context, 6),
            UiKit.dp(context, 6),
            UiKit.dp(context, 6),
            UiKit.dp(context, 8)
        );
        navigation.setBackgroundColor(UiKit.SURFACE_ALT);
        navigation.addView(navButton("🚀", R.string.nav_now, view -> showNextAction()));
        navigation.addView(navButton("➕", R.string.nav_add, view -> showNewLead()));
        navigation.addView(navButton("📊", R.string.nav_board, view -> showLeadBoard()));
        navigation.addView(navButton("✅", R.string.nav_actions, view -> showActions()));
        if (session.isAdministrator()) {
            navigation.addView(navButton("⚙", R.string.nav_admin, view -> showAdmin()));
        }
        scroll.addView(navigation);
        return scroll;
    }

    private Button navButton(String icon, int labelResource, OnClickListener listener) {
        Button button = new Button(context);
        button.setText(context.getString(
            R.string.navigation_item,
            icon,
            context.getString(labelResource)
        ));
        button.setAllCaps(false);
        button.setTextSize(12);
        button.setGravity(Gravity.CENTER);
        button.setOnClickListener(listener);
        button.setMinWidth(UiKit.dp(context, 94));
        return button;
    }

    private void replace(View screen) {
        content.removeAllViews();
        content.addView(screen, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
    }

    private void showNextAction() {
        replace(new NextActionView(context, api, session));
    }

    private void showNewLead() {
        replace(new NewLeadView(context, api, session, bootstrap, this::showNextAction));
    }

    private void showLeadBoard() {
        replace(new LeadBoardView(context, api, session, bootstrap));
    }

    private void showActions() {
        replace(new ActionsView(context, api, session));
    }

    private void showAdmin() {
        replace(new AdminView(context, api, session));
    }
}
