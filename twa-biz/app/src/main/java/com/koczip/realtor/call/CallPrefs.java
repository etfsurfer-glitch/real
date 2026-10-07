package com.koczip.realtor.call;

import android.content.Context;
import android.content.SharedPreferences;

/** 통화감지 설정 저장 — 네이티브 토큰·온보딩 상태. */
public class CallPrefs {
    private static final String P = "koczip_call";

    private static SharedPreferences sp(Context c) {
        return c.getSharedPreferences(P, Context.MODE_PRIVATE);
    }

    public static String token(Context c) { return sp(c).getString("token", null); }
    public static void setToken(Context c, String t) { sp(c).edit().putString("token", t).apply(); }

    /** 온보딩을 보여줘야 하나 — 로그인 안 됐고, '나중에'를 누른 적도 없을 때 1회. */
    public static boolean needsOnboarding(Context c) {
        return token(c) == null && !sp(c).getBoolean("onboard_dismissed", false);
    }
    public static void dismissOnboarding(Context c) {
        sp(c).edit().putBoolean("onboard_dismissed", true).apply();
    }
}
