// 관심단지 공용 스토어 — 목록 페이지의 하트 버튼 수십 개가 각자 /me/favorites 를
// 부르지 않도록, 세션당 1회만 불러와 공유한다. 토글 시 구독자 전원에 알림.
const API = import.meta.env.VITE_API_BASE;

let _favs: Set<string> | null = null;
let _loading: Promise<Set<string>> | null = null;
let _token: string | null = null;
const _subs = new Set<() => void>();

function notify() { _subs.forEach((f) => { try { f(); } catch { /* ignore */ } }); }

export function subscribeFavs(fn: () => void): () => void {
  _subs.add(fn);
  return () => { _subs.delete(fn); };
}

export function favsLoaded(): boolean { return _favs !== null; }
export function isFav(complexNo: string): boolean { return !!_favs?.has(complexNo); }
export function favCount(): number { return _favs?.size ?? 0; }

export async function loadFavs(token: string): Promise<Set<string>> {
  if (token !== _token) { _favs = null; _loading = null; _token = token; } // 계정 전환 대응
  if (_favs) return _favs;
  if (_loading) return _loading;
  _loading = fetch(`${API}/me/favorites`, { headers: { Authorization: `Bearer ${token}` } })
    .then((r) => r.json())
    .then((d) => {
      _favs = new Set<string>((d.items || []).map((x: { complex_no: string }) => x.complex_no));
      notify();
      return _favs;
    })
    .catch(() => {
      _loading = null;           // 실패 시 다음 호출에서 재시도
      return new Set<string>();
    });
  return _loading;
}

/** 토글. 성공 시 새 상태(true=추가됨)를, 실패 시 에러 메시지를 담아 반환. */
export async function toggleFav(
  token: string, complexNo: string, complexName?: string,
): Promise<{ fav: boolean; error?: string }> {
  await loadFavs(token);
  const cur = isFav(complexNo);
  try {
    if (cur) {
      const r = await fetch(`${API}/me/favorites/${complexNo}`, {
        method: "DELETE", headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(await errText(r));
      _favs?.delete(complexNo);
    } else {
      const r = await fetch(`${API}/me/favorites`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ complex_no: complexNo, complex_name: complexName }),
      });
      if (!r.ok) throw new Error(await errText(r));
      _favs?.add(complexNo);
    }
    notify();
    return { fav: !cur };
  } catch (e) {
    return { fav: cur, error: e instanceof Error ? e.message : "요청 실패" };
  }
}

async function errText(r: Response): Promise<string> {
  try {
    const d = await r.json();
    if (typeof d?.detail === "string") return d.detail;
  } catch { /* ignore */ }
  return `오류 ${r.status}`;
}
