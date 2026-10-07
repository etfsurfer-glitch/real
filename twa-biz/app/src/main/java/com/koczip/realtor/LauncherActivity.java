/*
 * Copyright 2020 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.koczip.realtor;

import android.app.role.RoleManager;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;

import com.koczip.realtor.call.CallSetupActivity;


public class LauncherActivity
        extends com.google.androidbrowserhelper.trusted.LauncherActivity {

    /** 발신자확인 미설정이고 '나중에'로 넘어온 게 아니면 TWA를 바로 띄우지 않는다(설정화면 먼저).
     *  베이스 클래스가 onCreate에서 이 값을 보고 TWA 실행 여부를 정하므로, 여기서 막아야
     *  TWA가 설정화면을 덮는 경쟁이 없다. */
    @Override
    protected boolean shouldLaunchImmediately() {
        if (!getIntent().getBooleanExtra("skip_call_setup", false) && needsCallSetup()) return false;
        return super.shouldLaunchImmediately();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // 앱은 곧바로 웹(/biz)으로 진입한다. 이미 콕집 회원(웹 로그인)이면 라운지가 바로 열리므로
        // 앱에서 전화번호 인증을 다시 강요하지 않는다. 통화 고객알림은 라운지 안에서 '원터치'로
        // 켜며(웹 세션 재사용 → koczip://call-enable 토큰 핸드오프), 그때만 발신자확인 역할을 요청한다.
        super.onCreate(savedInstanceState);   // shouldLaunchImmediately()가 false면 TWA 안 뜸
        try { com.koczip.realtor.call.CallDiag.flush(this); } catch (Exception ignored) { }  // 밀린 감지 진단 업로드
        // Setting an orientation crashes the app due to the transparent background on Android 8.0
        // Oreo and below. We only set the orientation on Oreo and above. This only affects the
        // splash screen and Chrome will still respect the orientation.
        // See https://github.com/GoogleChromeLabs/bubblewrap/issues/496 for details.
        if (Build.VERSION.SDK_INT > Build.VERSION_CODES.O) {
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_USER_PORTRAIT);
        } else {
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
        }
        // 발신자확인 미설정이면 설정 화면으로 보내고 이 액티비티는 종료(TWA는 위에서 안 띄웠음).
        // 설정을 마치면 CallSetupActivity.goTwa()가 LauncherActivity(skip)로 TWA를 띄운다.
        if (savedInstanceState == null
                && !getIntent().getBooleanExtra("skip_call_setup", false)
                && needsCallSetup()) {
            startActivity(new Intent(this, CallSetupActivity.class));
            finish();
        }
    }

    /** 통화 고객알림 설정 재유도가 필요한가 — **통화감지를 켠 적 있는(토큰 보유) 사용자만** 대상.
     *  신규 설치자는 무조건 웹(/biz)으로 바로 진입한다(로그인만으로 시작 — 2026-09-04 수정:
     *  이전엔 역할 미보유 전원을 설정화면으로 보내 첫 실행이 번호인증으로 막혔음).
     *  재유도 사유: ①켰었는데 역할이 풀림 ②배터리 최적화 예외 풀림(삼성이 주기적으로 되돌림)
     *  ③통화기록 권한 회수. */
    private boolean needsCallSetup() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false;
        try {
            if (com.koczip.realtor.call.CallPrefs.token(this) == null) return false;   // 켠 적 없음 → 방해 금지
            RoleManager rm = getSystemService(RoleManager.class);
            if (rm == null || !rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) return false;
            if (!rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) return true;   // 켰었는데 역할 풀림
            android.os.PowerManager pm = getSystemService(android.os.PowerManager.class);
            if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) return true;
            // 통화기록 권한 미허용이면 재요청(삼성 등 스크리닝 미동작 기기서 수신번호 취득에 필요)
            if (checkSelfPermission(android.Manifest.permission.READ_CALL_LOG)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED) return true;
            return false;
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    protected Uri getLaunchingUrl() {
        // Get the original launch Url.
        Uri uri = super.getLaunchingUrl();

        

        return uri;
    }
}
