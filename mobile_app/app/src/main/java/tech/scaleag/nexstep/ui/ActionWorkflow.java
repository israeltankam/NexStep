package tech.scaleag.nexstep.ui;

import android.app.AlertDialog;
import android.app.DatePickerDialog;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.provider.CalendarContract;
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
        String[] labels = {
            context.getString(R.string.action_call),
            context.getString(R.string.action_message),
            context.getString(R.string.action_meeting),
            context.getString(R.string.action_none)
        };
        String[] keys = {"call", "message", "meeting", "none"};
        choose(context.getString(R.string.next_question), labels, selected -> {
            String nextActionKey = keys[selected];
            if ("none".equals(nextActionKey)) {
                confirm(action, outcomeKey, nextActionKey, null, onSaved);
            } else {
                chooseDueDate(action, outcomeKey, nextActionKey, onSaved);
            }
        });
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
        EditText contact = UiKit.input(context, context.getString(R.string.contact_name), false);
        contact.setText(action.optString("contactName"));
        EditText obstacle = UiKit.input(context, context.getString(R.string.obstacle), false);
        EditText decision = UiKit.input(context, context.getString(R.string.decision), false);
        EditText nextComment = UiKit.multiline(context, context.getString(R.string.next_action_note));
        EditText targetPin = UiKit.input(context, context.getString(R.string.other_agent_pin), true);
        form.addView(note);
        form.addView(contact);
        form.addView(obstacle);
        form.addView(decision);
        form.addView(nextComment);
        form.addView(targetPin);

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
        new AlertDialog.Builder(context)
            .setTitle(title)
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
