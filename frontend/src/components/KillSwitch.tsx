import { useEffect, useState } from "react";
import { api } from "../api/client";

export function KillSwitch() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api
      .get<{ ai_enabled: boolean }>("/settings/ai/kill-switch")
      .then((r) => setEnabled(r.ai_enabled))
      .catch(() => setEnabled(null));
  }, []);

  if (enabled === null) return null;

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.post<{ ai_enabled: boolean }>("/settings/ai/kill-switch", { enabled: !enabled });
      setEnabled(r.ai_enabled);
    } catch {
      /* ignore — leave current state */
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      className={"kill" + (enabled ? "" : " off")}
      onClick={() => void toggle()}
      disabled={busy}
      title="المفتاح العام للذكاء الاصطناعي"
    >
      <span className="dot" />
      {enabled ? "الذكاء الاصطناعي يعمل" : "الذكاء الاصطناعي موقوف"}
    </button>
  );
}
