package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import tech.scaleag.nexstep.MainActivity;
import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;

/** Native daily view showing one priority action and one decision at a time. */
@SuppressLint("ViewConstructor")
public final class NextActionView extends LinearLayout {

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final ActionWorkflow workflow;
    private JSONArray actions = new JSONArray();
    private int currentIndex;

    public NextActionView(Context context, NexStepApiClient api, AppSession session) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        workflow = new ActionWorkflow(context, api, session);
        setOrientation(VERTICAL);
        load();
    }

    private void load() {
        removeAllViews();
        LinearLayout loading = UiKit.vertical(context);
        loading.setGravity(Gravity.CENTER);
        loading.addView(UiKit.progress(context));
        loading.addView(UiKit.caption(context, context.getString(R.string.loading_actions)));
        addView(loading);
        api.call("actions", new JSONObject(), session.accessToken(), new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                actions = data.optJSONArray("actions");
                if (actions == null) actions = new JSONArray();
                currentIndex = 0;
                renderCurrent();
            }

            @Override
            public void onError(String errorCode) {
                renderError(errorCode);
            }
        });
    }

    private void renderCurrent() {
        removeAllViews();
        LinearLayout content = UiKit.vertical(context);
        content.addView(UiKit.title(context, "🚀 " + context.getString(R.string.do_now)));
        content.addView(UiKit.caption(context, context.getString(R.string.do_now_caption)));
        if (currentIndex >= actions.length()) {
            content.addView(UiKit.heading(context, context.getString(R.string.no_action)));
            content.addView(UiKit.body(context, context.getString(R.string.no_action_detail)));
            Button again = UiKit.commandButton(context, context.getString(R.string.review_again));
            again.setOnClickListener(view -> {
                currentIndex = 0;
                renderCurrent();
            });
            if (actions.length() > 0) content.addView(again);
            addView(UiKit.scroll(context, content));
            return;
        }

        JSONObject action = actions.optJSONObject(currentIndex);
        if (action == null) {
            currentIndex += 1;
            renderCurrent();
            return;
        }
        String color = action.optString("urgencyColor", "gray");
        content.addView(UiKit.urgency(
            context,
            color,
            UiKit.urgencyLabel(context, color)
        ));
        content.addView(UiKit.heading(context, action.optString("leadName")));
        content.addView(UiKit.body(context, action.optString("title")));
        if (!action.optString("due_date").isBlank()) {
            content.addView(UiKit.caption(
                context,
                context.getString(R.string.due_date_value, action.optString("due_date"))
            ));
        }
        if (!action.optString("contactName").isBlank()) {
            content.addView(UiKit.caption(
                context,
                context.getString(R.string.contact_value, action.optString("contactName"))
            ));
        }
        String phone = action.optString("phoneRaw");
        if (!phone.isBlank()) {
            Button phoneButton = UiKit.commandButton(context, "☎  " + phone);
            phoneButton.setOnClickListener(view -> context.startActivity(
                new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(phone)))
            ));
            content.addView(phoneButton);
        }
        if (!action.optString("latestComment").isBlank()) {
            content.addView(UiKit.divider(context));
            content.addView(UiKit.caption(context, context.getString(R.string.latest_note)));
            content.addView(UiKit.body(context, action.optString("latestComment")));
        }

        Button done = UiKit.primaryButton(context, "✓  " + context.getString(R.string.done));
        done.setOnClickListener(view -> workflow.complete(action, this::load));
        content.addView(done);
        Button later = UiKit.commandButton(context, "→  " + context.getString(R.string.later));
        later.setOnClickListener(view -> {
            currentIndex += 1;
            renderCurrent();
        });
        content.addView(later);

        content.addView(UiKit.heading(context, context.getString(R.string.more_options)));
        Button comment = UiKit.commandButton(context, "💬  " + context.getString(R.string.add_comment));
        comment.setOnClickListener(view -> workflow.addComment(action, this::load));
        content.addView(comment);
        Button calendar = UiKit.commandButton(context, "📅  " + context.getString(R.string.add_to_calendar));
        calendar.setOnClickListener(view -> workflow.openCalendar(action));
        content.addView(calendar);
        Button ics = UiKit.commandButton(context, "⇩  " + context.getString(R.string.download_ics));
        ics.setOnClickListener(view -> workflow.downloadIcs(action));
        content.addView(ics);
        Button transfer = UiKit.commandButton(context, "↗  " + context.getString(R.string.transfer_action));
        transfer.setOnClickListener(view -> workflow.transfer(action, this::load));
        content.addView(transfer);
        addView(UiKit.scroll(context, content));
    }

    private void renderError(String errorCode) {
        removeAllViews();
        LinearLayout error = UiKit.vertical(context);
        String message = context instanceof MainActivity
            ? ((MainActivity) context).errorMessage(errorCode)
            : context.getString(R.string.generic_error);
        error.addView(UiKit.heading(context, message));
        Button retry = UiKit.primaryButton(context, context.getString(R.string.retry));
        retry.setOnClickListener(view -> load());
        error.addView(retry);
        addView(error);
    }
}
