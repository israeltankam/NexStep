package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Typeface;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.Locale;
import java.util.ArrayList;
import java.util.List;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;
import tech.scaleag.nexstep.util.FileExporter;

/** Native lead board with plain-language filters, details, and Excel export. */
@SuppressLint("ViewConstructor")
public final class LeadBoardView extends LinearLayout {

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final JSONObject bootstrap;
    private final List<JSONObject> allLeads = new ArrayList<>();
    private final List<JSONObject> visibleLeads = new ArrayList<>();
    private final List<String> ownerIds = new ArrayList<>();
    private final BoardAdapter adapter;
    private final EditText search;
    private final Spinner urgency;
    private final Spinner owner;
    private final TextView count;

    public LeadBoardView(
        Context context,
        NexStepApiClient api,
        AppSession session,
        JSONObject bootstrap
    ) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        this.bootstrap = bootstrap;
        setOrientation(VERTICAL);
        setPadding(UiKit.dp(context, 14), UiKit.dp(context, 12), UiKit.dp(context, 14), 0);
        addView(UiKit.title(context, "📊 " + context.getString(R.string.lead_board)));

        search = UiKit.input(context, context.getString(R.string.search_prospects), false);
        search.addTextChangedListener(new SearchWatcher(this::applyFilters));
        addView(search);

        LinearLayout filters = new LinearLayout(context);
        urgency = urgencySpinner();
        owner = ownerSpinner();
        filters.addView(urgency, new LayoutParams(0, UiKit.dp(context, 52), 1f));
        filters.addView(owner, new LayoutParams(0, UiKit.dp(context, 52), 1f));
        addView(filters);

