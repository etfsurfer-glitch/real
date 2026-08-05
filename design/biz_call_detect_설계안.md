# 콕집 중개사앱 통화감지 — 기술 설계안

2026-07-25 · 대상: 중개사앱(com.koczip.realtor, TWA 예정) · 참고 선례: 계약의 신(com.gyesin.official)

## 1. 목표 UX

| 시점 | 동작 |
|---|---|
| **전화 올 때** | 수신 번호를 즉시 감지 → 콕집 서버에서 번호 조회 → 수신화면 위에 카드 표시: "김OO님 · 래미안 32평 매수 문의(3일 전) · 상담리드 2건" |
| **통화 중** | 카드에서 한 번 탭 → 중개사앱 고객 화면으로 진입(메모·매물 연결) |
| **통화 후** | 통화 메타(번호·방향·시각·통화시간)를 서버에 기록 → 고객 타임라인에 "7/25 14:02 수신 4분 통화" 자동 축적 · 부재중이면 "부재중 → 콜백 필요" 리드 생성 |
| **웹/앱 어디서나** | 라운지·비즈앱 고객관리 화면과 계약캘린더에 통화 이력이 자연스럽게 합류(웹은 그대로, 데이터만 서버 경유) |

## 2. 아키텍처 — "TWA 유지 + 네이티브 사이드카"

```
┌─ Android APK (com.koczip.realtor) ─────────────────────────┐
│  TWA LauncherActivity ──────────► koczip.com/biz (기존 웹)  │
│  ┌─ 네이티브 사이드카(Kotlin) ─────────────────────────┐   │
│  │ CallScreeningService  ← 수신번호(전화 역할로 합법 취득)│   │
│  │ CallEventWorker       ← 통화 종료 감지·업로드         │   │
│  │ OverlayCard/알림      ← 수신 시 고객 카드 표시        │   │
│  │ NativeAuth(전화 OTP)  ← 알리고 OTP 재사용 경량 로그인 │   │
│  └───────────────┬───────────────────────────────────┘   │
└──────────────────┼───────────────────────────────────────┘
                   ▼ HTTPS (Bearer)
            api.koczip.com  /biz/call-lookup · /biz/call-events
                   ▼
        consultation_leads · biz_customers(신설) · 계약캘린더
```

**핵심 결정 3가지**

1) **TWA는 그대로 둔다.** 웹 셸(/biz)·라운지·캘린더는 이미 완성 — UI를 네이티브로 다시 만들지 않는다. 네이티브는 "전화 감지·카드 표시·이벤트 업로드"만 하는 사이드카.

2) **웹↔네이티브 직접 브리지를 만들지 않는다.** TWA는 JS 브리지가 없다. 대신 **서버를 허브로**: 네이티브가 서버에 쓰고, 웹은 서버에서 읽는다. 결합도 0, 웹 배포 흐름 무변.

3) **네이티브 인증은 전화번호 OTP 별도 발급.** TWA의 브라우저 세션(Supabase)은 네이티브가 못 읽는다. 이미 있는 알리고 SMS OTP + 라운지 전화매칭(realtor_members↔사무소, cell_phone 기반)을 재사용해 네이티브 전용 장수명 토큰을 1회 발급·보관(EncryptedSharedPreferences). 중개사는 앱 설치 후 "전화번호 인증 1회"만 하면 끝.

## 3. 전화 감지 방식 — 2단계 권한 전략 (심사 리스크 최소화)

### Phase 1 — CallScreeningService (구글 선언 심사 불필요) ★먼저 출시
- Android의 **전화 스크리닝 역할**(RoleManager `ROLE_CALL_SCREENING`)을 요청 — 사용자가 "콕집을 발신자 확인 앱으로" 승인하면 **READ_CALL_LOG 없이도 수신 번호가 합법적으로 들어온다**(후후·T전화가 쓰는 공식 경로).
- 수신 → `onScreenCall(details)` → 번호 → `/biz/call-lookup` → **헤드업 알림**으로 고객 카드(기본). "디스플레이 위에 표시" 권한을 켠 사용자에겐 계약의신식 **오버레이 카드**.
- 통화 종료는 `PHONE_STATE`(RINGING→OFFHOOK→IDLE) 전이로 감지해 방향·시각·통화시간 계산(번호는 스크리닝에서 이미 확보 — READ_CALL_LOG 불필요).
- 플레이 심사: 특수 선언 없음. 역할 요청 다이얼로그는 OS 표준이라 통과 무난.

### Phase 2 — READ_CALL_LOG (선언 심사) — 선택 확장
- 목적: **과거** 통화이력 일괄 동기화(설치 이전 고객 통화까지 타임라인 소급) + 발신 통화 기록.
- 구글 Permissions Declaration Form 제출 — 핵심기능 선언 문구(계약의신 선례 참조):
  > "본 앱은 공인중개사 전용 고객관리 앱으로, 핵심 기능인 '고객 통화 이력 관리'는 통화 기록 접근 없이는 제공될 수 없습니다. 앱 스토어 설명·첫 화면 모두 이 기능을 대표 기능으로 안내합니다."
- 반려 리스크 대비: Phase 1만으로도 실시간 감지·기록은 완성되므로 Phase 2는 승인되면 얹는 보너스.

## 4. 백엔드 API (local_api.py 추가분)

