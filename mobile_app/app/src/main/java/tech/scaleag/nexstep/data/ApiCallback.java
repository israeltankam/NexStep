package tech.scaleag.nexstep.data;

import org.json.JSONObject;

/** Delivers one asynchronous Edge Function result on Android's main thread. */
public interface ApiCallback {
    void onSuccess(JSONObject data);

    void onError(String errorCode);
}
