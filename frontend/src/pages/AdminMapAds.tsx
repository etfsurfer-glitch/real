import { useCallback, useEffect, useState } from "react";
import { Megaphone, Trash2, Save } from "lucide-react";
import { authClient } from "../auth";

const API = import.meta.env.VITE_API_BASE;

// 지도 시험판 광고 관리 — 자리 5곳의 광고 등록·수정·삭제 + 광고 안내에 보이는 접속 지표(손으로 입력).
type Ad = { id?: number; slot: string; scope: string; code: string; title: string; sub: string; url: string; image_url: string;
  complex_no: string; realtor_id: string; lat: number | null; lng: number | null; starts: string; ends: string; active: number;
  advertiser: string; note: string; clicks?: number; created_at?: string };
type Settings = { visitors: string; pageviews: string; complex_views: string; note: string };

const SLOTS: [string, string][] = [["pin", "광고 핀(지도)"], ["realtor_top", "중개사 상단 노출"], ["deals_top", "급매 목록 첫 칸"], ["stats_band", "통계 창 띠"], ["info_life", "생활 광고(단지정보)"]];
const SCOPES: [string, string][] = [["sigungu", "시·군·구(5자리)"], ["dong", "읍·면·동(10자리)"], ["nat", "전국"]];
const EMPTY: Ad = { slot: "pin", scope: "sigungu", code: "", title: "", sub: "", url: "", image_url: "", complex_no: "", realtor_id: "", lat: null, lng: null, starts: "", ends: "", active: 1, advertiser: "", note: "" };

async function afetch(path: string, init?: RequestInit) {
  const s = await authClient?.auth.getSession();
  const tok = s?.data?.session?.access_token;
  return fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(tok ? { Authorization: `Bearer ${tok}` } : {}), ...(init?.headers || {}) } });
}

