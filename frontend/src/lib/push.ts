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

/** 프로미스가 ms 안에 끝나지 않으면 reject. TWA에서 FCM 미응답·SW 미준비로 영구
 *  대기하는 await(서비스워커 ready·구독 생성·네트워크)를 끊어 무한 로딩을 막는다. */
function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`timeout:${label}`)), ms);
    p.then((v) => { clearTimeout(t); resolve(v); },
           (e) => { clearTimeout(t); reject(e); });
  });
}

function urlB64ToUint8Array(base64: string): Uint8Array {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

/** 권한 요청 + 구독 생성 + 서버 저장. token 없으면 익명 구독으로 저장(로그인 시 자동 승격).
 *  성공 시 {ok:true}. */
export async function enablePush(token?: string | null): Promise<{ ok: boolean; reason?: string }> {
  if (!pushSupported()) return { ok: false, reason: "이 기기/브라우저는 알림을 지원하지 않아요." };
  if (!API) return { ok: false, reason: "서버가 설정되지 않았어요." };
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return { ok: false, reason: "알림 권한이 거부됐어요. 브라우저 설정에서 허용해 주세요." };
  try {
    // 아래 await 들은 TWA(FCM/Play 서비스 미응답)·SW 미준비 시 무한 대기할 수 있어
    // 각각 타임아웃으로 감싼다 — 멈추면 ok:false 로 즉시 빠져나와 UI 가 진행된다.
    const reg = await withTimeout(navigator.serviceWorker.ready, 5000, "sw-ready");
    const keyRes = await withTimeout(
      fetch(`${API}/push/vapid-public-key`).then((r) => r.json()), 5000, "vapid",
    ).catch(() => ({} as { key?: string }));
    if (!keyRes.key) return { ok: false, reason: "서버 알림설정이 아직 준비되지 않았어요." };
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await withTimeout(reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(keyRes.key) as BufferSource,
      }), 8000, "subscribe");
    }
    // 로그인 안 했어도 익명으로 저장(인증 헤더 생략) — 공지·급매 알림 수신. 로그인 시 같은 endpoint가 user로 승격.
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    const r = await withTimeout(fetch(`${API}/push/subscribe`, {
      method: "POST", headers, body: JSON.stringify({ subscription: sub.toJSON() }),
    }), 6000, "save");
    return r.ok ? { ok: true } : { ok: false, reason: "구독 저장 실패" };
  } catch (e) {
    const msg = String((e as Error)?.message || "");
    if (msg.startsWith("timeout:")) return { ok: false, reason: "알림 설정이 지연돼 건너뛰었어요. 나중에 설정에서 켤 수 있어요." };
    return { ok: false, reason: "알림 설정에 실패했어요. 나중에 다시 시도해 주세요." };
  }
}

const OPTIN_KEY = "koczip_push_optin";

/** 알림 받기로 선택했는지(soft-ask 수락 플래그). 로그인 전 1번 사용자가 권한만 미리 받은 경우 포함. */
export function pushOptedIn(): boolean {
  try { return localStorage.getItem(OPTIN_KEY) === "1"; } catch { return false; }
}

/** soft-ask 수락 — 권한 요청 + 구독 저장. 로그인이면 user 구독, 미로그인이면 익명 구독으로 즉시 저장
 *  (로그인 안 해도 공지·급매 알림 수신. 이후 로그인 시 같은 endpoint가 user로 자동 승격). */
export async function acceptPush(token?: string | null): Promise<{ ok: boolean; reason?: string }> {
  const r = await enablePush(token);   // token 없으면 익명 저장
  if (r.ok) { try { localStorage.setItem(OPTIN_KEY, "1"); } catch { /* */ } }
  return r;
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
