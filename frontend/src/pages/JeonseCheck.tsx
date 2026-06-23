import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, Search, ChevronRight } from "lucide-react";
import { useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

type Verdict = { grade: string | null; ratio?: number; hug_limit: number; gongsi: number; gongsi_year: string; deposit: number | null; message: string };
type Nearby = { scope: string; sale_median: number | null; jeonse_median: number | null; risky_pct: number | null; n_buildings: number | null; listings: { building: string; area_m2: number | null; deposit: number; naver_url: string }[] };
type Resp = { ok: boolean; error?: string; resolved?: { text: string; building: string | null; kind: string | null; matched_area: number | null; sgg: string; umd: string }; verdict?: Verdict | null; nearby?: Nearby };
type Listing = { article_no: string; addr: string | null; building: string; area_m2: number | null; floor: string | null; deposit: number; lat: number; lng: number; naver_url: string };

function won(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
const GRADE: Record<string, { c: string; icon: typeof ShieldCheck }> = {
  "안전": { c: "#0a9d57", icon: ShieldCheck }, "양호": { c: "#1f7ae0", icon: ShieldCheck },
  "주의": { c: "#e08a00", icon: AlertTriangle }, "위험": { c: "#d4332b", icon: ShieldAlert },
};

export default function JeonseCheck() {
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const [mode, setMode] = useState<"browse" | "manual">("browse");
  const [listings, setListings] = useState<Listing[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const [addr, setAddr] = useState("");
  const [area, setArea] = useState("");
  const [deposit, setDeposit] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<Resp | null>(null);

  useEffect(() => {
    if (!API || !dong) { setListings([]); return; }
    setLoadingList(true); setRes(null); setSel(null);
    fetch(`${API}/tools/jeonse-listings?cortar=${dong}&limit=40`)
      .then((r) => r.json()).then((d) => setListings(d.listings || []))
      .catch(() => setListings([])).finally(() => setLoadingList(false));
  }, [dong]);

  const checkListing = (l: Listing) => {
    setSel(l.article_no); setLoading(true); setRes(null);
    const q = `lat=${l.lat}&lng=${l.lng}&area=${l.area_m2 || 0}&deposit=${Math.round(l.deposit / 10000)}&cortar=${dong}`;
    fetch(`${API}/tools/jeonse-check?${q}`).then((r) => r.json()).then(setRes)
      .catch(() => setRes({ ok: false, error: "조회 중 오류가 났어요." })).finally(() => setLoading(false));
  };
  const checkManual = () => {
    if (!addr.trim()) return;
    setLoading(true); setRes(null);
    const q = `addr=${encodeURIComponent(addr.trim())}&area=${area || 0}&deposit=${deposit || 0}`;
    fetch(`${API}/tools/jeonse-check?${q}`).then((r) => r.json()).then(setRes)
      .catch(() => setRes({ ok: false, error: "조회 중 오류가 났어요." })).finally(() => setLoading(false));
  };

  const v = res?.verdict;
  const g = v?.grade ? GRADE[v.grade] : null;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 21, fontWeight: 800, color: "#13294b", margin: "0 0 4px" }}>전세 안전 감별기</h2>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 14px" }}>
        지역을 고르고 <b>매물을 선택</b>하면 <b>공시가격(HUG 기준)</b>으로 깡통전세 위험을 알려드려요.
      </p>

      <div className="jc-seg">
        <button className={mode === "browse" ? "on" : ""} onClick={() => { setMode("browse"); setRes(null); }}>매물에서 찾기</button>
        <button className={mode === "manual" ? "on" : ""} onClick={() => { setMode("manual"); setRes(null); }}>주소 직접 입력</button>
      </div>

      {mode === "browse" ? (
        <>
          <div className="dong-pick" style={{ marginTop: 12 }}>
            <select value={sido} onChange={(e) => setSido(e.target.value)}>
              <option value="">시·도</option>
              {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
            <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
              <option value="">시·군·구</option>
              {sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
            <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}>
              <option value="">읍·면·동</option>
              {dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
            </select>
          </div>
          {!dong && <div className="jc-hint">동을 선택하면 전세 매물이 나옵니다. 매물을 누르면 바로 감별돼요.</div>}
          {loadingList && <div className="jc-hint">매물 불러오는 중…</div>}
          {dong && !loadingList && listings.length === 0 && <div className="dong-empty">이 동에 빌라 전세 매물이 없어요.</div>}
          {listings.length > 0 && (
            <div className="jc-picklist">
              {listings.map((l) => (
                <button key={l.article_no} className={`jc-pick ${sel === l.article_no ? "on" : ""}`} onClick={() => checkListing(l)}>
                  <span className="jc-pick-l">
                    <span className="jc-pick-b">{l.addr || l.building} <em>{l.area_m2}㎡{l.floor ? ` · ${l.floor}층` : ""}</em></span>
                    <span className="jc-pick-d">전세 {won(l.deposit)} · {l.building}</span>
                  </span>
                  {sel === l.article_no && loading ? <span className="jc-pick-load">…</span> : <ChevronRight size={16} className="jc-pick-arr" />}
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="jc-form" style={{ marginTop: 12 }}>
          <label>주소 <span>지번 (예: 서울 강서구 화곡동 102-119)</span>
            <input value={addr} onChange={(e) => setAddr(e.target.value)} onKeyDown={(e) => e.key === "Enter" && checkManual()} placeholder="서울 강서구 화곡동 102-119" />
          </label>
          <div className="jc-row">
            <label>전용면적 (㎡)<input type="number" value={area} onChange={(e) => setArea(e.target.value)} placeholder="35" /></label>
            <label>보증금 (만원) {deposit && <span>{won(Number(deposit) * 10000)}</span>}
              <input type="number" value={deposit} onChange={(e) => setDeposit(e.target.value)} onKeyDown={(e) => e.key === "Enter" && checkManual()} placeholder="26000" />
            </label>
          </div>
          <button className="jc-go" onClick={checkManual} disabled={loading || !addr.trim()}>
            <Search size={16} /> {loading ? "조회 중…" : "감별하기"}
          </button>
        </div>
      )}

      {res && !res.ok && <div className="jc-err">{res.error}</div>}

      {res?.ok && (
        <div className="jc-result">
          {v && g && (
            <div className="jc-verdict" style={{ borderColor: g.c, background: `${g.c}0d` }}>
              <div className="jc-vhead" style={{ color: g.c }}>
                <g.icon size={26} /> <span className="jc-grade">{v.grade}</span>
                {v.ratio != null && <span className="jc-ratio">전세가율 {v.ratio}%</span>}
              </div>
              <div className="jc-vmsg">{v.message}</div>
              <div className="jc-bars">
                <div className="jc-bar-row"><span>전세 보증금</span><b>{won(v.deposit)}</b></div>
                <div className="jc-bar-row"><span>공시가격 ({v.gongsi_year})</span><b>{won(v.gongsi)}</b></div>
                <div className="jc-bar-row hug"><span>HUG 한도 (공시가×140%)</span><b>{won(v.hug_limit)}</b></div>
              </div>
              <div className="jc-gauge">
                <div className="jc-gauge-fill" style={{ width: `${Math.min((v.ratio || 0) / 1.6, 100)}%`, background: g.c }} />
                <span className="jc-gauge-100">100%</span><span className="jc-gauge-140">140%</span>
              </div>
            </div>
          )}
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
            </>
          )}
          <p className="muted" style={{ fontSize: 11.5, marginTop: 16, lineHeight: 1.6 }}>
            ※ 국토교통부 공시가격 기준 <b>가격 위험도</b>입니다. <b>선순위 근저당·집주인 대출·세금 체납·관리상태는 반영되지 않습니다</b> —
            계약 전 반드시 <b>등기부등본</b>으로 권리관계를 확인하세요. HUG 전세보증 가입요건은 공시가격의 약 140%입니다.
          </p>
        </div>
      )}
    </div>
  );
}
