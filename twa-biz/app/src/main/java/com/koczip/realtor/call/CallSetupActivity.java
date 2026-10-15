package com.koczip.realtor.call;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.role.RoleManager;
import android.content.Intent;
import android.provider.Settings;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

/** 통화 고객알림 온보딩 — ① 전화번호 OTP 로그인 ② 발신자확인 역할 ③ 알림 권한.
 *  프로그램 UI(XML 없음) — 사이드카 최소 침습. 완료/건너뛰기 후 TWA(LauncherActivity)로. */
public class CallSetupActivity extends Activity {
    private static final int REQ_ROLE = 71;
    private static final int REQ_NOTI = 72;
    private static final int REQ_OVERLAY = 73;
    private static final int REQ_BATTERY = 74;
    private static final int REQ_DIAG = 75;

    private LinearLayout root;
    private EditText phoneIn, codeIn;
    private Button primaryBtn;
    private TextView status;
    private String phase = "phone";   // phone → code → role → done

    private LinearLayout diagBox;     // 설정 점검 패널
    private Row serverRow;            // 서버 연결(비동기 갱신)

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        buildUi();
        // 웹(라운지)에서 '전화 알림 켜기' → koczip://call-enable?t=<네이티브토큰> 으로 넘어온 경우:
        // 웹 로그인 세션으로 이미 발급된 토큰이 있으니 OTP를 건너뛰고 바로 역할 요청으로.
        android.net.Uri data = getIntent() != null ? getIntent().getData() : null;

        // 설정만 보기 — 앱 바로가기(홈 아이콘 길게 누르기)·koczip://call-setup 으로 들어오면
        // 로그인·번호인증 없이 '발신자 확인' 권한 안내와 요청 화면을 바로 연다.
        // 번호인증은 알림 내용을 서버에서 받아오기 위한 것이라, 권한 허용 자체와는 무관하다.
        // (2026-10-05: Play 심사자가 로그인에 막혀 이 화면에 도달하지 못해 권한 요청 미노출로
        //  리젝됨. 로그인 없이도 핵심 기능과 권한 프롬프트를 확인할 수 있어야 한다.)
        boolean setupOnly = (getIntent() != null && getIntent().getBooleanExtra("setup_only", false))
                || (data != null && "koczip".equals(data.getScheme())
                    && "call-setup".equals(data.getHost()));
        if (setupOnly) {
            phase = "role"; render();
            return;
        }

