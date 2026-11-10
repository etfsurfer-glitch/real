// 남이 쓰던 매물장 엑셀 → 우리 사무실 매물장.
//
// 서식이 제각각이라 '이 양식으로 맞춰 오세요'는 답이 아니다. 아무 파일이나 받아 읽고,
// **무엇을 어떻게 읽었는지 먼저 보여 준 다음** 사람이 확인하면 저장한다. 열 인식이
// 틀렸으면 그 자리에서 바꿀 수 있어야 한다 — 안 그러면 잘못 담고 나서야 알게 된다.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Upload, X, Loader2, FileSpreadsheet, Check, AlertTriangle, Copy } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Col = { index: number; header: string; field: string; label: string; unit: string;
  by: string; kind?: string; sample: string[] };
type Row = Record<string, any> & { _row?: number; _dup?: string };
type Sheet = { name: string; header_row: number; columns: Col[]; rows: Row[];
  skipped: { row: number; why: string; text: string }[]; n_skipped: number; n_dup: number;
  n_merged?: number; n_split?: number;
  cut?: number; stopped_at?: number; needs_complex?: boolean; complex_hint?: string; n_nowhere?: number };
type Preview = { sheets: Sheet[]; filename: string; fields: { key: string; label: string }[];
  needs_complex?: boolean; complex_hint?: string };

