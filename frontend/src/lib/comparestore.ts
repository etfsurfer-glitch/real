// 단지 비교 바구니 — 어느 페이지에서든 단지를 담아 최대 4개까지 비교한다.
// 로그인 불필요(localStorage). favstore 와 같은 구독 패턴으로 버튼 수십 개가 동기화된다.
export const MAX_COMPARE = 4;
const LS = "koczip:compare";

export type CartItem = { complex_no: string; complex_name: string };

let _items: CartItem[] = load();
const _subs = new Set<() => void>();

function load(): CartItem[] {
  try {
    const raw = JSON.parse(localStorage.getItem(LS) || "[]");
    return Array.isArray(raw) ? raw.filter((x) => x && x.complex_no).slice(0, MAX_COMPARE) : [];
  } catch { return []; }
}
function save() {
  try { localStorage.setItem(LS, JSON.stringify(_items)); } catch { /* ignore */ }
  _subs.forEach((f) => { try { f(); } catch { /* ignore */ } });
}

export function subscribeCompare(fn: () => void): () => void {
  _subs.add(fn);
  return () => { _subs.delete(fn); };
}

export function compareItems(): CartItem[] { return _items; }
export function inCompare(no: string): boolean { return _items.some((x) => x.complex_no === no); }
export function compareCount(): number { return _items.length; }
export function compareFull(): boolean { return _items.length >= MAX_COMPARE; }

/** 담기/빼기. 담기가 꽉 차면 담지 않고 false 반환(호출부에서 안내). */
export function toggleCompare(no: string, name: string): { added: boolean; full?: boolean } {
  const i = _items.findIndex((x) => x.complex_no === no);
  if (i >= 0) { _items = _items.filter((x) => x.complex_no !== no); save(); return { added: false }; }
  if (_items.length >= MAX_COMPARE) return { added: false, full: true };
  _items = [..._items, { complex_no: String(no), complex_name: name || "단지" }];
  save();
  return { added: true };
}

export function removeCompare(no: string) {
  _items = _items.filter((x) => x.complex_no !== no);
  save();
}
export function clearCompare() { _items = []; save(); }
