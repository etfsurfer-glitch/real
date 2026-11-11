// 중개사라운지 '명단 대조' — 사무소가 가진 입주자·소유자 명단 ↔ 지금 광고 중인 매물.
// 명단은 고객원장과 완전히 다른 저장소(roster.sqlite·별도 암호화 키)에 둔다. 이 화면은 고객원장을 읽지도 쓰지도 않는다.
// 명단은 지우지 않고 같은 명단에 새 파일을 올려 업데이트해 간다. 동의는 180일, 90일이 지나면 연장 동의를 받을 수 있다.
// 광고는 호수를 공개하지 않으므로 결과는 '그 집'이 아니라 '명단 세대가 있는 동·층에 올라온 광고'다.
import { Fragment, useCallback, useEffect, useState } from "react";

const API = import.meta.env.VITE_API_BASE;
const TRADE_L: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };

type RList = { id: number; name: string; filename: string; n_rows: number; n_linked: number; uploaded_at: string; updated_at: string | null; n_updates: number | null; ack_at: string; expires_at: string;
  state: "active" | "renewable" | "expired"; days_left: number; renew_from: string };
type Saved = { list_id: number; added: number; updated: number; same: number; n_rows: number };
type House = { article_no: string; trade: string; price: number; rent: number | null; area_name: string; excl_m2: number | null; floor_info: string; direction: string;
  n_offices: number; offices: string[]; mine: boolean; strength: string; confirm_ymd: string };
type Unit = { unit_id: number; complex_no: string; complex_name: string; dong: string; ho: string; floor: number; role: string; grade: string;
  name_masked: string; phone_masked: string; note: string; houses: House[]; type_raw: string; type_ok: boolean; types: string[]; type_note: string };
type Match = { units: Unit[]; n_units: number; n_exact: number; n_type_ok: number; n_exact_type: number; n_houses: number; n_ads: number; n_roster: number };
type Cand = { complex_no: string; name: string; addr: string; households: number; exact: boolean };
type Preview = { n_rows: number; skipped: number; fields: string[]; linked: number; complexes: { raw: string; complex_no: string; matched: string; n: number; picked: boolean; candidates: Cand[] }[];
  sample: { complex: string; dong: string; ho: string; name: string; phone: string }[] };

const FIELD_L: Record<string, string> = { complex: "단지", dongho: "동·호", dong: "동", ho: "호", name: "이름", phone: "연락처", role: "구분", note: "메모", area: "타입·면적" };
// 광고 가격은 원 단위로 온다 → 만원으로 바꿔 '5억 3,000' 꼴로
const won = (w: number | null | undefined) => {
  if (!w) return "";
  const v = Math.round(w / 10000);
  const eok = Math.floor(v / 10000), man = v % 10000;
  return eok ? `${eok}억${man ? ` ${man.toLocaleString()}` : ""}` : `${man.toLocaleString()}`;
};
const priceText = (h: House) => `${TRADE_L[h.trade] || h.trade} ${won(h.price)}${h.trade === "B2" && h.rent ? `/${Math.round(h.rent / 10000).toLocaleString()}` : ""}`;
const dongHo = (d: string, h: string) => `${/^\d+$/.test(d) ? `${d}동` : d} ${/^\d+$/.test(h) ? `${h}호` : h}`.trim();

export function RosterScreen({ authH }: { authH: () => Record<string, string> }) {
  const [lists, setLists] = useState<RList[] | null>(null);
  const [listId, setListId] = useState<number>(0);
  const [mode, setMode] = useState<"result" | "upload">("result");
  const [saved, setSaved] = useState<Saved | null>(null);
  const loadLists = useCallback(() => fetch(`${API}/lounge/roster/lists`, { headers: authH() })
    .then((r) => (r.ok ? r.json() : { items: [] })).then((j) => { setLists(j.items || []); if (!(j.items || []).length) setMode("upload"); }).catch(() => setLists([])), [authH]);
  useEffect(() => { loadLists(); }, [loadLists]);

  return (
    <div className="kokm">
      <div className="kokm-head">
        <div><h1>명단 대조</h1><p>우리 사무소가 가진 입주자·소유자 명단에서, 지금 광고가 올라온 동·층의 세대를 찾아요. 명단은 새 파일로 계속 업데이트하고, 고객원장과 따로 보관해 우리 사무소에만 보여요.</p></div>
        <div className="kokm-bar" style={{ flex: "none" }}>
          {mode === "result"
            ? <button className="kokm-lnk" onClick={() => { setSaved(null); setMode("upload"); }}>명단 올리기 · 업데이트</button>
            : (lists && lists.length > 0 && <button className="kokm-lnk mut" onClick={() => setMode("result")}>결과로 돌아가기</button>)}
        </div>
      </div>
      {mode === "upload"
        ? <Upload authH={authH} lists={lists || []} onDone={(r) => { setSaved(r); setListId(r.list_id); setMode("result"); loadLists(); }} />
        : <>
            {saved && <p className="kokm-note">반영했어요 — 새 세대 {saved.added.toLocaleString()} · 바뀐 세대 {saved.updated.toLocaleString()} · 그대로 {saved.same.toLocaleString()} (명단 전체 {saved.n_rows.toLocaleString()}세대). 동의 기간은 오늘부터 180일로 새로 열렸어요.</p>}
            <Lists lists={lists} listId={listId} setListId={setListId} authH={authH} reload={loadLists} />
            {lists && lists.length > 0 && <Result authH={authH} listId={listId} />}
          </>}
    </div>
  );
}