        LinearLayout commands = new LinearLayout(context);
        count = UiKit.caption(context, "");
        commands.addView(count, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button export = new Button(context);
        export.setText(R.string.export_excel);
        export.setAllCaps(false);
        export.setOnClickListener(view -> exportExcel());
        commands.addView(export);
        addView(commands);

        ListView list = new ListView(context);
        adapter = new BoardAdapter();
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) ->
            showDetail(visibleLeads.get(position))
        );
        addView(list, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        load();
    }

    private Spinner urgencySpinner() {
        Spinner spinner = new Spinner(context);
        spinner.setAdapter(new ArrayAdapter<>(
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
        spinner.setOnItemSelectedListener(filterListener());
        return spinner;
    }

    private Spinner ownerSpinner() {
        Spinner spinner = new Spinner(context);
        List<String> labels = new ArrayList<>();
        labels.add(context.getString(R.string.all_agents));
        ownerIds.add("");
        JSONArray members = bootstrap.optJSONArray("teamMembers");
        if (members != null) {
            for (int index = 0; index < members.length(); index += 1) {
                JSONObject member = members.optJSONObject(index);
                if (member == null) continue;
                labels.add(member.optString("displayName"));
                ownerIds.add(member.optString("orgUserId"));
            }
        }
        spinner.setAdapter(new ArrayAdapter<>(
            context,
            android.R.layout.simple_spinner_dropdown_item,
            labels
        ));
        spinner.setVisibility(session.canViewTeam() ? VISIBLE : GONE);
        spinner.setOnItemSelectedListener(filterListener());
        return spinner;
    }

    private AdapterView.OnItemSelectedListener filterListener() {
        return new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                applyFilters();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        };
    }

    private void load() {
        api.call("lead_board", new JSONObject(), session.accessToken(), new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                allLeads.clear();
                JSONArray source = data.optJSONArray("leads");
                if (source != null) {
                    for (int index = 0; index < source.length(); index += 1) {
                        JSONObject lead = source.optJSONObject(index);
                        if (lead != null) allLeads.add(lead);
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
        if (adapter == null || urgency == null || owner == null) return;
        visibleLeads.clear();
        String needle = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        String[] colors = {"", "red", "yellow", "green", "blue", "gray"};
        String color = colors[Math.max(0, urgency.getSelectedItemPosition())];
        int ownerPosition = Math.max(0, owner.getSelectedItemPosition());
        String ownerId = ownerPosition < ownerIds.size() ? ownerIds.get(ownerPosition) : "";

        for (JSONObject lead : allLeads) {
            String searchable = (
                lead.optString("name") + " " +
                lead.optString("contactsText") + " " +
                lead.optString("nextActionTitle") + " " +
                lead.optString("latestComment") + " " +
                lead.optString("ownerName") + " " +
                lead.optString("city")
            ).toLowerCase(Locale.ROOT);
            if (!needle.isEmpty() && !searchable.contains(needle)) continue;
            if (!color.isEmpty() && !color.equals(lead.optString("urgencyColor"))) continue;
            if (!ownerId.isEmpty() && !ownerId.equals(lead.optString("owner_org_user_id"))) continue;
            visibleLeads.add(lead);
        }
        count.setText(context.getResources().getQuantityString(
            R.plurals.prospect_count,
            visibleLeads.size(),
            visibleLeads.size()
        ));
        adapter.notifyDataSetChanged();
    }

    private void showDetail(JSONObject lead) {
        LinearLayout detail = UiKit.vertical(context);
        detail.addView(UiKit.title(context, lead.optString("name")));
        detail.addView(UiKit.caption(
            context,
            context.getString(
                R.string.lead_detail_summary,
                lead.optString("stageName"),
                lead.optString("statusName"),
                lead.optString("ownerName")
            )
        ));

        detail.addView(UiKit.heading(context, context.getString(R.string.contacts)));
        JSONArray contacts = lead.optJSONArray("contacts");
        if (contacts == null || contacts.length() == 0) {
            detail.addView(UiKit.caption(context, context.getString(R.string.no_contact)));
        } else {
            for (int index = 0; index < contacts.length(); index += 1) {
                JSONObject contact = contacts.optJSONObject(index);
                if (contact == null) continue;
                detail.addView(UiKit.body(context, join(
                    contact.optString("full_name"),
                    contact.optString("role_title"),
                    contact.optString("phone_raw"),
                    contact.optString("email"),
                    contact.optString("whatsapp")
                )));
                detail.addView(UiKit.divider(context));
            }
        }

        detail.addView(UiKit.heading(context, context.getString(R.string.actions)));
        JSONArray actions = lead.optJSONArray("actions");
        if (actions == null || actions.length() == 0) {
            detail.addView(UiKit.caption(context, context.getString(R.string.no_action)));
        } else {
            for (int index = 0; index < actions.length(); index += 1) {
                JSONObject action = actions.optJSONObject(index);
                if (action == null) continue;
                detail.addView(UiKit.body(context, join(
                    action.optString("title"),
                    action.optString("status"),
                    action.optString("due_date")
                )));
            }
        }

        detail.addView(UiKit.heading(context, context.getString(R.string.comments)));
        JSONArray comments = lead.optJSONArray("comments");
        if (comments == null || comments.length() == 0) {
            detail.addView(UiKit.caption(context, context.getString(R.string.no_comments)));
        } else {
            for (int index = 0; index < comments.length(); index += 1) {
                JSONObject comment = comments.optJSONObject(index);
                if (comment == null) continue;
                detail.addView(UiKit.body(context, comment.optString("body")));
                detail.addView(UiKit.caption(context, comment.optString("created_at")));
                detail.addView(UiKit.divider(context));
            }
        }

        new AlertDialog.Builder(context)
            .setView(UiKit.scroll(context, detail))
            .setNegativeButton(R.string.close, null)
            .setPositiveButton(R.string.add_comment, (dialog, which) -> addComment(lead))
            .show();
    }

    private void addComment(JSONObject lead) {
        EditText body = UiKit.multiline(context, context.getString(R.string.comment));
        new AlertDialog.Builder(context)
            .setTitle(R.string.add_comment)
            .setView(body)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save, (dialog, which) -> {
                try {
                    JSONObject payload = new JSONObject()
                        .put("leadId", lead.getString("id"))
                        .put("body", body.getText().toString());
                    api.call("add_comment", payload, session.accessToken(), new ApiCallback() {
                        @Override
                        public void onSuccess(JSONObject data) {
                            Toast.makeText(context, R.string.comment_saved, Toast.LENGTH_LONG).show();
                            load();
                        }

                        @Override
                        public void onError(String errorCode) {
                            Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
                        }
                    });
                } catch (JSONException exception) {
                    Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
                }
            })
            .show();
    }

    private void exportExcel() {
        JSONArray export = new JSONArray();
        for (JSONObject lead : visibleLeads) {
            try {
                lead.put(
                    "urgencyLabel",
                    UiKit.urgencyLabel(context, lead.optString("urgencyColor", "gray"))
                );
            } catch (JSONException ignored) {
            }
            export.put(lead);
        }
        try {
            FileExporter.saveLeadBoardExcel(
                context,
                export,
                !"en".equals(session.language())
            );
            Toast.makeText(context, R.string.excel_saved, Toast.LENGTH_LONG).show();
        } catch (IOException exception) {
            Toast.makeText(context, R.string.export_failed, Toast.LENGTH_LONG).show();
        }
    }

    private String join(String... values) {
        List<String> present = new ArrayList<>();
        for (String value : values) {
            if (value != null && !value.isBlank()) present.add(value);
        }
        return String.join(" · ", present);
    }

    private final class BoardAdapter extends BaseAdapter {
        @Override
        public int getCount() {
            return visibleLeads.size();
        }

        @Override
        public Object getItem(int position) {
            return visibleLeads.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View reusable, ViewGroup parent) {
            JSONObject lead = visibleLeads.get(position);
            LinearLayout row = UiKit.vertical(context);
            row.setPadding(UiKit.dp(context, 10), UiKit.dp(context, 10), UiKit.dp(context, 10), UiKit.dp(context, 10));
            TextView name = UiKit.body(context, lead.optString("name"));
            name.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            row.addView(name);
            if (!lead.optString("contactsText").isBlank()) {
                row.addView(UiKit.caption(context, lead.optString("contactsText")));
            }
            row.addView(UiKit.body(context, lead.optString(
                "nextActionTitle",
                context.getString(R.string.no_action)
            )));
            String color = lead.optString("urgencyColor", "gray");
            row.addView(UiKit.urgency(context, color, UiKit.urgencyLabel(context, color)));
            if (!lead.optString("latestComment").isBlank()) {
                row.addView(UiKit.caption(context, "💬 " + lead.optString("latestComment")));
            }
            row.addView(UiKit.divider(context));
            return row;
        }
    }

    private static final class SearchWatcher implements TextWatcher {
        private final Runnable changed;

        private SearchWatcher(Runnable changed) {
            this.changed = changed;
        }

        @Override
        public void beforeTextChanged(CharSequence text, int start, int count, int after) {
        }

        @Override
        public void onTextChanged(CharSequence text, int start, int before, int count) {
            changed.run();
        }

        @Override
        public void afterTextChanged(Editable editable) {
        }
    }
}
