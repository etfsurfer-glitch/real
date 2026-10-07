package com.koczip.realtor.call;

import android.os.Build;
import android.telecom.Call;
import android.telecom.CallScreeningService;
import android.util.Log;

import androidx.annotation.RequiresApi;

/** 발신자 확인(Call Screening) — 수신 번호를 합법 취득(READ_CALL_LOG 불필요).
 *  절대 차단하지 않고 통과시키며, 고객 카드 알림만 띄운다. 실패는 전부 조용히. */
@RequiresApi(api = Build.VERSION_CODES.N)
public class KoczipCallScreeningService extends CallScreeningService {

    private static final String TAG = "KoczipCall";

    @Override
    public void onCreate() {
        super.onCreate();
        // 서비스가 실제로 바인딩됐는지 진단 — 이게 안 찍히면 역할이 활성이 아니거나 삼성이 가로챈 것.
        Log.i(TAG, "screening service onCreate");
        CallDiag.log(this, "서비스생성", "screening bound");
    }

    @Override
    public void onScreenCall(Call.Details details) {
        // 무조건 통과 — 우리는 차단·필터링을 하지 않는다(전화 UX 무간섭 원칙)
        respondToCall(details, new CallResponse.Builder().build());
        try {
            Log.i(TAG, "onScreenCall fired");
            CallDiag.log(this, "감지", "onScreenCall");   // 서비스가 붙어 이벤트가 왔다
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
                    && details.getCallDirection() != Call.Details.DIRECTION_INCOMING) {
                Log.i(TAG, "not incoming → skip card");
                CallDiag.log(this, "감지", "발신 → 카드생략");
                return;   // 발신은 카드 불필요(이벤트는 CallStateReceiver가 담당)
            }
            if (details.getHandle() == null) { Log.w(TAG, "handle null"); CallDiag.log(this, "감지", "번호없음(handle null)"); return; }
            String phone = details.getHandle().getSchemeSpecificPart();
            if (phone == null || phone.isEmpty()) { Log.w(TAG, "phone empty"); CallDiag.log(this, "감지", "번호비어있음"); return; }
            Log.i(TAG, "incoming phone=" + phone);
            // 최초 감지 경로만 처리(PHONE_STATE 경로와 중복 방지). 이 기기는 스크리닝이 뜨는 정상 기기.
            if (CallSession.onIncoming(phone)) {
                CallCard.detect(this, phone, "screening");
            } else {
                Log.i(TAG, "already detected by other path — skip");
            }
        } catch (Exception e) {
            Log.e(TAG, "onScreenCall err", e);
            CallDiag.log(this, "오류", "onScreenCall: " + e.getClass().getSimpleName());
        }
    }
}
