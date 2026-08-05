// 라운지 대시보드 오른쪽 캘린더 패널.
// 계약서 탭(ContractCalendar)의 축약판 — 등록·인식 기능은 빼고 '보기'만 남긴다.
// 대시보드에서 알고 싶은 건 "이번 주에 뭐가 있나"이지 계약서 업로드가 아니다.
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, ChevronRight as Arrow, Lock } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type BzEvent = {
  id: number; title: string; event_date: string; event_time: string | null;
  event_type: string; memo: string | null; contract_id: number | null;
};
type View = "week" | "month" | "year";

const TYPE_COLOR: Record<string, string> = {
  계약: "#1268d3", 중도금: "#b45309", 잔금: "#c0392b", 입주: "#1a7f4b", 만기: "#6b39c9", 기타: "#64748b",
};
const VIEWS: { v: View; label: string }[] = [
  { v: "week", label: "주간" }, { v: "month", label: "월간" }, { v: "year", label: "연간" },
];
const ymd = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const ddayOf = (date: string, today: string): number =>
  Math.round((new Date(date + "T00:00:00").getTime() - new Date(today + "T00:00:00").getTime()) / 86400000);
const ddayText = (n: number): string => (n === 0 ? "오늘" : n > 0 ? `D-${n}` : `${-n}일 전`);

