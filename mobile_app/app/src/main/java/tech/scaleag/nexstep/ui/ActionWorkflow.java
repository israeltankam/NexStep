package tech.scaleag.nexstep.ui;

import android.app.AlertDialog;
import android.app.DatePickerDialog;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.provider.CalendarContract;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.time.LocalDate;
import java.time.ZoneId;

import tech.scaleag.nexstep.MainActivity;
import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;
import tech.scaleag.nexstep.util.DateChoices;
import tech.scaleag.nexstep.util.FileExporter;

/** Shared one-decision-at-a-time workflow for completing an action. */
public final class ActionWorkflow {

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;

    public ActionWorkflow(Context context, NexStepApiClient api, AppSession session) {
        this.context = context;
        this.api = api;
        this.session = session;
    }

    public void complete(JSONObject action, Runnable onSaved) {
        String[] labels = {
            context.getString(R.string.outcome_interested),
            context.getString(R.string.outcome_callback),
            context.getString(R.string.outcome_unavailable),
            context.getString(R.string.outcome_refusal)
        };
        String[] keys = {"interested", "callback", "unavailable", "refusal"};
        choose(context.getString(R.string.outcome_question), labels, selected ->
            chooseNextAction(action, keys[selected], onSaved)
        );
    }

    private void chooseNextAction(JSONObject action, String outcomeKey, Runnable onSaved) {
        String leadId = action.optString("leadId");
        if (leadId.isBlank()) {
            showNextActionChoices(action, outcomeKey, null, onSaved);
            return;
        }

        LinearLayout loading = UiKit.vertical(context);
        loading.addView(UiKit.progress(context));
        loading.addView(UiKit.caption(
            context,
            context.getString(R.string.intelligence_analyzing)
        ));
        AlertDialog loadingDialog = new AlertDialog.Builder(context)
            .setView(loading)
            .setCancelable(false)
            .create();
        loadingDialog.show();
        try {
            JSONObject payload = new JSONObject()
                .put("leadId", leadId)
                .put("currentOutcomeKey", outcomeKey);
            api.call("lead_recommendation", payload, session.accessToken(), new ApiCallback() {
                @Override
                public void onSuccess(JSONObject data) {
                    loadingDialog.dismiss();
                    showNextActionChoices(
                        action,
                        outcomeKey,
                        data.optJSONObject("recommendation"),
                        onSaved
                    );
                }

                @Override
                public void onError(String errorCode) {
                    // Recommendations are optional: an old or temporarily
                    // unavailable backend must not block action completion.
                    loadingDialog.dismiss();
                    showNextActionChoices(action, outcomeKey, null, onSaved);
                }
            });
        } catch (JSONException exception) {
            loadingDialog.dismiss();
            showNextActionChoices(action, outcomeKey, null, onSaved);
        }
    }

    private void showNextActionChoices(
        JSONObject action,
        String outcomeKey,
        JSONObject recommendation,
        Runnable onSaved
    ) {
        String[] labels = {
            context.getString(R.string.action_call),
            context.getString(R.string.action_message),
            context.getString(R.string.action_meeting),
            context.getString(R.string.action_none)
        };
        String[] keys = {"call", "message", "meeting", "none"};
        choose(
            context.getString(R.string.next_question),
            labels,
            recommendationText(recommendation),
            selected -> {
            String nextActionKey = keys[selected];
            if ("none".equals(nextActionKey)) {
                confirm(action, outcomeKey, nextActionKey, null, onSaved);
            } else {
                chooseDueDate(action, outcomeKey, nextActionKey, onSaved);
            }
        });
    }

