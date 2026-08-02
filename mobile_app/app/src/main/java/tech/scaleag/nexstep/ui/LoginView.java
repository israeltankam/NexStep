package tech.scaleag.nexstep.ui;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Color;
import android.text.method.PasswordTransformationMethod;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

import tech.scaleag.nexstep.R;

/** Native login that mirrors Streamlit's PIN-then-password sequence. */
@SuppressLint("ViewConstructor")
public final class LoginView extends LinearLayout {

    public interface Listener {
        void onIdentify(JSONObject credentials);

        void onLogin(JSONObject credentials);

        void onPasswordReset(JSONObject credentials);

        void onLanguage(String language);

        void onConfiguration();
    }

    private final EditText companyPin;
    private final EditText agentPin;
    private final EditText password;
    private final EditText newPassword;
    private final EditText confirmation;
    private final TextView stepMessage;
    private final TextView error;
    private final CheckBox showSecrets;
    private final Button submit;
    private final Button forgot;
    private final Button backToPins;
    private String mode = "identify";

    public LoginView(Context context, Listener listener) {
        super(context);
        setOrientation(VERTICAL);
        setGravity(Gravity.CENTER_HORIZONTAL);
        setPadding(
            UiKit.dp(context, 24),
            UiKit.dp(context, 24),
            UiKit.dp(context, 24),
            UiKit.dp(context, 32)
        );
        setBackgroundColor(Color.WHITE);

        LinearLayout languageRow = new LinearLayout(context);
        languageRow.setGravity(Gravity.END);
        Button french = compactButton(context, "FR");
        Button english = compactButton(context, "EN");
        french.setOnClickListener(view -> listener.onLanguage("fr"));
        english.setOnClickListener(view -> listener.onLanguage("en"));
        languageRow.addView(french);
        languageRow.addView(english);
        addView(languageRow, new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        ImageView logo = new ImageView(context);
        logo.setImageResource(R.drawable.nexstep_logo);
        logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        logo.setContentDescription(context.getString(R.string.app_name));
        LayoutParams logoParams = new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            UiKit.dp(context, 100)
        );
        logoParams.setMargins(0, UiKit.dp(context, 20), 0, UiKit.dp(context, 18));
        addView(logo, logoParams);

        addView(UiKit.title(context, context.getString(R.string.login_title)));
        addView(UiKit.caption(context, context.getString(R.string.login_caption)));

        stepMessage = UiKit.body(context, "");
        stepMessage.setVisibility(GONE);
        LayoutParams messageParams = new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        messageParams.setMargins(0, UiKit.dp(context, 14), 0, UiKit.dp(context, 8));
        addView(stepMessage, messageParams);

        error = UiKit.body(context, "");
        error.setTextColor(Color.rgb(190, 45, 54));
        error.setVisibility(GONE);
        LayoutParams errorParams = new LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        errorParams.setMargins(0, UiKit.dp(context, 14), 0, UiKit.dp(context, 8));
        addView(error, errorParams);

        companyPin = UiKit.input(context, context.getString(R.string.company_pin), true);
        agentPin = UiKit.input(context, context.getString(R.string.agent_pin), true);
        password = UiKit.input(context, context.getString(R.string.password), true);
        newPassword = UiKit.input(context, context.getString(R.string.new_password), true);
        confirmation = UiKit.input(context, context.getString(R.string.confirm_password), true);
        addView(companyPin);
        addView(agentPin);
        addView(password);
        addView(newPassword);
        addView(confirmation);
        password.setVisibility(GONE);
        newPassword.setVisibility(GONE);
        confirmation.setVisibility(GONE);

        showSecrets = new CheckBox(context);
        showSecrets.setText(context.getString(R.string.show_login_secrets));
        showSecrets.setTextSize(15);
        showSecrets.setTextColor(UiKit.TEXT);
        showSecrets.setOnCheckedChangeListener(
            (button, checked) -> setSecretsVisible(checked)
        );
        addView(showSecrets);

        submit = UiKit.primaryButton(context, context.getString(R.string.login_continue));
        submit.setOnClickListener(view -> {
            if ("identify".equals(mode)) {
                listener.onIdentify(credentials());
            } else {
                listener.onLogin(credentials());
            }
        });
        addView(submit);

        forgot = UiKit.commandButton(context, context.getString(R.string.forgot_password));
        forgot.setOnClickListener(view -> listener.onPasswordReset(credentials()));
        forgot.setVisibility(GONE);
        addView(forgot);

        backToPins = UiKit.commandButton(context, context.getString(R.string.edit_pins));
        backToPins.setOnClickListener(view -> showPinStep());
        backToPins.setVisibility(GONE);
        addView(backToPins);

        Button configuration = UiKit.commandButton(
            context,
            context.getString(R.string.configuration_open)
        );
        configuration.setOnClickListener(view -> listener.onConfiguration());
        addView(configuration);

        TextView security = UiKit.caption(context, context.getString(R.string.login_security_note));
        security.setGravity(Gravity.CENTER);
        security.setPadding(0, UiKit.dp(context, 18), 0, 0);
        addView(security);
    }

