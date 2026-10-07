package com.koczip.realtor.call;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

/** 수신 중 발신자 카드 오버레이 — 전화 화면 위에 떠서 누구인지 즉시 보여준다.
 *  헤드업 알림은 통화 알림에 가려 안 보이므로(실측 확인), 후후·T전화처럼 오버레이로 표시.
 *  터치는 카드 밖으로 통과(FLAG_NOT_TOUCH_MODAL)해 Answer/Decline 버튼을 막지 않는다.
 *  ※폴더블 메인(안쪽) 화면은 삼성 One UI가 풀스크린 통화 액티비티 아래로 서드파티 오버레이를
 *    편입·클립해 렌더를 막는다(실측: SurfaceFlinger에서 우리 레이어 버퍼가 비어 있음, TYPE_
 *    APPLICATION_OVERLAY로도 못 넘음). 커버 화면에선 정상. 메인 대응은 지속 알림이 담당. */
public class CallOverlay {
    private static final String TAG = "KoczipCall";
    private static View view;
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    public static boolean canShow(Context c) {
        return Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(c);
    }

    public static void show(Context c, String phone, JSONObject info) {
        if (!canShow(c)) { Log.w(TAG, "overlay 권한 없음 — 알림만"); return; }
        MAIN.post(() -> {
            try {
                hideInternal(c);
                WindowManager wm = (WindowManager) c.getSystemService(Context.WINDOW_SERVICE);
                View v = buildCard(c, phone, info);
                int type = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE;
                WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                        WindowManager.LayoutParams.MATCH_PARENT,
                        WindowManager.LayoutParams.WRAP_CONTENT,
                        type,
                        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                                | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                        PixelFormat.TRANSLUCENT);
                lp.gravity = Gravity.TOP;
                lp.y = dp(c, 190);   // 통화 헤드업 알림(시스템 창, 상위 z-order) 아래로 내려 완전히 보이게
                wm.addView(v, lp);
                view = v;
                Log.i(TAG, "overlay 표시");
                MAIN.postDelayed(() -> hide(c), 25000);   // 안전망: 25초 후 자동 제거
            } catch (Exception e) { Log.e(TAG, "overlay 실패", e); }
        });
    }

    public static void hide(Context c) { MAIN.post(() -> hideInternal(c)); }

    private static void hideInternal(Context c) {
        try {
            if (view != null && view.getParent() != null) {
                WindowManager wm = (WindowManager) c.getSystemService(Context.WINDOW_SERVICE);
                wm.removeView(view);
            }
        } catch (Exception ignored) { }
        view = null;
    }

    private static View buildCard(Context c, String phone, JSONObject info) {
        JSONObject cust = info != null ? info.optJSONObject("customer") : null;
        String name = cust != null ? cust.optString("name", "") : "";
        boolean isCustomer = name != null && !name.isEmpty() && !"null".equals(name);

        LinearLayout card = new LinearLayout(c);
        card.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.parseColor(isCustomer ? "#0F5FCC" : "#16202E"));
        bg.setCornerRadius(dp(c, 18));
        card.setBackground(bg);
        int pad = dp(c, 16);
        card.setPadding(pad, pad, pad, pad);
        card.setElevation(dp(c, 8));

        TextView title = new TextView(c);
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(null, Typeface.BOLD);

        TextView sub = new TextView(c);
        sub.setTextColor(Color.parseColor("#DCE6F2"));
        sub.setTextSize(14);
        sub.setPadding(0, dp(c, 5), 0, 0);

        if (isCustomer) {
            title.setText("📞 " + name + "님 전화");
            StringBuilder b = new StringBuilder(fmtPhone(phone));
            String extra = "";
            JSONArray leads = info.optJSONArray("leads");
            if (leads != null && leads.length() > 0) {
                JSONObject l0 = leads.optJSONObject(0);
                String msg = l0 != null ? l0.optString("message", "") : "";
                if (msg != null && !msg.isEmpty()) extra = "최근문의: " + msg;
            }
            if (extra.isEmpty()) {          // 리드 없으면 고객 메모를 보여준다
                String memo = cust.optString("memo", "");
                if (memo != null && !memo.isEmpty() && !"null".equals(memo)) extra = memo;
            }
            if (!extra.isEmpty())
                b.append("   ").append(extra.length() > 24 ? extra.substring(0, 24) + "…" : extra);
            sub.setText(b.toString());
        } else {
            title.setText("📞 " + fmtPhone(phone));
            sub.setText("콕집 미등록 번호 — 탭하면 고객으로 등록");
        }
        card.addView(title);
        card.addView(sub);

        final String url = isCustomer
                ? "https://koczip.com/biz/leads?phone=" + phone
                : "https://koczip.com/biz?call=" + phone;
        card.setOnClickListener(v -> {
            try {
                hide(c);
                Intent open = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                open.setPackage(c.getPackageName());
                open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                c.startActivity(open);
            } catch (Exception ignored) { }
        });

        LinearLayout wrap = new LinearLayout(c);
        int m = dp(c, 10);
        wrap.setPadding(m, 0, m, 0);
        wrap.addView(card, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return wrap;
    }

    private static String fmtPhone(String p) {
        String d = p.replaceAll("[^0-9]", "");
        if (d.length() == 11) return d.substring(0, 3) + "-" + d.substring(3, 7) + "-" + d.substring(7);
        if (d.length() == 10) return d.substring(0, 3) + "-" + d.substring(3, 6) + "-" + d.substring(6);
        return p;
    }

    private static int dp(Context c, int v) {
        return (int) (v * c.getResources().getDisplayMetrics().density);
    }
}
