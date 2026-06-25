// 웹푸시 구독 — VAPID 공개키로 PushSubscription 생성 후 백엔드에 저장.
const API = import.meta.env.VITE_API_BASE;

export type PushState = "unsupported" | "default" | "granted" | "denied";

export function pushSupported(): boolean {
  return typeof navigator !== "undefined" && "serviceWorker" in navigator
    && typeof window !== "undefined" && "PushManager" in window && "Notification" in window;
}

export function pushPermission(): PushState {
  if (!pushSupported()) return "unsupported";
  return Notification.permission as PushState;
}

function urlB64ToUint8Array(base64: string): Uint8Array {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

/** 알림 권한 요청 + 구독 생성 + 서버 저장. 성공 시 {ok:true}. */
export async function enablePush(token: string): Promise<{ ok: boolean; reason?: string }> {
  if (!pushSupported()) return { ok: false, reason: "이 기기/브라우저는 알림을 지원하지 않아요." };
  if (!API || !token) return { ok: false, reason: "로그인이 필요해요." };
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return { ok: false, reason: "알림 권한이 거부됐어요. 브라우저 설정에서 허용해 주세요." };
  const reg = await navigator.serviceWorker.ready;
  const keyRes = await fetch(`${API}/push/vapid-public-key`).then((r) => r.json()).catch(() => ({}));
  if (!keyRes.key) return { ok: false, reason: "서버 알림설정이 아직 준비되지 않았어요." };
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlB64ToUint8Array(keyRes.key) as BufferSource,
    });
  }
  const r = await fetch(`${API}/push/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ subscription: sub.toJSON() }),
  });
  return r.ok ? { ok: true } : { ok: false, reason: "구독 저장 실패" };
}

const OPTIN_KEY = "koczip_push_optin";

/** 알림 받기로 선택했는지(soft-ask 수락 플래그). 로그인 전 1번 사용자가 권한만 미리 받은 경우 포함. */
export function pushOptedIn(): boolean {
  try { return localStorage.getItem(OPTIN_KEY) === "1"; } catch { return false; }
}

/** soft-ask 수락 — OS 권한 요청. 로그인(token) 있으면 바로 구독 저장, 없으면 권한만 받고 플래그 기록
 *  (이후 로그인 시 maybeAutoSubscribe 가 구독 저장). */
export async function acceptPush(token?: string | null): Promise<{ ok: boolean; reason?: string }> {
  if (!pushSupported()) return { ok: false, reason: "이 기기/브라우저는 알림을 지원하지 않아요." };
  if (token) {
    const r = await enablePush(token);   // 권한+구독+저장 한 번에
    if (r.ok) { try { localStorage.setItem(OPTIN_KEY, "1"); } catch { /* */ } }
    return r;
  }
  // 미로그인: OS 권한만 미리 받아둠(구독은 로그인 후)
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return { ok: false, reason: "알림 권한이 거부됐어요. 나중에 설정에서 켤 수 있어요." };
  try { localStorage.setItem(OPTIN_KEY, "1"); } catch { /* */ }
  return { ok: true };
}

/** 로그인 직후 호출 — 알림 받기로 했고 권한 허용 상태인데 아직 구독 안 됐으면 조용히 구독 저장. */
export async function maybeAutoSubscribe(token: string): Promise<void> {
  try {
    if (!token || !pushOptedIn() || !pushSupported()) return;
    if (Notification.permission !== "granted") return;
    if (await isPushSubscribed()) return;
    await enablePush(token);
  } catch { /* ignore */ }
}

export async function disablePush(token: string): Promise<void> {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    const ep = sub?.endpoint;
    if (sub) await sub.unsubscribe();
    if (API && token) {
      await fetch(`${API}/push/unsubscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ endpoint: ep }),
      });
    }
  } catch { /* ignore */ }
}

/** 현재 구독돼 있는지(브라우저 기준). */
export async function isPushSubscribed(): Promise<boolean> {
  if (!pushSupported() || Notification.permission !== "granted") return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    return !!(await reg.pushManager.getSubscription());
  } catch { return false; }
}
