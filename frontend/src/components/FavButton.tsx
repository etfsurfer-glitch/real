import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

// 관심단지 토글 — 로그인 사용자만. 관심단지는 매일 16시 푸시알림 대상.
export default function FavButton({ complexNo, complexName }: { complexNo: string; complexName?: string }) {
  const { token } = useAuth();
  const [fav, setFav] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token || !API) return;
    fetch(`${API}/me/favorites`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => setFav((d.items || []).some((x: { complex_no: string }) => x.complex_no === complexNo)))
      .catch(() => {});
  }, [token, complexNo]);

  if (!token) return null;

  const toggle = async () => {
    setBusy(true);
    try {
      if (fav) {
        await fetch(`${API}/me/favorites/${complexNo}`, {
          method: "DELETE", headers: { Authorization: `Bearer ${token}` },
        });
        setFav(false);
      } else {
        await fetch(`${API}/me/favorites`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ complex_no: complexNo, complex_name: complexName }),
        });
        setFav(true);
      }
    } catch { /* ignore */ }
    setBusy(false);
  };

  return (
    <button className={`fav-btn${fav ? " on" : ""}`} onClick={toggle} disabled={busy} aria-label="관심단지">
      <Heart size={14} strokeWidth={2.4} fill={fav ? "currentColor" : "none"} aria-hidden />
      {fav ? "관심단지" : "관심단지 추가"}
    </button>
  );
}
