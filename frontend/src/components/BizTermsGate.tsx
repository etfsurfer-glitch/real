// 계약서 작성·계약캘린더·계약관리 진입 게이트(P5 개방, 2026-09-04):
// 중개사 회원 + 중개사 약관 동의(버전별) 확인. 관리자는 통과.
// BizApp(앱 셸)과 Lounge(PC 웹) 양쪽에서 쓰므로 별도 파일 — BizApp이 Lounge를
// 임포트하는 구조라 BizApp 안에 두면 순환 임포트가 된다(2026-09-05 라운지 개방).
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { Loading } from "./Loading";

const API_BASE = import.meta.env.VITE_API_BASE;

export function BizTermsGate({ children }: { children: React.ReactNode }) {
  const { user, token, ready } = useAuth();
  const [st, setSt] = useState<null | { version: string; member: boolean; member_pending: boolean;
    agreed: boolean; is_admin: boolean }>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const loadSt = useCallback(() => {
    if (!token || !API_BASE) return;
    fetch(`${API_BASE}/biz/terms/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(d => { setSt(d); setErr(""); })
      .catch(() => setErr("상태 확인에 실패했습니다 — 새로고침 후 다시 시도하세요"));
  }, [token]);
  useEffect(() => { loadSt(); }, [loadSt]);
  const agree = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/biz/terms/agree`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) { setErr("동의 저장에 실패했습니다"); return; }
      loadSt();
    } finally { setBusy(false); }
  };
  const card = (title: string, body: React.ReactNode) => (
    <div className="bzc-card" style={{ textAlign: "center", padding: "28px 16px" }}>
      <div style={{ fontSize: 14, fontWeight: 800, color: "#13294b", marginBottom: 6 }}>{title}</div>
      {body}
    </div>
  );
  if (!ready) return null;
  if (!user) return card("로그인이 필요합니다", <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
    우측 상단에서 로그인 후 이용하세요.</p>);
  if (err) return card("잠시 후 다시 시도해 주세요", <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>{err}</p>);
  if (!st) return <Loading />;
  if (st.is_admin || st.agreed) return <>{children}</>;
  if (st.member_pending) return card("대표님 승인 대기 중입니다", <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
    사무소 대표님이 가입을 승인하면 이용할 수 있습니다.</p>);
  if (!st.member) return card("중개사 인증이 필요합니다", <>
    <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
      계약서 작성은 사무소 연동을 마친 중개사 회원 전용 기능입니다.</p>
    <Link to="/biz/office" className="chip" style={{ marginTop: 12, display: "inline-flex" }}>사무소 연동하러 가기</Link>
  </>);
  return card("중개사 약관 동의가 필요합니다", <>
    <p className="muted" style={{ fontSize: 12.5, margin: "0 0 4px" }}>
      계약서 작성·확인설명서·계약캘린더는 중개사 약관(전자문서 작성 보조 도구 이용 조건)에
      동의한 뒤 이용할 수 있습니다. 작성 문서의 법적 책임은 개업공인중개사에게 있습니다.
    </p>
    <a href="/biz-terms" target="_blank" rel="noreferrer" style={{ fontSize: 12.5 }}>약관 전문 보기 ↗</a>
    <div>
      <button className="chip" disabled={busy} onClick={agree}
        style={{ marginTop: 12, display: "inline-flex", cursor: "pointer", fontWeight: 800 }}>
        {busy ? "저장 중…" : "약관을 확인했으며 동의합니다"}</button>
    </div>
  </>);
}
