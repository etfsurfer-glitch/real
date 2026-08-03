import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Building2, Phone, Sparkles } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;
const PY = 3.305785;
const areaLabel = (m2: number | null) => (m2 ? `${Math.round(m2 / PY)}평(${Math.round(m2)}㎡)` : "");

type Ls = { article_no: string; complex: string | null; area_m2: number | null;
            price: string | null; rent: string | null; floor: string | null; trade: string };
type Offer = { name: string; message: string; contact: string; listings: Ls[]; at: string };
type Data = {
  id: number; region: string; asset: string; trade: string; area: string; budget: string;
  memo: string; at: string; sent_to: number; offers: Offer[];
};

/** 손님이 문자로 받은 링크로 여는 제안함 — 로그인을 묻지 않는다.
 *  담기는 연락처는 '중개사무소 것'(사업자 공개정보)뿐이라 링크가 새도 손님 정보는 안전하다. */
export default function ProposalsByLink() {
  const { token = "" } = useParams();
  const { token: auth } = useAuth();
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    fetch(`${API}/proposals/${token}`)
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok) throw new Error(j?.detail || "링크를 열 수 없습니다");
        return j;
      })
      .then(setD).catch((e) => setErr(e?.message || "링크를 열 수 없습니다"));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  if (err) {
    return (
      <div className="kreq">
        <h2><Sparkles size={20} strokeWidth={2.3} /> 받은 제안</h2>
        <div className="kreq-card kreq-center"><p className="kreq-lead">{err}</p></div>
      </div>
    );
  }
  if (!d) return <div className="kreq"><div className="muted">불러오는 중…</div></div>;

  return (
    <div className="kreq">
      <h2><Sparkles size={20} strokeWidth={2.3} /> 받은 제안</h2>

      <div className="kreq-card">
        <div className="myreq-h">
          <b>{d.region || "지역 미지정"} · {d.asset} {d.trade}</b>
          <span className="muted">{(d.at || "").slice(5, 16)}</span>
        </div>
        <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>
          {[d.area, d.budget].filter(Boolean).join(" · ") || "조건 미기재"} · {d.sent_to}곳에 전달
        </div>
        {d.memo && <p style={{ fontSize: 14, marginTop: 8, lineHeight: 1.6 }}>{d.memo}</p>}
      </div>

      {d.offers.length === 0 ? (
        <div className="kreq-card">
          <div className="myoff-wait">
            <b>아직 도착한 제안이 없어요.</b> 제안이 오면 문자로 알려드릴게요.
          </div>
        </div>
      ) : (
        <div className="kreq-card">
          <div className="myoff-h" style={{ marginBottom: 8 }}>
            제안 {d.offers.length}건 — 마음에 드는 곳에 전화해 보세요
          </div>
          <div className="myoff">
            {d.offers.map((o, i) => (
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
        </div>
      )}

      <p className="muted" style={{ fontSize: 12, lineHeight: 1.6 }}>
        <b>내 연락처는 중개사무소에 전달되지 않았습니다.</b> 위 번호로 직접 거실 때만 알려집니다.
        {auth && <> 로그인 중이시라 <Link to="/me/requests">내 요청 목록</Link>에서도 보실 수 있어요.</>}
      </p>
      <div className="kreq-card kreq-center">
        <p className="muted" style={{ margin: "0 0 10px" }}>다른 조건으로도 찾아보시겠어요?</p>
        <Link className="kreq-primary" to="/request" style={{ textDecoration: "none" }}>
          콕집요청 보내기
        </Link>
      </div>
    </div>
  );
}
