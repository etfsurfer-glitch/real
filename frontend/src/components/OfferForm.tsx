import { useCallback, useEffect, useState } from "react";
import { Check, Search } from "lucide-react";

export type OfferListing = {
  article_no: string; complex: string | null; area_name?: string | null;
  area_m2: number | null; price: string | null; rent: string | null;
  floor: string | null; trade: string;
};   // area_name 은 없을 수도 있다(라운지 응답)
export type Offer = { message: string; contact: string; listings: OfferListing[]; at?: string };

const PY = 3.305785;
const areaLabel = (m2: number | null) =>
  (m2 ? `${Math.round(m2 / PY)}평(${Math.round(m2)}㎡)` : "");

/** 중개사가 손님 요청에 답하는 폼.
 *  빈 칸에 글을 쓰라고 하면 아무도 안 쓴다 — 자기 매물을 골라 첨부하고
 *  한 줄만 적으면 끝나도록 만든다. 라운지와 문자 링크 화면이 함께 쓴다. */
export default function OfferForm({
  listUrl, postUrl, authH, existing, suggestContact, onDone,
}: {
  listUrl: string;                              // 내 매물 조회 주소
  postUrl: string;                              // 제안 등록 주소
  authH?: () => Record<string, string>;         // 라운지에서만 필요(링크 화면은 토큰)
  existing?: Offer | null;
  suggestContact?: string;                      // 등록된 번호로 미리 채운다(수정 가능)
  onDone: () => void;
}) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<OfferListing[]>([]);
  const [picked, setPicked] = useState<string[]>(
    (existing?.listings || []).map((x) => x.article_no));
  const [message, setMessage] = useState(existing?.message || "");
  const [contact, setContact] = useState(existing?.contact || suggestContact || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const H = useCallback(() => (authH ? authH() : {}), [authH]);

  const load = useCallback((kw: string) => {
    fetch(`${listUrl}?limit=40${kw ? `&q=${encodeURIComponent(kw)}` : ""}`, { headers: H() })
      .then((r) => r.json()).then((d) => setItems(d.items || [])).catch(() => setItems([]));
  }, [listUrl, H]);
  useEffect(() => { load(""); }, [load]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(postUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...H() },
        body: JSON.stringify({ message, contact, article_nos: picked }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "보내지 못했어요");
      onDone();
    } catch (e: any) { setErr(e?.message || "보내지 못했어요"); }
    finally { setBusy(false); }
  };

  return (
    <div className="ofm">
      <div className="ofm-sec">
        <div className="ofm-lbl">1. 제안할 매물을 고르세요 <span>선택 · 최대 10개</span></div>
        <div className="ofm-search">
          <Search size={14} />
          <input value={q} placeholder="단지 이름으로 찾기"
            onChange={(e) => { setQ(e.target.value); load(e.target.value); }} />
        </div>
        {items.length === 0 ? (
          <p className="muted" style={{ fontSize: 13 }}>
            지금 등록된 매물이 없어요. 아래에 직접 적어 주셔도 됩니다.
          </p>
        ) : (
          <ul className="ofm-list">
            {items.map((x) => {
              const on = picked.includes(x.article_no);
              return (
                <li key={x.article_no}>
                  <button type="button" className={`ofm-item ${on ? "on" : ""}`}
                    onClick={() => setPicked((v) => (
                      on ? v.filter((a) => a !== x.article_no)
                         : [...v, x.article_no].slice(0, 10)))}>
                    <span className={`ofm-box ${on ? "on" : ""}`}>
                      {on && <Check size={12} strokeWidth={3.2} />}
                    </span>
                    <span className="ofm-item-b">
                      <b>{x.complex || "단지 미상"}</b>
                      <i>{[areaLabel(x.area_m2), x.floor ? `${x.floor}층` : "", x.trade]
                        .filter(Boolean).join(" · ")}</i>
                    </span>
                    <span className="ofm-price">{x.price || x.rent || "-"}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>{picked.length}개 선택됨</div>
      </div>

      <div className="ofm-sec">
        <div className="ofm-lbl">2. 손님에게 한 마디 <span>선택</span></div>
        <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)}
          placeholder="예: 말씀하신 조건에 맞는 물건 있습니다. 남향이고 즉시 입주 가능합니다." />
      </div>

      <div className="ofm-sec">
        <div className="ofm-lbl">3. 손님이 연락할 번호 <span>필수</span></div>
        <input value={contact} onChange={(e) => setContact(e.target.value)}
          placeholder="02-000-0000 또는 010-0000-0000" />
        <p className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>
          {!existing && suggestContact && contact === suggestContact
            ? <>등록된 번호를 넣어 뒀어요. <b>다른 번호로 받으시려면 고치시면 됩니다.</b><br /></>
            : null}
          손님 번호는 저희도 넘기지 않습니다. 이 번호를 보고 <b>손님이 직접 전화</b>합니다.
        </p>
      </div>

      {err && <div className="ofm-err">{err}</div>}
      <button className="ofm-send" disabled={busy || !contact.trim() || (!message.trim() && !picked.length)}
        onClick={submit}>
        {busy ? "보내는 중…" : existing ? "제안 수정하기" : "제안 보내기"}
      </button>
      {existing && (
        <p className="muted" style={{ fontSize: 12, marginTop: 8, textAlign: "center" }}>
          이미 보낸 제안이 있어요. 다시 보내면 내용이 바뀝니다.
        </p>
      )}
    </div>
  );
}
