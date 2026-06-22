import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;
type Region = { code: string; name: string };

/** 시도 → 시군구 종속 지역필터 상태 + 쿼리스트링(&sido=/&sigungu=/&dong=).
 *  초기값은 URL 쿼리(sido/sigungu/dong)에서 1회 복원 → 우리동네 '더보기'로 넘어올 때 그 지역을 그대로 보여줌.
 *  캐스케이드 초기화(상위 변경 시 하위 비우기)는 setter 안에서만 수행 → URL 복원값이 안 지워짐. */
export function useRegionFilter() {
  const [sidos, setSidos] = useState<Region[]>([]);
  const [sigungus, setSigungus] = useState<Region[]>([]);
  const [dongs, setDongs] = useState<Region[]>([]);
  // 초기값: URL 쿼리 > localStorage(마지막 선택 기억) > 빈값. 뒤로가기·재접속 시 지역 복원.
  const init = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const _ls = (k: string) => { try { return window.localStorage.getItem("koczip:region:" + k) || ""; } catch { return ""; } };
  const _save = (k: string, v: string) => { try { window.localStorage.setItem("koczip:region:" + k, v); } catch { /* ignore */ } };
  const [sido, setSidoRaw] = useState(() => init.get("sido") || _ls("sido"));
  const [sigungu, setSigunguRaw] = useState(() => init.get("sigungu") || _ls("sigungu"));
  const [dong, setDongRaw] = useState(() => init.get("dong") || _ls("dong"));

  useEffect(() => {
    if (!API_BASE) return;
    fetch(`${API_BASE}/stats/changes/sido-list`)
      .then((r) => r.json()).then((d) => setSidos(d.items || [])).catch(() => {});
  }, []);
  useEffect(() => {
    if (!API_BASE || !sido) { setSigungus([]); return; }
    fetch(`${API_BASE}/stats/sigungu-list?sido=${sido}`)
      .then((r) => r.json()).then((d) => setSigungus(d.items || []))
      .catch(() => setSigungus([]));
  }, [sido]);
  // 동 목록 — 시군구 종속 (지도 지역 이동용). 다른 페이지는 dong 미사용이라 비파괴적.
  useEffect(() => {
    if (!API_BASE || !sigungu) { setDongs([]); return; }
    fetch(`${API_BASE}/stats/dong-list?sigungu=${sigungu}`)
      .then((r) => r.json()).then((d) => setDongs(d.items || []))
      .catch(() => setDongs([]));
  }, [sigungu]);

  // 사용자가 상위를 바꾸면 하위 초기화 + localStorage 저장(마지막 선택 기억).
  const setSido = (v: string) => { setSidoRaw(v); setSigunguRaw(""); setDongRaw(""); _save("sido", v); _save("sigungu", ""); _save("dong", ""); };
  const setSigungu = (v: string) => { setSigunguRaw(v); setDongRaw(""); _save("sigungu", v); _save("dong", ""); };
  const setDong = (v: string) => { setDongRaw(v); _save("dong", v); };

  const query = dong
    ? `&dong=${dong}`
    : sigungu ? `&sigungu=${sigungu}` : sido ? `&sido=${sido}` : "";
  return { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong, query };
}

/** 실거래 통계 필터바용 시도/시군구 셀렉트 (.filter-select 스타일). */
export function RegionSelect(r: ReturnType<typeof useRegionFilter>) {
  return (
    <>
      <label className="filter-select">
        <span>시도</span>
        <select value={r.sido} onChange={(e) => r.setSido(e.target.value)}>
          <option value="">전국</option>
          {r.sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </label>
      <label className="filter-select">
        <span>시군구</span>
        <select value={r.sigungu} onChange={(e) => r.setSigungu(e.target.value)} disabled={!r.sido}>
          <option value="">{r.sido ? "전체" : "(시도 선택)"}</option>
          {r.sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </label>
      <label className="filter-select">
        <span>읍·면·동</span>
        <select value={r.dong} onChange={(e) => r.setDong(e.target.value)} disabled={!r.sigungu}>
          <option value="">{r.sigungu ? "전체" : "(시군구 선택)"}</option>
          {r.dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
        </select>
      </label>
    </>
  );
}
