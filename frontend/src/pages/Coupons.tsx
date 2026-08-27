import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Ticket, Coffee, Candy, Gift } from "lucide-react";
import { useAuth, loginKakao } from "../auth";
import { isInstalledApp } from "../lib/appmode";
import AppOnlyGate from "../components/AppOnlyGate";

const API = import.meta.env.VITE_API_BASE;

type Coupon = {
  id: number; kind: "coffee" | "lollipop"; kind_label: string;
  source: string; status: string; status_label: string;
  code: string | null; barcode_url: string | null;
  gifticon_ref: string | null; created_at: string;
};

function when(s: string): string {
  const t = new Date(s.replace(" ", "T"));
  if (isNaN(t.getTime())) return s.slice(5, 10);
  return `${t.getMonth() + 1}/${t.getDate()}`;
}

export default function Coupons() {
  const { token } = useAuth();
  const [items, setItems] = useState<Coupon[] | null>(null);

  const load = useCallback(() => {
    if (!token || !isInstalledApp()) { setItems([]); return; }
    fetch(`${API}/me/coupons`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setItems(d.items || [])).catch(() => setItems([]));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  if (!isInstalledApp()) {
    return (
      <AppOnlyGate title="쿠폰함은 앱에서 열려요"
        desc={<>받은 쿠폰은 <b>콕집 앱</b>에서만 확인·사용할 수 있어요.<br />앱에서 다시 열어주세요.</>} >
        <></>
      </AppOnlyGate>
    );
  }

  if (!token) {
    return (
      <div className="cp-wrap">
        <h1><Ticket size={20} strokeWidth={2.2} /> 쿠폰함</h1>
        <div className="cp-empty">
          <p>로그인하면 받은 쿠폰을 볼 수 있어요.</p>
          <button className="cp-kakao" onClick={loginKakao}><span aria-hidden>💬</span> 카카오로 로그인</button>
        </div>
      </div>
    );
  }

  return (
    <div className="cp-wrap">
      <h1><Ticket size={20} strokeWidth={2.2} /> 쿠폰함</h1>

      {items === null ? (
        <div className="cp-empty">불러오는 중…</div>
      ) : items.length === 0 ? (
        <div className="cp-empty">
          <Gift size={40} strokeWidth={1.6} />
          <p>아직 받은 쿠폰이 없어요.</p>
          <Link to="/event" className="cp-go">이벤트 참여하러 가기</Link>
        </div>
      ) : (
        <ul className="cp-list">
          {items.map((c) => (
            <li key={c.id} className={`cp-card ${c.kind} ${c.status}`}>
              <div className="cp-top">
                <div className="cp-ic">{c.kind === "coffee" ? <Coffee size={22} /> : <Candy size={22} />}</div>
                <div className="cp-body">
                  <div className="cp-name">{c.kind_label}</div>
                  <div className="cp-meta">{when(c.created_at)} 지급 · <b>{c.status_label}</b></div>
                </div>
              </div>
              {c.barcode_url && (
                <a className="cp-barcode" href={c.barcode_url} target="_blank" rel="noreferrer">
                  <img src={c.barcode_url} alt="쿠폰 바코드" loading="lazy" />
                </a>
              )}
              {c.code && <div className="cp-code">쿠폰번호 <b>{c.code}</b></div>}
              {c.kind === "coffee" && c.status === "issued" && (
                <div className="cp-terms">
                  매장에서 바코드를 제시하세요 · 유효기간 지급일로부터 30일 · 사용처 메가MGC커피<br />
                  상품공급자 (주)케이티알파 · 발행 런투온라인
                </div>
              )}
              {c.kind === "lollipop" && c.status === "issued" && (
                <div className="cp-terms">
                  편의점(GS25)에서 바코드를 제시하세요 · 유효기간 지급일로부터 30일 · 퍼페티 츄파춥스<br />
                  상품공급자 (주)케이티알파 · 발행 런투온라인
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="cp-note">발급 준비 중인 쿠폰은 순차적으로 발급돼요. 발급되면 바코드와 쿠폰번호가 표시됩니다.</p>

      <style>{`
.cp-wrap{max-width:560px;margin:0 auto;padding:16px 14px 80px}
.cp-wrap h1{display:flex;align-items:center;gap:8px;font-size:20px;font-weight:800;color:var(--c-text,#18233a);margin:0 0 16px}
.cp-empty{display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center;padding:56px 20px;color:var(--c-text-soft,#8b95a5)}
.cp-empty p{margin:6px 0 0;font-size:14.5px;font-weight:700;color:var(--c-text,#5a6b80)}
.cp-kakao{display:inline-flex;align-items:center;gap:7px;background:#FEE500;color:#181600;border:none;font-size:14px;font-weight:800;padding:11px 18px;border-radius:11px;cursor:pointer}
.cp-go{font-size:13.5px;font-weight:800;color:var(--c-primary,#1268d3);text-decoration:none;
  background:var(--c-primary-soft,#eaf2fd);padding:9px 16px;border-radius:10px}
.cp-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:11px}
.cp-card{display:flex;flex-direction:column;gap:11px;padding:15px 16px;
  background:var(--c-surface,#fff);border:1px solid var(--c-border,#e3e8ef);border-radius:15px}
.cp-card.used{opacity:.55}
.cp-top{display:flex;align-items:center;gap:13px}
.cp-ic{width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex:none}
.cp-card.coffee .cp-ic{background:#fbf1e3;color:#9a5b12}
.cp-card.lollipop .cp-ic{background:#fdeef4;color:#c0396f}
.cp-body{flex:1;min-width:0}
.cp-name{font-size:15px;font-weight:800;color:var(--c-text,#18233a)}
.cp-meta{font-size:12px;color:var(--c-text-soft,#5a6b80);margin-top:3px}
.cp-meta b{color:var(--c-primary,#1268d3);font-weight:800}
.cp-barcode{display:block;background:#fff;border:1px solid #eef2f7;border-radius:10px;padding:10px;text-align:center}
.cp-barcode img{max-width:100%;height:auto;max-height:130px}
.cp-code{font-size:13.5px;font-weight:800;color:var(--c-text,#33425a);text-align:center;letter-spacing:.05em}
.cp-code b{color:var(--c-primary,#1268d3)}
.cp-terms{font-size:10.5px;line-height:1.6;color:var(--c-text-soft,#8b95a5);
  border-top:1px dashed var(--c-border,#e3e8ef);padding-top:8px}
.cp-note{font-size:11.5px;line-height:1.6;color:var(--c-text-soft,#8b95a5);margin-top:16px}
      `}</style>
    </div>
  );
}
