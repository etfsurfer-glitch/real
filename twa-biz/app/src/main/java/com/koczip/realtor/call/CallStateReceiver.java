package com.koczip.realtor.call;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.telephony.TelephonyManager;

/** 통화 상태 전이 감지 — 종료(IDLE) 시 통화 메타를 서버로 업로드.
 *  번호는 CallScreeningService 세션에서 이미 확보(READ_CALL_LOG 불필요). */
public class CallStateReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        try {
            String state = intent.getStringExtra(TelephonyManager.EXTRA_STATE);
            android.util.Log.i("KoczipCall", "PHONE_STATE=" + state);
            CallDiag.log(context, "상태", String.valueOf(state));
            // 수신벨 순간 진단: 우리가 발신자확인 역할을 실제로 쥐고 있는지 + PHONE_STATE로 번호가
            // 오는지(없으면 CallScreeningService 없이는 번호 취득 불가). onScreenCall이 안 뜰 때 원인 분리.
            if (TelephonyManager.EXTRA_STATE_RINGING.equals(state)
                    && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                boolean held = false, avail = false;
                try {
                    android.app.role.RoleManager rm = (android.app.role.RoleManager)
                            context.getSystemService(android.content.Context.ROLE_SERVICE);
                    held = rm != null && rm.isRoleHeld(android.app.role.RoleManager.ROLE_CALL_SCREENING);
                    avail = rm != null && rm.isRoleAvailable(android.app.role.RoleManager.ROLE_CALL_SCREENING);
                } catch (Exception ignored) { }
                String num = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER);
                CallDiag.log(context, "수신벨진단", "역할보유=" + held + " 역할가능=" + avail
                        + " 번호=" + (num == null || num.isEmpty() ? "없음(차단됨)" : "있음" + CallDiag.tail(num)));
                // READ_CALL_LOG로 번호를 얻으면(삼성 등 스크리닝 미동작 기기 대비) PHONE_STATE로 감지.
                // 700ms 지연 후 아직 스크리닝이 감지 안 했으면(onIncoming true) 이 경로로 카드.
                if (num != null && !num.isEmpty()) {
                    final Context ctx = context.getApplicationContext();
                    final String phone = num;
                    final android.content.BroadcastReceiver.PendingResult pr = goAsync();
                    new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
                        if (CallSession.onIncoming(phone)) {
                            CallCard.detect(ctx, phone, "phone_state");
                        }
                        pr.finish();
                    }, 700);
                }
            }
            if (TelephonyManager.EXTRA_STATE_OFFHOOK.equals(state)) {
                CallSession.onOffhook();
            } else if (TelephonyManager.EXTRA_STATE_IDLE.equals(state)) {
                CallOverlay.hide(context);   // 통화 종료 → 오버레이 카드 제거
                Object[] s = CallSession.onIdle();
                if (s != null) {
                    CallNotifier.dismiss(context);   // 통화 중 라이브 카드 제거
                    final Context ctx = context.getApplicationContext();
                    final String phone = (String) s[0], dir = (String) s[1], startedAt = (String) s[2];
                    final int dur = (Integer) s[3];
                    final org.json.JSONObject info = (org.json.JSONObject) s[4];
                    KoczipApi.callEvent(ctx, phone, dir, startedAt, dur);
                    CallDiag.log(ctx, "이벤트전송", dir + " " + dur + "초");
                    CallDiag.flush(ctx);   // 밀린 진단 기록을 서버로(네트워크 되면)
                    // 통화 중 룩업이 성공했으면 그대로, 실패(절전으로 네트워크 차단 등)했으면
                    // 통화 종료 후 기기가 깨어난 상태에서 재조회해 알림창 카드에 이름을 채운다.
                    boolean gotCustomer = info != null && info.optJSONObject("customer") != null;
                    if (gotCustomer || CallPrefs.token(ctx) == null) {
                        CallNotifier.showAftercall(ctx, phone, dir, dur, info);
                    } else {
                        final android.content.BroadcastReceiver.PendingResult pr = goAsync();  // 콜백까지 프로세스 유지
                        KoczipApi.callLookup(ctx, phone, (info2, err2) -> {
                            android.util.Log.i("KoczipCall", "aftercall re-lookup err=" + err2
                                    + " scheduleNeeded=" + (info2 == null));
                            // 즉시 재조회조차 네트워크에 닿지 못했으면(부재중+화면꺼짐 → 여전히 Doze),
                            // 네트워크가 돌아올 때 실행되는 잡을 예약해 카드에 이름을 뒤늦게라도 채운다.
                            if (info2 == null) {
                                try { CallRetryJob.schedule(ctx, phone, dir, dur); }
                                catch (Throwable t) { android.util.Log.e("KoczipCall", "schedule failed", t); }
                            }
                            CallNotifier.showAftercall(ctx, phone, dir, dur, info2 != null ? info2 : info);
                            pr.finish();
                        });
                    }
                } else if (CallLogHelper.granted(context)) {
                    // 통화 중 어떤 경로(스크리닝·PHONE_STATE)로도 번호를 못 잡음(다른 감지앱/삼성이
                    // 가로챈 경우 등) → 통화기록에서 방금 통화 번호를 복구해 종료 후 카드/이벤트.
                    String[] last = CallLogHelper.lastRecentCall(context);
                    if (last != null) {
                        final Context ctx = context.getApplicationContext();
                        final String phone = last[0], dir = last[1];
                        CallDiag.log(ctx, "복구", "통화기록 " + dir + " " + CallDiag.tail(phone));
                        KoczipApi.callEvent(ctx, phone, dir, null, 0);
                        CallDiag.flush(ctx);
                        if (CallPrefs.token(ctx) != null) {
                            final android.content.BroadcastReceiver.PendingResult pr = goAsync();
                            KoczipApi.callLookup(ctx, phone, (info2, err2) -> {
                                if (info2 == null) {
                                    try { CallRetryJob.schedule(ctx, phone, dir, 0); }
                                    catch (Throwable ignored2) { }
                                }
                                CallNotifier.showAftercall(ctx, phone, dir, 0, info2);
                                pr.finish();
                            });
                        }
                    }
                }
            }
        } catch (Exception ignored) { }
    }
}
