import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { getSocket } from "../socket";
import { disablePush, enablePush, getExistingSubscription, isPushSupported } from "../push";

interface Notif {
  id: number;
  type: string;
  body: string | null;
  conversation_id: number | null;
  is_read: boolean;
  created_at?: string | null;
}

interface NotifEvent {
  id: number;
  type: string;
  body: string | null;
  conversation_id: number | null;
}

function timeLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("ar-EG", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

function beep() {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
    osc.start();
    osc.stop(ctx.currentTime + 0.26);
    osc.onended = () => ctx.close();
  } catch {
    /* audio not available — ignore */
  }
}

export function NotificationsBell() {
  const [items, setItems] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [pushOn, setPushOn] = useState(false);
  const [pushMsg, setPushMsg] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const pushSupported = isPushSupported();

  useEffect(() => {
    void api
      .get<{ notifications: Notif[]; unread_count: number }>("/notifications")
      .then((r) => {
        setItems(r.notifications);
        setUnread(r.unread_count);
      })
      .catch(() => undefined);

    const socket = getSocket();
    const onNew = (e: NotifEvent) => {
      setItems((prev) => {
        if (prev.some((n) => n.id === e.id)) return prev;
        return [{ ...e, is_read: false, created_at: new Date().toISOString() }, ...prev].slice(0, 100);
      });
      setUnread((u) => u + 1);
      if (e.type === "order_confirmed") beep();
    };
    socket.on("notification:new", onNew);
    return () => {
      socket.off("notification:new", onNew);
    };
  }, []);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (pushSupported) void getExistingSubscription().then((s) => setPushOn(!!s));
  }, [pushSupported]);

  async function togglePush() {
    setPushMsg(null);
    if (pushOn) {
      await disablePush();
      setPushOn(false);
      return;
    }
    const r = await enablePush();
    if (r === "enabled") setPushOn(true);
    else if (r === "denied") setPushMsg("تم رفض إذن الإشعارات في المتصفح");
    else if (r === "no-key") setPushMsg("إشعارات المتصفح غير مُهيّأة على الخادم");
    else setPushMsg("المتصفح لا يدعم الإشعارات");
  }

  async function markAll() {
    await api.post("/notifications/read-all");
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
  }

  async function markOne(n: Notif) {
    if (n.is_read) return;
    await api.post(`/notifications/${n.id}/read`);
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    setUnread((u) => Math.max(0, u - 1));
  }

  return (
    <div className="notif-wrap" ref={wrapRef}>
      <button className="iconbtn notif-btn" title="الإشعارات" onClick={() => setOpen((o) => !o)}>
        🔔
        {unread > 0 && <span className="notif-badge num">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="notif-panel">
          <div className="notif-hd">
            <b>الإشعارات</b>
            {unread > 0 && <button className="linklike" onClick={() => void markAll()}>تحديد الكل كمقروء</button>}
          </div>
          <div className="notif-list">
            {items.length === 0 && <div className="notif-empty">لا إشعارات</div>}
            {items.map((n) => (
              <div key={n.id}
                className={"notif-row" + (n.is_read ? "" : " unread") + (n.type === "order_confirmed" ? " order" : "")}
                onClick={() => void markOne(n)}>
                <div className="bd">{n.type === "order_confirmed" ? "🧾 " : ""}{n.body ?? n.type}</div>
                <div className="tm num">{timeLabel(n.created_at)}</div>
              </div>
            ))}
          </div>
          {pushSupported && (
            <div className="notif-foot">
              <span>🔔 إشعارات المتصفح</span>
              <button className="linklike" onClick={() => void togglePush()}>
                {pushOn ? "إيقاف" : "تفعيل"}
              </button>
            </div>
          )}
          {pushMsg && <div className="notif-foot msg">{pushMsg}</div>}
        </div>
      )}
    </div>
  );
}
