package tech.scaleag.nexstep.data;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

import tech.scaleag.nexstep.model.AppSession;

/**
 * Stores the revocable mobile bearer session using an Android Keystore key.
 *
 * <p>No PIN or password is persisted. Clearing the application data removes
 * both the encrypted payload and the device key.</p>
 */
public final class SessionStore {

    private static final String KEY_ALIAS = "nexstep_mobile_session_v1";
    private static final String PREFERENCES = "nexstep_secure_session";
    private static final String ENCRYPTED_VALUE = "encrypted_value";
    private static final String INITIALIZATION_VECTOR = "initialization_vector";

    private final SharedPreferences preferences;

    public SessionStore(Context context) {
        preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    public void save(AppSession session) {
        try {
            JSONObject payload = new JSONObject()
                .put("accessToken", session.accessToken())
                .put("expiresAt", session.expiresAt())
                .put("profile", session.profile());
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
            byte[] encrypted = cipher.doFinal(
                payload.toString().getBytes(StandardCharsets.UTF_8)
            );
            preferences.edit()
                .putString(ENCRYPTED_VALUE, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putString(
                    INITIALIZATION_VECTOR,
                    Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)
                )
                .apply();
        } catch (Exception exception) {
            clear();
        }
    }

    public AppSession load() {
        String encryptedValue = preferences.getString(ENCRYPTED_VALUE, null);
        String vectorValue = preferences.getString(INITIALIZATION_VECTOR, null);
        if (encryptedValue == null || vectorValue == null) return null;
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(
                Cipher.DECRYPT_MODE,
                getOrCreateKey(),
                new GCMParameterSpec(128, Base64.decode(vectorValue, Base64.NO_WRAP))
            );
            byte[] clear = cipher.doFinal(Base64.decode(encryptedValue, Base64.NO_WRAP));
            JSONObject payload = new JSONObject(new String(clear, StandardCharsets.UTF_8));
            AppSession session = AppSession.fromPayload(payload);
            if (session.isExpired()) {
                clear();
                return null;
            }
            return session;
        } catch (Exception exception) {
            clear();
            return null;
        }
    }

    public void clear() {
        preferences.edit().clear().apply();
    }

    private SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        java.security.Key existing = keyStore.getKey(KEY_ALIAS, null);
        if (existing instanceof SecretKey) return (SecretKey) existing;

        KeyGenerator generator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            "AndroidKeyStore"
        );
        generator.init(new KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build());
        return generator.generateKey();
    }
}
