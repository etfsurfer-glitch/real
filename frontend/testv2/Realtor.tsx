// 중개사무소 상세 창 — 운영 /realtor/{id} 를 지도 안에서 다시 그린다(같은 API).
import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { Stars, getJson, API } from "./Drawer";
import { Seg } from "./Stats";
import { LoginBox, authHeaders } from "./Request";
import { areaLabel } from "../src/lib/area";

type Detail = {
  realtor_id: string; realtor_name: string | null; total_count: number;
  listing_breakdown?: Record<string, number> & { total: number; complex: number };
  trade_totals?: { A1: number; B1: number; B2: number };
  rep_rank?: { type: string; type_key: string; count: number; national_rank: number; national_total: number; sido_name: string | null; sido_rank: number | null } | null;
  total_rank?: { count: number; national_rank: number; national_total: number } | null;
  by_sido: { sido_code: string; sido_name: string; count: number; rank: number; total_in_sido: number }[];
  by_complex: { complex_no: string | null; complex_name: string | null; A1: number; B1: number; B2: number; total: number }[];
  vworld: { match_type: string; sys_regno: string | null; representative: string | null; address: string | null; phone: string | null; status: string | null; registered_ymd: string | null; ra_regno: string | null;
    candidates: { sys_regno: string; name: string | null; rep: string | null }[]; employees?: { licensed: number; assistant: number; total: number } } | null;
  naver: { name: string | null; representative: string | null; address: string | null; tel: string | null; cell: string | null; homepage: string | null } | null;
};
type Lst = { article_no: string; complex_no: string | null; complex_name: string | null; trade_type: string; type: string; area_name: string; area2_m2: number; floor_info: string; direction: string;
  price_text: string; rent_price_text: string; confirm_ymd: string; building_name: string; naver_url: string; address: string };
type Review = { id: number; author_name: string; is_admin: boolean; review_type: string; verified: boolean; rating: number | null; body: string; created_at: string };
const CATS: [string, string, string][] = [["전체", "", "total"], ["단지형", "단지형", "complex"], ["빌라", "빌라", "villa"], ["단독", "단독", "house"], ["상가", "상가", "sangga"], ["사무실", "사무실", "office"],
  ["빌딩", "빌딩", "building"], ["토지", "토지", "land"], ["공장", "공장", "factory"], ["지식산업센터", "지식산업센터", "knowledge"], ["재개발", "재개발", "redev"], ["원룸", "원룸", "oneroom"]];
const tel = (s: string | null | undefined) => { const f = (s || "").split(/\s+/)[0].replace(/[^\d]/g, ""); return f.length >= 7 ? f : null; };
const ymd = (s: string) => (s && s.length === 8 ? `${s.slice(4, 6)}.${s.slice(6, 8)}` : s);

