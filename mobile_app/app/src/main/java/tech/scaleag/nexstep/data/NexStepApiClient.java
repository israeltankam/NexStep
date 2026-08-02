package tech.scaleag.nexstep.data;

import android.os.Handler;
import android.os.Looper;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.HttpsURLConnection;

import tech.scaleag.nexstep.BuildConfig;
import tech.scaleag.nexstep.data.PublicConfigurationStore.Configuration;

/**
 * Sole network data source for the native Android application.
 *
 * <p>The client can call only the dedicated Supabase Edge Function. It never
 * connects to PostgreSQL and cannot access tables through the Data API.</p>
 */
public final class NexStepApiClient {

    private static final int CONNECT_TIMEOUT_MS = 15_000;
    private static final int READ_TIMEOUT_MS = 45_000;
    private static final int MAX_RESPONSE_BYTES = 50 * 1024 * 1024;

    private final ExecutorService executor = Executors.newFixedThreadPool(3);
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final String endpoint;
    private final String publishableKey;

    public NexStepApiClient(Configuration configuration) {
        String baseUrl = configuration.projectUrl().replaceAll("/+$", "");
        endpoint = baseUrl + "/functions/v1/nexstep-mobile-api";
        publishableKey = configuration.publishableKey();
    }

    public void call(
        String operation,
        JSONObject payload,
        String accessToken,
        ApiCallback callback
    ) {
        executor.execute(() -> {
            try {
                JSONObject requestBody = new JSONObject()
                    .put("operation", operation)
                    .put("payload", payload == null ? new JSONObject() : payload);
                JSONObject envelope = execute(requestBody, accessToken);
                if (envelope.optBoolean("ok")) {
                    JSONObject data = envelope.optJSONObject("data");
                    deliverSuccess(callback, data == null ? new JSONObject() : data);
                } else {
                    deliverError(callback, envelope.optString("error", "server_error"));
                }
            } catch (JSONException exception) {
                deliverError(callback, "invalid_response");
            } catch (IOException exception) {
                deliverError(callback, "network_error");
            }
        });
    }

    private JSONObject execute(JSONObject requestBody, String accessToken)
        throws IOException, JSONException {
        HttpsURLConnection connection = (HttpsURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setDoOutput(true);
        connection.setUseCaches(false);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("apikey", publishableKey);
        connection.setRequestProperty("User-Agent", "NexStepAndroid/" + BuildConfig.VERSION_NAME);
        if (accessToken != null && !accessToken.isBlank()) {
            connection.setRequestProperty("Authorization", "Bearer " + accessToken);
        }

        byte[] requestBytes = requestBody.toString().getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(requestBytes.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(requestBytes);
        }

        int status = connection.getResponseCode();
        InputStream stream = status >= HttpURLConnection.HTTP_BAD_REQUEST
            ? connection.getErrorStream()
            : connection.getInputStream();
        if (stream == null) throw new IOException("Empty HTTP response.");
        String body;
        try (stream) {
            body = readLimited(stream);
        } finally {
            connection.disconnect();
        }
        JSONObject response = new JSONObject(body);
        if (!response.has("ok") && status == HttpURLConnection.HTTP_NOT_FOUND) {
            return new JSONObject().put("ok", false).put("error", "function_unavailable");
        }
        return response;
    }

    private String readLimited(InputStream stream) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8_192];
        int total = 0;
        int read;
        while ((read = stream.read(buffer)) != -1) {
            total += read;
            if (total > MAX_RESPONSE_BYTES) {
                throw new IOException("Response exceeds the safe mobile limit.");
            }
            output.write(buffer, 0, read);
        }
        return new String(output.toByteArray(), StandardCharsets.UTF_8);
    }

    private void deliverSuccess(ApiCallback callback, JSONObject data) {
        mainHandler.post(() -> callback.onSuccess(data));
    }

    private void deliverError(ApiCallback callback, String errorCode) {
        mainHandler.post(() -> callback.onError(errorCode));
    }

    public void shutdown() {
        executor.shutdownNow();
    }
}