function Lists({ lists, listId, setListId, authH, reload }: { lists: RList[] | null; listId: number; setListId: (n: number) => void; authH: () => Record<string, string>; reload: () => void }) {
  if (!lists) return <p className="muted kokm-pad">불러오는 중…</p>;
  if (!lists.length) return null;
  const [renewing, setRenewing] = useState<RList | null>(null);
  const del = async (l: RList) => {
    if (!window.confirm(`'${l.name}' 명단을 지울까요? 이름·연락처까지 바로 지워지고 되돌릴 수 없어요.`)) return;
    const r = await fetch(`${API}/lounge/roster/lists/${l.id}`, { method: "DELETE", headers: authH() });
    if (r.ok) { if (listId === l.id) setListId(0); reload(); }
  };
  const stateText = (l: RList) => l.state === "expired" ? <span style={{ color: "#c62828", fontWeight: 700 }}>기간 지남 · 대조 멈춤</span>
    : l.state === "renewable" ? <span style={{ color: "#b26a00", fontWeight: 700 }}>연장 가능 · {l.days_left}일 남음</span>
    : <span>사용 중 · {l.days_left}일 남음<small className="blk">연장은 {l.renew_from}부터</small></span>;
  return (
    <table className="kokm-tbl">
      <thead><tr><th>명단</th><th className="num">세대</th><th className="num">단지 연결</th><th>마지막 업데이트</th><th>동의 기간</th><th></th></tr></thead>
      <tbody>
        <tr className={listId === 0 ? "" : "off"}><td><button className="kokm-lnk" onClick={() => setListId(0)}>전체 명단 합쳐 보기</button></td>
          <td className="num">{lists.reduce((s, l) => s + l.n_rows, 0).toLocaleString()}</td><td className="num">{lists.reduce((s, l) => s + l.n_linked, 0).toLocaleString()}</td><td></td><td></td><td></td></tr>
        {lists.map((l) => (
          <Fragment key={l.id}><tr className={listId === l.id ? "" : "off"}>
            <td><button className="kokm-lnk" onClick={() => setListId(l.id)}>{l.name}</button>{l.filename && l.filename !== l.name && <small className="blk">{l.filename}</small>}</td>
            <td className="num">{l.n_rows.toLocaleString()}</td><td className="num">{l.n_linked.toLocaleString()}</td>
            <td>{(l.updated_at || l.uploaded_at).slice(0, 10)}<small className="blk">처음 {l.uploaded_at.slice(0, 10)}{l.n_updates ? ` · ${l.n_updates}번 업데이트` : ""}</small></td>
            <td>{stateText(l)}<small className="blk">~ {l.expires_at.slice(0, 10)}</small></td>
            <td className="act">{l.state !== "active" && <button className="kokm-lnk" onClick={() => setRenewing(l)}>연장 동의</button>}<button className="kokm-lnk mut" onClick={() => del(l)}>지우기</button></td>
          </tr>
          {renewing?.id === l.id && <tr className="kokm-edit"><td colSpan={6}><Renew authH={authH} l={l} onDone={() => { setRenewing(null); reload(); }} onCancel={() => setRenewing(null)} /></td></tr>}</Fragment>
        ))}
      </tbody>
    </table>
  );
}

