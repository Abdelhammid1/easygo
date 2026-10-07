// Web-push subscription helpers (NT-2). The backend supplies the VAPID public
// key and stores the subscription; the service worker (/sw.js) shows the toasts.
import { api } from "./api/client";

export type EnableResult = "enabled" | "denied" | "unsupported" | "no-key";

export function isPushSupported(): boolean {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function urlBase64ToBuffer(base64: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const buffer = new ArrayBuffer(raw.length);
  const out = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return buffer;
}

export async function getExistingSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function enablePush(): Promise<EnableResult> {
  if (!isPushSupported()) return "unsupported";

  const { public_key } = await api.get<{ public_key: string | null }>(
    "/notifications/push/key"
  );
  if (!public_key) return "no-key";

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "denied";

  const reg = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;

  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToBuffer(public_key),
    });
  }
  await api.post("/notifications/push/subscribe", sub.toJSON());
  return "enabled";
}

export async function disablePush(): Promise<void> {
  const sub = await getExistingSubscription();
  if (!sub) return;
  try {
    await api.post("/notifications/push/unsubscribe", { endpoint: sub.endpoint });
  } catch {
    /* ignore — unsubscribe locally regardless */
  }
  try {
    await sub.unsubscribe();
  } catch {
    /* ignore */
  }
}