const won = (v: any): string => {
  const n = Number(v);
  if (!n) return "";
  if (n >= 1e8) {
    const e = Math.floor(n / 1e8), m = Math.round((n % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`;
  }
  return `${Math.round(n / 1e4).toLocaleString()}만`;
};
// 미리보기 표에 세울 칸 — 중개사가 눈으로 대조하는 순서대로
const SHOW: [string, string][] = [
  ["type", "종류"], ["trade_type", "거래"], ["complex_name", "단지·건물"], ["address", "주소"],
  ["dong", "동"], ["ho", "호"], ["price", "매매가"], ["deposit", "보증금"], ["rent_price", "월세"],
  ["premium", "권리금"], ["area2_m2", "전용"], ["floor_info", "층"], ["contact", "연락처"],
  ["owner_name", "소유자"], ["manager", "담당"], ["memo", "비고"],
];
const MONEY = new Set(["price", "deposit", "rent_price", "premium", "maintenance_fee", "loan_amount"]);

function cellText(r: Row, k: string): string {
  const v = r[k];
  if (v === undefined || v === null || v === "") return "";
  if (MONEY.has(k)) return won(v);
  if (k === "area2_m2") return `${Math.round(Number(v) / 3.3058)}평(${Number(v)}㎡)`;
  return String(v);
}

export default function ImportListings({ authH, onClose, onSaved }: {
  authH: () => Record<string, string>; onClose: () => void; onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [prev, setPrev] = useState<Preview | null>(null);
  const [si, setSi] = useState(0);                     // 고른 시트
  const [drop, setDrop] = useState(false);
  const [skipDup, setSkipDup] = useState(true);        // 이미 있는 것은 빼고 담는다
  // 엑셀로 담은 매물은 늘 사무실 매물장으로 간다. 숨기는 길은 대표가 거기서
  // 비공개매물장으로 보내는 하나뿐 — 가져오기 화면에서 공개범위를 고르게 하지 않는다.
  const [off, setOff] = useState<Set<number>>(new Set());   // 사람이 뺀 줄
  const [done, setDone] = useState<{ saved: number; skipped: number } | null>(null);
  // 담은 직후 건축물대장으로 빈 칸을 채우며 검증한다 — 나중에 따로 돌릴 일이 아니다.
  const [fill, setFill] = useState<{ done: number; total: number; ok: number } | null>(null);
  const fillStop = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef("");
  // 올린 파일을 들고 있는다 — 열 매핑을 고치면 **다시 읽어야** 값도 따라 바뀐다.
  // 화면에서 값만 옮기면 금액 단위 계산이 어긋난다.
  const rawRef = useRef<File | null>(null);
  // 단지가 특정되지 않은 매물장(행마다 단지명이 없는 단일 단지 파일)은 담기 전에
  // 사용자가 단지를 고르게 한다 — 안 그러면 단지명 없는 매물이 쌓인다.
  const [cxQ, setCxQ] = useState("");
  const [cxHits, setCxHits] = useState<{ complex_no: string; complex_name: string; where?: string }[]>([]);
  const [cxPick, setCxPick] = useState<{ complex_no: string; complex_name: string } | null>(null);
  const [cxBusy, setCxBusy] = useState(false);
  const ovrRef = useRef<Record<string, { fields: Record<string, string>; units: Record<string, string> }>>({});

  const sheet = prev?.sheets[si] || null;
  // 시트마다 단지가 다르다(단지별 시트 매물장) — 시트를 바꾸면 고른 단지를 풀고 그 시트 이름을 힌트로
  const sheetNeedsCx = !!(sheet?.needs_complex ?? prev?.needs_complex);
  useEffect(() => { setCxPick(null); setCxHits([]); setCxQ(sheet?.needs_complex ? (sheet?.complex_hint || "") : ""); }, [si, sheet?.name]);   // eslint-disable-line react-hooks/exhaustive-deps

  const upload = useCallback(async (f: File, keepOvr = false) => {
    setBusy(true); setErr(""); setDone(null);
    if (!keepOvr) { setPrev(null); setOff(new Set()); ovrRef.current = {}; }
    nameRef.current = f.name; rawRef.current = f;
    try {
      const fd = new FormData();
      fd.append("file", f);
      if (keepOvr) fd.append("mapping", JSON.stringify(ovrRef.current));
      const r = await fetch(`${API_BASE}/lounge/import/preview`,
        { method: "POST", headers: authH(), body: fd });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `읽지 못했어요 (${r.status})`);
      setPrev(d); if (!keepOvr) setSi(0);
      if (!keepOvr) {
        setCxPick(null); setCxHits([]);
        setCxQ(d?.needs_complex ? (d?.complex_hint || "") : "");
      }
    } catch (e: any) {
      setErr(e.message || "읽지 못했어요");
    } finally { setBusy(false); }
  }, [authH]);

  // 열 인식을 사람이 바꾼다 — 자동이 틀렸을 때 여기서 고치지 못하면 파일을 못 쓴다.
  // 고치면 그 열의 값을 다시 읽어야 하므로 파일째 다시 올린다(파일은 손에 있다).
  const tweak = (colIndex: number, patch: { field?: string; unit?: string }) => {
    if (!sheet || !rawRef.current) return;
    const cur = ovrRef.current[sheet.name] || { fields: {}, units: {} };
    if (patch.field !== undefined) cur.fields[String(colIndex)] = patch.field;
    if (patch.unit !== undefined) cur.units[String(colIndex)] = patch.unit;
    ovrRef.current[sheet.name] = cur;
    setOff(new Set());
    upload(rawRef.current, true);
  };

  const cxSearch = async (kw: string) => {
    const q = kw.trim();
    if (q.length < 2) { setCxHits([]); return; }
    setCxBusy(true);
    try {
      const r = await fetch(`${API_BASE}/lounge/complex-search?q=${encodeURIComponent(q)}`,
        { headers: authH() });
      const d = await r.json().catch(() => null);
      setCxHits(r.ok ? (d?.items || []) : []);
    } catch { setCxHits([]); } finally { setCxBusy(false); }
  };

  const rows = sheet?.rows || [];
  const needCx = sheetNeedsCx && !cxPick;

  const picked = useMemo(() => rows.filter((r, i) => !off.has(i) && !(skipDup && r._dup)),
    [rows, off, skipDup]);

  const commit = async () => {
    if (!picked.length) return;
    if (needCx) { setErr("어느 단지의 매물장인지 먼저 골라 주세요."); return; }
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/lounge/import/commit`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({
          rows: picked, filename: nameRef.current, visibility: "office",
          complex_no: cxPick?.complex_no, complex_name: cxPick?.complex_name,
        }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `담지 못했어요 (${r.status})`);
      setDone({ saved: d.saved || 0, skipped: d.n_skipped || 0 });
      onSaved();
      await enrich(d.ids || []);
    } catch (e: any) {
      setErr(e.message || "담지 못했어요");
    } finally { setBusy(false); }
  };

  // 담은 행을 한 건씩 보강한다. 한 번에 몰면 외부 API(국토부) 응답을 기다리다
  // 게이트웨이가 끊는다. 실패한 건은 건너뛰고 계속 간다.
  const enrich = async (ids: number[]) => {
    if (!ids.length) return;
    fillStop.current = false;
    setFill({ done: 0, total: ids.length, ok: 0 });
    let ok = 0;
    for (let i = 0; i < ids.length; i++) {
      if (fillStop.current) break;
      try {
        const r = await fetch(`${API_BASE}/lounge/private-listings/${ids[i]}/enrich`, {
          method: "POST", headers: { ...authH(), "Content-Type": "application/json" }, body: "{}",
        });
        const d = await r.json().catch(() => null);
        if (d?.filled?.length) ok++;
      } catch { /* 한 건 실패가 전체를 멈추지 않는다 */ }
      setFill({ done: i + 1, total: ids.length, ok });
    }
    setFill(null);
    onSaved();
  };

  return (
    <div className="imp-back" onClick={onClose}>
      <div className="imp" onClick={(e) => e.stopPropagation()}>
        <div className="imp-h">
          <h3><Upload size={16} strokeWidth={2.3} /> 사무실 매물장으로 가져오기</h3>
          <button className="imp-x" onClick={onClose} aria-label="닫기"><X size={16} /></button>
        </div>

        {done ? (
          <div className="imp-done">
            <Check size={30} />
            <b>{done.saved.toLocaleString()}건을 사무실 매물장에 담았어요</b>
            {done.skipped > 0 && <span>{done.skipped}건은 이미 있는 매물이라 건너뛰었어요.</span>}
            {fill ? (
              <div className="imp-fill">
                <span>건축물대장으로 빈 칸 채우는 중… <b>{fill.done}/{fill.total}</b> · 채움 {fill.ok}건</span>
                <button onClick={() => { fillStop.current = true; }}>중단</button>
              </div>
            ) : (
              <span className="imp-done-s">전용면적·층은 건축물대장에서 확인해 채웠습니다.</span>
            )}
            <span className="imp-done-s">
              가져온 매물은 사무실 매물장에서 <i className="imp-chip"><FileSpreadsheet size={9} /></i> 표시로 구분됩니다.
            </span>
            <button className="imp-go" onClick={onClose}>사무실 매물장으로</button>
          </div>
        ) : !prev ? (
          <>
            <div className={"imp-drop" + (drop ? " on" : "")}
              onDragOver={(e) => { e.preventDefault(); setDrop(true); }}
              onDragLeave={() => setDrop(false)}
              onDrop={(e) => {
                e.preventDefault(); setDrop(false);
                const f = e.dataTransfer.files?.[0]; if (f) upload(f);
              }}
              onClick={() => fileRef.current?.click()}>
              {busy ? <Loader2 size={26} className="txm-spin" /> : <FileSpreadsheet size={26} />}
              <b>{busy ? "읽는 중…" : "엑셀 파일을 끌어다 놓거나 눌러서 고르세요"}</b>
              <span>.xlsx · .xls · .csv — 쓰시던 매물장 그대로 올리시면 됩니다</span>
              <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.xls,.csv,.txt" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
            </div>
            <div className="imp-help">
              <b>양식을 맞추실 필요 없습니다.</b>
              <ul>
                <li>열 이름을 보고 알아서 맞춥니다 — <i>단지·물건지·매가·전용·보증금</i> 같은 말을 읽습니다.</li>
                <li>이름이 없거나 낯설면 <i>값의 생김새</i>로 찾습니다(전화번호·층 표기·거래유형).</li>
                <li>제목 줄이 위에 있어도, 동·호가 한 칸이어도, 셀이 병합돼 있어도 읽습니다.</li>
                <li>금액 단위(억·만원·원)는 열마다 알아서 정하고 <b>무엇으로 읽었는지 보여 드립니다.</b></li>
                <li>담기 전에 미리보기로 확인하시고, 틀린 열은 그 자리에서 바꾸실 수 있습니다.</li>
              </ul>
            </div>
            {err && <p className="imp-err"><AlertTriangle size={13} /> {err}</p>}
          </>
        ) : (
          <>
            {prev.sheets.length > 1 && (
              <div className="imp-sheets">
                {prev.sheets.map((sh, i) => (
                  <button key={sh.name} className={i === si ? "on" : ""} onClick={() => { setSi(i); setOff(new Set()); }}>
                    {sh.name} <em>{sh.rows.length}</em>
                  </button>
                ))}
              </div>
            )}

            {sheet && (
              <>
                <div className="imp-sum">
                  <b>{sheet.rows.length.toLocaleString()}건</b>을 읽었어요
                  {sheet.header_row > 0 && <i>머리글 {sheet.header_row}행</i>}
                  {sheet.n_dup > 0 && <i className="dup"><Copy size={10} /> 이미 있는 것 {sheet.n_dup}건</i>}
                  {sheet.n_skipped > 0 && <i className="skip">건너뜀 {sheet.n_skipped}건</i>}
                  {/* 양식 차이를 어떻게 폈는지 숨기지 않는다 — 건수가 안 맞으면 바로 의심하게 된다 */}
                  {!!sheet.n_merged && <i className="skip" title="같은 집의 메모 줄을 그 매물에 합쳤습니다">메모줄 합침 {sheet.n_merged}건</i>}
                  {!!sheet.n_split && <i className="skip" title="한 줄에 매매가와 전세가가 같이 있어 매물 둘로 나눴습니다">매매·전세 나눔 {sheet.n_split}건</i>}
                </div>
                {/* 못 읽은 것을 조용히 넘기지 않는다 — 안 알리면 '다 가져왔다'로 읽힌다 */}
                {!!sheet.stopped_at && (
                  <p className="imp-warn"><AlertTriangle size={13} />
                    {sheet.stopped_at}행부터 <b>열 구성이 다른 표</b>가 시작돼 거기까지만 읽었어요.
                    아래 표는 시트를 나눠서 따로 올려 주세요.
                  </p>
                )}
                {!!sheet.cut && (
                  <p className="imp-warn"><AlertTriangle size={13} />
                    너무 길어 뒤쪽 <b>{sheet.cut.toLocaleString()}줄</b>은 읽지 않았어요. 나눠서 올려 주세요.
                  </p>
                )}

                {/* 열을 어떻게 읽었는지 — 여기가 이 화면의 핵심이다. 틀렸으면 바꾼다 */}
                {sheetNeedsCx && (
                  <div className={"imp-cx" + (cxPick ? " done" : "")}>
                    {cxPick ? (
                      <div className="imp-cx-done">
                        <b>{cxPick.complex_name}</b> 매물로 담습니다
                        <button onClick={() => { setCxPick(null); setCxHits([]); }}>바꾸기</button>
                      </div>
                    ) : (
                      <>
                        <div className="imp-cx-head">
                          이 시트에는 줄마다 단지명이 없어요{sheet?.n_nowhere ? ` (${sheet.n_nowhere}건)` : ""} — <b>어느 단지의 매물장인지 골라 주세요.</b> 시트 이름을 미리 넣어 뒀어요.
                        </div>
                        <div className="imp-cx-find">
                          <input
                            value={cxQ}
                            placeholder="단지명으로 찾기 (예: 칸타빌)"
                            onChange={(e) => setCxQ(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") cxSearch(cxQ); }}
                          />
                          <button onClick={() => cxSearch(cxQ)} disabled={cxBusy || cxQ.trim().length < 2}>
                            {cxBusy ? "찾는 중" : "찾기"}
                          </button>
                        </div>
                        {cxHits.length > 0 && (
                          <ul className="imp-cx-hits">
                            {cxHits.map((h) => (
                              <li key={h.complex_no}>
                                <button onClick={() => { setCxPick(h); setErr(""); }}>
                                  <b>{h.complex_name}</b>
                                  {h.where && <i>{h.where}</i>}
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                        {!cxBusy && cxQ.trim().length >= 2 && cxHits.length === 0 && (
                          <div className="imp-cx-none">
                            못 찾았어요. 지역을 함께 적어 보세요 (예: 아산 칸타빌).
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                <div className="imp-cols">
                  {sheet.columns.map((c) => (
                    <label key={c.index} className={"imp-col by-" + (c.by === "이름" ? "name" : c.by === "값" ? "val" : "guess")}>
                      <span className="imp-col-h">{c.header || `${c.index + 1}번째 열`}</span>
                      <select value={c.field} onChange={(e) => tweak(c.index, { field: e.target.value })}>
                        <option value="">안 가져옴</option>
                        {prev.fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                      </select>
                      <span className="imp-col-s">
                        {/* 단위는 가장 틀리기 쉬운 곳이다 — 무엇으로 읽었는지 보이고 바꿀 수 있게 */}
                        {c.kind === "money" && (
                          <select className="u" value={c.unit}
                            onChange={(e) => tweak(c.index, { unit: e.target.value })}>
                            <option value="auto">단위 자동</option>
                            <option value="억">억 단위</option>
                            <option value="만">만원 단위</option>
                            <option value="원">원 단위</option>
                          </select>
                        )}
                        {c.kind === "area" && (
                          <select className="u" value={c.unit}
                            onChange={(e) => tweak(c.index, { unit: e.target.value })}>
                            <option value="㎡">㎡</option>
                            <option value="평">평</option>
                          </select>
                        )}
                        <em className="by">{c.by}</em>
                        {c.sample.length > 0 && <em className="ex">{c.sample.join(" · ")}</em>}
                      </span>
                    </label>
                  ))}
                </div>

                <div className="imp-opts">
                  <label><input type="checkbox" checked={skipDup}
                    onChange={(e) => setSkipDup(e.target.checked)} /> 이미 사무실 매물장에 있는 것은 빼고 담기</label>
                </div>

                <div className="imp-tbl">
                  <table>
                    <thead>
                      <tr>
                        <th className="ck"></th>
                        {SHOW.filter(([k]) => sheet.rows.some((r) => r[k] !== undefined && r[k] !== null && r[k] !== ""))
                          .map(([k, lb]) => <th key={k}>{lb}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.slice(0, 200).map((r, i) => {
                        const skipped = off.has(i) || (skipDup && !!r._dup);
                        return (
                          <tr key={i} className={skipped ? "off" : ""} title={r._dup || ""}>
                            <td className="ck">
                              <input type="checkbox" checked={!skipped} disabled={skipDup && !!r._dup}
                                onChange={() => setOff((s) => {
                                  const n = new Set(s); n.has(i) ? n.delete(i) : n.add(i); return n;
                                })} />
                            </td>
                            {SHOW.filter(([k]) => sheet.rows.some((x) => x[k] !== undefined && x[k] !== null && x[k] !== ""))
                              .map(([k]) => <td key={k}>{cellText(r, k)}</td>)}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {rows.length > 200 && <p className="imp-more">아래 {rows.length - 200}건은 화면에만 줄였어요 — 담을 땐 전부 들어갑니다.</p>}
                </div>

                {sheet.skipped.length > 0 && (
                  <details className="imp-skip">
                    <summary>건너뛴 {sheet.n_skipped}건 — 왜 건너뛰었는지</summary>
                    <ul>
                      {sheet.skipped.map((s, i) => (
                        <li key={i}><b>{s.row}행</b> {s.why}{s.text ? ` — ${s.text}` : ""}</li>
                      ))}
                    </ul>
                  </details>
                )}

                {err && <p className="imp-err"><AlertTriangle size={13} /> {err}</p>}
                <div className="imp-foot">
                  <button className="imp-again" onClick={() => { setPrev(null); setErr(""); }}>다른 파일</button>
                  <button className="imp-save" onClick={commit} disabled={busy || !picked.length || needCx}>
                    {busy ? <Loader2 size={14} className="txm-spin" /> : <Check size={14} />}
                    {picked.length.toLocaleString()}건 사무실 매물장에 담기
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
