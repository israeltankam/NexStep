package tech.scaleag.nexstep;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;

import org.json.JSONException;
import org.json.JSONObject;

import tech.scaleag.nexstep.data.ApiCallback;
import tech.scaleag.nexstep.data.NexStepApiClient;
import tech.scaleag.nexstep.data.PublicConfigurationStore;
import tech.scaleag.nexstep.data.PublicConfigurationStore.Configuration;
import tech.scaleag.nexstep.data.SessionStore;
import tech.scaleag.nexstep.model.AppSession;
import tech.scaleag.nexstep.ui.ConfigurationView;
import tech.scaleag.nexstep.ui.LoginView;
import tech.scaleag.nexstep.ui.MainShellView;
import tech.scaleag.nexstep.ui.UiKit;
import tech.scaleag.nexstep.util.LanguageManager;

/** Entry point for the fully native NexStep Android application. */
public final class MainActivity extends Activity {

    private NexStepApiClient api;
    private PublicConfigurationStore configurationStore;
    private SessionStore sessionStore;
    private AppSession session;
    private ConfigurationView configurationView;
    private LoginView loginView;

    @Override
    protected void attachBaseContext(Context newBase) {
        super.attachBaseContext(LanguageManager.apply(newBase));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configurationStore = new PublicConfigurationStore(this);
        sessionStore = new SessionStore(this);
        Configuration configuration = configurationStore.load();
        if (configuration == null) {
            showConfiguration();
            return;
        }
        start(configuration);
    }

    private void start(Configuration configuration) {
        api = new NexStepApiClient(configuration);
        session = sessionStore.load();
        if (session == null) {
            showLogin();
        } else {
            validateSavedSession();
        }
    }

    private void showConfiguration() {
        configurationView = new ConfigurationView(
            this,
            configurationStore.suggestedUrl(),
            configurationStore.suggestedKey(),
            new ConfigurationView.Listener() {
                @Override
                public void onConnect(String projectUrl, String publishableKey) {
                    connectConfiguration(projectUrl, publishableKey);
                }

                @Override
                public void onLanguage(String language) {
                    LanguageManager.save(MainActivity.this, language);
                    recreate();
                }
            }
        );
        setContentView(configurationView);
    }

