import { useEffect, useState, useCallback } from "react";
import { Star, BadgeCheck, MessageSquarePlus, Home } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Review = {
  id: number; author_name: string | null; is_admin?: boolean;
  rating: number; body: string; resident: boolean; created_at: string;
};
type Resp = { count: number; avg_rating: number | null; resident_count: number; items: Review[] };

function Stars({ n, size = 13 }: { n: number; size?: number }) {
  return (
    <span style={{ display: "inline-flex", gap: 1 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={size} fill={i <= n ? "#f7b500" : "none"} stroke={i <= n ? "#f7b500" : "#cbd2da"} />
      ))}
    </span>
  );
}

export default function ComplexReviews({ complexNo }: { complexNo: string }) {
  const { token, refreshMe } = useAuth();
  const [data, setData] = useState<Resp | null>(null);
  const [rating, setRating] = useState(5);
  const [body, setBody] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!API) return;
    fetch(`${API}/complex/${complexNo}/reviews`).then((r) => r.json()).then(setData).catch(() => {});
  }, [complexNo]);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!token || busy) return;
    if (body.trim().length < 5) { setMsg("리뷰는 5자 이상 작성해주세요"); return; }
    setBusy(true); setMsg("");
    try {
      const r = await fetch(`${API}/complex/${complexNo}/reviews`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ rating, body: body.trim() }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setMsg(typeof d.detail === "string" ? d.detail : "작성 실패"); return; }
      setBody(""); setMsg(`리뷰 등록 완료! +${d.awarded ?? 30}P 적립`);
      await refreshMe(); load();
    } finally { setBusy(false); }
  };

  const verifyResident = async (file: File) => {
    if (!token) return;
    setBusy(true); setMsg("");
    const fd = new FormData(); fd.append("document", file);
    try {
      const r = await fetch(`${API}/complex/${complexNo}/resident-verify`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd,
      });
      const d = await r.json().catch(() => ({}));
      setMsg(r.ok ? "입주민 인증 신청됨 — 관리자 승인 후 뱃지가 부여됩니다"
        : (typeof d.detail === "string" ? d.detail : "신청 실패"));
    } finally { setBusy(false); }
  };

  return (
    <div className="cr-wrap">
      <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <MessageSquarePlus size={15} strokeWidth={2.3} /> 단지 리뷰
        {data && data.count > 0 && (
          <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
            <Stars n={Math.round(data.avg_rating ?? 0)} /> {data.avg_rating} · {data.count}개
          </span>
        )}
      </div>

      {/* 작성 폼 */}
      {!token ? (
        <div className="muted" style={{ fontSize: 13, padding: "8px 0" }}>리뷰를 쓰려면 로그인이 필요해요.</div>
      ) : (
        <div className="cr-form">
          <div className="cr-form-top">
            <span className="cr-star-pick">
              {[1, 2, 3, 4, 5].map((i) => (
                <button key={i} type="button" onClick={() => setRating(i)} aria-label={`${i}점`}>
                  <Star size={20} fill={i <= rating ? "#f7b500" : "none"} stroke={i <= rating ? "#f7b500" : "#cbd2da"} />
                </button>
              ))}
            </span>
            <label className="cr-resident-btn">
              <Home size={13} /> 입주민 인증
              <input type="file" accept="image/*,.pdf" hidden disabled={busy}
                onChange={(e) => e.target.files?.[0] && verifyResident(e.target.files[0])} />
            </label>
          </div>
          <textarea className="cr-textarea" rows={3} maxLength={2000} value={body}
            placeholder="실거주·임장 경험을 남겨주세요 (소음·주차·관리·학군 등). 작성 시 30P 적립"
            onChange={(e) => setBody(e.target.value)} />
          <div className="cr-form-foot">
            {msg && <span className="cr-msg">{msg}</span>}
            <button className="ai-send" style={{ padding: "0 16px" }} disabled={busy} onClick={submit}>등록</button>
          </div>
        </div>
      )}

      {/* 목록 */}
      <div className="cr-list">
        {data && data.items.length === 0 && <div className="muted" style={{ fontSize: 13 }}>아직 리뷰가 없어요. 첫 리뷰를 남겨보세요!</div>}
        {data?.items.map((r) => (
          <div key={r.id} className="cr-item">
            <div className="cr-item-head">
              <Stars n={r.rating} />
              <span className="cr-author">
                {r.is_admin && <span className="admin-badge">관리자</span>}
                {r.author_name ?? "회원"}
                {r.resident && <span className="cr-resident-badge"><BadgeCheck size={11} /> 입주민</span>}
              </span>
              <span className="cr-date">{(r.created_at ?? "").slice(0, 10)}</span>
            </div>
            <div className="cr-body">{r.body}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
