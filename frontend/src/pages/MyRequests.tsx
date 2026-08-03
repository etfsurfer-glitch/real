import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, Building2, Check } from "lucide-react";
import { useAuth, loginKakao } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Office = { name: string; status: string; at: string | null };
type Req = {
  id: number; region: string; asset: string; trade: string; area: string; budget: string;
  memo: string; status: string; at: string; target_count: number; offices: Office[];
};

const ST: Record<string, string> = {
  sent: "전달됨", read: "확인함", responded: "연락 예정", declined: "맞는 매물 없음",
};

/** 내가 보낸 콕집요청과 중개사무소별 진행 상태. */
export default function MyRequests() {
  const { token } = useAuth();
  const [items, setItems] = useState<Req[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API}/me/requests`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setItems(d.items || []))
      .catch(() => setItems([])).finally(() => setLoading(false));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  if (!token) {
    return (
      <div className="kreq">
        <h2><Sparkles size={20} strokeWidth={2.3} /> 내 콕집요청</h2>
        <div className="kreq-card kreq-center">
          <p className="muted">로그인하시면 보낸 요청과 진행 상태를 볼 수 있어요.</p>
          <button className="kreq-primary" onClick={loginKakao}>카카오로 로그인</button>
        </div>
      </div>
    );
  }

  return (
    <div className="kreq">
      <h2><Sparkles size={20} strokeWidth={2.3} /> 내 콕집요청</h2>

      {loading ? <div className="muted">불러오는 중…</div>
        : items.length === 0 ? (
          <div className="kreq-card kreq-center">
            <p className="kreq-lead">아직 보낸 요청이 없어요.</p>
            <p className="muted">
              원하는 조건을 남기시면 그 동네 중개사무소가 매물을 찾아 연락드립니다. 이용료는 없습니다.
            </p>
            <Link className="kreq-primary" to="/request" style={{ textDecoration: "none" }}>
              콕집요청 보내기
            </Link>
          </div>
        ) : (
          <>
            {items.map((r) => (
              <div key={r.id} className="kreq-card">
                <div className="myreq-h">
                  <b>{r.region || "지역 미지정"} · {r.asset} {r.trade}</b>
                  <span className="muted">{(r.at || "").slice(5, 16)}</span>
                </div>
                <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>
                  {[r.area, r.budget].filter(Boolean).join(" · ") || "조건 미기재"}
                </div>
                {r.memo && <p style={{ fontSize: 14, marginTop: 8, lineHeight: 1.6 }}>{r.memo}</p>}

                <div className="myreq-offices">
                  {r.offices.map((o, i) => (
                    <div key={i} className="myreq-office">
                      <Building2 size={14} />
                      <span>{o.name || "중개사무소"}</span>
                      <span className={`sns-st sns-st-${o.status === "responded" ? "done" : "pending"}`}>
                        {ST[o.status] || o.status}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                  연락처는 위 중개사무소에만 전달됐어요. 삭제를 원하시면 문의해 주세요.
                </p>
              </div>
            ))}
            <div className="kreq-card kreq-center">
              <p className="muted" style={{ margin: "0 0 10px" }}>다른 조건으로도 찾아보시겠어요?</p>
              <Link className="kreq-primary" to="/request" style={{ textDecoration: "none" }}>
                <Check size={15} strokeWidth={2.5} /> 새 요청 보내기
              </Link>
            </div>
          </>
        )}
    </div>
  );
}