    private void connectConfiguration(String projectUrl, String publishableKey) {
        String validationError = PublicConfigurationStore.validate(projectUrl, publishableKey);
        if (validationError != null) {
            configurationView.showError(configurationError(validationError));
            return;
        }

        Configuration candidate = new Configuration(projectUrl.trim(), publishableKey.trim());
        NexStepApiClient candidateApi = new NexStepApiClient(candidate);
        configurationView.setBusy(true);
        candidateApi.call("health", new JSONObject(), null, new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                if (api != null) api.shutdown();
                api = candidateApi;
                configurationStore.save(candidate);
                sessionStore.clear();
                session = null;
                showLogin();
            }

            @Override
            public void onError(String errorCode) {
                candidateApi.shutdown();
                configurationView.showError(configurationError(errorCode));
            }
        });
    }

    private void validateSavedSession() {
        showLoading(getString(R.string.restoring_session));
        api.call("bootstrap", new JSONObject(), session.accessToken(), new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                try {
                    JSONObject profile = data.getJSONObject("profile");
                    session = new AppSession(session.accessToken(), session.expiresAt(), profile);
                    sessionStore.save(session);
                    showMain(data);
                } catch (JSONException exception) {
                    clearAndShowLogin();
                }
            }

            @Override
            public void onError(String errorCode) {
                clearAndShowLogin();
            }
        });
    }

    private void showLogin() {
        loginView = new LoginView(this, new LoginView.Listener() {
            @Override
            public void onIdentify(JSONObject credentials) {
                loginView.setBusy(true);
                api.call("identify_login", credentials, null, new ApiCallback() {
                    @Override
                    public void onSuccess(JSONObject data) {
                        String passwordMode = data.optString("passwordMode", "login");
                        String displayName = data.optString("displayName", "");
                        loginView.showPasswordStep(passwordMode, displayName);
                    }

                    @Override
                    public void onError(String errorCode) {
                        if ("unknown_operation".equals(errorCode)) {
                            identifyWithLegacyApi(credentials);
                        } else {
                            loginView.showError(errorMessage(errorCode));
                        }
                    }
                });
            }

            @Override
            public void onLogin(JSONObject credentials) {
                if (!loginView.passwordsMatch()) {
                    loginView.showError(R.string.passwords_do_not_match);
                    return;
                }
                if (!loginView.passwordIsLongEnough()) {
                    loginView.showError(R.string.password_too_short);
                    return;
                }
                loginView.setBusy(true);
                api.call("login", credentials, null, new ApiCallback() {
                    @Override
                    public void onSuccess(JSONObject data) {
                        try {
                            session = AppSession.fromPayload(data);
                            sessionStore.save(session);
                            validateSavedSession();
                        } catch (JSONException exception) {
                            loginView.showError(R.string.invalid_server_response);
                        }
                    }

                    @Override
                    public void onError(String errorCode) {
                        if ("password_setup_required".equals(errorCode)) {
                            loginView.showPasswordStep("setup", "");
                        } else if ("password_change_required".equals(errorCode)) {
                            loginView.showPasswordStep("change", "");
                        } else {
                            loginView.showError(errorMessage(errorCode));
                        }
                    }
                });
            }

            @Override
            public void onPasswordReset(JSONObject credentials) {
                loginView.setBusy(true);
                api.call("request_password_reset", credentials, null, new ApiCallback() {
                    @Override
                    public void onSuccess(JSONObject data) {
                        loginView.setBusy(false);
                        message(
                            getString(R.string.reset_requested_title),
                            getString(R.string.reset_requested_message)
                        );
                    }

                    @Override
                    public void onError(String errorCode) {
                        loginView.showError(errorMessage(errorCode));
                    }
                });
            }

            @Override
            public void onLanguage(String language) {
                LanguageManager.save(MainActivity.this, language);
                recreate();
            }

            @Override
            public void onConfiguration() {
                showConfiguration();
            }
        });
        setContentView(UiKit.scroll(this, loginView));
    }

    /**
     * Keep the two-step screen usable while an older Edge Function is still
     * deployed. An empty password safely reveals only the required form mode.
     */
    private void identifyWithLegacyApi(JSONObject credentials) {
        api.call("login", credentials, null, new ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                try {
                    session = AppSession.fromPayload(data);
                    sessionStore.save(session);
                    validateSavedSession();
                } catch (JSONException exception) {
                    loginView.showError(R.string.invalid_server_response);
                }
            }

            @Override
            public void onError(String errorCode) {
                if ("password_setup_required".equals(errorCode)) {
                    loginView.showPasswordStep("setup", "");
                } else if ("invalid_credentials".equals(errorCode)) {
                    loginView.showPasswordStep("login", "");
                } else {
                    loginView.showError(errorMessage(errorCode));
                }
            }
        });
    }

    private void showMain(JSONObject bootstrap) {
        MainShellView shell = new MainShellView(
            this,
            api,
            session,
            bootstrap,
            new MainShellView.Listener() {
                @Override
                public void onLogout() {
                    api.call("logout", new JSONObject(), session.accessToken(), new ApiCallback() {
                        @Override
                        public void onSuccess(JSONObject data) {
                            clearAndShowLogin();
                        }

                        @Override
                        public void onError(String errorCode) {
                            clearAndShowLogin();
                        }
                    });
                }

                @Override
                public void onLanguage(String language) {
                    JSONObject payload = new JSONObject();
                    try {
                        payload.put("language", language);
                    } catch (JSONException ignored) {
                        return;
                    }
                    api.call("set_language", payload, session.accessToken(), new ApiCallback() {
                        @Override
                        public void onSuccess(JSONObject data) {
                            LanguageManager.save(MainActivity.this, language);
                            recreate();
                        }

                        @Override
                        public void onError(String errorCode) {
                            message(getString(R.string.error), errorMessage(errorCode));
                        }
                    });
                }
            }
        );
        setContentView(shell);
    }

    private void showLoading(String message) {
        LinearLayout loading = UiKit.vertical(this);
        loading.setGravity(Gravity.CENTER);
        loading.addView(UiKit.progress(this));
        loading.addView(UiKit.caption(this, message));
        setContentView(loading);
    }

    private void clearAndShowLogin() {
        sessionStore.clear();
        session = null;
        showLogin();
    }

    public String errorMessage(String code) {
        return switch (code) {
            case "invalid_credentials" -> getString(R.string.invalid_credentials);
            case "too_many_attempts" -> getString(R.string.too_many_attempts);
            case "network_error" -> getString(R.string.network_error);
            case "session_expired" -> getString(R.string.session_expired);
            case "password_too_short" -> getString(R.string.password_too_short);
            case "password_setup_required" -> getString(R.string.password_setup_required);
            case "password_change_required" -> getString(R.string.password_change_required);
            case "target_agent_not_found" -> getString(R.string.target_agent_not_found);
            case "comment_empty" -> getString(R.string.comment_empty);
            case "forbidden" -> getString(R.string.forbidden);
            default -> getString(R.string.generic_error);
        };
    }

    private String configurationError(String code) {
        return switch (code) {
            case "configuration_url_required" -> getString(R.string.configuration_url_required);
            case "configuration_url_invalid" -> getString(R.string.configuration_url_invalid);
            case "configuration_key_invalid" -> getString(R.string.configuration_key_invalid);
            case "invalid_client_key" -> getString(R.string.configuration_key_rejected);
            case "function_unavailable" -> getString(R.string.configuration_function_unavailable);
            case "network_error" -> getString(R.string.configuration_network_error);
            default -> getString(R.string.configuration_test_failed);
        };
    }

    public void message(String title, String body) {
        new AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(body)
            .setPositiveButton(android.R.string.ok, null)
            .show();
    }

    @Override
    protected void onDestroy() {
        if (api != null) api.shutdown();
        super.onDestroy();
    }
}
