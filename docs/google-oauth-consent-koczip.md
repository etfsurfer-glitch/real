# Google 로그인 동의화면을 "콕집"으로 — 설정 가이드 (방법 B)

## 목표
Google 로그인 시 보이는 화면을 콕집 브랜드로 다듬는다.
- **앱 이름** = "콕집" (현재는 비어있거나 기본값)
- **로고** = 콕집 로고 (동의화면에 표시)
- **지원 이메일/도메인** = koczip.com

> ⚠️ 참고: "to continue to **idkjsglzgvatwrjfpvnp.supabase.co**" 의 **도메인 텍스트 자체는 방법 B로는 바뀌지 않습니다**(그건 OAuth redirect 도메인이라 Supabase 커스텀 도메인=방법 A 필요). 방법 B는 **앱 이름·로고·신뢰도**를 콕집으로 만들어, 화면이 "콕집 로고 + 콕집 앱 이름"으로 보이게 합니다. 사용자 체감 브랜딩이 크게 올라갑니다.

---

## 사전 준비
- Google 계정: **콕집 OAuth 클라이언트를 만든 그 Google 계정**으로 로그인 (Supabase에서 Google provider 설정할 때 쓴 계정)
- 콕집 로고 PNG: 120×120px 이상 정사각형 권장 (`frontend/public/logo.svg` → PNG 변환본 또는 `twa/store_icon.png` 활용)

---

## 단계

### 1. Google Cloud Console 접속
https://console.cloud.google.com/ → 좌상단 프로젝트 선택에서 **콕집 OAuth 클라이언트가 속한 프로젝트** 선택.

### 2. OAuth 동의화면(OAuth consent screen) 이동
좌측 메뉴 ☰ → **APIs & Services → OAuth consent screen**
(또는 직접: https://console.cloud.google.com/apis/credentials/consent )

### 3. 앱 정보 편집 (Edit App)
**App information** 섹션:
- **App name**: `콕집` (또는 `콕집 - 부동산 매물·실거래 분석`)
- **User support email**: `etfsurfer@gmail.com` (또는 운영 이메일)
- **App logo**: 콕집 로고 PNG 업로드
  - 단, 로고를 올리면 Google **브랜드 인증(verification)** 이 필요할 수 있음 → 인증 전엔 로고가 안 보일 수 있으니, 급하면 로고는 생략하고 **App name만** 먼저 설정해도 됨.

### 4. 앱 도메인 (App domain) — 신뢰도·표시 개선
**App domain** 섹션:
- **Application home page**: `https://koczip.com`
- **Application privacy policy link**: `https://koczip.com/privacy`
- **Application terms of service link**: `https://koczip.com/terms` (있으면)
- **Authorized domains**: `koczip.com` 추가 (그리고 `supabase.co` 가 이미 있으면 유지)

### 5. 저장 → (선택) 게시 상태
- **Publishing status**가 "Testing"이면 → **Publish app**(프로덕션) 으로 전환해야 일반 사용자에게 정상 노출.
- "In production"이면 그대로 OK.

---

## 검증
- 새 시크릿창에서 koczip.com → 구글 로그인 클릭
- 동의화면 상단에 **"콕집"** 앱 이름과 (인증됐다면) **콕집 로고**가 표시되는지 확인.
- "to continue to ..." 의 도메인 부분은 그대로 supabase.co (방법 B 한계).

---

## 코드 변경
**없음.** 전부 Google Cloud Console 설정. 콕집 앱 코드(redirect URL 등)는 그대로 둔다.

## 더 완전한 브랜딩을 원하면 (나중에)
방법 A — Supabase 커스텀 도메인(`auth.koczip.com`, 유료 $10/월) → "to continue to **koczip.com**" 까지 바뀜. 그때 redirect URL 코드 반영은 별도 진행.
