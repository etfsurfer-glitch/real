# 콕집 iOS(App Store) 출시 계획 — Capacitor

안드로이드(TWA, `twa/`)와 별개. iOS 는 PWA(`dist/`)를 **Capacitor WKWebView** 로 감싼 네이티브 셸로 App Store 제출.

## 아키텍처
- `capacitor.config.ts`: `appId=com.koczip.app`, **`server.url=https://koczip.com`(원격 로드)**, `ios.appendUserAgent=KoczipApp/iOS`
- **원격 로드 이유(중요)**: 카카오맵 JS SDK 는 도메인 잠금(https://koczip.com)이라, 로컬 번들의 `capacitor://` origin 에선 타일이 403 으로 막혀 지도가 안 뜬다. iOS 는 `iosScheme=https` 를 예약어라 무시하므로 로컬로는 https origin 을 못 만든다 → 원격 로드가 사실상 필수. (부수 이점: 웹 변경이 앱 재제출 없이 즉시 반영. 단점: 오프라인 불가, 심사 4.2 웹래퍼 스크루티니↑ → 네이티브 푸시로 완화.)
- 웹앱은 UA 꼬리표로 iOS 앱 판별(`lib/appmode.ts` → `isInstalledApp()` true, 원격에서도 동작), API 는 `https://api.koczip.com`
- 스토어 링크: `generalStoreUrl()` 이 iOS Safari 면 App Store, 그 외 Play (게시 후 `STORE.ios` 채우면 자동 전환)

## 전제조건 (사용자 준비 — 병행)
- [ ] **Xcode 정식 설치**(App Store, ~7GB) — 현재 CommandLineTools 만 있음. `sudo xcode-select -s /Applications/Xcode.app` 후 `sudo xcodebuild -runFirstLaunch`
- [ ] **CocoaPods**: `sudo gem install cocoapods` (또는 `brew install cocoapods`)
- [ ] **Apple Developer Program 가입**($99/년, developer.apple.com) — 승인 1~2일 가능
- [ ] App Store Connect 에서 앱 레코드 생성(번들 ID `com.koczip.app` 등록)

## 스캐폴딩 (Xcode·CocoaPods 설치 후 실행)
```bash
cd frontend
npm run build            # dist 생성
npx cap add ios          # frontend/ios/ Xcode 프로젝트 생성(pod install 포함)
npx cap sync ios         # 웹 자산·플러그인 반영(웹 바뀔 때마다 build 후 실행)
npx cap open ios         # Xcode 로 열기 → 서명(팀 선택)·아이콘·스플래시·빌드·아카이브
```

## 심사 필수 대응
### 1) Sign in with Apple (지침 4.8) — **필수 가능성 높음**
카카오·구글 소셜로그인을 쓰므로 애플 로그인도 동등 제공해야 함.
- Apple Developer: **Service ID** 생성 + **Sign in with Apple key(.p8)** 발급
- Supabase(idkjsglzgvatwrjfpvnp) Auth → Apple provider 활성(Service ID·Team ID·Key ID·.p8)
- 프런트: `auth.tsx` 에 `loginApple()` 추가 + 카카오/구글 버튼 옆에 애플 버튼(iOS 에서 노출)
- redirect allowlist 에 운영 도메인 추가

### 2) 네이티브 푸시(APNs) — 웹래퍼 반려(4.2) 완화
- Apple: **APNs Auth Key(.p8)** 발급, Xcode Push Notifications capability 추가
- `@capacitor/push-notifications` 로 토큰 획득 → 서버(`push_subscriptions`)에 iOS 토큰 저장
- 서버 발송 경로에 APNs 분기 추가(현재 Web Push/VAPID) — 별도 작업

### 3) 웹래퍼로 보이지 않게 (4.2)
- 스플래시·앱아이콘·상태바 네이티브 처리(Capacitor 기본 제공)
- 최소한 네이티브 푸시로 "앱다움" 확보. 외부 링크는 앱 안에서 처리(SafariView 지양)

## App Store 자산
- [ ] 앱 아이콘 1024×1024 (알파 없음) — `store_icon.png` 재활용 가능(투명도 제거 필요)
- [ ] 스크린샷: 6.7"(1290×2796) 필수, 6.5"(1242×2688), iPad 12.9"(2048×2732) — 실기기/시뮬레이터 캡처
- [ ] 앱 설명(한국어), 키워드, 지원 URL(koczip.com), 개인정보처리방침 URL(koczip.com/privacy)
- [ ] **개인정보 보호 영양성분표**(App Privacy): 수집 항목(전화·이메일·위치 등) 선언 — koczip 로그/인증 기준
- [ ] 연령 등급, 카테고리(부동산/금융)

## 진행 상태
- [x] Capacitor 설치(core/ios/cli 8.5) + `capacitor.config.ts`
- [x] iOS 앱 판별(appmode) + 플랫폼별 스토어 링크(generalStoreUrl)
- [x] Xcode 26.6 설치·라이선스 동의, CocoaPods 1.17 설치
- [x] `npx cap add ios` — `frontend/ios/` Xcode 프로젝트 생성(SPM), 앱명 콕집·번들ID com.koczip.app
- [x] 앱 아이콘(흰 배경+파란 집, 1024 불투명) + 스플래시(라이트/다크) 생성·반영
- [x] `sudo xcodebuild -runFirstLaunch` + iOS 26.5 시뮬레이터 런타임 설치
- [x] **시뮬레이터 빌드·구동 성공**(iPhone 17 Pro Max) — 웹 정상 로드 확인
- [x] 인앱브라우저 게이트 예외 처리(설치형 앱은 InAppBrowserBanner 미표시 — WKWebView 오판 수정)
- [x] **카카오맵 정상화** — `server.url=https://koczip.com` 원격 로드로 origin 을 https 로(로컬 capacitor:// 는 타일 403). 시뮬레이터에서 홈·급매지도 렌더 확인
- [x] Sign in with Apple 프런트(loginApple·AppleLoginButton, 주요 로그인 surface 삽입) — `APPLE_LOGIN_ENABLED=false`로 대기
- [ ] Apple Developer 계정 → Xcode 서명(팀) → 아카이브 → App Store Connect 제출
- [ ] Supabase Apple provider 설정 → `APPLE_LOGIN_ENABLED=true`
- [ ] APNs 네이티브 푸시(@capacitor/push-notifications + 서버 APNs 분기)
- [ ] 스크린샷·개인정보표·앱설명·제출

## 재현: 시뮬레이터 구동
```bash
export PATH="/opt/homebrew/bin:$PATH"; cd frontend
npm run build && npx cap sync ios
cd ios/App && xcodebuild -project App.xcodeproj -scheme App -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro Max' -configuration Debug \
  -derivedDataPath build CODE_SIGNING_ALLOWED=NO build
xcrun simctl boot "iPhone 17 Pro Max"; open -a Simulator
xcrun simctl install "iPhone 17 Pro Max" build/Build/Products/Debug-iphonesimulator/App.app
xcrun simctl launch "iPhone 17 Pro Max" com.koczip.app
```
