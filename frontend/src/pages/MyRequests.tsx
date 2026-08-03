import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, Building2, Check, Phone } from "lucide-react";
import { useAuth, loginKakao } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Office = { name: string; status: string; at: string | null };
type OfferListing = { article_no: string; complex: string | null; area_m2: number | null;
                      price: string | null; rent: string | null; floor: string | null; trade: string };
type Offer = { name: string; message: string; contact: string;
               listings: OfferListing[]; at: string };
const PY = 3.305785;
const areaLabel = (m2: number | null) => (m2 ? `${Math.round(m2 / PY)}평(${Math.round(m2)}㎡)` : "");
type Req = {
  id: number; region: string; asset: string; trade: string; area: string; budget: string;
  memo: string; status: string; at: string; target_count: number; offices: Office[];
  offers: Offer[];
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

                {r.offers.length > 0 ? (
                  <div className="myoff">
                    <div className="myoff-h">받은 제안 {r.offers.length}건 — 마음에 드는 곳에 전화해 보세요</div>
                    {r.offers.map((o, i) => (
                      <div key={i} className="myoff-card">
                        <div className="myoff-top">
                          <b><Building2 size={14} /> {o.name || "중개사무소"}</b>
                          <a className="myoff-tel" href={`tel:${o.contact}`}>
                            <Phone size={13} strokeWidth={2.5} /> {o.contact}
                          </a>
                        </div>
                        {o.message && <p className="myoff-msg">{o.message}</p>}
                        {o.listings.length > 0 && (
                          <ul className="myoff-ls">
                            {o.listings.map((x) => (
                              <li key={x.article_no}>
                                <b>{x.complex || "단지 미상"}</b>
                                <i>{[areaLabel(x.area_m2), x.floor ? `${x.floor}층` : "", x.trade]
                                  .filter(Boolean).join(" · ")}</i>
                                <em>{x.price || x.rent || "-"}</em>
                              </li>
                            ))}
                          </ul>
                        )}
                        <div className="muted" style={{ fontSize: 11.5 }}>{(o.at || "").slice(5, 16)}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="myoff-wait">
                    <b>{r.offices.length}곳에 전달했어요.</b> 제안이 오면 알려드릴게요 — 보통 하루 안에 옵니다.
                  </div>
                )}
                <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                  <b>내 연락처는 중개사무소에 전달되지 않았습니다.</b> 위 번호로 직접 거실 때만 알려집니다.
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
