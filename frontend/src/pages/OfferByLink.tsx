import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Building2, Check, Sparkles } from "lucide-react";
import OfferForm, { Offer } from "../components/OfferForm";

const API = import.meta.env.VITE_API_BASE;

type Data = {
  request_id: number;
  office: { realtor_id: string; name: string };
  request: { region: string; asset: string; trade: string; area: string; budget: string;
             memo: string; at: string };
  offer: Offer | null;
};

/** 문자로 받은 링크로 들어오는 화면 — 앱에 가입하지 않은 사무소용.
 *  링크 자체가 열쇠(72시간)라 로그인을 묻지 않는다. 손님 이름·전화는 여기에도 없다. */
export default function OfferByLink() {
  const { token = "" } = useParams();
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);

  const load = useCallback(() => {
    fetch(`${API}/r/${token}`)
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
        <h2><Sparkles size={20} strokeWidth={2.3} /> 콕집요청</h2>
        <div className="kreq-card kreq-center">
          <p className="kreq-lead">{err}</p>
          <p className="muted">링크는 문자를 받은 뒤 72시간까지 열 수 있어요.</p>
        </div>
      </div>
    );
  }
  if (!d) return <div className="kreq"><div className="muted">불러오는 중…</div></div>;

  if (done) {
    return (
      <div className="kreq">
        <h2><Check size={20} strokeWidth={2.6} /> 제안을 보냈습니다</h2>
        <div className="kreq-card">
          <p className="kreq-lead">손님이 확인하고 마음에 들면 직접 연락드릴 거예요.</p>
          <p className="muted">
            내용을 고치시려면 이 링크로 다시 들어와 수정하시면 됩니다(72시간).
          </p>
          <p className="muted" style={{ marginTop: 12 }}>
            콕집에 사무소를 연결하시면 이런 요청을 <b>앱 알림</b>으로 바로 받고,
            매물 광고 점검·홈페이지도 무료로 쓰실 수 있어요. →{" "}
            <a href="/lounge">중개사 라운지</a>
          </p>
        </div>
      </div>
    );
  }

  const r = d.request;
  return (
    <div className="kreq">
      <h2><Sparkles size={20} strokeWidth={2.3} /> 손님 매물요청</h2>
      <div className="kreq-card">
        <div className="ofl-office"><Building2 size={15} /> {d.office.name}</div>
        <div className="kreq-sum" style={{ marginTop: 10 }}>
          <div><span>지역</span><b>{r.region || "-"}</b></div>
          <div><span>유형·거래</span><b>{r.asset} · {r.trade}</b></div>
          {r.area && <div><span>면적</span><b>{r.area}</b></div>}
          {r.budget && <div><span>예산</span><b>{r.budget}</b></div>}
          {r.memo && <div><span>요청</span><b>{r.memo}</b></div>}
          <div><span>접수</span><b>{(r.at || "").slice(0, 16)}</b></div>
        </div>
        <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
          손님 이름과 연락처는 전달되지 않습니다. 매물을 제안하시면 손님이 보고 직접 연락합니다.
        </p>
      </div>

      <div className="kreq-card">
        <OfferForm
          listUrl={`${API}/r/${token}/listings`}
          postUrl={`${API}/r/${token}/offer`}
          existing={d.offer}
          onDone={() => setDone(true)} />
      </div>
    </div>
  );
}
