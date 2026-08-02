package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Typeface;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Locale;

import java.util.ArrayList;
import java.util.List;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;

/** Searchable, urgency-filtered native action list. */
@SuppressLint("ViewConstructor")
public final class ActionsView extends LinearLayout {

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final ActionWorkflow workflow;
    private final List<JSONObject> allActions = new ArrayList<>();
    private final List<JSONObject> visibleActions = new ArrayList<>();
    private final ActionAdapter adapter;
    private final EditText search;
    private final Spinner urgency;

    public ActionsView(Context context, NexStepApiClient api, AppSession session) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        workflow = new ActionWorkflow(context, api, session);
        setOrientation(VERTICAL);
        setPadding(UiKit.dp(context, 16), UiKit.dp(context, 12), UiKit.dp(context, 16), 0);

        addView(UiKit.title(context, "✅ " + context.getString(R.string.my_actions)));
        search = UiKit.input(context, context.getString(R.string.search), false);
        search.addTextChangedListener(new SimpleTextWatcher(this::applyFilters));
        addView(search);
        urgency = new Spinner(context);
        urgency.setAdapter(new ArrayAdapter<>(
            context,
            android.R.layout.simple_spinner_dropdown_item,
            new String[] {
                context.getString(R.string.all_urgencies),
                context.getString(R.string.urgency_red),
                context.getString(R.string.urgency_yellow),
                context.getString(R.string.urgency_green),
                context.getString(R.string.urgency_blue),
                context.getString(R.string.urgency_gray)
            }
        ));
        urgency.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                applyFilters();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
        addView(urgency, new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            UiKit.dp(context, 52)
        ));
        ListView list = new ListView(context);
        adapter = new ActionAdapter();
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) ->
            workflow.complete(visibleActions.get(position), this::load)
        );
        addView(list, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        load();
    }

    private void load() {
        api.call("actions", new JSONObject(), session.accessToken(), new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                allActions.clear();
                JSONArray source = data.optJSONArray("actions");
                if (source != null) {
                    for (int index = 0; index < source.length(); index += 1) {
                        JSONObject action = source.optJSONObject(index);
                        if (action != null) allActions.add(action);
                    }
                }
                applyFilters();
            }

            @Override
            public void onError(String errorCode) {
                Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
            }
        });
    }

    private void applyFilters() {
        if (adapter == null) return;
        visibleActions.clear();
        String needle = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        int urgencyIndex = urgency.getSelectedItemPosition();
        String[] colors = {"", "red", "yellow", "green", "blue", "gray"};
        String selectedColor = colors[Math.max(0, urgencyIndex)];
        for (JSONObject action : allActions) {
            String searchable = (
                action.optString("leadName") + " " +
                action.optString("title") + " " +
                action.optString("latestComment")
            ).toLowerCase(Locale.ROOT);
            if (!needle.isEmpty() && !searchable.contains(needle)) continue;
            if (!selectedColor.isEmpty()
                && !selectedColor.equals(action.optString("urgencyColor"))) continue;
            visibleActions.add(action);
        }
        adapter.notifyDataSetChanged();
    }

    private final class ActionAdapter extends BaseAdapter {
        @Override
        public int getCount() {
            return visibleActions.size();
        }

        @Override
        public Object getItem(int position) {
            return visibleActions.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View reusable, ViewGroup parent) {
            JSONObject action = visibleActions.get(position);
            LinearLayout row = UiKit.vertical(context);
            row.setPadding(UiKit.dp(context, 10), UiKit.dp(context, 10), UiKit.dp(context, 10), UiKit.dp(context, 10));
            TextView lead = UiKit.body(context, action.optString("leadName"));
            lead.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            row.addView(lead);
            row.addView(UiKit.caption(context, action.optString("title")));
            row.addView(UiKit.urgency(
                context,
                action.optString("urgencyColor", "gray"),
                UiKit.urgencyLabel(context, action.optString("urgencyColor", "gray"))
            ));
            row.addView(UiKit.divider(context));
            return row;
        }
    }

    private static final class SimpleTextWatcher implements TextWatcher {
        private final Runnable changed;

        private SimpleTextWatcher(Runnable changed) {
            this.changed = changed;
        }

        @Override
        public void beforeTextChanged(CharSequence value, int start, int count, int after) {
        }

        @Override
        public void onTextChanged(CharSequence value, int start, int before, int count) {
            changed.run();
        }

        @Override
        public void afterTextChanged(Editable editable) {
        }
    }
}
