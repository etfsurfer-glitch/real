package com.koczip.realtor.call;

import android.content.Context;
import android.util.Log;

import org.json.JSONObject;

/** 수신 감지 → 고객 룩업 → 오버레이/알림 카드. CallScreeningService와 PHONE_STATE(READ_CALL_LOG)
 *  두 경로가 공통으로 호출한다(중복은 CallSession.onIncoming이 막음). source=경로 태그. */
public class CallCard {
    private static final String TAG = "KoczipCall";

    public static void detect(Context c, String phone, String source) {
        final Context ctx = c.getApplicationContext();
        Log.i(TAG, "detect via " + source + " phone=" + phone);
        CallDiag.log(ctx, "감지", source);
        CallDiag.log(ctx, "수신", CallDiag.tail(phone));
        KoczipApi.callLookup(ctx, phone, (info, err) -> {
            if (err != null) {
                CallDiag.log(ctx, "룩업실패", err.length() > 60 ? err.substring(0, 60) : err);
                if ("no-token".equals(err)) return;   // 로그인 없으면 카드 없음
            } else {
                JSONObject cu = info != null ? info.optJSONObject("customer") : null;
                CallDiag.log(ctx, "룩업성공", cu != null ? "고객:" + cu.optString("name", "?") : "미등록번호");
            }
            CallSession.setInfo(info);
            CallOverlay.show(ctx, phone, info);
            CallNotifier.showCard(ctx, phone, info);
            boolean ov = CallOverlay.canShow(ctx);
            Log.i(TAG, "card shown (overlayOk=" + ov + ", src=" + source + ")");
            CallDiag.log(ctx, "카드표시", "오버레이=" + ov + " 경로=" + source);
        });
    }
}