function Result({ authH, listId }: { authH: () => Record<string, string>; listId: number }) {
  const [m, setM] = useState<Match | null>(null);
  const [err, setErr] = useState("");
  const [others, setOthers] = useState(false);
  const [grade, setGrade] = useState<"all" | "exact">("exact");
  const [open, setOpen] = useState<Record<number, { name: string; phone: string }>>({});
  useEffect(() => {
    setM(null); setErr("");
    fetch(`${API}/lounge/roster/match?list_id=${listId}&others=${others ? 1 : 0}`, { headers: authH() })
      .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "불러오지 못했어요"); return r.json(); })
      .then(setM).catch((e) => setErr(String(e.message || e)));
  }, [authH, listId, others]);
  const reveal = async (u: Unit) => {
    const r = await fetch(`${API}/lounge/roster/reveal/${u.unit_id}`, { method: "POST", headers: authH() });
    if (r.ok) { const j = await r.json(); setOpen((o) => ({ ...o, [u.unit_id]: j })); }
  };
  if (err) return <p className="kokm-gate">{err}</p>;
  if (!m) return <p className="muted kokm-pad">광고와 맞춰 보는 중…</p>;
  const rows = m.units.filter((u) => grade === "all" || u.grade === "층 일치");
  return (
    <div className="kokm-sec">
      <div className="kokm-kpi audit">
        <div><b>{m.n_roster.toLocaleString()}</b><span>단지 연결된 세대</span></div>
        <div><b>{m.n_units.toLocaleString()}</b><span>광고가 걸린 세대<small>같은 동 · 같은 층(대)</small></span></div>
        <div className="good"><b>{m.n_exact.toLocaleString()}</b><span>층 일치<small>광고 층 숫자가 같음</small></span></div>
        <div className={m.n_exact_type ? "good" : ""}><b>{m.n_exact_type.toLocaleString()}</b><span>층·타입 일치<small>명단 타입과 광고 타입이 같음</small></span></div>
        <div><b>{(m.n_units - m.n_exact).toLocaleString()}</b><span>층대만 일치<small>광고가 고·중·저로만 나옴</small></span></div>
      </div>
      <div className="kokm-filters">
        <span className="kokm-seg">
          <button className={grade === "exact" ? "on" : ""} onClick={() => setGrade("exact")}>층 일치만</button>
          <button className={grade === "all" ? "on" : ""} onClick={() => setGrade("all")}>층대까지</button>
        </span>
        <span className="kokm-seg">
          <button className={!others ? "on" : ""} onClick={() => setOthers(false)}>모든 광고</button>
          <button className={others ? "on" : ""} onClick={() => setOthers(true)}>다른 사무소 광고만</button>
        </span>
      </div>
      <p className="kokm-note">명단에 타입(101·84A·34평·76.79 등)이 있으면 단지의 실제 타입으로 바꿔 같은 타입 광고만 남겨요. 광고는 호수를 공개하지 않아요. 아래는 명단 세대와 <b>같은 동·같은 층</b>에 올라온 광고라서, 한 층에 여러 세대가 있으면 그 집이 아닐 수 있어요. 연락 여부와 방법의 판단·책임은 사무소에 있어요.</p>
      {!rows.length ? <p className="kokm-empty">조건에 맞는 세대가 없어요.</p> : (
        <table className="kokm-tbl">
          <thead><tr><th>세대</th><th>명단</th><th>올라온 광고</th><th></th></tr></thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.unit_id}>
                <td><b>{u.complex_name}</b><small className="blk">{dongHo(u.dong, u.ho)} · {u.floor}층{u.role ? ` · ${u.role}` : ""}</small>
                  <small className={`blk ${u.grade === "층 일치" ? "kokm-on" : ""}`}>{u.grade}{u.type_ok ? ` · 타입 일치(${u.types.join("·")})` : ""}</small>
                  {u.type_raw && !u.type_ok && <small className="blk" style={{ color: "#b26a00" }}>명단 타입 '{u.type_raw}' — {u.type_note}, 타입 없이 대조</small>}</td>
                <td>{open[u.unit_id]
                  ? <><b>{open[u.unit_id].name || "-"}</b><small className="blk">{open[u.unit_id].phone ? <a href={`tel:${open[u.unit_id].phone.replace(/\D/g, "")}`}>{open[u.unit_id].phone}</a> : "번호 없음"}</small></>
                  : <>{u.name_masked || "-"}<small className="blk">{u.phone_masked || "번호 없음"}</small></>}
                  {u.note && <small className="blk">{u.note}</small>}</td>
                <td>{u.houses.slice(0, 4).map((h) => (
                  <div key={h.article_no} className="kokm-rh">
                    <b>{priceText(h)}</b> {h.area_name}{/^\d+[A-Z]?$/.test(h.area_name) ? "타입" : ""} · {h.floor_info}층{h.direction ? ` · ${h.direction}` : ""}
                    <small className="blk">{h.mine ? "우리 사무소 광고 포함 · " : ""}{h.n_offices}곳 광고{h.offices.length ? ` (${h.offices.slice(0, 3).join(", ")}${h.offices.length > 3 ? " 외" : ""})` : ""}{h.strength !== "층 일치" ? ` · ${h.strength}` : ""}</small>
                  </div>
                ))}{u.houses.length > 4 && <small className="blk">외 {u.houses.length - 4}집</small>}</td>
                <td className="act">{open[u.unit_id] ? <span className="muted" style={{ fontSize: 12 }}>열람 기록됨</span> : <button className="kokm-lnk" onClick={() => reveal(u)}>연락처 보기</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Notice() {
  return (
    <ul className="kokm-note" style={{ margin: 0, paddingLeft: 18 }}>
      <li>이 명단은 사무소가 적법하게 수집·보유한 것이고, 그 책임은 사무소에 있어요.</li>
      <li>콕집은 사무소의 위탁을 받아 보관하고 광고와 대조하는 일만 해요. 다른 사무소에는 보이지 않아요.</li>
      <li>고객원장과 섞이지 않게 따로 보관해요. 이름·연락처는 암호화하고, 연락처를 열면 누가 언제 열었는지 남겨요.</li>
      <li>동의는 180일 동안 유효해요. 90일이 지나면 연장 동의를 할 수 있고, 연장하면 그날부터 다시 180일이에요. 기간이 지나면 연장 동의 전까지 대조와 연락처 열람이 멈춰요.</li>
    </ul>
  );
}

function Renew({ authH, l, onDone, onCancel }: { authH: () => Record<string, string>; l: RList; onDone: () => void; onCancel: () => void }) {
  const [ack, setAck] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    const fd = new FormData(); fd.append("ack", "1");
    const r = await fetch(`${API}/lounge/roster/lists/${l.id}/renew`, { method: "POST", headers: authH(), body: fd });
    if (r.ok) onDone(); else setErr((await r.json().catch(() => ({}))).detail || "연장하지 못했어요");
  };
  return (
    <div className="kokm-sec">
      <b>'{l.name}' 보관·대조 연장</b>
      <Notice />
      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5 }}>
        <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> 위 내용을 다시 확인했고, 오늘부터 180일 동안 보관과 대조를 콕집에 맡겨요.
      </label>
      {err && <p className="kokm-gate">{err}</p>}
      <div className="kokm-bar" style={{ justifyContent: "flex-start" }}>
        <button className="kokm-pri" disabled={!ack} onClick={go}>연장 동의</button>
        <button className="kokm-lnk mut" onClick={onCancel}>닫기</button>
      </div>
    </div>
  );
}

