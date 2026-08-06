import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import FetchError from "../components/FetchError";
import ShareBar from "../components/ShareBar";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import { useStickyState } from "../hooks/useStickyState";
import { wonShort } from "../lib/kakaomap";
import { Info, Building2, MapPin, Coins, TrendingUp, Search, X } from "lucide-react";
import { areaLabel } from "../lib/area";

const API_BASE = import.meta.env.VITE_API_BASE;

type Region = { code: string; name: string };
type CxHit = { complex_no: string; complex_name: string; region: string; households: number; type_name?: string };
type Item = {
  article_no: string; complex_no: string; complex_name: string;
  area_name: string; area1_m2: number; area2_m2: number | null; price: number;
  floor_info: string; direction: string; realtor_name: string;
  desc: string; confirm_ymd: string; matched: string;
  region_name: string; naver_url: string;
};
type Stats = {
  total: number; avg_price: number | null; min_price: number | null;
  max_price: number | null; complexes: number; over20: number;
  top_regions: { name: string; n: number }[];
};

// 세 조건은 '누가 그 집에 사느냐 / 누가 돈을 대느냐'가 다르다. 용어만으로는 구분이 안 돼
// 매수자가 실익을 오해하기 쉬운 영역이라, 선택한 조건의 설명을 항상 함께 노출한다.
const KINDS = [
  { key: "owner", label: "주인전세", short: "전세",
    desc: "매도인이 집을 판 뒤 그 집에 전세로 계속 사는 조건입니다. 세입자를 새로 구할 필요가 없어, 잔금과 동시에 전세금으로 매매대금 일부를 충당할 수 있습니다." },
  { key: "tenant", label: "세안고", short: "세안고",
    desc: "이미 살고 있는 임차인을 그대로 승계해 매수합니다. 전세보증금만큼 적은 돈으로 살 수 있지만, 남은 계약기간 동안은 실입주할 수 없습니다." },
  { key: "loan", label: "주인대출", short: "대출",
    desc: "매도인이 매수인에게 직접 자금을 대준다고 밝힌 매물입니다(‘집주인대출6억’, ‘매도인 잔금5억 대여가능’). 매수인이 은행 대출을 넘겨받는 ‘대출승계’와는 다릅니다." },
] as const;

const PAGE = 50;
const eok = (v: number | null | undefined) =>
  v == null ? "-" : `${(v / 1e8).toFixed(v / 1e8 >= 10 ? 0 : 1)}억`;