export default function LoungeCalendarPanel({ authH, onOpenFull }: {
  authH: () => Record<string, string>; onOpenFull?: () => void;
}) {
  const [events, setEvents] = useState<BzEvent[]>([]);
  const [locked, setLocked] = useState(false);   // 아직 열리지 않은 기능(가오픈)
  const [loaded, setLoaded] = useState(false);
  const [view, setView] = useState<View>("week");
  const [cur, setCur] = useState(() => { const n = new Date(); return { y: n.getFullYear(), m: n.getMonth() }; });
  const [selDate, setSelDate] = useState<string | null>(null);   // 날짜 클릭 → 그 날만
  const today = ymd(new Date());

  const load = useCallback(() => {
    fetch(`${API_BASE}/biz/events`, { headers: authH() })
      .then((r) => {
        if (r.status === 401 || r.status === 403) { setLocked(true); return { events: [] }; }
        return r.ok ? r.json() : { events: [] };
      })
      .then((d) => setEvents(d.events ?? []))
      .catch(() => { /* 대시보드는 캘린더 실패로 무너지면 안 된다 */ })
      .finally(() => setLoaded(true));
  }, [authH]);
  useEffect(() => { load(); }, [load]);

  const byDate = useMemo(() => {
    const m: Record<string, BzEvent[]> = {};
    for (const e of events) (m[e.event_date] = m[e.event_date] || []).push(e);
    return m;
  }, [events]);

  // 6주 고정 그리드 — 달마다 높이가 바뀌면 옆 열 길이가 흔들린다.
  const grid = useMemo(() => {
    const first = new Date(cur.y, cur.m, 1);
    const start = new Date(first); start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start); d.setDate(start.getDate() + i);
      return { iso: ymd(d), day: d.getDate(), inMonth: d.getMonth() === cur.m, dow: d.getDay() };
    });
  }, [cur]);

  // 목록 범위 — 주간은 '고른 날(없으면 오늘)이 속한 주', 월간·연간은 그리드가 보는 달/해.
  const range = useMemo(() => {
    if (view === "week") {
      const base = new Date((selDate || today) + "T00:00:00");
      const s = new Date(base); s.setDate(base.getDate() - base.getDay());
      const e = new Date(s); e.setDate(s.getDate() + 6);
      return { from: ymd(s), to: ymd(e), label: `${s.getMonth() + 1}.${s.getDate()} ~ ${e.getMonth() + 1}.${e.getDate()}` };
    }
    if (view === "month") return { from: ymd(new Date(cur.y, cur.m, 1)), to: ymd(new Date(cur.y, cur.m + 1, 0)), label: `${cur.y}년 ${cur.m + 1}월` };
    return { from: `${cur.y}-01-01`, to: `${cur.y}-12-31`, label: `${cur.y}년` };
  }, [view, cur, selDate, today]);

  const inRange = useMemo(() =>
    events.filter((e) => e.event_date >= range.from && e.event_date <= range.to)
      .sort((a, b) => a.event_date.localeCompare(b.event_date)), [events, range]);
  // 날짜를 콕 집었으면 그 날만, 아니면 범위 전체
  const listed = selDate && view !== "year" ? inRange.filter((e) => e.event_date === selDate) : inRange;
  // 연간은 목록이 길어 월별 건수로 접는다(클릭하면 그 달 그리드로)
  const byMonth = useMemo(() => {
    const m = Array.from({ length: 12 }, () => 0);
    for (const e of inRange) m[+e.event_date.slice(5, 7) - 1]++;
    return m;
  }, [inRange]);

  const move = (delta: number) => {
    setSelDate(null);
    if (view === "year") { setCur((c) => ({ ...c, y: c.y + delta })); return; }
    setCur((c) => {
      const d = new Date(c.y, c.m + delta, 1);
      return { y: d.getFullYear(), m: d.getMonth() };
    });
  };
  const goToday = () => {
    const n = new Date();
    setCur({ y: n.getFullYear(), m: n.getMonth() }); setSelDate(null);
  };

  return (
    <div className="lcal">
      <div className="lcal-h">
        <h3><CalendarDays size={15} strokeWidth={2.3} /> 일정</h3>
        {/* 계약캘린더 탭은 아직 관리자만 있다 — 못 가는 곳으로 보내지 않는다 */}
        {onOpenFull && !locked && (
          <button className="lcal-more" onClick={onOpenFull}>캘린더 <Arrow size={12} /></button>
        )}
      </div>

      <div className="lcal-seg">
        {VIEWS.map((v) => (
          <button key={v.v} className={view === v.v ? "on" : ""}
            onClick={() => { setView(v.v); setSelDate(null); }}>{v.label}</button>
        ))}
      </div>

      <div className="lcal-nav">
        <button onClick={() => move(-1)} aria-label="이전"><ChevronLeft size={16} /></button>
        <b>{view === "year" ? `${cur.y}년` : `${cur.y}년 ${cur.m + 1}월`}</b>
        <button onClick={() => move(1)} aria-label="다음"><ChevronRight size={16} /></button>
        <button className="lcal-today" onClick={goToday}>오늘</button>
      </div>

      {view === "year" ? (
        <div className="lcal-year">
          {byMonth.map((n, i) => (
            <button key={i} className={`lcal-ym${n ? " has" : ""}`}
              onClick={() => { setCur({ y: cur.y, m: i }); setView("month"); }}>
              <span>{i + 1}월</span><b>{n || "-"}</b>
            </button>
          ))}
        </div>
      ) : (
        <div className="lcal-grid">
          {["일", "월", "화", "수", "목", "금", "토"].map((w, i) => (
            <div key={w} className={`lcal-dow${i === 0 ? " sun" : i === 6 ? " sat" : ""}`}>{w}</div>
          ))}
          {grid.map((g) => {
            const evs = byDate[g.iso] ?? [];
            return (
              <button key={g.iso}
                className={"lcal-d"
                  + (g.inMonth ? "" : " out")
                  + (g.iso === today ? " today" : "")
                  + (g.iso === selDate ? " sel" : "")
                  + (g.dow === 0 ? " sun" : g.dow === 6 ? " sat" : "")}
                onClick={() => setSelDate(g.iso === selDate ? null : g.iso)}>
                <span>{g.day}</span>
                {evs.length > 0 && (
                  <em className="lcal-dots">
                    {evs.slice(0, 3).map((e) => (
                      <i key={e.id} style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }} />
                    ))}
                  </em>
                )}
              </button>
            );
          })}
        </div>
      )}

      <div className="lcal-lh">
        <span>{selDate && view !== "year" ? `${+selDate.slice(5, 7)}월 ${+selDate.slice(8, 10)}일` : range.label}</span>
        <em>{listed.length}건</em>
        {selDate && view !== "year" && <button onClick={() => setSelDate(null)}>범위 전체</button>}
      </div>

      <div className="lcal-list">
        {!loaded && <div className="lcal-empty">불러오는 중…</div>}
        {loaded && locked && (
          <div className="lcal-empty"><Lock size={13} /> 계약 일정은 준비 중입니다. 곧 열립니다.</div>
        )}
        {loaded && !locked && listed.length === 0 && (
          <div className="lcal-empty">이 기간에 등록된 일정이 없어요.</div>
        )}
        {listed.map((e) => {
          const dd = ddayOf(e.event_date, today);
          return (
            <div key={e.id} className={`lcal-ev${dd < 0 ? " past" : ""}`}>
              <span className="lcal-ev-t" style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }}>{e.event_type}</span>
              <span className="lcal-ev-n">{e.title}</span>
              <span className="lcal-ev-d">{+e.event_date.slice(5, 7)}/{+e.event_date.slice(8, 10)}</span>
              <span className={`lcal-ev-dd${dd === 0 ? " now" : ""}`}>{ddayText(dd)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
