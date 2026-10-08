package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;

/** Read-only team history; every tap fetches only the requested offset page. */
@SuppressLint("ViewConstructor")
public final class TeamActionsView extends LinearLayout {
    private static final int PAGE_SIZE = 20;

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final LinearLayout rows;
    private final TextView range;
    private final Button previous;
    private final Button next;
    private int offset;

    public TeamActionsView(Context context, NexStepApiClient api, AppSession session) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        setOrientation(VERTICAL);
        setPadding(UiKit.dp(context, 16), UiKit.dp(context, 12),
            UiKit.dp(context, 16), UiKit.dp(context, 12));
        addView(UiKit.title(context, "👥 " + context.getString(R.string.team_actions)));
        range = UiKit.caption(context, "");
        addView(range);
        rows = UiKit.vertical(context);
        addView(UiKit.scroll(context, rows), new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        LinearLayout navigation = new LinearLayout(context);
        previous = UiKit.commandButton(context, context.getString(R.string.previous_page));
        next = UiKit.commandButton(context, context.getString(R.string.next_page));
        navigation.addView(previous, new LayoutParams(0, UiKit.dp(context, 50), 1f));
        navigation.addView(next, new LayoutParams(0, UiKit.dp(context, 50), 1f));
        previous.setOnClickListener(view -> load(offset - PAGE_SIZE));
        next.setOnClickListener(view -> load(offset + PAGE_SIZE));
        addView(navigation);
        load(0);
    }

    private void load(int requestedOffset) {
        if (requestedOffset < 0) return;
        previous.setEnabled(false);
        next.setEnabled(false);
        rows.removeAllViews();
        rows.addView(UiKit.progress(context));
        rows.addView(UiKit.caption(context, context.getString(R.string.team_actions_loading)));
        try {
            JSONObject payload = new JSONObject().put("offset", requestedOffset);
            api.call("team_actions", payload, session.accessToken(), new ApiCallback() {
                @Override public void onSuccess(JSONObject data) {
                    JSONArray actions = data.optJSONArray("actions");
                    rows.removeAllViews();
                    if (actions == null || actions.length() == 0) {
                        offset = requestedOffset;
                        range.setText("");
                        rows.addView(UiKit.caption(context,
                            context.getString(R.string.team_actions_empty)));
                        if (requestedOffset > 0) previous.setEnabled(true);
                        return;
                    }
                    offset = requestedOffset;
                    range.setText(context.getString(R.string.team_actions_range,
                        offset + 1, offset + actions.length()));
                    for (int index = 0; index < actions.length(); index++) {
                        JSONObject action = actions.optJSONObject(index);
                        if (action != null) rows.addView(actionRow(action));
                    }
                    previous.setEnabled(offset > 0);
                    next.setEnabled(data.optBoolean("hasMore"));
                }
                @Override public void onError(String code) {
                    rows.removeAllViews();
                    int message = "unknown_operation".equals(code) ||
                        "function_unavailable".equals(code)
                        ? R.string.mobile_update_required : R.string.team_actions_load_error;
                    rows.addView(UiKit.caption(context, context.getString(message)));
                    Button retry = UiKit.commandButton(context, context.getString(R.string.retry));
                    retry.setOnClickListener(view -> load(requestedOffset));
                    rows.addView(retry);
                    previous.setEnabled(offset > 0);
                }
            });
        } catch (JSONException exception) {
            rows.removeAllViews();
            rows.addView(UiKit.caption(context,
                context.getString(R.string.team_actions_load_error)));
        }
    }

    private View actionRow(JSONObject action) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(VERTICAL);
        row.setPadding(0, UiKit.dp(context, 8), 0, UiKit.dp(context, 8));
        row.addView(UiKit.heading(context, action.optString("title")));
        String lead = action.optString("leadName");
        String agent = action.optString("completedByName");
        if (agent.isBlank()) agent = context.getString(R.string.unknown_agent);
        row.addView(UiKit.caption(context, context.getString(R.string.team_action_summary,
            lead, agent, action.optString("completedAt"))));
        String note = action.optString("completionNote");
        if (!note.isBlank()) {
            row.addView(UiKit.body(context,
                note.length() > 240 ? note.substring(0, 240) + "…" : note));
        }
        row.addView(UiKit.divider(context));
        return row;
    }
}