```
POST /biz/native-auth/otp        { phone }                → 알리고 SMS 발송(기존 모듈)
POST /biz/native-auth/verify     { phone, code }          → realtor_members 매칭 → 장수명 토큰(전용 테이블 biz_native_tokens, 회전 가능)

GET  /biz/call-lookup?phone=010...        (Bearer)
  ← { customer: {name, memo, last_contact}, leads: [{source, message, at}],
      listings: [단지·매물 요청], history: [최근 통화 3건] }
  · 매칭 소스: biz_customers.phone → consultation_leads.phone → (없으면) "신규 번호"
  · 응답 150ms 목표(번호 인덱스) — 벨 울리는 동안 떠야 함

POST /biz/call-events            (Bearer)
  { phone, direction: in|out|missed, started_at, duration_s }
  → biz_call_events 적재 + 부재중이면 consultation_leads(source='call_missed') 생성
  → 웹 고객관리·계약캘린더가 이 테이블을 읽어 타임라인 표시press
```

**신설 테이블 (reviews.sqlite — 라운지 계열과 동거)**
```sql
biz_customers(id, realtor_id, phone UNIQUE(realtor_id,phone), name, memo, created_at)
biz_call_events(id, realtor_id, phone, direction, started_at, duration_s, created_at)
biz_native_tokens(token PK, user_id, realtor_id, created_at, last_used_at)
```

## 5. 네이티브 구현 스케치 (Kotlin, 핵심만)

```kotlin
class KoczipCallScreening : CallScreeningService() {
    override fun onScreenCall(details: Call.Details) {
        respondToCall(details, CallResponse.Builder().build())  // 차단 안 함 — 통과
        if (details.callDirection != Call.Details.DIRECTION_INCOMING) return
        val phone = details.handle?.schemeSpecificPart ?: return
        scope.launch {
            val info = api.callLookup(phone) ?: return@launch   // 미가입 번호면 조용히
            CallCard.show(this@KoczipCallScreening, info)        // 헤드업 알림/오버레이
            CallSession.begin(phone)                             // 종료 시 call-events 업로드용
        }
    }
}
```
- 오버레이 카드: 이름·최근 문의·매물 2줄 + [고객 열기](딥링크 `https://koczip.com/biz/leads?phone=...` → TWA로 열림) + [통화 후 메모] 버튼.
- 실패는 전부 조용히(전화 UX를 절대 방해하지 않음) — 계약의신도 같은 원칙으로 보임.

## 6. 패키징
- 기존 TWA 패키징 계획을 **Android Studio 프로젝트로 승격**(Bubblewrap 산출물을 베이스로 모듈 추가). TWA Activity + 사이드카 서비스 동거, `assetlinks.json`은 기존 koczip.com 것 그대로.
- 배포 트랙: 내부테스트 → 비공개(현 일반앱과 동일 절차).

## 7. 컴플라이언스 (필수 선행)
- **개인정보처리방침 갱신**: 수집항목에 "통화 상대방 전화번호·통화 일시·통화 시간(내용/녹음 아님)" 명시, 목적=고객관리, 보관기간·삭제권.
- **중개사 약관 동의 게이트**(기존 TODO와 병합): 통화 기록 연동 최초 활성화 시 별도 동의 체크.
- 통화 **녹음은 범위 제외**(통신비밀보호 이슈·구글 정책 리스크 — 메타데이터만).
- 오버레이·전화역할·알림 권한은 전부 **옵트인 온보딩**(하나라도 거부해도 앱 나머지는 정상).

## 8. 마일스톤 (예상 공수)

| 단계 | 내용 | 공수 |
|---|---|---|
| M1 | 백엔드: native-auth·call-lookup·call-events + 테이블 + 웹 고객 타임라인 표시 | 2~3일 |
| M2 | 네이티브: TWA 프로젝트 승격 + CallScreening + 알림 카드 + OTP 로그인 | 4~5일 |
| M3 | 오버레이 카드·부재중 리드·캘린더 연계·온보딩 플로우 | 2~3일 |
| M4 | 내부테스트 → 심사 제출(Phase 1 권한은 선언 불필요) | 1주 대기 |
| (M5) | READ_CALL_LOG 선언 심사 + 과거 이력 동기화 | 승인 리스크 별도 |

**총 개발 약 2주 + 심사 대기.** M1은 앱 없이도 가치가 있음(웹 고객관리에 수동 통화메모 UI가 같은 테이블을 씀).

## 9. 인터넷전화(사무소 070) 지원 — 계약의신 방식 분석 반영

계약의신 FAQ 확인(2026-07-25): "SK·KT·LG-U+ 3사 인터넷전화 모두 연동구축, 통신사 교체 불필요"
+ "PC화면·핸드폰 액정에 누가 전화왔는지 식별" → **통신사 CTI(수신 이벤트 API) 연동** 방식으로 판단
(자체 070 발급형이면 통신사 무관이라 해당 FAQ가 성립하지 않음).

- **Phase 0(개발 ~0)**: 사무소 070 → 휴대폰 동시착신/착신전환 안내(통신사 부가서비스).
  착신된 수신은 일반 휴대폰 수신이므로 Phase 1 CallScreening이 그대로 커버. 온보딩 문서만.
- **Phase 3(중기)**: 통신사 인터넷전화 CTI 웹훅 → /biz/call-events 재사용.
  PC 스크린 팝은 기존 웹푸시(VAPID)로 순수 웹 구현 — 계약의신 대비 우리 강점.
  본체는 코드가 아니라 통신사별 제휴·사무소별 연동신청 절차 → 회원 통신사 분포 보고 1개사부터.

## 10. 리스크와 대응
- **역할 승인 UX 이탈**: "발신자 확인 앱으로 설정" 다이얼로그가 낯섦 → 온보딩에 계약의신처럼 1장짜리 설명 화면("전화 오면 고객정보가 뜹니다") 선행.
- **제조사 파편화**(삼성 통화앱 오버레이 z-order 등): 헤드업 알림을 기본값으로, 오버레이는 옵션.
- **듀얼심/업무폰**: 번호 정규화(+82→0) 후 매칭 — 라운지 전화매칭에서 이미 쓰는 정규화 재사용.
```
