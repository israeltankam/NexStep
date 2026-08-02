package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.app.DatePickerDialog;
import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
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
import tech.scaleag.nexstep.util.DateChoices;

/** Four-step native prospect creation flow with up to five contacts. */
@SuppressLint("ViewConstructor")
public final class NewLeadView extends LinearLayout {

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final JSONObject bootstrap;
    private final Runnable onCreated;
    private final JSONObject draft = new JSONObject();
    private int step = 1;

    public NewLeadView(
        Context context,
        NexStepApiClient api,
        AppSession session,
        JSONObject bootstrap,
        Runnable onCreated
    ) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        this.bootstrap = bootstrap;
        this.onCreated = onCreated;
        setOrientation(VERTICAL);
        render();
    }

    private void render() {
        removeAllViews();
        switch (step) {
            case 1 -> identity();
            case 2 -> action();
            case 3 -> dueDate();
            default -> confirmation();
        }
    }

    private LinearLayout base(String question) {
        LinearLayout content = UiKit.vertical(context);
        content.addView(UiKit.title(context, "➕ " + context.getString(R.string.add_prospect)));
        content.addView(UiKit.caption(
            context,
            context.getString(R.string.step_progress, step, 4)
        ));
        content.addView(UiKit.heading(context, question));
        return content;
    }

    private void identity() {
        LinearLayout content = base(context.getString(R.string.prospect_identity_question));
        EditText name = UiKit.input(context, context.getString(R.string.prospect_name), false);
        name.setText(draft.optString("name"));
        content.addView(name);

        Spinner count = new Spinner(context);
        count.setAdapter(new ArrayAdapter<>(
            context,
            android.R.layout.simple_spinner_dropdown_item,
            new String[] {
                context.getString(R.string.no_contact),
                context.getString(R.string.one_contact),
                context.getResources().getQuantityString(R.plurals.contact_count, 2, 2),
                context.getResources().getQuantityString(R.plurals.contact_count, 3, 3),
                context.getResources().getQuantityString(R.plurals.contact_count, 4, 4),
                context.getResources().getQuantityString(R.plurals.contact_count, 5, 5)
            }
        ));
        JSONArray saved = draft.optJSONArray("contacts");
        count.setSelection(saved == null ? 1 : saved.length());
        content.addView(count, new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            UiKit.dp(context, 52)
        ));

        LinearLayout contactContainer = new LinearLayout(context);
        contactContainer.setOrientation(VERTICAL);
        content.addView(contactContainer);
        List<ContactFields> fields = new ArrayList<>();
        Runnable rebuild = () -> {
            contactContainer.removeAllViews();
            fields.clear();
            for (int index = 0; index < count.getSelectedItemPosition(); index += 1) {
                JSONObject source = saved == null ? null : saved.optJSONObject(index);
                ContactFields contact = new ContactFields(source);
                fields.add(contact);
                contactContainer.addView(UiKit.heading(
                    context,
                    context.getString(R.string.contact_number, index + 1)
                ));
                contactContainer.addView(contact.name);
                contactContainer.addView(contact.role);
                contactContainer.addView(contact.phone);
                contactContainer.addView(contact.email);
                contactContainer.addView(contact.whatsapp);
            }
        };
        count.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                rebuild.run();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
        rebuild.run();

        Button next = UiKit.primaryButton(context, context.getString(R.string.continue_label));
        next.setOnClickListener(view -> {
            String value = name.getText().toString().trim();
            if (value.isEmpty()) {
                Toast.makeText(context, R.string.prospect_name_required, Toast.LENGTH_LONG).show();
                return;
            }
            try {
                JSONArray contacts = new JSONArray();
                for (ContactFields field : fields) contacts.put(field.toJson());
                draft.put("name", value).put("contacts", contacts);
                step = 2;
                render();
            } catch (JSONException exception) {
                Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
            }
        });
        content.addView(next);
        addView(UiKit.scroll(context, content));
    }

    private void action() {
        LinearLayout content = base(context.getString(R.string.prospect_action_question));
        choiceButton(content, "☎  " + context.getString(R.string.action_call), "call");
        choiceButton(content, "💬  " + context.getString(R.string.action_message), "message");
        choiceButton(content, "📍  " + context.getString(R.string.action_visit), "visit");
        choiceButton(content, "📅  " + context.getString(R.string.action_meeting), "meeting");
        content.addView(backButton());
        addView(UiKit.scroll(context, content));
    }

    private void choiceButton(LinearLayout content, String label, String key) {
        Button button = UiKit.primaryButton(context, label);
        button.setOnClickListener(view -> {
            try {
                draft.put("actionKey", key);
                step = 3;
                render();
            } catch (JSONException ignored) {
            }
        });
        content.addView(button);
    }

    private void dueDate() {
        LinearLayout content = base(context.getString(R.string.prospect_when_question));
        dueButton(content, context.getString(R.string.delay_today), "today");
        dueButton(content, context.getString(R.string.delay_tomorrow), "tomorrow");
        dueButton(content, context.getString(R.string.delay_three_days), "3");
        dueButton(content, context.getString(R.string.delay_seven_days), "7");
        dueButton(content, context.getString(R.string.delay_none), "none");
        Button custom = UiKit.commandButton(context, "📅  " + context.getString(R.string.delay_custom));
        custom.setOnClickListener(view -> {
            LocalDate today = LocalDate.now();
            new DatePickerDialog(
                context,
                (picker, year, month, day) -> selectDue(
                    "custom",
                    LocalDate.of(year, month + 1, day)
                ),
                today.getYear(),
                today.getMonthValue() - 1,
                today.getDayOfMonth()
            ).show();
        });
        content.addView(custom);
        content.addView(backButton());
        addView(UiKit.scroll(context, content));
    }

    private void dueButton(LinearLayout content, String label, String key) {
        Button button = UiKit.primaryButton(context, label);
        button.setOnClickListener(view -> selectDue(key, null));
        content.addView(button);
    }

    private void selectDue(String key, LocalDate custom) {
        try {
            String date = DateChoices.fromKey(key, custom);
            draft.put("dueDate", date == null ? JSONObject.NULL : date);
            step = 4;
            render();
        } catch (JSONException ignored) {
        }
    }

    private void confirmation() {
        LinearLayout content = base(context.getString(R.string.prospect_confirm_question));
        content.addView(UiKit.body(
            context,
            context.getString(
                R.string.prospect_summary,
                draft.optString("name"),
                actionLabel(draft.optString("actionKey")),
                draft.isNull("dueDate")
                    ? context.getString(R.string.no_due_date)
                    : draft.optString("dueDate")
            )
        ));
        EditText city = UiKit.input(context, context.getString(R.string.city), false);
        EditText contextNote = UiKit.multiline(context, context.getString(R.string.context_note));
        EditText actionDetails = UiKit.multiline(context, context.getString(R.string.action_details));
        content.addView(city);

        Spinner category = new Spinner(context);
        List<String> categories = categories();
        category.setAdapter(new ArrayAdapter<>(
            context,
            android.R.layout.simple_spinner_dropdown_item,
            categories
        ));
        content.addView(category, new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            UiKit.dp(context, 52)
        ));
        content.addView(contextNote);
        content.addView(actionDetails);

        Button create = UiKit.primaryButton(context, "✓  " + context.getString(R.string.create_prospect));
        create.setOnClickListener(view -> {
            try {
                JSONObject payload = new JSONObject(draft.toString())
                    .put("city", city.getText().toString())
                    .put("categoryName", category.getSelectedItemPosition() == 0
                        ? ""
                        : category.getSelectedItem().toString())
                    .put("contextNote", contextNote.getText().toString())
                    .put("actionDetails", actionDetails.getText().toString())
                    .put("actionTitle", actionLabel(draft.optString("actionKey")));
                create.setEnabled(false);
                api.call("create_lead", payload, session.accessToken(), new ApiCallback() {
                    @Override
                    public void onSuccess(JSONObject data) {
                        Toast.makeText(context, R.string.prospect_created, Toast.LENGTH_LONG).show();
                        onCreated.run();
                    }

                    @Override
                    public void onError(String errorCode) {
                        create.setEnabled(true);
                        Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
                    }
                });
            } catch (JSONException exception) {
                Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
            }
        });
        content.addView(create);
        content.addView(backButton());
        addView(UiKit.scroll(context, content));
    }

    private Button backButton() {
        Button back = UiKit.commandButton(context, "←  " + context.getString(R.string.back));
        back.setOnClickListener(view -> {
            step = Math.max(1, step - 1);
            render();
        });
        return back;
    }

    private List<String> categories() {
        List<String> values = new ArrayList<>();
        values.add(context.getString(R.string.no_category));
        JSONObject references = bootstrap.optJSONObject("references");
        JSONArray source = references == null ? null : references.optJSONArray("categories");
        if (source != null) {
            for (int index = 0; index < source.length(); index += 1) {
                JSONObject category = source.optJSONObject(index);
                if (category != null) values.add(category.optString("name"));
            }
        }
        return values;
    }

    private String actionLabel(String key) {
        return switch (key) {
            case "message" -> context.getString(R.string.action_message);
            case "visit" -> context.getString(R.string.action_visit);
            case "meeting" -> context.getString(R.string.action_meeting);
            default -> context.getString(R.string.action_call);
        };
    }

    private final class ContactFields {
        private final EditText name;
        private final EditText role;
        private final EditText phone;
        private final EditText email;
        private final EditText whatsapp;

        private ContactFields(JSONObject saved) {
            name = UiKit.input(context, context.getString(R.string.contact_name), false);
            role = UiKit.input(context, context.getString(R.string.contact_role), false);
            phone = UiKit.input(context, context.getString(R.string.phone), false);
            email = UiKit.input(context, context.getString(R.string.email), false);
            whatsapp = UiKit.input(context, "WhatsApp", false);
            if (saved != null) {
                name.setText(saved.optString("fullName"));
                role.setText(saved.optString("roleTitle"));
                phone.setText(saved.optString("phone"));
                email.setText(saved.optString("email"));
                whatsapp.setText(saved.optString("whatsapp"));
            }
        }

        private JSONObject toJson() throws JSONException {
            return new JSONObject()
                .put("fullName", name.getText().toString())
                .put("roleTitle", role.getText().toString())
                .put("phone", phone.getText().toString())
                .put("email", email.getText().toString())
                .put("whatsapp", whatsapp.getText().toString());
        }
    }
}