function Upload({ authH, lists, onDone }: { authH: () => Record<string, string>; lists: RList[]; onDone: (r: Saved) => void }) {
  const [target, setTarget] = useState<number>(lists[0]?.id || 0);
  const [file, setFile] = useState<File | null>(null);
  const [pv, setPv] = useState<Preview | null>(null);
  const [name, setName] = useState("");
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [cxMap, setCxMap] = useState<Record<string, string>>({});
  const preview = async (f: File, cm: Record<string, string>) => {
    setBusy(true);
    const fd = new FormData(); fd.append("file", f); fd.append("cx_map", JSON.stringify(cm));
    try {
      const r = await fetch(`${API}/lounge/roster/preview`, { method: "POST", headers: authH(), body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "읽지 못했어요");
      setPv(j);
    } catch (e) { setErr(String((e as Error).message || e)); } finally { setBusy(false); }
  };
  const pick = (f: File | null) => {
    setFile(f); setPv(null); setErr(""); setAck(false); setCxMap({});
    if (!f) return;
    if (!target) setName(f.name.replace(/\.[^.]+$/, ""));
    preview(f, {});
  };
  const choose = (raw: string, cno: string) => { if (!file) return; const cm = { ...cxMap, [raw]: cno }; if (!cno) delete cm[raw]; setCxMap(cm); preview(file, cm); };
  const save = async () => {
    if (!file || !ack) return;
    setBusy(true); setErr("");
    const fd = new FormData(); fd.append("file", file); fd.append("ack", "1"); fd.append("name", name); if (target) fd.append("list_id", String(target)); fd.append("cx_map", JSON.stringify(cxMap));
    try {
      const r = await fetch(`${API}/lounge/roster/upload`, { method: "POST", headers: authH(), body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "저장하지 못했어요");
      onDone(j);
    } catch (e) { setErr(String((e as Error).message || e)); } finally { setBusy(false); }
  };
  return (
    <div className="kokm-sec">
      <div className="kokm-lead">엑셀(xlsx·xls·csv) 명단을 올려 주세요. <b>단지 · 동 · 호 · 이름 · 연락처</b> 칸을 알아서 찾고, 타입이나 면적 칸이 있으면 대조에 함께 써요.
        <p>올리기 전에 먼저 어떻게 읽었는지 보여 드려요. 이 단계에서는 아무것도 저장하지 않아요.</p>
        <p>기존 명단에 올리면 업데이트돼요 — 동·호가 같은 세대는 새 값으로 바꾸고(빈 칸은 기존 값 유지), 새 세대는 더하고, 파일에 없는 세대는 그대로 둬요.</p></div>
      {lists.length > 0 && (
        <span className="kokm-seg" style={{ alignSelf: "flex-start", flexWrap: "wrap" }}>
          {lists.map((l) => <button key={l.id} className={target === l.id ? "on" : ""} onClick={() => setTarget(l.id)}>{l.name} 업데이트</button>)}
          <button className={target === 0 ? "on" : ""} onClick={() => setTarget(0)}>새 명단</button>
        </span>
      )}
      <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => pick(e.target.files?.[0] || null)} />
      {busy && !pv && <p className="muted">읽는 중…</p>}
      {err && <p className="kokm-gate">{err}</p>}
      {pv && (<>
        <h3 className="kokm-h3">이렇게 읽었어요</h3>
        <dl className="kokm-dl">
          <div><dt>세대</dt><dd>{pv.n_rows.toLocaleString()}줄{pv.skipped ? ` (동·호나 이름·연락처가 없어 건너뛴 줄 ${pv.skipped.toLocaleString()})` : ""}</dd></div>
          <div><dt>단지 연결</dt><dd>{pv.linked.toLocaleString()}줄{pv.n_rows - pv.linked > 0 && <small className="blk">연결 안 된 {(pv.n_rows - pv.linked).toLocaleString()}줄은 저장은 되지만 대조에서 빠져요.</small>}</dd></div>
          <div><dt>읽은 칸</dt><dd>{pv.fields.map((f) => FIELD_L[f] || f).join(" · ") || "-"}</dd></div>
        </dl>
        <table className="kokm-tbl">
          <thead><tr><th>명단의 단지 이름</th><th>연결된 단지</th><th className="num">세대</th></tr></thead>
          <tbody>{pv.complexes.map((c) => (
            <tr key={c.raw + c.complex_no}>
              <td>{c.raw}</td>
              <td>{c.candidates.length > 0
                ? <select value={cxMap[c.raw] || ""} onChange={(e) => choose(c.raw, e.target.value)} style={{ maxWidth: 420 }}>
                    <option value="">{c.matched ? "다시 고르기" : "단지를 골라 주세요"}</option>
                    {c.candidates.map((k) => <option key={k.complex_no} value={k.complex_no}>{k.name} — {k.addr}{k.households ? ` · ${k.households.toLocaleString()}세대` : ""}</option>)}
                  </select>
                : (c.matched || <span className="muted">연결 못 함 · 후보 없음</span>)}
                {c.matched && <small className="blk kokm-on">{c.picked ? "고른 단지" : "자동 연결"}: {c.matched}</small>}</td>
              <td className="num">{c.n.toLocaleString()}</td></tr>))}</tbody>
        </table>
        <table className="kokm-tbl">
          <thead><tr><th>앞 5줄</th><th>동·호</th><th>이름</th><th>연락처</th></tr></thead>
          <tbody>{pv.sample.map((s, i) => <tr key={i}><td>{s.complex}</td><td>{dongHo(s.dong, s.ho)}</td><td>{s.name}</td><td>{s.phone}</td></tr>)}</tbody>
        </table>
        <h3 className="kokm-h3">보관 안내</h3>
        <Notice />
        {!target && <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13.5 }}>
          명단 이름 <input value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1, maxWidth: 320 }} />
        </label>}
        <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5 }}>
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> 위 내용을 확인했고, 이 명단의 보관과 대조를 오늘부터 180일 동안 콕집에 맡겨요.
        </label>
        <button className="kokm-pri" disabled={!ack || busy || !pv.n_rows} onClick={save}>{busy ? "저장 중…" : target ? `${lists.find((l) => l.id === target)?.name || "명단"}에 ${pv.n_rows.toLocaleString()}세대 반영하기` : `${pv.n_rows.toLocaleString()}세대 저장하고 대조하기`}</button>
      </>)}
    </div>
  );
}
