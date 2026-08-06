// 전화 고객알림(통화감지) 켜기 — 웹 로그인 세션으로 네이티브 토큰을 발급받아(OTP 불필요)
// koczip://call-enable 커스텀 스킴으로 중개사앱 네이티브에 넘긴다(발신자확인 역할은 네이티브가 요청).
// 홈 카드(CallDetectCard)와 설정 화면(BizSettings)이 공유.
const API = import.meta.env.VITE_API_BASE;

export async function enableCallDetect(token: string | null): Promise<{ ok: boolean; error?: string }> {
  if (!API || !token) return { ok: false, error: "로그인이 필요해요." };
  try {
    const r = await fetch(`${API}/biz/native-auth/from-session`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` },
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.token) {
      return { ok: false, error: d?.detail?.message || "사무소 연결 확인이 필요해요." };
    }
    // Android intent:// URL — TWA/Chrome에서 커스텀 스킴보다 확실히 네이티브 앱을 띄운다.
    // (scheme=koczip 인텐트필터로 CallSetupActivity 가 받아 토큰 저장 + 발신자확인 역할 요청)
    const t = encodeURIComponent(d.token);
    window.location.href =
      `intent://call-enable?t=${t}#Intent;scheme=koczip;package=com.koczip.realtor;end`;
    return { ok: true };
  } catch {
    return { ok: false, error: "일시적인 오류예요. 잠시 후 다시 시도해 주세요." };
  }
}
