package com.koczip.realtor.call;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.os.PersistableBundle;

import org.json.JSONObject;

/** 통화 종료 직후 즉시 재조회마저 실패(기기 Doze로 네트워크 차단)한 경우의 최후 보루.
 *  JobScheduler 잡은 배터리 최적화 하에서도 실행 창에 네트워크가 허용되므로, 네트워크가
 *  돌아올 때(대개 사용자가 폰을 깨울 때) 실행돼 통화 후 알림 카드에 고객 이름을 채운다. */
public class CallRetryJob extends JobService {

    private static final int JOB_ID = 7110;

    /** 즉시 재조회조차 네트워크에 닿지 못했을 때 예약 — 네트워크 복귀 시 1회 재조회. */
    public static void schedule(Context ctx, String phone, String dir, int dur) {
        JobScheduler js = (JobScheduler) ctx.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        PersistableBundle x = new PersistableBundle();
        x.putString("phone", phone);
        x.putString("dir", dir);
        x.putInt("dur", dur);
        JobInfo job = new JobInfo.Builder(JOB_ID, new ComponentName(ctx, CallRetryJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)  // 어떤 네트워크든 복귀 시
                .setMinimumLatency(1500)                           // 통화 직후 소음 회피
                .setOverrideDeadline(6L * 60 * 60 * 1000)          // 최대 6시간 내 실행
                .setExtras(x)
                .build();
        js.schedule(job);   // 같은 JOB_ID면 최신 통화로 교체
        android.util.Log.i("KoczipCall", "retry job scheduled phone=" + phone);
    }

    @Override
    public boolean onStartJob(JobParameters params) {
        PersistableBundle x = params.getExtras();
        final String phone = x.getString("phone");
        final String dir = x.getString("dir");
        final int dur = x.getInt("dur", 0);
        // 네트워크가 보장된 실행창 — 밀린 진단 기록을 이때 확실히 올린다.
        CallDiag.flush(getApplicationContext());
        if (phone == null) return false;
        KoczipApi.callLookup(getApplicationContext(), phone, (info, err) -> {
            android.util.Log.i("KoczipCall", "job re-lookup err=" + err);
            CallDiag.log(getApplicationContext(), "지연룩업", err != null ? "실패:" + err : "성공");
            JSONObject cust = info != null ? info.optJSONObject("customer") : null;
            if (cust != null) {
                CallNotifier.showAftercall(getApplicationContext(), phone, dir, dur, info);
            }
            CallDiag.flush(getApplicationContext());
            jobFinished(params, false);   // 성공/실패 무관하게 종료(무한재시도 금지)
        });
        return true;   // 콜백까지 진행 중
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return false;   // 재스케줄 안 함
    }
}
