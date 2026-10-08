package tech.scaleag.nexstep.ui;

import android.app.AlertDialog;
import android.content.Context;
import android.text.InputType;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;

/** One company-specific agent link, including the shared person profile. */
final class AgentEditorDialog {
    private static final String[] ROLES = {"agent", "manager", "company_admin"};
    private static final String[] LANGUAGES = {"fr", "en"};

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;

    AgentEditorDialog(Context context, NexStepApiClient api, AppSession session) {
        this.context = context;
        this.api = api;
        this.session = session;
    }

    void show(JSONObject agent) {
        LinearLayout content = UiKit.vertical(context);
        content.addView(UiKit.caption(context, context.getString(R.string.agent_scope_hint)));
        EditText name = field(content, R.string.agent_name, agent.optString("displayName"), 0);
        EditText email = field(content, R.string.agent_email, agent.optString("email"),
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        EditText phone = field(content, R.string.agent_phone, agent.optString("phone"),
            InputType.TYPE_CLASS_PHONE);
        Spinner language = spinner(content, R.string.agent_language,
            new String[]{context.getString(R.string.language_french), context.getString(R.string.language_english)},
            "en".equals(agent.optString("language")) ? 1 : 0);
        String[] roleNames = {context.getString(R.string.agent_role),
            context.getString(R.string.manager_role), context.getString(R.string.company_admin_role)};
        int roleIndex = "company_admin".equals(agent.optString("role")) ? 2 :
            "manager".equals(agent.optString("role")) ? 1 : 0;
        Spinner role = spinner(content, R.string.agent_authority, roleNames, roleIndex);
        CheckBox team = check(content, R.string.agent_team_access, agent.optBoolean("canViewTeam"));
        // Company administrators always see the team. Mirror that rule in the form.
        role.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (position == 2) team.setChecked(true);
                team.setEnabled(position != 2);
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });
        CheckBox linkActive = check(content, R.string.agent_company_active,
            agent.optBoolean("linkActive"));
        CheckBox accountActive = check(content, R.string.agent_account_active,
            agent.optBoolean("accountActive"));
        EditText pin = field(content, R.string.agent_new_pin, "",
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        ProgressBar saving = new ProgressBar(context);
        saving.setVisibility(View.GONE);
        content.addView(saving);

        AlertDialog dialog = new AlertDialog.Builder(context)
            .setTitle(agent.optString("organizationName") + " · " + agent.optString("displayName"))
            .setView(UiKit.scroll(context, content))
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save, null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            .setOnClickListener(view -> save(dialog, agent, name, email, phone, language, role,
                team, linkActive, accountActive, pin, saving)));
        dialog.show();
    }

    private EditText field(LinearLayout content, int label, String value, int inputType) {
        EditText input = UiKit.input(context, context.getString(label), false);
        input.setText(value);
        if (inputType != 0) input.setInputType(inputType);
        content.addView(input);
        return input;
    }

    private Spinner spinner(LinearLayout content, int label, String[] options, int selected) {
        content.addView(UiKit.caption(context, context.getString(label)));
        Spinner spinner = new Spinner(context);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(context,
            android.R.layout.simple_spinner_item, options);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        spinner.setSelection(selected);
        content.addView(spinner);
        return spinner;
    }

    private CheckBox check(LinearLayout content, int label, boolean checked) {
        CheckBox box = new CheckBox(context);
        box.setText(label);
        box.setChecked(checked);
        content.addView(box);
        return box;
    }

    private void save(AlertDialog dialog, JSONObject agent, EditText name, EditText email,
                      EditText phone, Spinner language, Spinner role, CheckBox team,
                      CheckBox linkActive, CheckBox accountActive, EditText pin,
                      ProgressBar saving) {
        String cleanName = name.getText().toString().trim();
        String cleanEmail = email.getText().toString().trim();
        if (cleanName.isEmpty() || (!cleanEmail.isEmpty() &&
            !android.util.Patterns.EMAIL_ADDRESS.matcher(cleanEmail).matches())) {
            Toast.makeText(context, R.string.agent_invalid_details, Toast.LENGTH_LONG).show();
            return;
        }
        try {
            JSONObject payload = new JSONObject()
                .put("orgUserId", agent.getString("orgUserId"))
                .put("displayName", cleanName).put("email", cleanEmail)
                .put("phone", phone.getText().toString().trim())
                .put("language", LANGUAGES[language.getSelectedItemPosition()])
                .put("role", ROLES[role.getSelectedItemPosition()])
                .put("canViewTeam", team.isChecked())
                .put("linkActive", linkActive.isChecked())
                .put("accountActive", accountActive.isChecked())
                .put("newPin", pin.getText().toString());
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
            saving.setVisibility(View.VISIBLE);
            Toast.makeText(context, R.string.saving, Toast.LENGTH_SHORT).show();
            api.call("update_agent", payload, session.accessToken(), new ApiCallback() {
                @Override public void onSuccess(JSONObject data) {
                    dialog.dismiss();
                    Toast.makeText(context, R.string.agent_saved, Toast.LENGTH_LONG).show();
                }
                @Override public void onError(String code) {
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                    saving.setVisibility(View.GONE);
                    Toast.makeText(context, "duplicate_pin".equals(code) ? R.string.agent_duplicate_pin :
                        "invalid_agent_details".equals(code) ? R.string.agent_invalid_details :
                        "mobile_migration_required".equals(code) ? R.string.mobile_migration_required :
                        "unknown_operation".equals(code) ? R.string.mobile_update_required :
                        R.string.generic_error, Toast.LENGTH_LONG).show();
                }
            });
        } catch (JSONException exception) {
            Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
        }
    }
}
