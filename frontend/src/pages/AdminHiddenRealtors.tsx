import { useCallback, useEffect, useState } from "react";
import { EyeOff, Eye, Search } from "lucide-react";
import { authClient } from "../auth";

const API = import.meta.env.VITE_API_BASE;

async function authFetch(path: string, init?: RequestInit) {
  const s = await authClient?.auth.getSession();
  const tok = s?.data?.session?.access_token;
  return fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
      ...(init?.headers || {}),
    },
  });
}

type SearchItem = {
  realtor_id: string; realtor_name: string;
  representative?: string | null; address?: string | null; region?: string | null;
};
type Hidden = { realtor_id: string; name: string | null; reason: string | null; created_at: string };

export default function AdminHiddenRealtors() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [hidden, setHidden] = useState<Hidden[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const loadHidden = useCallback(async () => {
    const r = await authFetch("/admin/hidden-realtors");
    if (r.ok) setHidden((await r.json()).items ?? []);
  }, []);
  useEffect(() => { loadHidden(); }, [loadHidden]);

  const hiddenIds = new Set(hidden.map((h) => h.realtor_id));

  const search = useCallback(async (kw: string) => {
    const term = kw.trim();
    if (term.length < 1) { setResults(null); return; }
    setSearching(true);
    try {
      const r = await fetch(`${API}/stats/realtors/search?q=${encodeURIComponent(term)}&limit=30`);
      setResults(r.ok ? ((await r.json()).items ?? []) : []);
    } catch { setResults([]); }
    finally { setSearching(false); }
  }, []);

  const hide = async (it: SearchItem) => {
    setBusy(it.realtor_id);
    try {
      const r = await authFetch("/admin/hidden-realtors", {
        method: "POST",
        body: JSON.stringify({ realtor_id: it.realtor_id, name: it.realtor_name }),
      });
      if (r.ok) await loadHidden();
    } finally { setBusy(null); }
  };

  const unhide = async (rid: string) => {
    setBusy(rid);
    try {
      const r = await authFetch(`/admin/hidden-realtors/${encodeURIComponent(rid)}`, { method: "DELETE" });
      if (r.ok) setHidden((hs) => hs.filter((h) => h.realtor_id !== rid));
    } finally { setBusy(null); }
  };

  return (
    <div className="admin-wrap" style={{ maxWidth: 860, margin: "0 auto", padding: "18px 16px 60px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, margin: "4px 0 4px" }}>
        <EyeOff size={20} style={{ verticalAlign: -3, marginRight: 6 }} /> 중개사 노출차단
      </h1>
      <p style={{ color: "var(--c-muted)", fontSize: 13.5, margin: "0 0 18px" }}>
        차단한 중개사무소는 <b>사이트 노출(검색·랭킹·상세·단지별·우리동네)에서 가려집니다.</b>{" "}
        통계·내부데이터에는 그대로 사용됩니다.
      </p>

      {/* 검색 → 노출금지 */}
      <div className="hr-card" style={cardStyle}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>중개사무소 검색해서 차단</div>
        <form onSubmit={(e) => { e.preventDefault(); search(q); }} style={{ display: "flex", gap: 8 }}>
          <div style={{ position: "relative", flex: 1 }}>
            <Search size={15} style={{ position: "absolute", left: 11, top: 11, color: "#9aa7bd" }} />
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="상호·대표자·지역 (예: 밀리빌리, 정영진)"
              style={inputStyle}
            />
          </div>
          <button type="submit" style={btnPrimary} disabled={searching}>
            {searching ? "검색 중…" : "검색"}
          </button>
        </form>

        {results && (
          <div style={{ marginTop: 12 }}>
            {results.length === 0 && <div style={{ color: "var(--c-muted)", fontSize: 13, padding: "8px 2px" }}>결과 없음 (이미 차단된 곳은 아래 목록에 있습니다)</div>}
            {results.map((it) => {
              const already = hiddenIds.has(it.realtor_id);
              return (
                <div key={it.realtor_id} style={rowStyle}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{it.realtor_name}</div>
                    <div style={{ fontSize: 12, color: "var(--c-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {[it.representative, it.region || it.address].filter(Boolean).join(" · ")}
                      <span style={{ color: "#b8c1d1", marginLeft: 6 }}>{it.realtor_id}</span>
                    </div>
                  </div>
                  {already ? (
                    <span style={{ ...tag, background: "#eef1f6", color: "#8a97ad" }}>차단됨</span>
                  ) : (
                    <button onClick={() => hide(it)} disabled={busy === it.realtor_id} style={btnDanger}>
                      <EyeOff size={14} /> 노출금지
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 차단 목록 */}
      <div className="hr-card" style={{ ...cardStyle, marginTop: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>
          차단된 중개사무소 <span style={{ color: "var(--c-muted)", fontWeight: 600 }}>({hidden.length})</span>
        </div>
        {hidden.length === 0 && <div style={{ color: "var(--c-muted)", fontSize: 13, padding: "6px 2px" }}>차단된 중개사무소가 없습니다.</div>}
        {hidden.map((h) => (
          <div key={h.realtor_id} style={rowStyle}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{h.name || h.realtor_id}</div>
              <div style={{ fontSize: 12, color: "var(--c-muted)" }}>
                <span style={{ color: "#b8c1d1" }}>{h.realtor_id}</span>
                {h.reason ? ` · ${h.reason}` : ""} · {(h.created_at || "").slice(0, 10)}
              </div>
            </div>
            <button onClick={() => unhide(h.realtor_id)} disabled={busy === h.realtor_id} style={btnGhost}>
              <Eye size={14} /> 해제
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: "var(--c-card, #fff)", border: "1px solid var(--c-border, #e4e8ef)",
  borderRadius: 14, padding: "16px 16px 14px",
};
const inputStyle: React.CSSProperties = {
  width: "100%", padding: "9px 12px 9px 32px", borderRadius: 9,
  border: "1px solid var(--c-border, #dadce0)", fontSize: 14, fontFamily: "inherit",
};
const rowStyle: React.CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
  padding: "10px 4px", borderBottom: "1px solid var(--c-border2, #f0f2f6)",
};
const btnBase: React.CSSProperties = {
  display: "inline-flex", alignItems: "center", gap: 5, borderRadius: 8, padding: "8px 13px",
  fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap", border: "none",
};
const btnPrimary: React.CSSProperties = { ...btnBase, background: "#1268d3", color: "#fff" };
const btnDanger: React.CSSProperties = { ...btnBase, background: "#fdecec", color: "#c0392b" };
const btnGhost: React.CSSProperties = { ...btnBase, background: "#eef4ff", color: "#1268d3" };
const tag: React.CSSProperties = { fontSize: 12, fontWeight: 700, padding: "5px 10px", borderRadius: 999 };