        if (data != null && "koczip".equals(data.getScheme())) {
            String t = data.getQueryParameter("t");
            if (t != null && !t.isEmpty()) {
                CallPrefs.setToken(this, t);
                phase = "role"; render();
                requestRole();   // 인증 UI 없이 바로 발신자확인 역할 요청
                return;
            }
        }
        // 기본 진입은 'role' — 번호인증은 알림에 **고객 이름**을 채우기 위한 것이고, 발신자 확인
        // 권한 자체와는 무관하다. 그래서 첫 실행 온보딩도 로그인을 요구하지 않고 바로 기능 설명 +
        // 권한 안내로 들어간다(번호인증은 아래 '내 폰 설정 점검'의 '로그인' 줄에서 선택적으로).
        phase = "role"; render();
        if (CallPrefs.token(this) != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // 발신자확인 역할이 이미 있으면(배터리 예외만 다시 요청하는 재실행 등) 역할 화면을
            // 거치지 않고 곧바로 다음 단계(알림·오버레이·배터리)로 흘려보낸다.
            RoleManager rm = getSystemService(RoleManager.class);
            if (rm != null && rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)
                    && rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
                afterRole();
            }
        }
    }

    private void buildUi() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);
        int p = dp(24);
        root.setPadding(p, dp(48), p, p);

        TextView title = new TextView(this);
        title.setText("📞 전화 고객알림");
        title.setTextSize(24); title.setTypeface(null, Typeface.BOLD);
        title.setTextColor(Color.parseColor("#16202E"));
        root.addView(title);

        TextView desc = new TextView(this);
        desc.setText("고객 전화가 오면, 받기 전에 누구인지·무슨 문의였는지 화면에 띄워드려요.\n\n" +
                "· 사무실 070 전화도 휴대폰 착신전환만 해두면 똑같이 알려드립니다\n" +
                "· 통화 내용·녹음은 수집하지 않습니다(번호·시각·통화시간만)");
        desc.setTextSize(14); desc.setTextColor(Color.parseColor("#6B7280"));
        desc.setPadding(0, dp(12), 0, dp(24));
        root.addView(desc);

        phoneIn = input("휴대폰 번호 (라운지 사무소 연결 번호)", InputType.TYPE_CLASS_PHONE);
        codeIn = input("인증번호 6자리", InputType.TYPE_CLASS_NUMBER);
        codeIn.setVisibility(View.GONE);
        root.addView(phoneIn); root.addView(codeIn);

        status = new TextView(this);
        status.setTextSize(13); status.setTextColor(Color.parseColor("#1268D3"));
        status.setPadding(0, dp(8), 0, dp(8));
        root.addView(status);

        primaryBtn = new Button(this);
        stylePrimary(primaryBtn);
        primaryBtn.setOnClickListener(v -> onPrimary());
        root.addView(primaryBtn);

        // 핵심 기능이 어떻게 보이는지 전화를 기다리지 않고 바로 확인 — 예시 데이터로 실제와
        // 똑같은 발신자 카드를 띄운다. 로그인·통화 없이 기능을 점검할 수 있는 유일한 경로여서
        // Play 심사자의 확인 수단도 된다(2026-10 반려: '인앱 환경에서 핵심 기능 확인 불가').
        Button preview = new Button(this);
        preview.setText("발신자 카드 미리보기 (예시)");
        preview.setBackgroundColor(Color.parseColor("#EEF3FB"));
        preview.setTextColor(Color.parseColor("#1268D3"));
        preview.setAllCaps(false);
        LinearLayout.LayoutParams pvLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        pvLp.topMargin = dp(10);
        preview.setLayoutParams(pvLp);
        preview.setOnClickListener(v -> previewCard());
        root.addView(preview);

        Button skip = new Button(this);
        skip.setText("나중에 할게요");
        skip.setBackgroundColor(Color.TRANSPARENT);
        skip.setTextColor(Color.parseColor("#6B7280"));
        skip.setOnClickListener(v -> { CallPrefs.dismissOnboarding(this); goTwa(); });
        root.addView(skip);

        buildDiagnostics();

        android.widget.ScrollView sv = new android.widget.ScrollView(this);
        sv.addView(root);
        setContentView(sv);
        render();
        refreshDiagnostics();
    }

    private void render() {
        switch (phase) {
            case "phone":
                primaryBtn.setText("인증번호 받기"); break;
            case "code":
                codeIn.setVisibility(View.VISIBLE);
                primaryBtn.setText("확인"); break;
            case "role":
                phoneIn.setVisibility(View.GONE); codeIn.setVisibility(View.GONE);
                status.setText("걸려온 번호가 어느 고객인지 통화 화면에 바로 띄워 드립니다.\n"
                        + "이 기능에는 '발신자 확인' 역할과 통화·통화기록 권한이 필요합니다.\n"
                        + "번호는 기기 안에서 대조하며, 통화 내용은 읽지 않습니다.");
                primaryBtn.setText("전화 알림 켜기 (발신자 확인 설정)"); break;
            case "done":
                status.setText("설정 완료 — 이제 고객 전화가 오면 카드가 떠요.");
                primaryBtn.setText("콕집 중개사 시작하기"); break;
        }
    }

    private void onPrimary() {
        switch (phase) {
            case "phone": {
                String phone = phoneIn.getText().toString().replaceAll("[^0-9]", "");
                if (phone.length() < 10) { toast("휴대폰 번호를 확인해주세요"); return; }
                status.setText("인증번호 발송 중…");
                KoczipApi.sendOtp(phone, (r, e) -> {
                    if (r != null && r.optBoolean("ok", false)) {
                        phase = "code"; status.setText("문자로 온 인증번호를 입력해주세요"); render();
                    } else {
                        status.setText(errMsg(r, e));
                    }
                });
                break;
            }
            case "code": {
                String phone = phoneIn.getText().toString().replaceAll("[^0-9]", "");
                String code = codeIn.getText().toString().trim();
                status.setText("확인 중…");
                KoczipApi.verifyOtp(phone, code, (r, e) -> {
                    if (r != null && r.optString("token", null) != null) {
                        CallPrefs.setToken(this, r.optString("token"));
                        phase = "role"; render();
                        // 점검표를 즉시 다시 그린다 — 안 그리면 방금 로그인했는데도 '로그인' 줄이
                        // '휴대폰 번호 인증이 필요해요'로 남아 있어, 실패한 줄 안다('다시 점검'을
                        // 눌러야 바뀐다). 서버 연결 줄도 이때 비로소 확인된다.
                        refreshDiagnostics();
                    } else {
                        status.setText(errMsg(r, e));
                    }
                });
                break;
            }
            case "role": requestRole(); break;
            case "done": goTwa(); break;
        }
    }

    /** 예시 데이터로 실제와 동일한 발신자 카드를 띄운다 — 오버레이(권한 있으면) + 알림.
     *  둘 다 막혀 있으면 화면 안 대화상자로라도 보여줘, 어떤 상태에서도 기능을 확인할 수 있다. */
    private void previewCard() {
        final String phone = "01012345678";
        JSONObject info = new JSONObject();
        try {
            info.put("customer", new JSONObject()
                    .put("name", "김민수")
                    .put("memo", "래미안 32평 매수 문의"));
            info.put("leads", new org.json.JSONArray().put(new JSONObject()
                    .put("message", "래미안 32평 매수 문의 (3일 전)")));
        } catch (Exception ignored) { }

        boolean ov = CallOverlay.canShow(this);
        if (ov) CallOverlay.show(this, phone, info);
        CallNotifier.showCard(this, phone, info);

        if (!ov && !notiGranted()) {
            new android.app.AlertDialog.Builder(this)
                    .setTitle("📞 김민수님 전화")
                    .setMessage("010-1234-5678\n최근문의: 래미안 32평 매수 문의 (3일 전)\n\n"
                            + "실제로는 전화가 올 때 통화 화면 위에 이 카드가 떠서, 받기 전에 "
                            + "누구인지 알 수 있습니다.\n\n'전화 알림 켜기'로 권한을 허용하면 "
                            + "통화 화면 위/알림창에 그대로 표시됩니다.")
                    .setPositiveButton("확인", null)
                    .show();
            status.setText("예시 카드를 화면에 띄웠습니다. 권한을 허용하면 통화 화면 위에 떠요.");
            return;
        }
        status.setText(ov
                ? "예시 카드를 통화 화면 위에 띄웠습니다(25초 후 자동 사라짐). 알림창에도 남아 있어요."
                : "예시 카드를 알림창에 띄웠습니다. '다른 앱 위에 표시'를 허용하면 통화 화면 위에도 떠요.");
    }

    private void requestRole() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            RoleManager rm = getSystemService(RoleManager.class);
            if (rm != null && rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
                if (rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) { afterRole(); return; }
                startActivityForResult(rm.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), REQ_ROLE);
                return;
            }
        }
        toast("이 기기(Android 10 미만)는 발신자 확인을 지원하지 않아요");
        afterRole();
    }

    private void afterRole() {
        // 알림 권한(Android 13+)
        // 통화·통화기록 권한: READ_PHONE_STATE(상태) + READ_CALL_LOG(스크리닝 미동작 기기서 수신번호),
        // + 알림(13+). 하나라도 미허용이면 한 번에 요청.
        java.util.List<String> need = new java.util.ArrayList<>();
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                        != android.content.pm.PackageManager.PERMISSION_GRANTED)
            need.add(android.Manifest.permission.POST_NOTIFICATIONS);
        if (checkSelfPermission(android.Manifest.permission.READ_PHONE_STATE)
                != android.content.pm.PackageManager.PERMISSION_GRANTED)
            need.add(android.Manifest.permission.READ_PHONE_STATE);
        if (checkSelfPermission(android.Manifest.permission.READ_CALL_LOG)
                != android.content.pm.PackageManager.PERMISSION_GRANTED)
            need.add(android.Manifest.permission.READ_CALL_LOG);
        if (!need.isEmpty()) {
            showDisclosure(need);   // Play 정책: 시스템 권한 프롬프트 전 명시적 공개+동의(2026-09-04)
            return;
        }
        afterPerms();
    }

    /** Prominent disclosure — READ_CALL_LOG 등 민감 권한 요청 직전, 어떤 데이터를 왜·어떻게
     *  쓰는지 앱 UI로 공개하고 긍정 동의를 받은 뒤에만 시스템 프롬프트를 띄운다(Play 정책). */
    private void showDisclosure(java.util.List<String> need) {
        StringBuilder msg = new StringBuilder("전화 고객알림을 켜려면 아래 접근이 필요합니다.\n\n");
        if (need.contains(android.Manifest.permission.READ_PHONE_STATE))
            msg.append("• 전화 상태: 전화가 오고 끊기는 것을 감지합니다.\n");
        if (need.contains(android.Manifest.permission.READ_CALL_LOG))
            msg.append("• 통화 기록: 일부 기기에서 수신 번호 확인을 위해 벨이 울릴 때 최근 수신 번호 1건만 읽습니다. "
                    + "통화 기록을 열람·저장하거나 외부로 전송하지 않습니다.\n");
        if (need.contains(android.Manifest.permission.POST_NOTIFICATIONS))
            msg.append("• 알림: 발신자 정보 카드를 표시합니다.\n");
        msg.append("\n수신 번호는 이 기기에서 회원님의 고객 정보와 대조하는 데만 사용됩니다.");
        new android.app.AlertDialog.Builder(this)
                .setTitle("접근 권한 안내")
                .setMessage(msg.toString())
                .setPositiveButton("동의하고 계속", (d, w) ->
                        requestPermissions(need.toArray(new String[0]), REQ_NOTI))
                .setNegativeButton("취소", (d, w) -> afterPerms())
                .setCancelable(false)
                .show();
    }

    /** 발신자 카드를 통화 화면 위에 띄우려면 '다른 앱 위에 표시' 권한이 필요하다
     *  (헤드업 알림만으론 통화 알림에 가려 안 보임 — 실측 확인). */
    private void afterPerms() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            try {
                status.setText("거의 다 됐어요! 전화 화면 위에 고객 카드를 띄우도록 허용해주세요.");
                startActivityForResult(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        android.net.Uri.parse("package:" + getPackageName())), REQ_OVERLAY);
                return;
            } catch (Exception ignored) { }
        }
        requestBatteryExemption();
    }

    /** 배터리 최적화 예외 — 백그라운드에서 통화감지가 죽지 않게. 설정을 헤맬 필요 없이
     *  시스템 팝업에서 '허용' 한 번만 누르면 된다(완전 자동은 안드로이드가 금지). 거부해도 진행. */
    @SuppressLint("BatteryLife")
    private void requestBatteryExemption() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                android.os.PowerManager pm = getSystemService(android.os.PowerManager.class);
                if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
                    status.setText("마지막! 전화가 언제 와도 놓치지 않도록 '허용'을 눌러주세요.");
                    startActivityForResult(new Intent(
                            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                            android.net.Uri.parse("package:" + getPackageName())), REQ_BATTERY);
                    return;
                }
            } catch (Exception ignored) { }
        }
        phase = "done"; render();
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_ROLE) afterRole();               // 거부해도 진행(알림만 못 띄움을 감수)
        else if (req == REQ_OVERLAY) requestBatteryExemption();
        else if (req == REQ_BATTERY) { phase = "done"; render(); }
        else if (req == REQ_DIAG) { /* 점검에서 개별 설정만 열었을 때는 흐름을 잇지 않음 */ }
        refreshDiagnostics();
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        super.onRequestPermissionsResult(req, perms, res);
        if (req == REQ_NOTI) afterPerms();
        refreshDiagnostics();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshDiagnostics();   // 설정 화면에서 돌아오면 상태 즉시 반영
        CallDiag.flush(this);   // 밀린 감지 진단을 서버로 올림(앱 열 때마다)
    }

    private void goTwa() {
        // 이 화면을 한 번 끝까지 본 사람에겐 다시 띄우지 않는다. '나중에 할게요'뿐 아니라
        // 설정을 마치고 나가는 경로에서도 표시해야, 번호인증을 안 한 사용자가 매 실행마다
        // 설정 화면을 다시 보는 일이 없다(온보딩 조건이 토큰 유무라서 생기던 문제).
        CallPrefs.dismissOnboarding(this);
        // 설정 화면은 TWA 위에 얹혀 있으므로, 닫으면 뒤의 웹(라운지)이 그대로 드러난다.
        // (TWA가 뒤에 없는 예외 상황이면 홈으로 — 무해)
        if (isTaskRoot()) {
            Intent i = new Intent(this, com.koczip.realtor.LauncherActivity.class);
            i.putExtra("skip_call_setup", true);
            startActivity(i);
        }
        finish();
    }

    // ── 설정 점검(진단) ──
    /** 한 점검 항목: 아이콘 + 상세를 비동기로 갱신할 수 있게 참조 보관. */
    private static class Row { LinearLayout view; TextView icon; TextView detail; }

    private void buildDiagnostics() {
        View sep = new View(this);
        LinearLayout.LayoutParams sepLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(1));
        sepLp.topMargin = dp(28); sepLp.bottomMargin = dp(16);
        sep.setLayoutParams(sepLp);
        sep.setBackgroundColor(Color.parseColor("#E5E7EB"));
        root.addView(sep);

        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        TextView h = new TextView(this);
        h.setText("🔍 내 폰 설정 점검");
        h.setTextSize(17); h.setTypeface(null, Typeface.BOLD);
        h.setTextColor(Color.parseColor("#16202E"));
        h.setLayoutParams(new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        TextView recheck = new TextView(this);
        recheck.setText("다시 점검 ⟳");
        recheck.setTextColor(Color.parseColor("#1268D3"));
        recheck.setTextSize(13);
        recheck.setPadding(dp(8), dp(6), dp(4), dp(6));
        recheck.setOnClickListener(v -> refreshDiagnostics());
        head.addView(h); head.addView(recheck);
        root.addView(head);

        TextView hint = new TextView(this);
        hint.setText("문제 항목(✗)을 누르면 바로 고칠 수 있어요.");
        hint.setTextSize(12.5f); hint.setTextColor(Color.parseColor("#6B7280"));
        hint.setPadding(0, dp(2), 0, dp(10));
        root.addView(hint);

        diagBox = new LinearLayout(this);
        diagBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(diagBox);
    }

    /** 모든 항목을 다시 평가해 표시. 로컬 항목은 즉시, 서버 연결만 비동기로 갱신. */
    private void refreshDiagnostics() {
        if (diagBox == null) return;
        diagBox.removeAllViews();

        boolean login = CallPrefs.token(this) != null;
        addRow("로그인 (사무소 연결)", login,
                login ? "완료" : "휴대폰 번호 인증이 필요해요",
                () -> { phase = "phone"; phoneIn.setVisibility(View.VISIBLE);
                        codeIn.setVisibility(View.GONE); render(); phoneIn.requestFocus(); });

        boolean role = roleHeld();
        addRow("발신자 확인 (수신번호 취득)", role,
                role ? "허용됨" : "미허용 — 이게 없으면 전화 감지 자체가 안 돼요",
                this::requestRole);

        boolean noti = notiGranted();
        addRow("알림 표시", noti,
                noti ? "허용됨" : "미허용 — 통화 후 카드 알림이 안 떠요",
                this::openNotiSettings);

        boolean overlay = Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this);
        addRow("다른 앱 위에 표시 (통화 중 카드)", overlay,
                overlay ? "허용됨" : "미허용 — 벨 울릴 때 발신자 카드가 안 떠요",
                this::openOverlaySettings);

        boolean battery = batteryExempt();
        addRow("배터리 최적화 예외", battery,
                battery ? "예외됨"
                        : "제한됨 — 통화 순간 인터넷이 막혀 등록 고객이 '새 번호'로 떠요",
                this::requestBatteryExemption);

        serverRow = addRow("서버 연결", null, "확인 중…", null);
        checkServer(serverRow);

        addAdvisory("⚠ 삼성 '앱 절전(딥슬립)' 목록 제외는 앱에서 못 바꿔요. "
                + "설정 → 배터리 → 백그라운드 사용 제한에서 '콕집 중개사'가 절전 목록에 없는지 확인하세요.");
    }

    private Row addRow(String label, Boolean ok, String detailText, Runnable fix) {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setPadding(0, dp(11), 0, dp(11));
        r.setGravity(Gravity.CENTER_VERTICAL);

        TextView icon = new TextView(this);
        icon.setTextSize(18); icon.setTypeface(null, Typeface.BOLD);
        icon.setWidth(dp(30));
        setIcon(icon, ok);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setLayoutParams(new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        TextView lb = new TextView(this);
        lb.setText(label); lb.setTextSize(15); lb.setTypeface(null, Typeface.BOLD);
        lb.setTextColor(Color.parseColor("#16202E"));
        TextView dt = new TextView(this);
        dt.setText(detailText); dt.setTextSize(12.5f);
        dt.setTextColor(detailColor(ok));
        dt.setPadding(0, dp(2), 0, 0);
        col.addView(lb); col.addView(dt);

        r.addView(icon); r.addView(col);

        if (fix != null && ok != Boolean.TRUE) {
            TextView act = new TextView(this);
            act.setText("고치기 ›");
            act.setTextColor(Color.parseColor("#1268D3")); act.setTextSize(13);
            act.setTypeface(null, Typeface.BOLD);
            act.setPadding(dp(8), 0, 0, 0);
            r.addView(act);
            r.setOnClickListener(v -> fix.run());
        }
        diagBox.addView(r);

        View div = new View(this);
        LinearLayout.LayoutParams dl = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(1));
        div.setLayoutParams(dl);
        div.setBackgroundColor(Color.parseColor("#F1F3F5"));
        diagBox.addView(div);

        Row row = new Row(); row.view = r; row.icon = icon; row.detail = dt;
        return row;
    }

    private void addAdvisory(String text) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(12.5f); t.setTextColor(Color.parseColor("#8A6D3B"));
        t.setBackgroundColor(Color.parseColor("#FCF3E3"));
        int p = dp(12);
        t.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(14);
        t.setLayoutParams(lp);
        diagBox.addView(t);
    }

    /** 서버에 실제로 닿는지 + 토큰이 유효한지 확인(읽기 전용 call-lookup, 더미번호). */
    private void checkServer(final Row row) {
        if (CallPrefs.token(this) == null) { setRow(row, Boolean.FALSE, "로그인 후 확인돼요"); return; }
        KoczipApi.callLookup(this, "01000000000", (res, err) -> {
            if (row != serverRow) return;   // 그 사이 다시 점검했으면 무시
            if (res != null) {
                int st = res.optInt("_status", 0);
                if (st == 200) setRow(row, Boolean.TRUE, "정상 (서버 응답 OK)");
                else if (st == 401 || st == 403)
                    setRow(row, Boolean.FALSE, "로그인 만료 — 다시 로그인하세요");
                else setRow(row, null, "서버 응답 코드 " + st);
            } else {
                setRow(row, Boolean.FALSE,
                        "인터넷에 못 닿았어요 — 통화 순간 차단됐을 수 있어요(배터리 예외 확인)");
            }
        });
    }

    private void setRow(Row row, Boolean ok, String detail) {
        if (row == null) return;
        setIcon(row.icon, ok);
        row.detail.setText(detail);
        row.detail.setTextColor(detailColor(ok));
    }

    private void setIcon(TextView icon, Boolean ok) {
        if (ok == null) { icon.setText("…"); icon.setTextColor(Color.parseColor("#9CA3AF")); }
        else if (ok) { icon.setText("✓"); icon.setTextColor(Color.parseColor("#22A06B")); }
        else { icon.setText("✗"); icon.setTextColor(Color.parseColor("#E5484D")); }
    }

    private int detailColor(Boolean ok) {
        if (ok == null) return Color.parseColor("#6B7280");
        return ok ? Color.parseColor("#22A06B") : Color.parseColor("#C0362C");
    }

    private boolean roleHeld() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false;
        RoleManager rm = getSystemService(RoleManager.class);
        return rm != null && rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)
                && rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING);
    }

    private boolean notiGranted() {
        if (Build.VERSION.SDK_INT < 33) return true;   // 그 이하는 별도 권한 불필요
        return checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    private boolean batteryExempt() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true;
        android.os.PowerManager pm = getSystemService(android.os.PowerManager.class);
        return pm != null && pm.isIgnoringBatteryOptimizations(getPackageName());
    }

    private void openNotiSettings() {
        if (Build.VERSION.SDK_INT >= 33 && !notiGranted()) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTI);
            return;
        }
        try {
            Intent i = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
            startActivityForResult(i, REQ_DIAG);
        } catch (Exception e) { openAppDetails(); }
    }

    private void openOverlaySettings() {
        try {
            startActivityForResult(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    android.net.Uri.parse("package:" + getPackageName())), REQ_OVERLAY);
        } catch (Exception e) { openAppDetails(); }
    }

    private void openAppDetails() {
        try {
            startActivityForResult(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    android.net.Uri.parse("package:" + getPackageName())), REQ_DIAG);
        } catch (Exception ignored) { }
    }

    // ── UI 헬퍼 ──
    private EditText input(String hint, int type) {
        EditText e = new EditText(this);
        e.setHint(hint); e.setInputType(type); e.setTextSize(16);
        e.setPadding(dp(12), dp(14), dp(12), dp(14));
        return e;
    }
    private void stylePrimary(Button btn) {
        btn.setText("계속");
        btn.setTextColor(Color.WHITE);
        btn.setBackgroundColor(Color.parseColor("#1268D3"));
        btn.setPadding(0, dp(14), 0, dp(14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(8);
        btn.setLayoutParams(lp);
        btn.setGravity(Gravity.CENTER);
    }
    private String errMsg(org.json.JSONObject r, String e) {
        if (r != null) {
            Object d = r.opt("detail");
            if (d instanceof org.json.JSONObject) return ((org.json.JSONObject) d).optString("message", "오류");
            if (d instanceof String) return (String) d;
        }
        return e != null ? "네트워크 오류: " + e : "오류가 발생했어요";
    }
    private void toast(String m) { Toast.makeText(this, m, Toast.LENGTH_SHORT).show(); }
    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
