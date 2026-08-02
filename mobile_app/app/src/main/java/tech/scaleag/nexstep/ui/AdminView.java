package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;

import tech.scaleag.nexstep.R;
import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.model.AppSession;
import tech.scaleag.nexstep.util.FileExporter;

/** Native administrator console for reset approvals and disaster backups. */
@SuppressLint("ViewConstructor")
public final class AdminView extends LinearLayout {

    private final Context context;
    private final NexStepApiClient api;
    private final AppSession session;
    private final LinearLayout requestList;

    public AdminView(Context context, NexStepApiClient api, AppSession session) {
        super(context);
        this.context = context;
        this.api = api;
        this.session = session;
        setOrientation(VERTICAL);

        LinearLayout content = UiKit.vertical(context);
        content.addView(UiKit.title(context, "⚙ " + context.getString(R.string.administration)));
        content.addView(UiKit.heading(context, context.getString(R.string.password_reset_requests)));
        requestList = new LinearLayout(context);
        requestList.setOrientation(VERTICAL);
        content.addView(requestList);

        content.addView(UiKit.heading(context, context.getString(R.string.backups)));
        Button companyBackup = UiKit.primaryButton(
            context,
            context.getString(R.string.download_company_backup)
        );
        companyBackup.setOnClickListener(view -> downloadBackup(false, ""));
        content.addView(companyBackup);
        if (session.isGlobalAdmin()) {
            Button globalBackup = UiKit.primaryButton(
                context,
                context.getString(R.string.download_global_backup)
            );
            globalBackup.setOnClickListener(view -> requestGlobalBackupPassword());
            content.addView(globalBackup);
            content.addView(UiKit.caption(
                context,
                context.getString(R.string.global_backup_description)
            ));
        }
        addView(UiKit.scroll(context, content));
        loadRequests();
    }

    private void loadRequests() {
        requestList.removeAllViews();
        requestList.addView(UiKit.caption(context, context.getString(R.string.loading)));
        api.call(
            "pending_password_resets",
            new JSONObject(),
            session.accessToken(),
            new ApiCallback() {
                @Override
                public void onSuccess(JSONObject data) {
                    requestList.removeAllViews();
                    JSONArray requests = data.optJSONArray("requests");
                    if (requests == null || requests.length() == 0) {
                        requestList.addView(UiKit.caption(
                            context,
                            context.getString(R.string.no_reset_requests)
                        ));
                        return;
                    }
                    for (int index = 0; index < requests.length(); index += 1) {
                        JSONObject request = requests.optJSONObject(index);
                        if (request != null) requestList.addView(requestRow(request));
                    }
                }

                @Override
                public void onError(String errorCode) {
                    requestList.removeAllViews();
                    requestList.addView(UiKit.caption(
                        context,
                        context.getString(R.string.generic_error)
                    ));
                }
            }
        );
    }

    private View requestRow(JSONObject request) {
        LinearLayout row = UiKit.vertical(context);
        row.setPadding(UiKit.dp(context, 8), UiKit.dp(context, 8), UiKit.dp(context, 8), UiKit.dp(context, 8));
        row.addView(UiKit.body(context, request.optString("displayName")));
        if (session.isGlobalAdmin()) {
            row.addView(UiKit.caption(
                context,
                context.getString(
                    R.string.reset_request_company,
                    request.optString("organizationName")
                )
            ));
        }
        row.addView(UiKit.caption(context, request.optString("requested_at")));
        LinearLayout commands = new LinearLayout(context);
        Button approve = new Button(context);
        approve.setText(R.string.approve);
        approve.setAllCaps(false);
        approve.setOnClickListener(view -> review(request, true));
        Button reject = new Button(context);
        reject.setText(R.string.reject);
        reject.setAllCaps(false);
        reject.setOnClickListener(view -> review(request, false));
        commands.addView(approve, new LayoutParams(0, UiKit.dp(context, 48), 1f));
        commands.addView(reject, new LayoutParams(0, UiKit.dp(context, 48), 1f));
        row.addView(commands);
        row.addView(UiKit.divider(context));
        return row;
    }

    private void review(JSONObject request, boolean approve) {
        try {
            JSONObject payload = new JSONObject()
                .put("requestId", request.getString("id"))
                .put("approve", approve);
            api.call("review_password_reset", payload, session.accessToken(), new ApiCallback() {
                @Override
                public void onSuccess(JSONObject data) {
                    Toast.makeText(
                        context,
                        approve ? R.string.reset_approved : R.string.reset_rejected,
                        Toast.LENGTH_LONG
                    ).show();
                    loadRequests();
                }

                @Override
                public void onError(String errorCode) {
                    Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
                }
            });
        } catch (JSONException exception) {
            Toast.makeText(context, R.string.generic_error, Toast.LENGTH_LONG).show();
        }
    }

    private void requestGlobalBackupPassword() {
        EditText password = UiKit.input(context, context.getString(R.string.password), true);
        new AlertDialog.Builder(context)
            .setTitle(R.string.confirm_global_backup)
            .setMessage(R.string.confirm_global_backup_detail)
            .setView(password)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.download, (dialog, which) ->
                downloadBackup(true, password.getText().toString())
            )
            .show();
    }

    private void downloadBackup(boolean global, String password) {
        JSONObject payload = new JSONObject();
        try {
            payload.put("global", global).put("password", password);
        } catch (JSONException ignored) {
            return;
        }
        Toast.makeText(context, R.string.preparing_backup, Toast.LENGTH_LONG).show();
        api.call("backup", payload, session.accessToken(), new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                try {
                    FileExporter.saveJson(
                        context,
                        global ? "NexStep_global_backup" : "NexStep_company_backup",
                        data
                    );
                    Toast.makeText(context, R.string.backup_saved, Toast.LENGTH_LONG).show();
                } catch (IOException exception) {
                    Toast.makeText(context, R.string.export_failed, Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onError(String errorCode) {
                Toast.makeText(
                    context,
                    "invalid_credentials".equals(errorCode)
                        ? R.string.invalid_credentials
                        : R.string.generic_error,
                    Toast.LENGTH_LONG
                ).show();
            }
        });
    }
}
