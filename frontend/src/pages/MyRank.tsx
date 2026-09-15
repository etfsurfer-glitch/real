import { useCallback, useEffect, useMemo, useState } from "react";
import { TrendingUp, RefreshCw, ExternalLink, Info, ArrowUpCircle } from "lucide-react";
import { Loading } from "../components/Loading";

const API_BASE = import.meta.env.VITE_API_BASE;

type Competitor = { realtor_name: string; verification_type: string | null; confirm_ymd: string | null };
type RankItem = {
  article_no: string; complex_no: string; complex_name: string;
  trade_type: string; area_name: string; floor_info: string; direction: string;
  price_text: string; confirm_ymd: string | null; verification_type: string | null;
  verif_label: string; cp_name: string | null; expose_left: number | null;
  feature: string | null;
  rank_in_group: number; group_size: number; same_addr_cnt: number | null; top_pct: number | null;
  bump_needed: boolean; bump_reason: "solo" | "top" | "recommended" | "verif_block";
  competitors_above: Competitor[];
  method: "collected" | "estimated"; naver_url: string;
};
type Resp = { realtor_id: string; count: number; any_estimated: boolean; items: RankItem[] };

const TRADE: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
const VERIF: Record<string, string> = {
  NDOC1: "신홍보", NDOC2: "신홍보", DOC: "구홍보", DOCV1: "구홍보", DOCV2: "구홍보",
  SITE: "현장", S_VR: "현장", OWNER: "집주인", MOBL: "집주인", NONE: "미확인",
};
const fmtYmd = (y?: string | null) => (y && y.length === 8 ? `${y.slice(4, 6)}.${y.slice(6, 8)}` : "—");

function rankColor(pos: number, size: number): string {
  if (size <= 1) return "#8A93A1";
  if (pos === 1) return "#137333";
  if (pos / size <= 0.25) return "#1A56B0";
  if (pos / size <= 0.6) return "#B45309";
  return "#B3261E";
}

type Sort = "rank" | "bump" | "stale" | "expire";
type TradeF = "all" | "A1" | "B1" | "B2";

function leftColor(d: number): string {
  if (d <= 3) return "#B3261E";
  if (d <= 7) return "#B45309";
  return "#8A93A1";
}

