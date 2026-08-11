// ══════════════════════════════════════════════════════════════════════════
// AI 비용 — 우리가 쓰는 AI 호출을 기능별로 세어 원화로 보여준다
//
//   호출 한 건마다 토큰을 적어 두고, 그때 단가로 계산한 달러값을 함께 저장한다.
//   단가표를 나중에 고쳐도 과거 비용이 소급해 흔들리지 않는다.
//   청구는 달러로 오므로 원화는 참고치다(환율은 아래에 표시).
// ══════════════════════════════════════════════════════════════════════════
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Coins, RefreshCw } from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type Row = { feature: string; calls: number; in_tokens: number; out_tokens: number; usd: number };
type ModelRow = { model: string; calls: number; in_tokens: number; out_tokens: number; usd: number };
type DayRow = { day: string; calls: number; usd: number };
type Price = { model: string; in: number; out: number };
type Data = {
  usd_krw: number;
  since: string | null;
  today: { usd: number; calls: number };
  month: { usd: number; calls: number };
  by_feature: Row[];
  by_day: DayRow[];
  by_model: ModelRow[];
  prices: Price[];
};

// 기능 코드 → 사람이 읽는 이름
const NAME: Record<string, string> = {
  "ai-ask": "AI 질문(콕집 AI)",
  "sns-radar": "SNS 분석",
  cardnews: "카드뉴스 v2",
  "contract-parse": "계약서 일정 추출",
  "sns-post": "SNS 자동포스팅",
  "sns-brag": "SNS 문구",
};

const DAYS = [7, 30, 90];
const won = (usd: number, fx: number) => Math.round(usd * fx);
const nf = (v: number) => v.toLocaleString();