export default function AdminMapAds() {
  const [items, setItems] = useState<Ad[]>([]);
  const [st, setSt] = useState<Settings>({ visitors: "", pageviews: "", complex_views: "", note: "" });
  const [form, setForm] = useState<Ad>(EMPTY);
  const [msg, setMsg] = useState("");
  const load = useCallback(() => {
    afetch("/admin/map-ads").then((r) => r.json()).then((d) => { setItems(d.items || []); if (d.settings) setSt(d.settings); }).catch(() => setMsg("불러오지 못했어요"));
  }, []);
  useEffect(load, [load]);
  const f = (k: keyof Ad, v: string) => setForm((o) => ({ ...o, [k]: k === "lat" || k === "lng" ? (v === "" ? null : Number(v)) : k === "active" ? Number(v) : v }));
  const save = async () => {
    setMsg("");
    const r = await afetch("/admin/map-ads", { method: "POST", body: JSON.stringify(form) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { setMsg(typeof d.detail === "string" ? d.detail : `저장 실패 ${r.status}`); return; }
    setMsg(form.id ? "수정했어요" : "등록했어요"); setForm(EMPTY); load();
  };
  const del = async (id: number) => {
    if (!window.confirm("이 광고를 지울까요?")) return;
    await afetch(`/admin/map-ads/${id}`, { method: "DELETE" }); load();
  };
  const saveSt = async () => {
    const r = await afetch("/admin/map-ads/settings", { method: "POST", body: JSON.stringify(st) });
    setMsg(r.ok ? "지표를 저장했어요. 지도 광고 안내에 바로 보여요." : "지표 저장 실패");
  };
  const inp = (k: keyof Ad, ph: string, w = 160) => <input className="ai-input" style={{ width: w }} placeholder={ph} value={form[k] == null ? "" : String(form[k])} onChange={(e) => f(k, e.target.value)} />;
  return (
    <div>
      <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}><Megaphone size={20} /> 지도 광고 관리</h2>
      <p className="muted" style={{ fontSize: 13 }}>testv2.koczip.com 지도의 광고 자리 5곳. 광고는 '광고' 표시를 달고 순위와 섞이지 않아요. 지역 코드는 시·군·구 5자리(예 11710 송파구) 또는 읍·면·동 10자리.</p>

      <h3 style={{ marginTop: 20 }}>광고 안내 지표 <span className="muted" style={{ fontSize: 12, fontWeight: 500 }}>광고 안내 창 맨 위에 보이는 숫자 · 비우면 그 칸은 안 보여요</span></h3>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input className="ai-input" style={{ width: 150 }} placeholder="하루 방문 (예: 약 370명)" value={st.visitors} onChange={(e) => setSt({ ...st, visitors: e.target.value })} />
        <input className="ai-input" style={{ width: 170 }} placeholder="하루 페이지뷰 (예: 약 22,000)" value={st.pageviews} onChange={(e) => setSt({ ...st, pageviews: e.target.value })} />
        <input className="ai-input" style={{ width: 170 }} placeholder="하루 단지 조회 (예: 약 12,000)" value={st.complex_views} onChange={(e) => setSt({ ...st, complex_views: e.target.value })} />
        <input className="ai-input" style={{ width: 260 }} placeholder="기준 설명 (예: 2026년 11월 기준 · 봇 제외)" value={st.note} onChange={(e) => setSt({ ...st, note: e.target.value })} />
        <button className="auth-btn kakao" onClick={saveSt}><Save size={14} /> 지표 저장</button>
      </div>

      <h3 style={{ marginTop: 24 }}>{form.id ? `광고 #${form.id} 수정` : "광고 등록"}</h3>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select className="ai-input" style={{ width: 170 }} value={form.slot} onChange={(e) => f("slot", e.target.value)}>{SLOTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <select className="ai-input" style={{ width: 150 }} value={form.scope} onChange={(e) => f("scope", e.target.value)}>{SCOPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        {form.scope !== "nat" && inp("code", "지역 코드", 130)}
        {inp("title", "제목(20자)", 220)}
        {inp("sub", "설명(40자)", 260)}
        {inp("advertiser", "광고주 표기", 140)}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
        {inp("url", "연결 주소(https://…)", 260)}
        {inp("image_url", "이미지 주소(선택)", 220)}
        {inp("complex_no", "단지번호(단지로 연결 시)", 170)}
        {inp("realtor_id", "사무소 ID(사무소 창으로 연결 시)", 200)}
        {form.slot === "pin" && <>{inp("lat", "위도", 110)}{inp("lng", "경도", 110)}</>}
        {inp("starts", "시작일 YYYY-MM-DD", 150)}
        {inp("ends", "종료일 YYYY-MM-DD", 150)}
        <label style={{ fontSize: 13 }}><input type="checkbox" checked={!!form.active} onChange={(e) => f("active", e.target.checked ? "1" : "0")} /> 켜기</label>
        {inp("note", "메모(내부)", 160)}
        <button className="auth-btn kakao" onClick={save} disabled={!form.title.trim()}>{form.id ? "수정 저장" : "등록"}</button>
        {form.id && <button className="auth-btn" onClick={() => setForm(EMPTY)}>취소</button>}
      </div>
      {msg && <p style={{ color: "#1268d3", fontSize: 13, marginTop: 8 }}>{msg}</p>}

      <h3 style={{ marginTop: 24 }}>등록된 광고 {items.length}건</h3>
      <div className="table-scroll">
        <table>
          <thead><tr><th>#</th><th>자리</th><th>범위</th><th>제목</th><th>광고주</th><th>기간</th><th>상태</th><th className="num">클릭</th><th /></tr></thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td><td>{SLOTS.find(([k]) => k === a.slot)?.[1] || a.slot}</td><td>{a.scope === "nat" ? "전국" : a.code}</td>
                <td><b>{a.title}</b><div className="muted" style={{ fontSize: 12 }}>{a.sub}</div></td><td>{a.advertiser}</td>
                <td className="muted" style={{ fontSize: 12 }}>{a.starts || "-"} ~ {a.ends || "-"}</td><td>{a.active ? "켜짐" : "꺼짐"}</td><td className="num">{a.clicks ?? 0}</td>
                <td style={{ whiteSpace: "nowrap" }}><button className="auth-btn" style={{ padding: "4px 10px" }} onClick={() => setForm({ ...EMPTY, ...a })}>수정</button> <button className="auth-btn" style={{ padding: "4px 8px" }} onClick={() => del(a.id!)} aria-label="삭제"><Trash2 size={14} /></button></td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={9} className="muted">등록된 광고가 없어요.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
