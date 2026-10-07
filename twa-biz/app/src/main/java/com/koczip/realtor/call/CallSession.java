package com.koczip.realtor.call;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** 진행 중 통화 세션(단일) — 스크리닝에서 번호를 받고, 상태 전이로 방향·시간을 계산.
 *  RINGING→OFFHOOK→IDLE = 수신통화 / RINGING→IDLE = 부재중. */
public class CallSession {
    private static String phone;
    private static long ringAt;
    private static long offhookAt;
    private static org.json.JSONObject info;   // 수신 시 룩업 결과(통화 후 알림에 재사용)

    /** 수신 감지 — 최초 경로만 true(스크리닝/PHONE_STATE 중복 방지). 이미 진행 중이면 false. */
    public static synchronized boolean onIncoming(String p) {
        if (phone != null) return false;   // 다른 경로가 먼저 감지 → 중복 스킵
        phone = p;
        ringAt = System.currentTimeMillis();
        offhookAt = 0;
        info = null;
        return true;
    }

    public static synchronized void setInfo(org.json.JSONObject i) { info = i; }

    public static synchronized void onOffhook() {
        if (phone != null) offhookAt = System.currentTimeMillis();
    }

    /** IDLE 도달 — 세션 확정 후 초기화. 반환: [phone, direction, started_at, duration_s, info] 또는 null. */
    public static synchronized Object[] onIdle() {
        if (phone == null) return null;
        String p = phone;
        String direction = offhookAt > 0 ? "in" : "missed";
        long start = offhookAt > 0 ? offhookAt : ringAt;
        int dur = offhookAt > 0 ? (int) ((System.currentTimeMillis() - offhookAt) / 1000) : 0;
        String startedAt = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date(start));
        org.json.JSONObject in = info;
        phone = null; ringAt = 0; offhookAt = 0; info = null;
        return new Object[]{p, direction, startedAt, dur, in};
    }
}
