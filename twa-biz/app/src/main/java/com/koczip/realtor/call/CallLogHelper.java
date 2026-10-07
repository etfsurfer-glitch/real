package com.koczip.realtor.call;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.database.Cursor;
import android.provider.CallLog;
import android.text.TextUtils;

import java.util.ArrayList;
import java.util.List;

/** READ_CALL_LOG 기반 보조 — 통화 중 어떤 경로로도 번호를 못 잡았을 때(다른 감지앱/삼성 기능이
 *  CallScreeningService를 가로챈 경우 등) 통화 종료 후 통화기록에서 번호를 복구한다. */
public class CallLogHelper {

    public static boolean granted(Context c) {
        return c.checkSelfPermission(android.Manifest.permission.READ_CALL_LOG)
                == PackageManager.PERMISSION_GRANTED;
    }

    /** 최근(60초 내) 마지막 통화 [번호, 방향(in|out|missed)] 또는 null. */
    public static String[] lastRecentCall(Context c) {
        if (!granted(c)) return null;
        Cursor cur = null;
        try {
            cur = c.getContentResolver().query(
                    CallLog.Calls.CONTENT_URI,
                    new String[]{CallLog.Calls.NUMBER, CallLog.Calls.TYPE, CallLog.Calls.DATE},
                    null, null, CallLog.Calls.DATE + " DESC");
            if (cur != null && cur.moveToFirst()) {
                String num = cur.getString(0);
                int type = cur.getInt(1);
                long date = cur.getLong(2);
                if (num == null || num.isEmpty()) return null;
                if (System.currentTimeMillis() - date > 60000) return null;   // 이 통화가 아님
                String dir = type == CallLog.Calls.OUTGOING_TYPE ? "out"
                        : type == CallLog.Calls.MISSED_TYPE ? "missed" : "in";
                return new String[]{num, dir};
            }
        } catch (Exception ignored) {
        } finally {
            if (cur != null) cur.close();
        }
        return null;
    }

    /** 설치된 '다른' CallScreeningService 앱 패키지 목록(우리 제외) — 충돌 진단용. */
    public static String otherScreeningApps(Context c) {
        try {
            List<ResolveInfo> rs = c.getPackageManager()
                    .queryIntentServices(new Intent("android.telecom.CallScreeningService"), 0);
            List<String> pkgs = new ArrayList<>();
            for (ResolveInfo r : rs) {
                String p = r.serviceInfo != null ? r.serviceInfo.packageName : null;
                if (p != null && !p.equals(c.getPackageName()) && !pkgs.contains(p)) pkgs.add(p);
            }
            return TextUtils.join(",", pkgs);
        } catch (Exception e) {
            return "";
        }
    }
}
