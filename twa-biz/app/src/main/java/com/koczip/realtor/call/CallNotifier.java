package com.koczip.realtor.call;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;

/** 수신 시 고객 카드 — 헤드업 알림(전화 UI 위에 배너로 뜸). 탭하면 비즈앱 리드 화면. */
public class CallNotifier {
    private static final String CH = "koczip_call";
    private static final String CH_AFTER = "koczip_call_after";
    private static final int ID = 7100;
    private static final int ID_AFTER = 7101;

    private static void ensureChannel(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm.getNotificationChannel(CH) == null) {
            NotificationChannel ch = new NotificationChannel(CH, "전화 고객알림", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("전화가 오면 콕집 고객 정보를 보여드려요");
            nm.createNotificationChannel(ch);
        }
        if (nm.getNotificationChannel(CH_AFTER) == null) {
            NotificationChannel ch = new NotificationChannel(CH_AFTER, "통화 후 알림", NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("통화가 끝나면 등록·상담할 번호를 알림창에 남겨드려요");
            nm.createNotificationChannel(ch);
        }
    }

    /** 통화 종료 후 알림창에 남기는 카드 — 미등록=등록 유도, 등록=통화 요약/상담 링크. 부재중처럼 지속. */
    public static void showAftercall(Context c, String phone, String direction, int durationS, JSONObject info) {
        ensureChannel(c);
        boolean missed = "missed".equals(direction);
        JSONObject cust = info != null ? info.optJSONObject("customer") : null;
        String name = cust != null ? cust.optString("name", "") : "";
        boolean isCustomer = name != null && !name.isEmpty() && !"null".equals(name);

        String title;
        StringBuilder body = new StringBuilder();
        if (isCustomer) {
            title = (missed ? "📵 부재중 · " : "📞 통화 · ") + name + "님";
            if (missed) body.append("콜백이 필요할 수 있어요. ");
            else if (durationS > 0) body.append("통화 ").append(fmtDur(durationS)).append(". ");
            body.append("탭해서 상담 기록·타임라인 보기");
        } else {
            title = (missed ? "📵 부재중 · " : "📞 통화 · ") + fmtPhone(phone);
            body.append("콕집 미등록 번호예요. 탭해서 고객으로 등록하세요.");
        }
        String url = isCustomer
                ? "https://koczip.com/biz/leads?phone=" + phone
                : "https://koczip.com/biz?call=" + phone;
        Intent open = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        open.setPackage(c.getPackageName());
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent pi = PendingIntent.getActivity(c, 1, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = (Build.VERSION.SDK_INT >= 26)
                ? new Notification.Builder(c, CH_AFTER) : new Notification.Builder(c);
        b.setSmallIcon(c.getApplicationInfo().icon)
                .setContentTitle(title)
                .setContentText(body.toString())
                .setStyle(new Notification.BigTextStyle().bigText(body.toString()))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_CALL)
                .setWhen(System.currentTimeMillis())
                .setShowWhen(true);
        if (Build.VERSION.SDK_INT < 26) b.setPriority(Notification.PRIORITY_DEFAULT);
        try {
            c.getSystemService(NotificationManager.class).notify(ID_AFTER, b.build());
        } catch (Exception ignored) { }
    }

    private static String fmtPhone(String p) {
        String d = p == null ? "" : p.replaceAll("[^0-9]", "");
        if (d.length() == 11) return d.substring(0, 3) + "-" + d.substring(3, 7) + "-" + d.substring(7);
        if (d.length() == 10) return d.substring(0, 3) + "-" + d.substring(3, 6) + "-" + d.substring(6);
        return p;
    }

    private static String fmtDur(int s) {
        if (s <= 0) return "";
        int m = s / 60, ss = s % 60;
        return m > 0 ? (m + "분 " + ss + "초") : (ss + "초");
    }

    /** lookup 응답으로 카드 구성. found=false면 "새 번호" 최소 표기(설정으로 끌 수도 있게 추후). */
    public static void showCard(Context c, String phone, JSONObject info) {
        ensureChannel(c);
        String title;
        StringBuilder body = new StringBuilder();
        // '고객 등록' 여부로 판단 — 통화이력만 있고 미등록이면 등록을 유도한다.
        JSONObject cust = info != null ? info.optJSONObject("customer") : null;
        String name = cust != null ? cust.optString("name", "") : "";
        boolean isCustomer = name != null && !name.isEmpty() && !"null".equals(name);
        if (isCustomer) {
            title = "📞 " + name + "님 전화";
            JSONArray leads = info.optJSONArray("leads");
            if (leads != null && leads.length() > 0) {
                JSONObject l0 = leads.optJSONObject(0);
                String msg = l0 != null ? l0.optString("message", "") : "";
                body.append("최근 문의: ").append(msg.isEmpty() ? l0.optString("source", "") : msg);
                if (leads.length() > 1) body.append(" 외 ").append(leads.length() - 1).append("건");
            }
            JSONArray hist = info.optJSONArray("history");
            if (hist != null && hist.length() > 0) {
                if (body.length() > 0) body.append("\n");
                JSONObject h0 = hist.optJSONObject(0);
                body.append("최근 통화: ").append(h0 != null ? h0.optString("at", "") : "");
            }
            if (body.length() == 0) body.append("콕집에 기록이 있는 고객입니다");
        } else {
            title = "📞 새 번호 · " + phone;
            body.append("콕집 미등록 번호예요. 탭해서 고객으로 등록하세요.");
        }

        // 등록고객=상담/타임라인(leads), 미등록=고객 등록 화면(?call=)으로
        String url = isCustomer
                ? "https://koczip.com/biz/leads?phone=" + phone
                : "https://koczip.com/biz?call=" + phone;
        Intent open = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        open.setPackage(c.getPackageName());
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent pi = PendingIntent.getActivity(c, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = (Build.VERSION.SDK_INT >= 26)
                ? new Notification.Builder(c, CH) : new Notification.Builder(c);
        b.setSmallIcon(c.getApplicationInfo().icon)
                .setContentTitle(title)
                .setContentText(body.toString())
                .setStyle(new Notification.BigTextStyle().bigText(body.toString()))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_CALL);
        if (Build.VERSION.SDK_INT < 26) b.setPriority(Notification.PRIORITY_HIGH);
        try {
            c.getSystemService(NotificationManager.class).notify(ID, b.build());
        } catch (Exception ignored) { }
    }

    public static void dismiss(Context c) {
        try { c.getSystemService(NotificationManager.class).cancel(ID); } catch (Exception ignored) { }
    }
}