    private String recommendationText(JSONObject recommendation) {
        if (recommendation == null) return "";
        JSONObject evidence = recommendation.optJSONObject("evidence");
        if (evidence == null) evidence = new JSONObject();
        String reason = switch (recommendation.optString("reasonCode")) {
            case "already_churn" -> context.getString(
                R.string.intelligence_reason_already_churn
            );
            case "repeated_refusal" -> context.getString(
                R.string.intelligence_reason_repeated_refusal,
                evidence.optInt("refusalSignals")
            );
            case "repeated_negative" -> context.getString(
                R.string.intelligence_reason_repeated_negative,
                evidence.optInt("negativeSignals"),
                evidence.optInt("missedDeadlines")
            );
            case "chronophage" -> context.getString(
                R.string.intelligence_reason_chronophage,
                evidence.optInt("completedActions"),
                evidence.optInt("noResponseSignals"),
                evidence.optInt("missedDeadlines")
            );
            case "recent_interest" -> context.getString(
                R.string.intelligence_reason_recent_interest
            );
            case "callback_requested" -> context.getString(
                R.string.intelligence_reason_callback_requested
            );
            case "latest_refusal" -> context.getString(
                R.string.intelligence_reason_latest_refusal
            );
            case "repeated_no_response" -> context.getString(
                R.string.intelligence_reason_repeated_no_response,
                evidence.optInt("noResponseSignals")
            );
            case "alternate_after_call" -> context.getString(
                R.string.intelligence_reason_alternate_after_call
            );
            case "alternate_after_message" -> context.getString(
                R.string.intelligence_reason_alternate_after_message
            );
            default -> context.getString(R.string.intelligence_reason_default_followup);
        };
        String action = localizedAction(recommendation.optString("suggestedAction", "call"));
        int message = recommendation.optBoolean("suggestChurn")
            ? R.string.intelligence_churn_suggestion
            : R.string.intelligence_suggestion;
        return context.getString(message, action, reason);
    }

    private void chooseDueDate(
        JSONObject action,
        String outcomeKey,
        String nextActionKey,
        Runnable onSaved
    ) {
        String[] labels = {
            context.getString(R.string.delay_today),
            context.getString(R.string.delay_tomorrow),
            context.getString(R.string.delay_three_days),
            context.getString(R.string.delay_seven_days),
            context.getString(R.string.delay_custom),
            context.getString(R.string.delay_none)
        };
        String[] keys = {"today", "tomorrow", "3", "7", "custom", "none"};
        choose(context.getString(R.string.when_question), labels, selected -> {
            String key = keys[selected];
            if (!"custom".equals(key)) {
                confirm(
                    action,
                    outcomeKey,
                    nextActionKey,
                    DateChoices.fromKey(key, null),
                    onSaved
                );
                return;
            }
            LocalDate today = LocalDate.now();
            new DatePickerDialog(
                context,
                (view, year, month, day) -> confirm(
                    action,
                    outcomeKey,
                    nextActionKey,
                    LocalDate.of(year, month + 1, day).toString(),
                    onSaved
                ),
                today.getYear(),
                today.getMonthValue() - 1,
                today.getDayOfMonth()
            ).show();
        });
    }