    private Button compactButton(Context context, String label) {
        Button button = new Button(context);
        button.setText(label);
        button.setAllCaps(false);
        button.setMinWidth(UiKit.dp(context, 52));
        button.setMinHeight(UiKit.dp(context, 40));
        return button;
    }

    /** Display only the password fields required by the identified account. */
    public void showPasswordStep(String passwordMode, String displayName) {
        mode = switch (passwordMode) {
            case "setup", "change", "login" -> passwordMode;
            default -> "login";
        };
        companyPin.setVisibility(GONE);
        agentPin.setVisibility(GONE);
        password.setVisibility("setup".equals(mode) ? GONE : VISIBLE);
        newPassword.setVisibility("login".equals(mode) ? GONE : VISIBLE);
        confirmation.setVisibility("login".equals(mode) ? GONE : VISIBLE);
        forgot.setVisibility("login".equals(mode) ? VISIBLE : GONE);
        backToPins.setVisibility(VISIBLE);
        error.setVisibility(GONE);

        if (displayName == null || displayName.isBlank()) {
            int genericMessage = switch (mode) {
                case "setup" -> R.string.password_setup_required;
                case "change" -> R.string.password_change_required;
                default -> R.string.login_password_prompt;
            };
            stepMessage.setText(genericMessage);
        } else {
            int namedMessage = switch (mode) {
                case "setup" -> R.string.login_setup_hello;
                case "change" -> R.string.login_change_hello;
                default -> R.string.login_password_hello;
            };
            stepMessage.setText(getContext().getString(namedMessage, displayName));
        }
        stepMessage.setVisibility(VISIBLE);
        setBusy(false);

        EditText firstField = "setup".equals(mode) ? newPassword : password;
        firstField.requestFocus();
    }

    private void showPinStep() {
        mode = "identify";
        companyPin.setVisibility(VISIBLE);
        agentPin.setVisibility(VISIBLE);
        password.setVisibility(GONE);
        newPassword.setVisibility(GONE);
        confirmation.setVisibility(GONE);
        password.setText("");
        newPassword.setText("");
        confirmation.setText("");
        stepMessage.setVisibility(GONE);
        error.setVisibility(GONE);
        forgot.setVisibility(GONE);
        backToPins.setVisibility(GONE);
        setBusy(false);
        companyPin.requestFocus();
    }

    public boolean passwordsMatch() {
        return "login".equals(mode) || "identify".equals(mode) ||
            newPassword.getText().toString().equals(confirmation.getText().toString());
    }

    public boolean passwordIsLongEnough() {
        return "login".equals(mode) || "identify".equals(mode) ||
            newPassword.getText().length() >= 4;
    }

    public void showError(int messageResource) {
        showError(getContext().getString(messageResource));
    }

    public void showError(String message) {
        error.setText(message);
        error.setVisibility(VISIBLE);
        setBusy(false);
    }

    public void setBusy(boolean busy) {
        companyPin.setEnabled(!busy);
        agentPin.setEnabled(!busy);
        password.setEnabled(!busy);
        newPassword.setEnabled(!busy);
        confirmation.setEnabled(!busy);
        showSecrets.setEnabled(!busy);
        submit.setEnabled(!busy);
        forgot.setEnabled(!busy);
        backToPins.setEnabled(!busy);
        submit.setText(busy ? R.string.please_wait : buttonLabel());
    }

    private int buttonLabel() {
        return switch (mode) {
            case "identify" -> R.string.login_continue;
            case "setup" -> R.string.create_password_and_sign_in;
            case "change" -> R.string.change_password_and_sign_in;
            default -> R.string.sign_in;
        };
    }

    private void setSecretsVisible(boolean visible) {
        for (EditText field : new EditText[]{
            companyPin,
            agentPin,
            password,
            newPassword,
            confirmation
        }) {
            int selection = field.getSelectionStart();
            field.setTransformationMethod(
                visible ? null : PasswordTransformationMethod.getInstance()
            );
            field.setSelection(Math.max(0, Math.min(selection, field.length())));
        }
    }

    private JSONObject credentials() {
        try {
            return new JSONObject()
                .put("companyPin", companyPin.getText().toString().trim())
                .put("agentPin", agentPin.getText().toString().trim())
                .put("password", password.getText().toString())
                .put("newPassword", newPassword.getVisibility() == VISIBLE
                    ? newPassword.getText().toString()
                    : "");
        } catch (JSONException exception) {
            return new JSONObject();
        }
    }
}
