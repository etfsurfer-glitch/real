import { useState } from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, ExternalLink, Search } from "lucide-react";
import { openListingPopup } from "../lib/listingPopup";

const API = import.meta.env.VITE_API_BASE;

type Verdict = { grade: string | null; ratio?: number; hug_limit: number; gongsi: number; gongsi_year: string; deposit: number | null; message: string };
type Nearby = { scope: string; sale_median: number | null; jeonse_median: number | null; risky_pct: number | null; n_buildings: number | null; listings: { building: string; area_m2: number | null; deposit: number; naver_url: string }[] };
type Resp = { ok: boolean; error?: string; resolved?: { text: string; building: string | null; kind: string | null; matched_area: number | null; sgg: string; umd: string }; verdict?: Verdict | null; nearby?: Nearby };

function won(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
const GRADE: Record<string, { c: string; icon: typeof ShieldCheck }> = {
  "안전": { c: "#0a9d57", icon: ShieldCheck },
  "양호": { c: "#1f7ae0", icon: ShieldCheck },
  "주의": { c: "#e08a00", icon: AlertTriangle },
  "위험": { c: "#d4332b", icon: ShieldAlert },
};

export default function JeonseCheck() {
  const [addr, setAddr] = useState("");
  const [area, setArea] = useState("");
  const [deposit, setDeposit] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<Resp | null>(null);

  const run = () => {
    if (!API || !addr.trim()) return;
    setLoading(true); setRes(null);
    const q = `addr=${encodeURIComponent(addr.trim())}&area=${area || 0}&deposit=${deposit || 0}`;
    fetch(`${API}/tools/jeonse-check?${q}`).then((r) => r.json()).then(setRes)
      .catch(() => setRes({ ok: false, error: "조회 중 오류가 났어요." })).finally(() => setLoading(false));
  };

  const v = res?.verdict;
  const g = v?.grade ? GRADE[v.grade] : null;
  const depWon = deposit ? Number(deposit) * 10000 : 0;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 21, fontWeight: 800, color: "#13294b", margin: "0 0 4px" }}>전세 안전 감별기</h2>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 16px" }}>
        주소·전용면적·보증금을 넣으면 <b>공시가격(HUG 기준)</b>으로 깡통전세 위험도를 알려드려요.
      </p>

      <div className="jc-form">
        <label>주소 <span>도로명 또는 지번</span>
          <input value={addr} onChange={(e) => setAddr(e.target.value)}
            placeholder="예) 서울 강서구 화곡동 102-119" onKeyDown={(e) => e.key === "Enter" && run()} />
        </label>
        <div className="jc-row">
          <label>전용면적 (㎡)
            <input type="number" value={area} onChange={(e) => setArea(e.target.value)} placeholder="35" />
          </label>
          <label>보증금 (만원) {deposit && <span>{won(depWon)}</span>}
            <input type="number" value={deposit} onChange={(e) => setDeposit(e.target.value)}
              placeholder="26000" onKeyDown={(e) => e.key === "Enter" && run()} />
          </label>
        </div>
        <button className="jc-go" onClick={run} disabled={loading || !addr.trim()}>
          <Search size={16} /> {loading ? "조회 중…" : "감별하기"}
        </button>
      </div>

      {res && !res.ok && <div className="jc-err">{res.error}</div>}

      {res?.ok && (
        <>
          {v && g && (
            <div className="jc-verdict" style={{ borderColor: g.c, background: `${g.c}0d` }}>
              <div className="jc-vhead" style={{ color: g.c }}>
                <g.icon size={26} /> <span className="jc-grade">{v.grade}</span>
                {v.ratio != null && <span className="jc-ratio">전세가율 {v.ratio}%</span>}
              </div>
              <div className="jc-vmsg">{v.message}</div>
              <div className="jc-bars">
                <div className="jc-bar-row"><span>내 보증금</span><b>{won(v.deposit)}</b></div>
                <div className="jc-bar-row"><span>공시가격 ({v.gongsi_year})</span><b>{won(v.gongsi)}</b></div>
                <div className="jc-bar-row hug"><span>HUG 한도 (공시가×140%)</span><b>{won(v.hug_limit)}</b></div>
              </div>
              {v.deposit != null && (
                <div className="jc-gauge">
                  <div className="jc-gauge-fill" style={{ width: `${Math.min((v.ratio || 0) / 1.6, 100)}%`, background: g.c }} />
                  <span className="jc-gauge-100" title="공시가격 100%">100%</span>
                  <span className="jc-gauge-140" title="HUG 한도 140%">140%</span>
                </div>
              )}
            </div>
          )}
          {v && !v.grade && <div className="jc-note2">공시가격 {won(v.gongsi)} ({v.gongsi_year}) · HUG 한도 {won(v.hug_limit)}. 보증금을 입력하면 위험도를 판정해요.</div>}

          {res.resolved && (
            <div className="jc-resolved">
              <b>{res.resolved.building || res.resolved.text}</b>
              <span>{res.resolved.kind}{res.resolved.matched_area ? ` · 전용 ${res.resolved.matched_area}㎡ 기준` : ""}</span>
            </div>
          )}

          {res.nearby && (
            <>
              <div className="ats-section" style={{ marginTop: 18 }}>{res.nearby.scope} 시세</div>
              <div className="jc-near">
                <div><span>매매 중위</span><b>{won(res.nearby.sale_median)}</b></div>
                <div><span>전세 중위</span><b>{won(res.nearby.jeonse_median)}</b></div>
                <div><span>위험 건물</span><b className={(res.nearby.risky_pct || 0) >= 30 ? "danger" : ""}>{res.nearby.risky_pct ?? "-"}%</b></div>
              </div>
              {res.nearby.risky_pct != null && res.nearby.n_buildings != null && (
                <div className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
                  분석 건물 {res.nearby.n_buildings.toLocaleString()}곳 중 전세가율 80% 이상이 {res.nearby.risky_pct}%
                </div>
              )}

              {res.nearby.listings.length > 0 && (
                <>
                  <div className="ats-section" style={{ marginTop: 16 }}>주변 전세 매물</div>
                  <div className="jc-listings">
                    {res.nearby.listings.map((l, i) => (
                      <button key={i} className="jc-listing" onClick={() => openListingPopup(l.naver_url)}>
                        <span className="jc-l-b">{l.building} <em>{l.area_m2}㎡</em></span>
                        <span className="jc-l-d">{won(l.deposit)} <ExternalLink size={11} /></span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          <p className="muted" style={{ fontSize: 11.5, marginTop: 16, lineHeight: 1.6 }}>
            ※ 국토교통부 공시가격 기준 가격위험도입니다. <b>선순위 근저당·집주인 대출·세금 체납·관리상태는 반영되지 않습니다</b> —
            계약 전 반드시 <b>등기부등본</b>으로 권리관계를 확인하세요. HUG 전세보증 가입요건은 공시가격의 약 140%입니다.
          </p>
        </>
      )}
    </div>
  );
}
