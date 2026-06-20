import { useEffect, useState } from "react";
import { Loading } from "../components/Loading";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";

type Item = {
  realtor_id: string;
  naver_name: string | null;
  sgg_cd: string | null;
  listings: number | null;
  representative: string | null;
  address: string | null;
  phone: string | null;
  cell: string | null;
  registration_no: string | null;
  category: "A" | "B" | "C" | "D" | "E";
  vworld_status: string | null;
};

type Resp = { items: Item[]; total: number };

const API_BASE = import.meta.env.VITE_API_BASE;
const CAT_LABEL: Record<string, string> = {
  E: "vworld 영업정지/휴업 확인",
  A: "매물 정보 없음 (article 만료)",
  B: "매물 등록번호 없음",
  C: "옛/이상 포맷 등록번호",
  D: "표준 등록번호지만 vworld 미등록 (폐업/말소 의심)",
};
const CAT_COLOR: Record<string, string> = {
  E: "#c00000",
  A: "#888",
  B: "#a09000",
  C: "#a06000",
  D: "#c0392b",
};

export default function SuspiciousRealtors() {
  const { token } = useAuth();
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [catFilter, setCatFilter] = useState<string>("ALL");

  useEffect(() => {
    if (!API_BASE) {
      setError("local API가 필요합니다 (VITE_API_BASE).");
      setLoading(false);
      return;
    }
    if (!token) return;
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/admin/suspicious-realtors?limit=500`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error(`status ${r.status}`);
        const j = (await r.json()) as Resp;
        setItems(j.items);
        setLoading(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      }
    })();
  }, [token]);

  if (loading) return <Loading />;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;

  const counts: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, E: 0 };
  for (const it of items) counts[it.category] = (counts[it.category] || 0) + 1;
  const filtered = catFilter === "ALL" ? items : items.filter((x) => x.category === catFilter);

  return (
    <>
      <Link to="/overview" className="back">← 전국현황</Link>
      <h2 style={{ margin: "0 0 4px" }}>의심 중개사 — vworld 미등록 / 등록 이슈</h2>
      <div className="muted" style={{ marginBottom: 16, fontSize: 13 }}>
        매물 광고는 올리고 있지만 vworld 영업중 사무소와 매칭이 안 되는 곳. 폐업·말소·등록정보 불일치 의심.
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        <Chip label={`전체 (${items.length})`} active={catFilter === "ALL"} color="#444" onClick={() => setCatFilter("ALL")} />
        {(["E", "D", "C", "B", "A"] as const).map((k) => (
          <Chip
            key={k}
            label={`${k}. ${CAT_LABEL[k]} (${counts[k] || 0})`}
            active={catFilter === k}
            color={CAT_COLOR[k]}
            onClick={() => setCatFilter(k)}
          />
        ))}
      </div>

      <table>
        <thead>
          <tr>
            <th>분류</th>
            <th>중개사무소</th>
            <th>대표자</th>
            <th>전화</th>
            <th>등록번호</th>
            <th>주소</th>
            <th className="num">매물</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((it) => (
            <tr key={it.realtor_id}>
              <td>
                <span style={{
                  background: CAT_COLOR[it.category] + "22",
                  color: CAT_COLOR[it.category],
                  padding: "2px 6px", borderRadius: 4,
                  fontSize: 11, fontWeight: 600,
                }}>{it.category}</span>
                {it.vworld_status && (
                  <div style={{ fontSize: 10, color: "#c00000", marginTop: 2 }}>
                    {it.vworld_status}
                  </div>
                )}
              </td>
              <td>
                <Link to={`/realtor/${encodeURIComponent(it.realtor_id)}`} style={{ fontSize: 13 }}>
                  {it.naver_name ?? <span style={{ color: "#aaa" }}>(이름 없음)</span>}
                </Link>
              </td>
              <td style={{ fontSize: 13 }}>{it.representative ?? "—"}</td>
              <td style={{ fontSize: 12, color: "#555" }}>
                {it.phone ?? "—"}
                {it.cell && it.cell !== it.phone && <><br/>{it.cell}</>}
              </td>
              <td style={{ fontSize: 12, fontFamily: "monospace" }}>{it.registration_no ?? "—"}</td>
              <td style={{ fontSize: 12, color: "#555", maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {it.address ?? "—"}
              </td>
              <td className="num" style={{ fontWeight: 600 }}>{it.listings ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Chip({ label, active, color, onClick }: { label: string; active: boolean; color: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "4px 10px",
        border: `1px solid ${active ? color : "#ccc"}`,
        borderRadius: 16,
        background: active ? color : "white",
        color: active ? "white" : "#333",
        cursor: "pointer",
        fontSize: 12,
      }}
    >
      {label}
    </button>
  );
}