    private void confirm(
        JSONObject action,
        String outcomeKey,
        String nextActionKey,
        String dueDate,
        Runnable onSaved
    ) {
        LinearLayout form = UiKit.vertical(context);
        form.addView(UiKit.body(
            context,
            context.getString(
                R.string.completion_summary,
                localizedOutcome(outcomeKey),
                localizedAction(nextActionKey),
                dueDate == null ? context.getString(R.string.no_due_date) : dueDate
            )
        ));
        EditText note = UiKit.multiline(context, context.getString(R.string.optional_note));
        // Optional details start collapsed so routine completion stays short.
        EditText contact = UiKit.input(context, context.getString(R.string.new_contact_met), false);
        EditText contactRole = UiKit.input(context, context.getString(R.string.contact_role), false);
        EditText contactPhone = UiKit.input(context, context.getString(R.string.phone), false);
        EditText contactEmail = UiKit.input(context, context.getString(R.string.email), false);
        EditText contactWhatsapp = UiKit.input(context, "WhatsApp", false);
        EditText obstacle = UiKit.input(context, context.getString(R.string.obstacle), false);
        EditText decision = UiKit.input(context, context.getString(R.string.decision), false);
        EditText nextComment = UiKit.multiline(context, context.getString(R.string.next_action_note));
        EditText targetPin = UiKit.input(context, context.getString(R.string.other_agent_pin), true);
        LinearLayout options = UiKit.vertical(context);
        options.addView(note);
        options.addView(contact);
        options.addView(contactRole);
        options.addView(contactPhone);
        options.addView(contactEmail);
        options.addView(contactWhatsapp);
        options.addView(obstacle);
        options.addView(decision);
        options.addView(nextComment);
        options.addView(targetPin);
        options.setVisibility(View.GONE);
        android.widget.Button reveal = UiKit.commandButton(context, context.getString(R.string.more_options));
        reveal.setOnClickListener(view -> options.setVisibility(
            options.getVisibility() == View.GONE ? View.VISIBLE : View.GONE));
        form.addView(reveal);
        form.addView(options);

        new AlertDialog.Builder(context)
            .setTitle(R.string.confirm_action)
            .setView(UiKit.scroll(context, form))
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save_and_continue, (dialog, which) -> {
                try {
                    JSONObject payload = new JSONObject()
                        .put("actionId", action.getString("id"))
                        .put("outcomeKey", outcomeKey)
                        .put("nextActionKey", nextActionKey)
                        .put("nextDueDate", dueDate == null ? JSONObject.NULL : dueDate)
                        .put("nextTitle", localizedAction(nextActionKey))
                        .put("note", note.getText().toString())
                        .put("contactName", contact.getText().toString())
                        .put("contactRole", contactRole.getText().toString())
                        .put("contactPhone", contactPhone.getText().toString())
                        .put("contactEmail", contactEmail.getText().toString())
                        .put("contactWhatsapp", contactWhatsapp.getText().toString())
                        .put("obstacle", obstacle.getText().toString())
                        .put("decision", decision.getText().toString())
                        .put("nextComment", nextComment.getText().toString())
                        .put("targetAgentPin", targetPin.getText().toString());
                    api.call("complete_action", payload, session.accessToken(), callback(
                        context.getString(R.string.action_saved),
                        onSaved
                    ));
                } catch (JSONException exception) {
                    showError("invalid_response");
                }
            })
            .show();
    }

    public void addComment(JSONObject action, Runnable onSaved) {
        EditText body = UiKit.multiline(context, context.getString(R.string.comment));
        new AlertDialog.Builder(context)
            .setTitle(R.string.add_comment)
            .setView(body)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save, (dialog, which) -> {
                try {
                    JSONObject payload = new JSONObject()
                        .put("leadId", action.getString("leadId"))
                        .put("actionId", action.optString("id"))
                        .put("body", body.getText().toString());
                    api.call("add_comment", payload, session.accessToken(), callback(
                        context.getString(R.string.comment_saved),
                        onSaved
                    ));
                } catch (JSONException exception) {
                    showError("invalid_response");
                }
            })
            .show();
    }

    /** Add a newly discovered contact without leaving the current action. */
    public void addContact(JSONObject action, Runnable onSaved) {
        LinearLayout form = UiKit.vertical(context);
        EditText name = UiKit.input(context, context.getString(R.string.contact_name), false);
        EditText role = UiKit.input(context, context.getString(R.string.contact_role), false);
        EditText phone = UiKit.input(context, context.getString(R.string.phone), false);
        EditText email = UiKit.input(context, context.getString(R.string.email), false);
        EditText whatsapp = UiKit.input(context, "WhatsApp", false);
        EditText notes = UiKit.multiline(context, context.getString(R.string.contact_notes));
        phone.setInputType(InputType.TYPE_CLASS_PHONE);
        whatsapp.setInputType(InputType.TYPE_CLASS_PHONE);
        email.setInputType(
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
        );
        form.addView(name);
        form.addView(role);
        form.addView(phone);
        form.addView(email);
        form.addView(whatsapp);
        form.addView(notes);

        AlertDialog dialog = new AlertDialog.Builder(context)
            .setTitle(R.string.add_contact)
            .setView(UiKit.scroll(context, form))
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save, null)
            .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            .setOnClickListener(view -> {
                String fullName = name.getText().toString().trim();
                String phoneValue = phone.getText().toString().trim();
                String emailValue = email.getText().toString().trim();
                String whatsappValue = whatsapp.getText().toString().trim();
                if (
                    fullName.isBlank() && phoneValue.isBlank() &&
                    emailValue.isBlank() && whatsappValue.isBlank()
                ) {
                    Toast.makeText(context, R.string.contact_required, Toast.LENGTH_LONG).show();
                    return;
                }
                try {
                    JSONObject payload = new JSONObject()
                        .put("leadId", action.getString("leadId"))
                        .put("actionId", action.getString("id"))
                        .put("fullName", fullName)
                        .put("roleTitle", role.getText().toString())
                        .put("phone", phoneValue)
                        .put("email", emailValue)
                        .put("whatsapp", whatsappValue)
                        .put("notes", notes.getText().toString());
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                    api.call("add_contact", payload, session.accessToken(), new ApiCallback() {
                        @Override
                        public void onSuccess(JSONObject data) {
                            dialog.dismiss();
                            Toast.makeText(context, R.string.contact_saved, Toast.LENGTH_LONG).show();
                            onSaved.run();
                        }

                        @Override
                        public void onError(String errorCode) {
                            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                            showError(errorCode);
                        }
                    });
                } catch (JSONException exception) {
                    showError("invalid_response");
                }
            }));
        dialog.show();
    }

    public void transfer(JSONObject action, Runnable onSaved) {
        LinearLayout form = UiKit.vertical(context);
        EditText targetPin = UiKit.input(context, context.getString(R.string.target_agent_pin), true);
        EditText note = UiKit.multiline(context, context.getString(R.string.transfer_note));
        form.addView(targetPin);
        form.addView(note);
        new AlertDialog.Builder(context)
            .setTitle(R.string.transfer_action)
            .setView(form)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.transfer, (dialog, which) -> {
                try {
                    JSONObject payload = new JSONObject()
                        .put("actionId", action.getString("id"))
                        .put("targetAgentPin", targetPin.getText().toString())
                        .put("note", note.getText().toString());
                    api.call("transfer_action", payload, session.accessToken(), callback(
                        context.getString(R.string.action_transferred),
                        onSaved
                    ));
                } catch (JSONException exception) {
                    showError("invalid_response");
                }
            })
            .show();
    }

    public void openCalendar(JSONObject action) {
        String dueDate = action.optString("due_date");
        if (dueDate.isBlank()) {
            Toast.makeText(context, R.string.no_due_date, Toast.LENGTH_LONG).show();
            return;
        }
        LocalDate date = LocalDate.parse(dueDate.substring(0, 10));
        long start = date.atTime(9, 0).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli();
        Intent intent = new Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, start)
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, start + 3_600_000)
            .putExtra(CalendarContract.Events.TITLE, action.optString("title"))
            .putExtra(
                CalendarContract.Events.DESCRIPTION,
                action.optString("leadName") + "\n" + action.optString("details")
            );
        try {
            context.startActivity(intent);
        } catch (Exception exception) {
            Toast.makeText(context, R.string.calendar_unavailable, Toast.LENGTH_LONG).show();
        }
    }

    public void downloadIcs(JSONObject action) {
        String dueDate = action.optString("due_date");
        if (dueDate.isBlank()) {
            Toast.makeText(context, R.string.no_due_date, Toast.LENGTH_LONG).show();
            return;
        }
        try {
            FileExporter.saveIcs(
                context,
                action.optString("title"),
                action.optString("leadName") + "\n" + action.optString("details"),
                dueDate.substring(0, 10)
            );
            Toast.makeText(context, R.string.ics_saved, Toast.LENGTH_LONG).show();
        } catch (IOException exception) {
            Toast.makeText(context, R.string.export_failed, Toast.LENGTH_LONG).show();
        }
    }

    private ApiCallback callback(String successMessage, Runnable onSaved) {
        return new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                Toast.makeText(context, successMessage, Toast.LENGTH_LONG).show();
                onSaved.run();
            }

            @Override
            public void onError(String errorCode) {
                showError(errorCode);
            }
        };
    }

    private void choose(String title, String[] labels, ChoiceListener listener) {
        choose(title, labels, "", listener);
    }

    private void choose(
        String title,
        String[] labels,
        String message,
        ChoiceListener listener
    ) {
        AlertDialog.Builder builder = new AlertDialog.Builder(context).setTitle(title);
        if (message != null && !message.isBlank()) builder.setMessage(message);
        builder
            .setItems(labels, (dialog, which) -> listener.onChoice(which))
            .setNegativeButton(android.R.string.cancel, null)
            .show();
    }

    private String localizedOutcome(String key) {
        return switch (key) {
            case "interested" -> context.getString(R.string.outcome_interested);
            case "callback" -> context.getString(R.string.outcome_callback);
            case "unavailable" -> context.getString(R.string.outcome_unavailable);
            default -> context.getString(R.string.outcome_refusal);
        };
    }

    private String localizedAction(String key) {
        return switch (key) {
            case "call" -> context.getString(R.string.action_call);
            case "message" -> context.getString(R.string.action_message);
            case "meeting" -> context.getString(R.string.action_meeting);
            case "visit" -> context.getString(R.string.action_visit);
            default -> context.getString(R.string.action_none);
        };
    }

    private void showError(String code) {
        String message = context instanceof MainActivity
            ? ((MainActivity) context).errorMessage(code)
            : context.getString(R.string.generic_error);
        Toast.makeText(context, message, Toast.LENGTH_LONG).show();
    }

    private interface ChoiceListener {
        void onChoice(int index);
    }
}
