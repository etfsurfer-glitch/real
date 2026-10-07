package com.koczip.realtor.call;

import android.app.role.RoleManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

/** 통화 감지 원격 진단 — 각 단계를 로컬 링버퍼에 남기고, 네트워크가 될 때 서버로 올려
 *  (사용자 협조·캡처 없이) 어디서 끊기는지 서버에서 대조한다.
 *  개인정보 최소화: 전화번호는 뒷 4자리만 기록. */
public class CallDiag {
    private static final String APP_VER = "1.0.5-callog";   // 빌드마다 갱신 — 설치 확인용
    private static final String PREF = "koczip_calldiag";
    private static final String KEY = "entries";
    private static final int MAX = 60;

    /** 한 단계 기록 — 예: log(ctx, "감지", "…1234"), log(ctx, "룩업", "고객:홍길동"). */
    public static synchronized void log(Context c, String stage, String detail) {
        try {
            SharedPreferences sp = c.getApplicationContext()
                    .getSharedPreferences(PREF, Context.MODE_PRIVATE);
            JSONArray arr = new JSONArray(sp.getString(KEY, "[]"));
            JSONObject e = new JSONObject();
            e.put("t", System.currentTimeMillis());
            e.put("stage", stage);
            if (detail != null) e.put("detail", detail);
            arr.put(e);
            while (arr.length() > MAX) arr.remove(0);   // 링버퍼
            sp.edit().putString(KEY, arr.toString()).apply();
        } catch (Exception ignored) { }
    }

    /** 번호 뒷 4자리만(개인정보 최소화). */
    public static String tail(String phone) {
        if (phone == null) return "?";
        String d = phone.replaceAll("[^0-9]", "");
        return d.length() >= 4 ? "…" + d.substring(d.length() - 4) : (d.isEmpty() ? "?" : d);
    }

    /** 기기·권한 상태 스냅샷 — 제조사/모델/안드로이드버전 + 역할·오버레이·배터리·알림·토큰. */
    public static JSONObject snapshot(Context c) {
        JSONObject o = new JSONObject();
        try {
            o.put("manufacturer", Build.MANUFACTURER);
            o.put("model", Build.MODEL);
            o.put("sdk", Build.VERSION.SDK_INT);
            o.put("release", Build.VERSION.RELEASE);
            o.put("ver", APP_VER);   // 설치된 APK 버전 확인용
            o.put("role", roleHeld(c));
            o.put("overlay", Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(c));
            o.put("battery", batteryExempt(c));
            o.put("noti", notiGranted(c));
            o.put("callog", callogGranted(c));   // READ_CALL_LOG(수신번호 취득)
            o.put("other_screen", CallLogHelper.otherScreeningApps(c));   // 충돌 가능 발신자ID 앱들
            o.put("token", CallPrefs.token(c) != null);
        } catch (Exception ignored) { }
        return o;
    }

    /** 버퍼 + 스냅샷을 서버로 전송. 성공 시 버퍼를 비운다(실패 시 유지 → 다음 기회에 재전송). */
    public static void flush(Context c) {
        final Context app = c.getApplicationContext();
        if (CallPrefs.token(app) == null) return;
        final SharedPreferences sp = app.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        final String entries = sp.getString(KEY, "[]");
        JSONObject body = new JSONObject();
        try {
            body.put("device", snapshot(app));
            body.put("entries", new JSONArray(entries));
        } catch (Exception e) { return; }
        if ("[]".equals(entries)) return;   // 보낼 것 없음(스냅샷만 굳이 안 보냄)
        KoczipApi.postDiag(app, body, ok -> {
            if (ok) {
                // 전송 사이 새로 쌓인 게 있으면 지우지 않도록, 보낸 만큼만 앞에서 제거
                try {
                    JSONArray now = new JSONArray(sp.getString(KEY, "[]"));
                    int sent = new JSONArray(entries).length();
                    JSONArray rest = new JSONArray();
                    for (int i = sent; i < now.length(); i++) rest.put(now.get(i));
                    sp.edit().putString(KEY, rest.toString()).apply();
                } catch (Exception e) { sp.edit().putString(KEY, "[]").apply(); }
            }
        });
    }

    // ── 상태 헬퍼 ──
    public static boolean roleHeld(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false;
        try {
            RoleManager rm = (RoleManager) c.getSystemService(Context.ROLE_SERVICE);
            return rm != null && rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)
                    && rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING);
        } catch (Exception e) { return false; }
    }

    public static boolean batteryExempt(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true;
        try {
            android.os.PowerManager pm = (android.os.PowerManager)
                    c.getSystemService(Context.POWER_SERVICE);
            return pm != null && pm.isIgnoringBatteryOptimizations(c.getPackageName());
        } catch (Exception e) { return false; }
    }

    public static boolean notiGranted(Context c) {
        if (Build.VERSION.SDK_INT < 33) return true;
        try {
            return c.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED;
        } catch (Exception e) { return false; }
    }

    public static boolean callogGranted(Context c) {
        try {
            return c.checkSelfPermission(android.Manifest.permission.READ_CALL_LOG)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED;
        } catch (Exception e) { return false; }
    }
}