export function RealtorWindow({ id, onClose, phone, session, onGo, onMe }: {
  id: string; onClose: () => void; phone: boolean; session: Session | null; onGo: (no: string, name: string) => void; onMe: () => void;
}) {
  const [d, setD] = useState<Detail | null | undefined>(undefined);
  const [rv, setRv] = useState<{ summary: { avg_rating: number | null; verified_count: number; total_count: number }; items: Review[] } | null>(null);
  const [staff, setStaff] = useState<{ count: number; as_of: string | null; items: { name: string; role: string | null; position: string | null; status: string | null }[] } | null | undefined>(undefined);
  const [cat, setCat] = useState(""); const [trade, setTrade] = useState(""); const [sort, setSort] = useState("confirm"); const [q, setQ] = useState("");
  const [lst, setLst] = useState<Lst[] | null>(null); const [shown, setShown] = useState(30);
  const [body, setBody] = useState(""); const [posting, setPosting] = useState(false); const [perr, setPerr] = useState("");
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h);
  }, [onClose]);
  useEffect(() => {
    setD(undefined); setRv(null); setStaff(undefined); setCat(""); setTrade(""); setQ("");
    getJson(`/realtor/${encodeURIComponent(id)}`).then(setD).catch(() => setD(null));
    loadRv();
  }, [id]);   // eslint-disable-line react-hooks/exhaustive-deps
  const loadRv = () => getJson(`/realtor/${encodeURIComponent(id)}/reviews`).then(setRv).catch(() => setRv({ summary: { avg_rating: null, verified_count: 0, total_count: 0 }, items: [] }));
  useEffect(() => {
    let alive = true; setLst(null); setShown(30);
    getJson(`/realtor/${encodeURIComponent(id)}/listings?${new URLSearchParams({ cat, trade, sort, limit: "1500" })}`).then((j) => { if (alive) setLst(j.listings || []); }).catch(() => { if (alive) setLst([]); });
    return () => { alive = false; };
  }, [id, cat, trade, sort]);
  const openStaff = () => { if (staff !== undefined) { setStaff(undefined); return; } setStaff(null); getJson(`/realtor/${encodeURIComponent(id)}/staff`).then(setStaff).catch(() => setStaff({ count: 0, as_of: null, items: [] })); };
  const post = async () => {
    if (!session || !body.trim()) return; setPosting(true); setPerr("");
    try {
      const r = await fetch(`${API}/realtor/${encodeURIComponent(id)}/reviews`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) }, body: JSON.stringify({ body: body.trim() }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : r.status === 409 ? "닉네임을 먼저 정해야 해요(내 정보)." : "남기지 못했어요");
      setBody(""); loadRv();
    } catch (e: any) { setPerr(e.message); } finally { setPosting(false); }
  };

  const ql = q.trim();
  const filtered = useMemo(() => (lst || []).filter((l) => !ql || (l.complex_name || "").includes(ql) || (l.building_name || "").includes(ql) || (l.address || "").includes(ql) || (l.area_name || "").includes(ql)), [lst, ql]);
  const tt = d?.trade_totals ?? { A1: 0, B1: 0, B2: 0 };
  const gt = tt.A1 + tt.B1 + tt.B2;
  const regYear = d?.vworld?.registered_ymd ? parseInt(String(d.vworld.registered_ymd).replace(/[^\d]/g, "").slice(0, 4), 10) : null;
  const tenure = regYear && regYear > 1900 ? new Date().getFullYear() - regYear + 1 : null;
  const emp = d?.vworld?.employees;
  const licPct = emp && emp.total > 0 ? Math.round((emp.licensed / emp.total) * 100) : null;
  const office = d?.vworld?.phone || d?.naver?.tel || null; const cell = d?.naver?.cell || null;
  const rep = d?.vworld?.representative || d?.naver?.representative || null;
  const addr = d?.vworld?.address || d?.naver?.address || null;
  const matched = !!d?.vworld?.sys_regno && !d.vworld.match_type.startsWith("multi") && d.vworld.match_type !== "none";
  const bd = d?.listing_breakdown;

  return (
    <section className={"t2-win" + (phone ? " phone" : "")} role="dialog" aria-label="중개사무소">
      <header className="t2-win-h">
        <button className="t2-win-x" onClick={onClose} aria-label="지도로 돌아가기"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>지도</button>
        <h2>중개사무소</h2>
      </header>
      <div className="t2-win-b">
        <div className="t2-win-in">
          {d === undefined ? <div className="t2-sload"><i /><i /><i /></div> : d === null ? <p className="t2-sempty">중개사무소를 찾을 수 없어요.</p> : (
            <>
              <div className="t2-rth">
                <div>
                  <h3 className="t2-win-ttl">{d.realtor_name ?? d.realtor_id}{d.vworld?.status && <small className={d.vworld.status.startsWith("영업") ? "ok" : "warn"}>{d.vworld.status}</small>}</h3>
                  <p className="t2-favmeta">{[rep ? `대표 ${rep}` : "", matched && d.vworld?.ra_regno ? `등록 ${d.vworld.ra_regno}` : "", addr || ""].filter(Boolean).join(" · ")}</p>
                  <p className="t2-favmeta">{rv && rv.summary.total_count > 0 ? <><Stars v={rv.summary.avg_rating || 0} /> {rv.summary.avg_rating != null ? rv.summary.avg_rating.toFixed(1) : ""} · 리뷰 {rv.summary.total_count}{rv.summary.verified_count > 0 ? ` · 거래인증 ${rv.summary.verified_count}` : ""}</> : "아직 리뷰가 없어요"}</p>
                </div>
                <div className="t2-rtc">
                  {tel(office) && <a className="t2-telbtn pri" href={`tel:${tel(office)}`}>전화 {office!.split(/\s+/)[0]}</a>}
                  {tel(cell) && <a className="t2-telbtn" href={`tel:${tel(cell)}`}>휴대폰 {cell}</a>}
                </div>
              </div>
              <div className="t2-kpis">
                {d.rep_rank && <div><span>{d.rep_rank.type} 순위 <small>대표 분야</small></span><b>#{d.rep_rank.national_rank.toLocaleString()}</b><small>{d.rep_rank.count.toLocaleString()}개{d.rep_rank.type_key === "complex" ? ` · ${d.by_complex.length}개 단지` : ""} · 전국 {d.rep_rank.national_total.toLocaleString()}곳{d.rep_rank.sido_rank ? ` · ${d.rep_rank.sido_name} #${d.rep_rank.sido_rank.toLocaleString()}` : ""}</small></div>}
                {d.total_rank && <div><span>전체 매물 순위</span><b>#{d.total_rank.national_rank.toLocaleString()}</b><small>{d.total_rank.count.toLocaleString()}개 · 전국 {d.total_rank.national_total.toLocaleString()}곳</small></div>}
                {emp && emp.total > 0 && <div><span>소속 인원</span><b>{emp.total}명{licPct != null && <em> 자격증 {licPct}%</em>}</b><small>공인중개사 {emp.licensed}{emp.assistant > 0 ? ` · 중개보조 ${emp.assistant}` : ""} <button className="t2-lnk" onClick={openStaff}>{staff === undefined ? "명단 보기" : "닫기"}</button></small></div>}
                {tenure != null && <div><span>업력</span><b>{tenure}년차</b><small>개업 {regYear}년</small></div>}
              </div>
              {staff !== undefined && (
                <div className="t2-safe-sec" style={{ marginTop: 0 }}>
                  {staff === null ? <div className="t2-sload"><i /><i /></div> : (
                    <>
                      <table className="t2-tbl"><thead><tr><th>이름</th><th>구분</th><th>직위</th><th>상태</th></tr></thead>
                        <tbody>{staff.items.map((s, i) => <tr key={s.name + i}><td><b>{s.name}</b></td><td>{s.role || ""}</td><td>{s.position || ""}</td><td className="mut">{s.status || ""}</td></tr>)}{staff.items.length === 0 && <tr><td colSpan={4} className="mut">공시된 직원 정보가 없어요.</td></tr>}</tbody></table>
                      <p className="t2-snote">출처: 국가공간정보포털 부동산중개업 공시{staff.as_of ? ` · ${staff.as_of.slice(0, 10)} 기준` : ""}</p>
                    </>
                  )}
                </div>
              )}
              {bd && bd.total > 0 && (
                <p className="t2-favmeta" style={{ marginTop: 6 }}>매물 유형 · {CATS.slice(1).filter(([, , k]) => (bd[k] || 0) > 0).map(([l, , k]) => `${l} ${(bd[k] || 0).toLocaleString()}`).join(" · ")} · 전체 {bd.total.toLocaleString()}
                  {gt > 0 && <> · 매매 {tt.A1.toLocaleString()} · 전세 {tt.B1.toLocaleString()} · 월세 {tt.B2.toLocaleString()}</>}</p>
              )}
              {d.vworld && !matched && <p className="t2-snote">{d.vworld.match_type.startsWith("multi") ? `국토부 등록 사무소 후보 ${d.vworld.candidates.length}개(자동 확정 보류): ${d.vworld.candidates.map((c) => `${c.name || ""}${c.rep ? `(${c.rep})` : ""}`).join(", ")}` : "국토부 부동산중개업 등록 정보와 맞춰지지 않았어요(폐업·말소·미등록 가능)."}</p>}

              {d.by_sido.length > 1 && (
                <>
                  <div className="t2-sh"><h3>지역별 활동</h3></div>
                  <table className="t2-tbl"><thead><tr><th>지역</th><th className="num">매물</th><th className="num">지역 순위</th></tr></thead>
                    <tbody>{d.by_sido.map((s) => <tr key={s.sido_code}><td>{s.sido_name}</td><td className="num">{s.count.toLocaleString()}</td><td className="num">#{s.rank.toLocaleString()} <small>/ {s.total_in_sido.toLocaleString()}</small></td></tr>)}</tbody></table>
                </>
              )}

              <div className="t2-sh"><h3>보유 매물 <small>{lst ? `${filtered.length.toLocaleString()}개` : ""}</small></h3></div>
              <div className="t2-sbar">
                <Seg opts={CATS.filter(([, v, k]) => v === "" || (bd?.[k] || 0) > 0).map(([l, v, k]) => ({ k: v, l: v === "" ? l : `${l} ${(bd?.[k] || 0).toLocaleString()}` }))} value={cat} onChange={(v) => { setCat(v); setQ(""); }} />
                <Seg opts={[{ k: "", l: "전체" }, { k: "매매", l: "매매" }, { k: "전세", l: "전세" }, { k: "월세", l: "월세" }]} value={trade} onChange={setTrade} />
                <Seg opts={[{ k: "confirm", l: "최신확인순" }, { k: "price_desc", l: "가격 높은순" }, { k: "price_asc", l: "가격 낮은순" }]} value={sort} onChange={setSort} />
                <input className="t2-sbar-q" placeholder="단지·건물·지역 검색" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              {!lst ? <div className="t2-sload"><i /><i /><i /></div> : filtered.length === 0 ? <p className="t2-sempty">표시할 매물이 없어요.</p> : (
                <>
                  <table className="t2-tbl t2-rtl">
                    <thead><tr><th>거래</th><th>유형</th><th>단지 · 건물</th><th>면적</th><th>층</th><th>방향</th><th className="num">가격</th><th>확인</th></tr></thead>
                    <tbody>
                      {filtered.slice(0, shown).map((l) => (
                        <tr key={l.article_no} className={l.complex_no ? "pick" : ""} onClick={() => { if (l.complex_no) onGo(l.complex_no, l.complex_name || ""); else window.open(l.naver_url, "_blank", "noreferrer"); }}>
                          <td><b className={`t2-trd ${l.trade_type}`}>{l.trade_type}</b></td><td className="mut">{l.type}</td>
                          <td><b>{l.complex_name || l.building_name || l.area_name || "매물"}</b>{l.address && <small className="blk">{l.address}</small>}</td>
                          <td>{l.area2_m2 ? areaLabel(l.area2_m2) : ""}</td><td>{l.floor_info ? `${l.floor_info}층` : ""}</td><td>{l.direction || ""}</td>
                          <td className="num"><b>{l.trade_type === "월세" && l.rent_price_text ? `${l.price_text}/${l.rent_price_text}` : l.price_text}</b></td><td className="mut">{ymd(l.confirm_ymd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {shown < filtered.length && <button className="t2-more-btn" onClick={() => setShown((s) => s + 60)}>더보기 ({(filtered.length - shown).toLocaleString()}개 더)</button>}
                  <p className="t2-snote">단지형 매물은 누르면 지도의 그 단지로, 나머지는 원본 매물로 가요. 유형당 최대 1,500건.</p>
                </>
              )}

              <div className="t2-sh"><h3>리뷰 <small>{rv ? `${rv.summary.total_count}건` : ""}</small></h3></div>
              {!rv ? <div className="t2-sload"><i /></div> : rv.items.length === 0 ? <p className="t2-sempty">아직 리뷰가 없어요. 첫 리뷰를 남겨 주세요.</p> : (
                <div className="t2-revs">
                  {rv.items.map((r) => <div className="t2-rev" key={r.id}><div className="t2-rev-h"><b>{r.author_name}</b>{r.verified && <span className="t2-tag res">거래인증</span>}{r.is_admin && <span className="t2-tag">콕집</span>}{r.rating != null && <Stars v={r.rating} />}<small>{(r.created_at || "").slice(2, 10).replace(/-/g, ".")}</small></div><p>{r.body}</p></div>)}
                </div>
              )}
              {!session ? <div style={{ maxWidth: 420, marginTop: 10 }}><LoginBox why="리뷰를 남기려면 로그인이 필요해요." /></div> : (
                <div className="t2-revform">
                  <textarea rows={3} maxLength={1000} placeholder="이 사무소와 거래하거나 상담한 경험을 적어 주세요." value={body} onChange={(e) => setBody(e.target.value)} />
                  {perr && <p className="t2-err">{perr}{perr.includes("닉네임") && <> <button className="t2-lnk" onClick={onMe}>내 정보에서 정하기</button></>}</p>}
                  <button className="t2-cta1" disabled={posting || !body.trim()} onClick={post}>{posting ? "남기는 중…" : "리뷰 남기기"}</button>
                </div>
              )}
              <p className="t2-snote" style={{ marginTop: 14 }}>ID {d.realtor_id}{d.vworld?.match_type ? ` · 매칭 ${d.vworld.match_type}` : ""}{d.vworld?.registered_ymd ? ` · 등록일 ${d.vworld.registered_ymd}` : ""}</p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
