package tech.scaleag.nexstep.ui;

import android.app.AlertDialog;
import android.app.DatePickerDialog;
import android.content.Context;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;

/** Rare lead changes stay behind the detail screen's More options button. */
final class LeadManagementDialogs {
    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final JSONObject bootstrap;
    private final Runnable onSaved;

    LeadManagementDialogs(Context context, NexStepApiClient api, AppSession session,
                          JSONObject bootstrap, Runnable onSaved) {
        this.context = context;
        this.api = api;
        this.session = session;
        this.bootstrap = bootstrap;
        this.onSaved = onSaved;
    }

    void show(JSONObject lead) {
        boolean stopped = lead.optInt("pendingActionCount") == 0 &&
            (lead.optInt("churn_flag") != 0 || lead.optJSONArray("actions") != null &&
             lead.optJSONArray("actions").length() > 0);
        String[] options = stopped
            ? new String[]{context.getString(R.string.edit_lead), context.getString(R.string.reactivate_lead)}
            : new String[]{context.getString(R.string.edit_lead)};
        new AlertDialog.Builder(context).setTitle(R.string.more_options)
            .setItems(options, (dialog, index) -> {
                if (index == 0) edit(lead); else reactivate(lead);
            }).setNegativeButton(android.R.string.cancel, null).show();
    }

    private void edit(JSONObject lead) {
        LinearLayout form = UiKit.vertical(context);
        EditText name = UiKit.input(context, context.getString(R.string.prospect_name), false);
        name.setText(lead.optString("name"));
        EditText city = UiKit.input(context, context.getString(R.string.city), false);
        city.setText(lead.optString("city"));
        EditText details = UiKit.multiline(context, context.getString(R.string.context_note));
        details.setText(lead.optString("context_full"));
        form.addView(name); form.addView(city); form.addView(details);
        JSONArray contacts = lead.optJSONArray("contacts");
        List<EditText[]> fields = new ArrayList<>();
        if (contacts != null) for (int i = 0; i < contacts.length(); i++) {
            JSONObject contact = contacts.optJSONObject(i);
            if (contact == null) continue;
            form.addView(UiKit.heading(context, context.getString(R.string.contact_number, i + 1)));
            EditText person = UiKit.input(context, context.getString(R.string.contact_name), false);
            EditText role = UiKit.input(context, context.getString(R.string.contact_role), false);
            EditText phone = UiKit.input(context, context.getString(R.string.phone), false);
            EditText email = UiKit.input(context, context.getString(R.string.email), false);
            EditText whatsapp = UiKit.input(context, "WhatsApp", false);
            EditText notes = UiKit.input(context, context.getString(R.string.contact_notes), false);
            person.setText(contact.optString("full_name")); role.setText(contact.optString("role_title"));
            phone.setText(contact.optString("phone_raw")); email.setText(contact.optString("email"));
            whatsapp.setText(contact.optString("whatsapp")); notes.setText(contact.optString("channel_notes"));
            form.addView(person); form.addView(role); form.addView(phone); form.addView(email);
            form.addView(whatsapp); form.addView(notes);
            fields.add(new EditText[]{person, role, phone, email, whatsapp, notes});
        }
        EditText password = UiKit.input(context, context.getString(R.string.edit_password), true);
        form.addView(password);
        new AlertDialog.Builder(context).setTitle(R.string.edit_lead)
            .setView(UiKit.scroll(context, form)).setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save, (dialog, which) -> {
                try {
                    JSONArray changed = new JSONArray();
                    if (contacts != null) for (int i = 0; i < contacts.length(); i++) {
                        JSONObject original = contacts.optJSONObject(i);
                        if (original == null) continue;
                        EditText[] row = fields.get(i);
                        changed.put(new JSONObject().put("id", original.optString("id"))
                            .put("full_name", row[0].getText().toString())
                            .put("role_title", row[1].getText().toString())
                            .put("phone_raw", row[2].getText().toString())
                            .put("email", row[3].getText().toString())
                            .put("whatsapp", row[4].getText().toString())
                            .put("channel_notes", row[5].getText().toString()));
                    }
                    JSONObject payload = new JSONObject().put("leadId", lead.getString("id"))
                        .put("name", name.getText().toString()).put("city", city.getText().toString())
                        .put("contextFull", details.getText().toString()).put("contacts", changed)
                        .put("password", password.getText().toString());
                    save("update_lead", payload, R.string.lead_saved);
                } catch (JSONException exception) { error(); }
            }).show();
    }

    private void reactivate(JSONObject lead) {
        LinearLayout form = UiKit.vertical(context);
        EditText reason = UiKit.multiline(context, context.getString(R.string.reactivation_reason));
        EditText title = UiKit.input(context, context.getString(R.string.new_action), false);
        EditText due = UiKit.input(context, context.getString(R.string.due_date), false);
        due.setText(LocalDate.now().toString());
        due.setFocusable(false);
        due.setOnClickListener(view -> {
            LocalDate current = LocalDate.now();
            new DatePickerDialog(context, (picker, year, month, day) ->
                due.setText(LocalDate.of(year, month + 1, day).toString()),
                current.getYear(), current.getMonthValue() - 1, current.getDayOfMonth()).show();
        });
        form.addView(reason); form.addView(title); form.addView(due);
        JSONArray types = bootstrap.optJSONObject("references") != null
            ? bootstrap.optJSONObject("references").optJSONArray("actionTypes") : null;
        List<String> labels = new ArrayList<>();
        List<String> ids = new ArrayList<>();
        if (types != null) for (int i = 0; i < types.length(); i++) {
            JSONObject type = types.optJSONObject(i);
            if (type != null) { labels.add(type.optString("name")); ids.add(type.optString("id")); }
        }
        final int[] selected = {0};
        android.widget.Spinner typeChoice = new android.widget.Spinner(context);
        typeChoice.setAdapter(new android.widget.ArrayAdapter<>(context,
            android.R.layout.simple_spinner_dropdown_item, labels));
        typeChoice.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> p, android.view.View v, int index, long id) { selected[0] = index; }
            @Override public void onNothingSelected(android.widget.AdapterView<?> p) { }
        });
        form.addView(typeChoice);
        new AlertDialog.Builder(context).setTitle(R.string.reactivate_lead)
            .setView(UiKit.scroll(context, form)).setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.reactivate_lead, (dialog, which) -> {
                if (reason.getText().toString().trim().isEmpty() || title.getText().toString().trim().isEmpty()) {
                    Toast.makeText(context, R.string.reason_action_required, Toast.LENGTH_LONG).show(); return;
                }
                try {
                    JSONObject payload = new JSONObject().put("leadId", lead.getString("id"))
                        .put("reason", reason.getText().toString()).put("title", title.getText().toString())
                        .put("dueDate", due.getText().toString())
                        .put("actionTypeId", ids.isEmpty() ? JSONObject.NULL : ids.get(selected[0]));
                    save("reactivate_lead", payload, R.string.lead_reactivated);
                } catch (JSONException exception) { error(); }
            }).show();
    }

    private void save(String operation, JSONObject payload, int success) {
        Toast.makeText(context, R.string.saving, Toast.LENGTH_SHORT).show();
        api.call(operation, payload, session.accessToken(), new ApiCallback() {
            @Override public void onSuccess(JSONObject data) {
                Toast.makeText(context, success, Toast.LENGTH_LONG).show(); onSaved.run();
            }
            @Override public void onError(String code) {
                Toast.makeText(context, "invalid_password".equals(code)
                    ? R.string.invalid_credentials : R.string.generic_error, Toast.LENGTH_LONG).show();
            }
        });
    }

    private void error() { Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show(); }
}