export default function SpecialDeals() {
  const shareRef = useRef<HTMLDivElement>(null);
  const [kind, setKind] = useStickyState<string>("special:kind", "owner");
  const [sido, setSidoRaw] = useStickyState<string>("special:sido", "");
  const [sigungu, setSigunguRaw] = useStickyState<string>("special:sigungu", "");
  const [dong, setDongRaw] = useStickyState<string>("special:dong", "");
  const [asset, setAsset] = useStickyState<string>("special:asset", "all");
  const [sort, setSort] = useStickyState<string>("special:sort", "price_desc");
  const [page, setPage] = useState(0);
  // 단지 콕 집기 — 지역 필터와 배타(단지를 고르면 지역은 무시된다, 서버도 동일 규칙)
  const [cx, setCx] = useState<CxHit | null>(null);
  const [cxQ, setCxQ] = useState("");
  const [cxHits, setCxHits] = useState<CxHit[]>([]);

  const setSido = (v: string) => { setSidoRaw(v); setSigunguRaw(""); setDongRaw(""); setPage(0); };
  const setSigungu = (v: string) => { setSigunguRaw(v); setDongRaw(""); setPage(0); };
  const setDong = (v: string) => { setDongRaw(v); setPage(0); };

  const sidos = useFetchJson<{ items: Region[] }>(
    API_BASE ? `${API_BASE}/stats/changes/sido-list` : null).data?.items ?? [];
  const sigungus = useFetchJson<{ items: Region[] }>(
    API_BASE && sido ? `${API_BASE}/stats/sigungu-list?sido=${sido}` : null).data?.items ?? [];
  const dongs = useFetchJson<{ items: Region[] }>(
    API_BASE && sigungu ? `${API_BASE}/stats/dong-list?sigungu=${sigungu}` : null).data?.items ?? [];

  useEffect(() => {
    const q = cxQ.trim();
    if (!API_BASE || q.length < 2 || (cx && q === cx.complex_name)) { setCxHits([]); return; }
    const tm = setTimeout(() => {
      fetch(`${API_BASE}/complexes/search?q=${encodeURIComponent(q)}&limit=8`)
        .then((r) => r.json()).then((j) => setCxHits(j.items ?? [])).catch(() => {});
    }, 250);
    return () => clearTimeout(tm);
  }, [cxQ, cx]);

  const pickCx = (h: CxHit | null) => { setCx(h); setCxQ(h?.complex_name ?? ""); setCxHits([]); setPage(0); };

  const url = useMemo(() => {
    if (!API_BASE) return null;
    const qs = new URLSearchParams({
      kind, asset, sort, limit: String(PAGE), offset: String(page * PAGE),
    });
    if (cx) qs.set("complex_no", cx.complex_no);
    else if (dong) qs.set("dong", dong);
    else if (sigungu) qs.set("sigungu", sigungu);
    else if (sido) qs.set("sido", sido);
    return `${API_BASE}/stats/special-deals?${qs}`;
  }, [kind, sido, sigungu, dong, cx, asset, sort, page]);
  const { data, loading, error } = useFetchJson<{
    items: Item[]; total: number; stats: Stats; by_kind: Record<string, number>;
  }>(url);

  const cur = KINDS.find((k) => k.key === kind) ?? KINDS[0];
  const st = data?.stats;
  const total = data?.total ?? 0;
  const regionLabel = cx?.complex_name ||
    dongs.find((d) => d.code === dong)?.name ||
    sigungus.find((s) => s.code === sigungu)?.name ||
    sidos.find((s) => s.code === sido)?.name || "전국";

  if (!API_BASE) {
    return <div style={{ color: "crimson" }}>로컬 API(VITE_API_BASE)가 설정되지 않았습니다.</div>;
  }

  return (
    <div ref={shareRef} className="share-target">
      <Link to="/changes" className="back">← 매물호가</Link>
      <h2 style={{ margin: "0 0 4px" }}>주인 — 대출·전세·세안고</h2>
      <div className="muted" style={{ marginBottom: 14 }}>
        중개사가 매물 설명란에 적어 광고하는 특수조건 매매를 모았습니다. 설명 문구를 분류한
        것이라 실제 조건은 반드시 중개사무소에 확인하세요.
      </div>
      <ShareBar targetRef={shareRef} title="주인 — 대출·전세·세안고" fileName="콕집_주인" />

      {/* 조건 선택 — 전국 총건수를 함께 보여 규모 차이를 먼저 인지하게 한다 */}
      <div className="chip-row" style={{ marginBottom: 12 }}>
        <span className="label">조건</span>
        {KINDS.map((k) => (
          <button key={k.key} className={"chip" + (kind === k.key ? " active" : "")}
            onClick={() => { setKind(k.key); setPage(0); }}>
            {k.label}
            {data?.by_kind?.[k.key] != null && (
              <em style={{ fontStyle: "normal", opacity: 0.65, marginLeft: 5, fontSize: 11 }}>
                {data.by_kind[k.key].toLocaleString()}
              </em>
            )}
          </button>
        ))}
      </div>

      {/* 단지 검색 — "이 단지에 이런 조건 매물이 있나"를 바로 확인. 고르면 지역 필터는 잠긴다. */}
      <div style={{ position: "relative", marginBottom: 10, maxWidth: 440 }}>
        <Search size={14} style={{
          position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)",
          color: "var(--c-faint)", pointerEvents: "none",
        }} />
        <input
          value={cxQ}
          onChange={(e) => { setCxQ(e.target.value); if (cx) setCx(null); }}
          placeholder="단지명으로 찾기 (예: 헬리오시티)"
          style={{
            width: "100%", padding: "8px 32px 8px 32px", fontSize: 13,
            border: `1px solid ${cx ? "var(--c-primary)" : "var(--c-border)"}`,
            borderRadius: "var(--r-md)", background: "var(--c-card)",
          }} />
        {(cx || cxQ) && (
          <button onClick={() => pickCx(null)} title="단지 선택 해제"
            style={{
              position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)",
              border: "none", background: "transparent", cursor: "pointer",
              color: "var(--c-muted)", display: "flex", padding: 4,
            }}><X size={14} /></button>
        )}
        {cxHits.length > 0 && (
          <div style={{
            position: "absolute", top: "100%", left: 0, right: 0, zIndex: 20, marginTop: 4,
            background: "var(--c-card)", border: "1px solid var(--c-border)",
            borderRadius: "var(--r-md)", boxShadow: "var(--sh-md)", overflow: "hidden",
          }}>
            {cxHits.map((h) => (
              <button key={h.complex_no} onClick={() => pickCx(h)}
                style={{
                  display: "block", width: "100%", textAlign: "left", padding: "8px 12px",
                  border: "none", borderBottom: "1px solid var(--c-border-soft)",
                  background: "transparent", cursor: "pointer", fontSize: 13,
                }}>
                <b>{h.complex_name}</b>
                {h.type_name && (
                  <i className={"hood-cx-ty ty-" + (h.type_name === "아파트" ? "apt" : "etc")}
                     style={{ marginLeft: 6 }}>{h.type_name}</i>
                )}
                <span className="muted" style={{ marginLeft: 6 }}>{h.region}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {cx && (
        <div style={{
          display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
          padding: "9px 12px", marginBottom: 12, fontSize: 13,
          background: "var(--c-primary-tint)", border: "1px solid var(--c-border)",
          borderRadius: "var(--r-md)",
        }}>
          <Building2 size={14} style={{ color: "var(--c-primary)" }} />
          <b>{cx.complex_name}</b>
          <span className="muted">{cx.region}</span>
          <span style={{ marginLeft: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
            {KINDS.map((k) => {
              const n = data?.by_kind?.[k.key] ?? 0;
              return (
                <span key={k.key} className={"badge " + (n > 0 ? "b1" : "")}
                  style={n > 0 ? undefined : { opacity: 0.5 }}>
                  {k.label} {n.toLocaleString()}
                </span>
              );
            })}
          </span>
        </div>
      )}

      <div className="filter-bar" style={{ marginBottom: 14, opacity: cx ? 0.45 : 1 }}>
        <label><span className="muted">시도</span>
          <select className="filter-select" value={sido} disabled={!!cx} onChange={(e) => setSido(e.target.value)}>
            <option value="">전국</option>
            {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
        </label>
        <label><span className="muted">시군구</span>
          <select className="filter-select" value={sigungu} disabled={!sido || !!cx}
            onChange={(e) => setSigungu(e.target.value)}>
            <option value="">{sido ? "전체" : "(시도 선택)"}</option>
            {sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
        </label>
        <label><span className="muted">읍면동</span>
          <select className="filter-select" value={dong} disabled={!sigungu || !!cx}
            onChange={(e) => setDong(e.target.value)}>
            <option value="">{sigungu ? "전체" : "(시군구 선택)"}</option>
            {dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
          </select>
        </label>
        <label><span className="muted">유형</span>
          <select className="filter-select" value={asset}
            onChange={(e) => { setAsset(e.target.value); setPage(0); }}>
            <option value="all">전체</option>
            <option value="apt">아파트</option>
            <option value="offi">오피스텔</option>
          </select>
        </label>
        <label><span className="muted">정렬</span>
          <select className="filter-select" value={sort}
            onChange={(e) => { setSort(e.target.value); setPage(0); }}>
            <option value="price_desc">가격 높은순</option>
            <option value="price_asc">가격 낮은순</option>
            <option value="recent">최근 확인순</option>
          </select>
        </label>
      </div>

      {/* 상단 요약 — 목록과 완전히 같은 필터로 집계된 값 */}
      <div className="chg-cards">
        <div className="chg-card" style={{ ["--ac" as any]: "var(--c-primary)" }}>
          <div className="chg-label"><span className="chg-dot" />{regionLabel} {cur.label}</div>
          <div className="chg-num">{(st?.total ?? 0).toLocaleString()}건</div>
          <div className="chg-sub">단지 {(st?.complexes ?? 0).toLocaleString()}곳</div>
        </div>
        <div className="chg-card" style={{ ["--ac" as any]: "var(--c-sale)" }}>
          <div className="chg-label"><Coins size={12} />평균 호가</div>
          <div className="chg-num">{eok(st?.avg_price)}</div>
          <div className="chg-sub">{eok(st?.min_price)} ~ {eok(st?.max_price)}</div>
        </div>
        <div className="chg-card" style={{ ["--ac" as any]: "var(--c-warn)" }}>
          <div className="chg-label"><TrendingUp size={12} />20억 이상</div>
          <div className="chg-num">{(st?.over20 ?? 0).toLocaleString()}건</div>
          <div className="chg-sub">
            {st?.total ? `전체의 ${((st.over20 / st.total) * 100).toFixed(1)}%` : "-"}
          </div>
        </div>
        <div className="chg-card" style={{ ["--ac" as any]: "var(--c-wolse)" }}>
          <div className="chg-label"><MapPin size={12} />많은 지역</div>
          <div className="chg-num" style={{ fontSize: 15, lineHeight: 1.35, marginTop: 7 }}>
            {st?.top_regions?.length
              ? st.top_regions.slice(0, 2).map((r) => `${r.name} ${r.n}`).join(" · ")
              : "-"}
          </div>
          <div className="chg-sub">
            {st?.top_regions?.slice(2, 5).map((r) => `${r.name} ${r.n}`).join(" · ") || ""}
          </div>
        </div>
      </div>

      <div style={{
        display: "flex", gap: 8, alignItems: "flex-start", padding: "10px 12px",
        background: "var(--c-primary-tint)", border: "1px solid var(--c-border)",
        borderRadius: "var(--r-md)", marginBottom: 14, fontSize: 13, lineHeight: 1.55,
      }}>
        <Info size={15} style={{ color: "var(--c-primary)", flexShrink: 0, marginTop: 2 }} />
        <div><b>{cur.label}</b> — {cur.desc}</div>
      </div>

      {error && <FetchError message={error} />}
      {loading && <Loading />}

      {!loading && data && data.items.length === 0 && (
        <div className="muted" style={{ padding: "28px 0", textAlign: "center" }}>
          {regionLabel}에는 조건에 맞는 매물이 없습니다.
        </div>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        {data?.items.map((it) => (
          <div key={it.article_no} className="card" style={{ padding: "12px 14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
              <div style={{ minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
                <Building2 size={14} style={{ color: "var(--c-faint)", flexShrink: 0 }} />
                <Link to={`/complex/${it.complex_no}`} style={{ fontWeight: 700, fontSize: 14.5 }}>
                  {it.complex_name}
                </Link>
                <span className="muted">{it.region_name}</span>
              </div>
              <div style={{ fontWeight: 800, fontSize: 15, color: "var(--c-sale)", whiteSpace: "nowrap" }}>
                {wonShort(it.price)}
              </div>
            </div>
            <div className="muted" style={{ marginTop: 3 }}>
              {it.area2_m2 ? areaLabel(it.area2_m2) : `${it.area_name}㎡`} · {it.floor_info} · {it.direction} · {it.realtor_name}
            </div>
            {it.desc && (
              <div style={{ fontSize: 12.5, marginTop: 6, color: "var(--c-text-soft)", lineHeight: 1.5 }}>
                {it.desc}
              </div>
            )}
            <div style={{ marginTop: 7, display: "flex", gap: 8, alignItems: "center" }}>
              <span className="badge b1">{it.matched}</span>
              <a href={it.naver_url} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
                네이버 매물로 이동
              </a>
            </div>
          </div>
        ))}
      </div>

      {total > PAGE && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16, alignItems: "center" }}>
          <button className="chip" disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}>이전</button>
          <span className="muted">{page + 1} / {Math.ceil(total / PAGE)}</span>
          <button className="chip" disabled={(page + 1) * PAGE >= total}
            onClick={() => setPage((p) => p + 1)}>다음</button>
        </div>
      )}

      <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
        네이버 매물 기준 · 단지명을 누르면 콕집 단지상세로, ‘네이버 매물로 이동’을 누르면 원본 매물로 이동
      </p>

      <div className="muted" style={{ marginTop: 14, lineHeight: 1.6 }}>
        분류 기준 | 매물 설명란의 표현을 규칙으로 분류했습니다.
        ‘근저당없음·무근저당·주인대출無·집주인대출X·무융자’처럼 반대 의미의 문구는 제외했고,
        ‘대출 6억 가능’처럼 매수인이 받을 수 있는 한도를 뜻하는 문구, 분양권·입주권의
        중도금·분담금 대출승계, 시행사의 잔금유예 조건도 성격이 달라 뺐습니다.
        설명 문구 기반이므로 실제 조건과 다를 수 있어 참고용으로만 사용하시고,
        계약 전 반드시 해당 중개사무소에 확인하시기 바랍니다.
      </div>
    </div>
  );
}