export function MyRankTab({ authH }: { authH: () => Record<string, string> }) {
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [tradeF, setTradeF] = useState<TradeF>("all");
  const [bumpOnly, setBumpOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("bump");
  const [bumpFrom, setBumpFrom] = useState<number>(() => {
    try { return Number(localStorage.getItem("bizRankBumpFrom")) || 2; } catch { return 2; }
  });
  const changeBumpFrom = (n: number) => {
    setBumpFrom(n); try { localStorage.setItem("bizRankBumpFrom", String(n)); } catch { /* ignore */ }
  };
  // 끌올 필요 = 끌올하면 상위 이동 가능(recommended)하고, 내 등수가 사용자가 정한 기준 이상.
  const needBump = useCallback(
    (it: RankItem) => it.bump_reason === "recommended" && it.rank_in_group >= bumpFrom,
    [bumpFrom],
  );

  const load = useCallback(() => {
    setLoading(true); setErr(false);
    fetch(`${API_BASE}/biz/my-rank?_=${Date.now()}`, { headers: authH(), cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((d: Resp) => setData(d)).catch(() => setErr(true)).finally(() => setLoading(false));
  }, [authH]);
  useEffect(() => { load(); }, [load]);

  const all = data?.items ?? [];
  const bumpCount = all.filter(needBump).length;

  const rows = useMemo(() => {
    let r = all.slice();
    if (tradeF !== "all") r = r.filter((x) => x.trade_type === tradeF);
    if (bumpOnly) r = r.filter(needBump);
    r.sort((a, b) => {
      if (sort === "bump") {
        const na = needBump(a), nb = needBump(b);
        if (na !== nb) return na ? -1 : 1;
        return a.rank_in_group - b.rank_in_group;
      }
      if (sort === "stale") return (Number(a.confirm_ymd) || 0) - (Number(b.confirm_ymd) || 0);
      if (sort === "expire") return (a.expose_left ?? 9999) - (b.expose_left ?? 9999);
      // rank
      if (a.rank_in_group !== b.rank_in_group) return a.rank_in_group - b.rank_in_group;
      return (b.group_size || 0) - (a.group_size || 0);
    });
    return r;
  }, [all, tradeF, bumpOnly, sort, needBump]);

  if (loading) return <Loading />;
  if (err) return (
    <div style={{ padding: 24, textAlign: "center", color: "#5C6673" }}>
      순위를 불러오지 못했습니다.
      <div><button className="biz-btn" style={{ marginTop: 12 }} onClick={load}>다시 시도</button></div>
    </div>
  );

  const chip = (active: boolean): React.CSSProperties => ({
    padding: "5px 11px", borderRadius: 16, fontSize: 12.5, fontWeight: 600, cursor: "pointer",
    border: `1px solid ${active ? "#1268D3" : "#D8DCE2"}`,
    background: active ? "#1268D3" : "#fff", color: active ? "#fff" : "#5C6673", whiteSpace: "nowrap",
  });

  return (
    <div style={{ padding: "6px 12px 90px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "6px 2px 2px" }}>
        <TrendingUp size={18} color="#1268D3" />
        <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0 }}>내 매물 순위</h2>
        <button aria-label="새로고침" onClick={load}
          style={{ marginLeft: "auto", background: "none", border: "none", color: "#5C6673", cursor: "pointer", padding: 6 }}>
          <RefreshCw size={16} />
        </button>
      </div>
      <p style={{ fontSize: 12, color: "#5C6673", margin: "0 2px 10px", lineHeight: 1.5 }}>
        같은 물건을 올린 중개사들 중 내 매물이 네이버 <b>랭킹순</b> 몇 등인지. <b style={{ color: "#B45309" }}>끌올 필요 {bumpCount}건</b> · 총 {all.length}건
      </p>

      {/* 필터 */}
      <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8, margin: "0 -2px 4px", alignItems: "center" }}>
        {(["all", "A1", "B1", "B2"] as TradeF[]).map((t) => (
          <button key={t} style={chip(tradeF === t)} onClick={() => setTradeF(t)}>
            {t === "all" ? "전체" : TRADE[t]}
          </button>
        ))}
        <span style={{ width: 1, height: 18, background: "#E3E6EB", flexShrink: 0 }} />
        <button style={{ ...chip(bumpOnly), borderColor: bumpOnly ? "#D97A1E" : "#D8DCE2", background: bumpOnly ? "#D97A1E" : "#fff" }} onClick={() => setBumpOnly((v) => !v)}>
          끌올 필요만
        </button>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0, fontSize: 12, color: "#5C6673", whiteSpace: "nowrap" }}>
          끌올 기준
          <select value={bumpFrom} onChange={(e) => changeBumpFrom(Number(e.target.value))}
            style={{ padding: "5px 6px", borderRadius: 9, border: "1px solid #D8DCE2", fontSize: 12.5, color: "#3A4150", background: "#fff" }}>
            {[2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}등부터</option>)}
          </select>
        </label>
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}
          style={{ marginLeft: "auto", flexShrink: 0, padding: "5px 8px", borderRadius: 9, border: "1px solid #D8DCE2", fontSize: 12.5, color: "#3A4150", background: "#fff" }}>
          <option value="bump">끌올 우선</option>
          <option value="rank">등수순</option>
          <option value="stale">확인일 오래된순</option>
          <option value="expire">잔여 적은순</option>
        </select>
      </div>

      {/* 테이블 */}
      <div style={{ background: "#fff", border: "1px solid #E3E6EB", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 52px 48px 60px", gap: 0, padding: "8px 12px", fontSize: 11, fontWeight: 700, color: "#8A93A1", borderBottom: "1px solid #E3E6EB", background: "#FAFBFC" }}>
          <span>매물</span>
          <span style={{ textAlign: "center" }}>등수</span>
          <span style={{ textAlign: "center" }}>확인</span>
          <span style={{ textAlign: "center" }}>끌올</span>
        </div>

        {rows.length === 0 && (
          <div style={{ padding: 26, textAlign: "center", color: "#8A93A1", fontSize: 13 }}>
            {all.length === 0 ? "네이버에 노출 중인 매물이 없습니다." : "조건에 맞는 매물이 없습니다."}
          </div>
        )}

        {rows.map((it) => {
          const solo = it.group_size <= 1;
          const rc = rankColor(it.rank_in_group, it.group_size);
          const isOpen = expanded === it.article_no;
          return (
            <div key={it.article_no} style={{ borderBottom: "1px solid #F0F2F5" }}>
              <div onClick={() => setExpanded(isOpen ? null : it.article_no)}
                style={{ display: "grid", gridTemplateColumns: "1fr 52px 48px 60px", alignItems: "center", padding: "9px 12px", cursor: "pointer", background: isOpen ? "#F7F9FB" : "#fff" }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#171B22", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.complex_name}</div>
                  <div style={{ fontSize: 11.5, color: "#5C6673", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {TRADE[it.trade_type] || it.trade_type} {it.price_text} · {it.floor_info}층 · {it.area_name}
                  </div>
                  <div style={{ fontSize: 11, color: "#8A93A1", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {it.cp_name && <>{it.cp_name} · </>}{it.verif_label}
                    {it.expose_left != null && <> · <span style={{ color: leftColor(it.expose_left), fontWeight: it.expose_left <= 7 ? 700 : 400 }}>잔여 {it.expose_left}일</span></>}
                  </div>
                </div>
                <div style={{ textAlign: "center", color: rc, fontWeight: 800, fontSize: 14, lineHeight: 1.1 }}>
                  {solo ? <span style={{ fontSize: 11, fontWeight: 700, color: "#8A93A1" }}>단독</span>
                    : <>{it.rank_in_group}<span style={{ fontSize: 10, fontWeight: 600, color: "#8A93A1" }}>/{it.group_size}</span></>}
                </div>
                <div style={{ textAlign: "center", fontSize: 11.5, color: "#5C6673" }}>{fmtYmd(it.confirm_ymd)}</div>
                <div style={{ textAlign: "center" }}>
                  {needBump(it)
                    ? <span style={{ display: "inline-flex", alignItems: "center", gap: 2, background: "#FDE7D3", color: "#B45309", fontWeight: 700, fontSize: 10.5, padding: "2px 6px", borderRadius: 12 }}><ArrowUpCircle size={11} />필요</span>
                    : it.rank_in_group === 1 && !solo
                      ? <span style={{ color: "#137333", fontSize: 11, fontWeight: 700 }}>1등</span>
                      : <span style={{ color: "#BCC3CC", fontSize: 12 }}>—</span>}
                </div>
              </div>

              {isOpen && (
                <div style={{ padding: "2px 14px 13px", background: "#F7F9FB" }}>
                  {it.competitors_above.length > 0 && (
                    <>
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: "#5C6673", margin: "6px 0 4px" }}>내 위 {it.competitors_above.length}곳</div>
                      <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#3A4150", lineHeight: 1.65 }}>
                        {it.competitors_above.map((c, i) => (
                          <li key={i}>{c.realtor_name}
                            <span style={{ color: "#8A93A1" }}> · {VERIF[c.verification_type || ""] || "—"} · 확인 {fmtYmd(c.confirm_ymd)}</span>
                          </li>
                        ))}
                      </ol>
                    </>
                  )}
                  {(() => {
                    if (needBump(it)) return null;  // 끌올 필요는 ⬆필요 플래그로 충분 — 별도 안내 없음
                    const belowThr = it.bump_reason === "recommended";
                    if (!belowThr && !["top", "solo", "verif_block"].includes(it.bump_reason)) return null;
                    return (
                      <div style={{ display: "flex", gap: 7, marginTop: 9, background: "#EEF2F7", borderRadius: 8, padding: "8px 10px", fontSize: 11.5, color: "#5C6673", lineHeight: 1.5 }}>
                        <Info size={13} style={{ flexShrink: 0, marginTop: 1 }} />
                        <span>
                          {belowThr && <>지금 {it.rank_in_group}/{it.group_size}등 — 끌올 기준({bumpFrom}등)보다 위라 여유 있어요.</>}
                          {it.bump_reason === "top" && <>이 물건에서 <b>1등</b>입니다.</>}
                          {it.bump_reason === "solo" && <>이 물건은 <b>나만 등록</b>했습니다(경쟁 없음).</>}
                          {it.bump_reason === "verif_block" && <>이미 오늘 확인해 확인일은 최신입니다.</>}
                        </span>
                      </div>
                    );
                  })()}
                  <a href={it.naver_url} target="_blank" rel="noreferrer"
                    style={{ display: "inline-flex", alignItems: "center", gap: 4, marginTop: 9, fontSize: 12, color: "#1268D3", textDecoration: "none" }}>
                    네이버에서 보기 <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p style={{ fontSize: 10.5, color: "#8A93A1", marginTop: 12, lineHeight: 1.5, padding: "0 2px" }}>
        ※ 랭킹순은 동순위 매물끼리 노출이 수시로 바뀝니다(네이버 회전). 정확한 등수보다 <b>상위권·끌올 필요 여부</b>로 참고하세요.
      </p>
    </div>
  );
}
