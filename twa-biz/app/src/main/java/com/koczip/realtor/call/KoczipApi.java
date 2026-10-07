package com.koczip.realtor.call;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** api.koczip.com 통신 — 표준 라이브러리만 사용(의존성 0). 모든 호출은 백그라운드 스레드. */
public class KoczipApi {
    private static final String BASE = "https://api.koczip.com";
    private static final ExecutorService EX = Executors.newCachedThreadPool();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    public interface Cb { void done(JSONObject res, String err); }
    public interface OkCb { void done(boolean ok); }

    private static JSONObject request(String method, String path, String bearer, JSONObject body) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(BASE + path).openConnection();
        conn.setRequestMethod(method);
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(8000);
        conn.setRequestProperty("User-Agent", "koczip-realtor-app/1.0");
        if (bearer != null) conn.setRequestProperty("Authorization", "Bearer " + bearer);
        if (body != null) {
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body.toString().getBytes("UTF-8"));
            }
        }
        int code = conn.getResponseCode();
        InputStream is = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        StringBuilder sb = new StringBuilder();
        if (is != null) {
            BufferedReader br = new BufferedReader(new InputStreamReader(is, "UTF-8"));
            String line;
            while ((line = br.readLine()) != null) sb.append(line);
        }
        JSONObject out = sb.length() > 0 ? new JSONObject(sb.toString()) : new JSONObject();
        out.put("_status", code);
        return out;
    }

    private static void run(String method, String path, String bearer, JSONObject body, Cb cb) {
        EX.execute(() -> {
            try {
                JSONObject r = request(method, path, bearer, body);
                MAIN.post(() -> cb.done(r, null));
            } catch (Exception e) {
                MAIN.post(() -> cb.done(null, e.getMessage()));
            }
        });
    }

    public static void sendOtp(String phone, Cb cb) {
        try {
            JSONObject b = new JSONObject().put("phone", phone);
            run("POST", "/biz/native-auth/otp", null, b, cb);
        } catch (Exception e) { cb.done(null, e.getMessage()); }
    }

    public static void verifyOtp(String phone, String code, Cb cb) {
        try {
            JSONObject b = new JSONObject().put("phone", phone).put("code", code);
            run("POST", "/biz/native-auth/verify", null, b, cb);
        } catch (Exception e) { cb.done(null, e.getMessage()); }
    }

    public static void callLookup(Context c, String phone, Cb cb) {
        String tok = CallPrefs.token(c);
        if (tok == null) { cb.done(null, "no-token"); return; }
        try {
            run("GET", "/biz/call-lookup?phone=" + URLEncoder.encode(phone, "UTF-8"), tok, null, cb);
        } catch (Exception e) { cb.done(null, e.getMessage()); }
    }

    /** 통화 감지 진단 업로드(원격 무협조 진단용). 200이면 성공. */
    public static void postDiag(Context c, JSONObject body, OkCb cb) {
        String tok = CallPrefs.token(c);
        if (tok == null) { cb.done(false); return; }
        run("POST", "/biz/call-diag", tok, body, (r, e) ->
                cb.done(r != null && r.optInt("_status", 0) == 200));
    }

    public static void callEvent(Context c, String phone, String direction, String startedAt, int durationS) {
        String tok = CallPrefs.token(c);
        if (tok == null) return;
        try {
            JSONObject b = new JSONObject().put("phone", phone).put("direction", direction)
                    .put("started_at", startedAt).put("duration_s", durationS);
            run("POST", "/biz/call-events", tok, b, (r, e) -> { /* 조용히 */ });
        } catch (Exception ignored) { }
    }
}