export default function AiCost() {
  const { token } = useAuth();
  const [d, setD] = useState<Data | null>(null);
  const [days, setDays] = useState(30);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/admin/ai-cost?days=${days}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 160)}`);
      setD(await r.json());
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [token, days]);

  useEffect(() => {
    if (token && API_BASE) load();
  }, [token, load]);

  const fx = d?.usd_krw ?? 1400;
  const total = useMemo(
    () => (d?.by_feature ?? []).reduce((a, x) => a + x.usd, 0), [d]);
  // 최근 실적으로 한 달을 어림한다 — 오늘 하루치만 보면 들쭉날쭉해서 기간 평균을 쓴다
  const perDay = useMemo(() => {
    const rows = d?.by_day ?? [];
    if (!rows.length) return 0;
    return rows.reduce((a, x) => a + x.usd, 0) / rows.length;
  }, [d]);
  const maxDay = useMemo(
    () => Math.max(1e-9, ...(d?.by_day ?? []).map((x) => x.usd)), [d]);

  return (
    <div className="ac">
      <style>{css}</style>

      <div className="section-title" style={{ marginTop: 4 }}>
        <Coins size={16} strokeWidth={2.2} /> AI 비용{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          기능별 사용량과 요금 · 관리자
        </span>
      </div>
      <p className="ac-lead">
        AI 호출 한 건마다 토큰을 적어 두고 그때 단가로 계산한다. 청구는 달러로 오므로
        원화는 참고치다(1달러 = {nf(fx)}원 기준).
      </p>

      {err && <div className="ac-err"><AlertCircle size={15} strokeWidth={2.3} /><span>{err}</span></div>}

      {/* 요약 */}
      <div className="ac-sum">
        <div>
          <b>{d ? nf(won(d.today.usd, fx)) : "-"}<i>원</i></b>
          <span>오늘 · {d ? nf(d.today.calls) : "-"}회</span>
        </div>
        <div>
          <b>{d ? nf(won(d.month.usd, fx)) : "-"}<i>원</i></b>
          <span>이번 달 · {d ? nf(d.month.calls) : "-"}회</span>
        </div>
        <div>
          <b>{d ? nf(won(perDay * 30, fx)) : "-"}<i>원</i></b>
          <span>이 추세면 한 달</span>
        </div>
        <div className="ac-sum-act">
          {d?.since && <em>{d.since}부터 기록</em>}
          <div className="ac-seg">
            {DAYS.map((n) => (
              <button key={n} className={days === n ? "on" : ""} onClick={() => setDays(n)}>
                {n}일
              </button>
            ))}
          </div>
          <button className="ac-refresh" onClick={load}>
            <RefreshCw size={12} strokeWidth={2.4} /> 새로고침
          </button>
        </div>
      </div>

      {d && d.by_feature.length === 0 && (
        <p className="ac-empty">
          아직 기록이 없다. 지금부터 쌓인다 — 이 화면을 만들기 전의 호출은 남아 있지 않다.
        </p>
      )}

      {/* 기능별 */}
      {d && d.by_feature.length > 0 && (
        <>
          <h3 className="ac-h">기능별</h3>
          <table className="ac-tb">
            <thead>
              <tr>
                <th>기능</th><th>호출</th><th>입력 토큰</th><th>출력 토큰</th>
                <th>1회 평균</th><th>비용</th><th className="ac-share">비중</th>
              </tr>
            </thead>
            <tbody>
              {d.by_feature.map((r) => (
                <tr key={r.feature}>
                  <td className="ac-name">{NAME[r.feature] || r.feature}</td>
                  <td>{nf(r.calls)}</td>
                  <td>{nf(r.in_tokens)}</td>
                  <td>{nf(r.out_tokens)}</td>
                  <td>{r.calls ? `${(r.usd / r.calls * fx).toFixed(2)}원` : "-"}</td>
                  <td className="ac-won">{nf(won(r.usd, fx))}원</td>
                  <td className="ac-share">
                    <i style={{ width: `${total ? (r.usd / total) * 100 : 0}%` }} />
                    <span>{total ? Math.round((r.usd / total) * 100) : 0}%</span>
                  </td>
                </tr>
              ))}
              <tr className="ac-total">
                <td>합계</td>
                <td>{nf(d.by_feature.reduce((a, x) => a + x.calls, 0))}</td>
                <td colSpan={3} />
                <td className="ac-won">{nf(won(total, fx))}원</td>
                <td className="ac-share" />
              </tr>
            </tbody>
          </table>
        </>
      )}

      {/* 일별 */}
      {d && d.by_day.length > 0 && (
        <>
          <h3 className="ac-h">일별</h3>
          <div className="ac-bars">
            {d.by_day.map((x) => (
              <div key={x.day} className="ac-bar" title={`${x.day} · ${nf(x.calls)}회 · ${nf(won(x.usd, fx))}원`}>
                <i style={{ height: `${Math.max(2, (x.usd / maxDay) * 100)}%` }} />
                <span>{x.day.slice(5).replace("-", ".")}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 모델별·단가 */}
      {d && d.by_model.length > 0 && (
        <>
          <h3 className="ac-h">모델별</h3>
          <table className="ac-tb">
            <thead>
              <tr><th>모델</th><th>호출</th><th>입력</th><th>출력</th><th>단가(입력/출력, $/1M)</th><th>비용</th></tr>
            </thead>
            <tbody>
              {d.by_model.map((r) => {
                const pr = d.prices.find((p) => (r.model || "").toLowerCase().startsWith(p.model));
                return (
                  <tr key={r.model || "-"}>
                    <td className="ac-name">{r.model || "(미상)"}</td>
                    <td>{nf(r.calls)}</td>
                    <td>{nf(r.in_tokens)}</td>
                    <td>{nf(r.out_tokens)}</td>
                    <td>{pr ? `$${pr.in} / $${pr.out}` : "기본단가 적용"}</td>
                    <td className="ac-won">{nf(won(r.usd, fx))}원</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="ac-note">
            생각(thinking) 토큰은 출력으로 과금된다. 모르는 모델은 가장 비싼 flash 단가로 잡아
            비용을 낮춰 보지 않게 했다.
          </p>
        </>
      )}
    </div>
  );
}

const css = `
.ac{max-width:980px}
.ac-lead{margin:6px 0 16px;font-size:13.5px;line-height:1.6;color:var(--c-muted);max-width:64ch}
.ac-err{display:flex;align-items:flex-start;gap:8px;margin:10px 0;padding:10px 13px;
  border:1px solid #f3c9c9;background:#fdf3f3;border-radius:var(--r-md);font-size:13px;color:#a52a2a}

.ac-sum{display:flex;align-items:center;gap:30px;flex-wrap:wrap;margin-bottom:18px;padding:15px 18px;
  border:1px solid var(--c-border);background:var(--c-card);border-radius:var(--r-lg);
  box-shadow:var(--sh-sm)}
.ac-sum>div{display:flex;flex-direction:column;gap:2px}
.ac-sum b{font-size:23px;font-weight:800;color:var(--c-text);font-variant-numeric:tabular-nums;
  letter-spacing:-.02em}
.ac-sum b i{font-style:normal;font-size:13px;font-weight:700;margin-left:2px;color:var(--c-muted)}
.ac-sum span{font-size:11.5px;font-weight:600;color:var(--c-muted)}
.ac-sum-act{margin-left:auto;flex-direction:row!important;align-items:center;gap:8px!important}
.ac-sum-act em{font-style:normal;font-size:11px;color:var(--c-faint)}
.ac-seg{display:inline-flex;border:1px solid #cdd9ea;border-radius:8px;overflow:hidden}
.ac-seg button{border:none;background:#fff;padding:5px 11px;font:inherit;font-size:11.5px;
  font-weight:700;color:#66748a;cursor:pointer}
.ac-seg button.on{background:var(--c-primary);color:#fff}
.ac-refresh{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--c-border);
  background:#fff;border-radius:var(--r-pill);padding:5px 11px;font:inherit;font-size:11.5px;
  font-weight:700;color:#42506a;cursor:pointer}

.ac-h{margin:22px 0 8px;font-size:13.5px;font-weight:800;color:var(--c-text)}
.ac-tb{width:100%;border-collapse:collapse;background:var(--c-card);border:1px solid var(--c-border);
  border-radius:var(--r-md);overflow:hidden;font-size:12.5px}
.ac-tb th{background:#f6f8fb;padding:9px 11px;text-align:right;font-size:11px;font-weight:800;
  color:#5a6b80;border-bottom:1px solid var(--c-border)}
.ac-tb th:first-child{text-align:left}
.ac-tb td{padding:9px 11px;text-align:right;color:var(--c-text-soft);
  font-variant-numeric:tabular-nums;border-bottom:1px solid var(--c-border-soft)}
.ac-tb tr:last-child td{border-bottom:none}
.ac-tb td.ac-name{text-align:left;font-weight:700;color:var(--c-text)}
.ac-tb td.ac-won{font-weight:800;color:var(--c-text)}
.ac-tb tr.ac-total td{background:#f6f8fb;font-weight:800;color:var(--c-text)}
.ac-share{position:relative;width:110px}
td.ac-share i{position:absolute;left:11px;top:50%;transform:translateY(-50%);height:6px;
  border-radius:3px;background:var(--c-primary);max-width:calc(100% - 46px)}
td.ac-share span{position:absolute;right:11px;top:50%;transform:translateY(-50%);
  font-size:11px;color:var(--c-muted)}

.ac-bars{display:flex;align-items:flex-end;gap:3px;height:110px;padding:10px 12px 0;
  border:1px solid var(--c-border);background:var(--c-card);border-radius:var(--r-md);
  overflow-x:auto}
.ac-bar{flex:1;min-width:16px;display:flex;flex-direction:column;align-items:center;
  justify-content:flex-end;height:100%;gap:4px}
.ac-bar i{width:100%;max-width:22px;background:var(--c-primary);border-radius:3px 3px 0 0;
  display:block}
.ac-bar span{font-size:9px;color:var(--c-faint);white-space:nowrap}

.ac-note{margin:8px 0 0;font-size:11.5px;line-height:1.5;color:var(--c-faint)}
.ac-empty{font-size:13px;color:var(--c-muted)}
`;
