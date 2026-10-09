import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { usePermission } from "../auth";
import type { PromptVersion } from "../api/types";

export function Settings() {
  const canAi = usePermission("ai_settings");
  const canChannels = usePermission("manage_channels");
  const canOrg = usePermission("manage_org_settings");
  return (
    <div className="page">
      <div className="page-head"><h1>الإعدادات</h1></div>
      {canAi && <AISettingsCard />}
      {canAi && <PromptsCard />}
      {canChannels && <ChannelsCard />}
      {canOrg && <OrgSettingsCard />}
      {!canAi && !canChannels && !canOrg && <div className="muted">لا توجد إعدادات متاحة لدورك.</div>}
    </div>
  );
}

/* ----------------------------- AI ----------------------------- */

interface AISettings {
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  ai_enabled: boolean;
  confidence_threshold: number;
  max_consecutive_replies: number;
  send_delay_seconds: number;
}

function AISettingsCard() {
  const [s, setS] = useState<AISettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.get<{ settings: AISettings }>("/settings/ai").then((r) => setS(r.settings));
  }, []);

  if (!s) return <div className="card"><h2>الذكاء الاصطناعي</h2><div className="muted">جارٍ التحميل…</div></div>;

  async function save() {
    if (!s) return;
    setError(null);
    setSaved(false);
    const body: Record<string, unknown> = {
      provider: s.provider, model: s.model, base_url: s.base_url,
      ai_enabled: s.ai_enabled, confidence_threshold: s.confidence_threshold,
      max_consecutive_replies: s.max_consecutive_replies,
      send_delay_seconds: s.send_delay_seconds,
    };
    if (apiKey.trim()) body.api_key = apiKey.trim();
    try {
      const r = await api.put<{ settings: AISettings }>("/settings/ai", body);
      setS(r.settings);
      setApiKey("");
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "تعذّر الحفظ");
    }
  }

  return (
    <div className="card">
      <h2>الذكاء الاصطناعي <span className="muted">(DeepSeek افتراضيًا)</span></h2>
      <label className="checkbox">
        <input type="checkbox" checked={s.ai_enabled}
          onChange={(e) => setS({ ...s, ai_enabled: e.target.checked })} />
        تفعيل الرد الآلي عامًا (المفتاح العام — Kill Switch)
      </label>
      <div className="row" style={{ marginTop: 14 }}>
        <div className="field"><label>المزوّد</label>
          <input value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })} dir="ltr" /></div>
        <div className="field"><label>النموذج</label>
          <input value={s.model} onChange={(e) => setS({ ...s, model: e.target.value })} dir="ltr" /></div>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <div className="field"><label>Base URL</label>
          <input value={s.base_url} onChange={(e) => setS({ ...s, base_url: e.target.value })} dir="ltr" /></div>
        <div className="field">
          <label>مفتاح الـ API {s.has_api_key && <span className="ok">(محفوظ)</span>}</label>
          <input type="password" placeholder={s.has_api_key ? "••••••••  (اتركه فارغًا للإبقاء)" : "sk-..."}
            value={apiKey} onChange={(e) => setApiKey(e.target.value)} dir="ltr" />
        </div>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <div className="field"><label>حد الثقة (0–1)</label>
          <input type="number" min={0} max={1} step={0.05} value={s.confidence_threshold}
            onChange={(e) => setS({ ...s, confidence_threshold: Number(e.target.value) })} dir="ltr" /></div>
        <div className="field"><label>أقصى ردود متتالية</label>
          <input type="number" min={1} value={s.max_consecutive_replies}
            onChange={(e) => setS({ ...s, max_consecutive_replies: Number(e.target.value) })} dir="ltr" /></div>
        <div className="field"><label>تأخير الإرسال (ثوانٍ)</label>
          <input type="number" min={0} value={s.send_delay_seconds}
            onChange={(e) => setS({ ...s, send_delay_seconds: Number(e.target.value) })} dir="ltr" /></div>
      </div>
      {error && <div className="banner err" style={{ marginTop: 12 }}>{error}</div>}
      <div className="actions" style={{ marginTop: 14 }}>
        <button className="btn sm" onClick={() => void save()}>حفظ</button>
        {saved && <span className="ok">تم الحفظ ✓</span>}
      </div>
    </div>
  );
}

/* --------------------------- prompts --------------------------- */

function PromptsCard() {
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [draft, setDraft] = useState("");
  const [tone, setTone] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    void api.get<{ prompts: PromptVersion[] }>("/settings/prompts").then((r) => setPrompts(r.prompts));
  }
  useEffect(reload, []);

  async function create(activate: boolean) {
    setError(null);
    if (!draft.trim()) return;
    try {
      await api.post("/settings/prompts", { system_prompt: draft, tone: tone || null, activate });
      setDraft(""); setTone("");
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "تعذّر الحفظ");
    }
  }

  async function activate(id: number) {
    await api.post(`/settings/prompts/${id}/activate`);
    reload();
  }

  const active = prompts.find((p) => p.is_active);

  return (
    <div className="card">
      <h2>شخصية الذكاء الاصطناعي (البرومت)</h2>
      {active && (
        <div className="muted" style={{ marginBottom: 10, fontSize: 12 }}>
          النسخة المفعّلة حاليًا: v{active.version}{active.tone ? ` · ${active.tone}` : ""}
        </div>
      )}
      <div className="field">
        <label>نص برومت جديد</label>
        <textarea className="ta" value={draft} onChange={(e) => setDraft(e.target.value)}
          placeholder="تعليمات النظام للذكاء الاصطناعي…" />
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <div className="field"><label>النبرة (اختياري)</label>
          <input value={tone} onChange={(e) => setTone(e.target.value)} /></div>
      </div>
      {error && <div className="banner err" style={{ marginTop: 10 }}>{error}</div>}
      <div className="actions" style={{ marginTop: 12 }}>
        <button className="btn sm" onClick={() => void create(true)} disabled={!draft.trim()}>حفظ وتفعيل</button>
        <button className="btn sm ghost" onClick={() => void create(false)} disabled={!draft.trim()}>حفظ كمسودة</button>
      </div>

      <h2 style={{ marginTop: 18 }}>النسخ ({prompts.length})</h2>
      <div className="list-rows">
        {prompts.map((p) => (
          <div key={p.id} className="kb-item">
            <div className="t">
              <div className="ttl">النسخة v{p.version} {p.is_active && <span className="pill connected">مفعّلة</span>}</div>
              <div className="mt" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {p.system_prompt.slice(0, 80)}
              </div>
            </div>
            {!p.is_active && <button className="btn sm ghost" onClick={() => void activate(p.id)}>تفعيل</button>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* --------------------------- channels --------------------------- */

interface Channel {
  id: number;
  type: string;
  name: string;
  status: string;
  has_credentials: boolean;
  account_id: string | null;
  bot_link: string | null;
  page_name: string | null;
  webhook_url: string | null;
  commands: { command: string; description: string }[];
  last_error: string | null;
}

function ChannelsCard() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [newType, setNewType] = useState("telegram");
  const [newName, setNewName] = useState("");

  function reload() {
    void api.get<{ channels: Channel[] }>("/settings/channels").then((r) => setChannels(r.channels));
  }
  useEffect(reload, []);

  async function create() {
    if (!newName.trim()) return;
    await api.post("/settings/channels", { type: newType, name: newName.trim() });
    setNewName("");
    reload();
  }

  return (
    <div className="card">
      <h2>القنوات</h2>
      <div className="actions" style={{ marginBottom: 16 }}>
        <div className="field" style={{ minWidth: 150 }}>
          <label>نوع القناة</label>
          <select value={newType} onChange={(e) => setNewType(e.target.value)}>
            <option value="telegram">Telegram</option>
            <option value="messenger">Messenger</option>
            <option value="instagram">Instagram</option>
          </select>
        </div>
        <div className="field" style={{ minWidth: 180 }}>
          <label>الاسم</label>
          <input value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
        <button className="btn sm" onClick={() => void create()}>إضافة قناة</button>
      </div>

      <div className="list-rows">
        {channels.map((c) => <ChannelCard key={c.id} channel={c} onChanged={reload} />)}
        {channels.length === 0 && <div className="muted">لا قنوات بعد</div>}
      </div>
    </div>
  );
}

function ChannelCard({ channel, onChanged }: { channel: Channel; onChanged: () => void }) {
  const isTelegram = channel.type === "telegram";
  const isInstagram = channel.type === "instagram";
  const [botToken, setBotToken] = useState("");
  const [pageToken, setPageToken] = useState("");
  const [pageId, setPageId] = useState("");
  const [igId, setIgId] = useState("");
  const [commands, setCommands] = useState(
    channel.commands.map((c) => `${c.command}|${c.description}`).join("\n")
  );
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function saveCreds() {
    setError(null); setMsg(null);
    const body: Record<string, unknown> = {};
    if (isTelegram) {
      if (botToken.trim()) body.bot_token = botToken.trim();
      body.commands = commands.split("\n").map((l) => {
        const [command, ...rest] = l.split("|");
        return { command: command.trim(), description: rest.join("|").trim() };
      }).filter((c) => c.command);
    } else {
      if (pageToken.trim()) body.page_access_token = pageToken.trim();
      if (pageId.trim()) body.page_id = pageId.trim();
      if (isInstagram && igId.trim()) body.ig_id = igId.trim();
    }
    try {
      await api.put(`/settings/channels/${channel.id}`, body);
      setBotToken(""); setPageToken("");
      setMsg("تم الحفظ");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "تعذّر الحفظ");
    }
  }

  async function action(path: string) {
    setError(null); setMsg(null);
    try {
      const r = await api.post<{ ok?: boolean; info?: { link?: string; name?: string } }>(
        `/settings/channels/${channel.id}/${path}`);
      setMsg(r.info?.link ?? r.info?.name ?? "تم");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? String((e.data as { error?: string })?.error ?? e.message) : "فشل");
    }
  }

  return (
    <div className="kb-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 12 }}>
      <div className="actions" style={{ justifyContent: "space-between" }}>
        <div className="t">
          <div className="ttl">{channel.name} <span className="muted">({channel.type})</span></div>
          <div className="mt">
            {channel.bot_link ? <a className="link" href={channel.bot_link} target="_blank" rel="noreferrer">{channel.bot_link}</a> : null}
            {channel.page_name ? channel.page_name : null}
            {channel.account_id ? ` · ${channel.account_id}` : ""}
          </div>
        </div>
        <span className={"pill " + channel.status}>{channel.status}</span>
      </div>

      {isTelegram ? (
        <>
          <div className="field">
            <label>توكن البوت (من @BotFather)</label>
            <input type="password" placeholder={channel.has_credentials ? "••••••  (اتركه فارغًا للإبقاء)" : "123456:ABC..."}
              value={botToken} onChange={(e) => setBotToken(e.target.value)} dir="ltr" />
          </div>
          <div className="field">
            <label>الأوامر <span className="muted">(سطر لكل أمر: الأمر|الوصف)</span></label>
            <textarea className="ta" style={{ minHeight: 70 }} value={commands}
              onChange={(e) => setCommands(e.target.value)} dir="ltr" />
          </div>
        </>
      ) : (
        <div className="row">
          <div className="field"><label>Page Access Token</label>
            <input type="password" placeholder={channel.has_credentials ? "••••••" : "EAAB..."}
              value={pageToken} onChange={(e) => setPageToken(e.target.value)} dir="ltr" /></div>
          <div className="field"><label>Page ID</label>
            <input value={pageId} onChange={(e) => setPageId(e.target.value)} dir="ltr" /></div>
          {isInstagram && (
            <div className="field"><label>Instagram ID</label>
              <input value={igId} onChange={(e) => setIgId(e.target.value)} dir="ltr" /></div>
          )}
        </div>
      )}

      {error && <div className="banner err">{error}</div>}
      {msg && <div className="ok">{msg}</div>}

      <div className="actions">
        <button className="btn sm" onClick={() => void saveCreds()}>حفظ البيانات</button>
        <button className="btn sm ghost" onClick={() => void action("test")}>اختبار الاتصال</button>
        <button className="btn sm" onClick={() => void action("connect")}>ربط</button>
        <button className="btn sm ghost" onClick={() => void action("disconnect")}>فصل</button>
      </div>
    </div>
  );
}

/* ------------------------ org / automation ------------------------ */

interface OrgSettings {
  welcome_enabled: boolean;
  welcome_text: string;
  timezone: string;
  business_hours: Record<string, [string, string]>;
  out_of_hours_enabled: boolean;
  out_of_hours_text: string;
  auto_assign_enabled: boolean;
  auto_assign_strategy: string;
  sla_minutes: number | null;
  auto_close_minutes: number | null;
  retention_days: number | null;
  handoff_text: string;
  order_notify_telegram_chat_id: string | null;
}

const DAYS: { key: string; label: string }[] = [
  { key: "sat", label: "السبت" }, { key: "sun", label: "الأحد" },
  { key: "mon", label: "الإثنين" }, { key: "tue", label: "الثلاثاء" },
  { key: "wed", label: "الأربعاء" }, { key: "thu", label: "الخميس" },
  { key: "fri", label: "الجمعة" },
];

interface DayHours { open: boolean; from: string; to: string; }

function OrgSettingsCard() {
  const [s, setS] = useState<OrgSettings | null>(null);
  const [hours, setHours] = useState<Record<string, DayHours>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.get<{ settings: OrgSettings }>("/settings/org").then((r) => {
      setS(r.settings);
      const bh = r.settings.business_hours || {};
      const init: Record<string, DayHours> = {};
      for (const d of DAYS) {
        const w = bh[d.key];
        init[d.key] = w
          ? { open: true, from: w[0], to: w[1] }
          : { open: false, from: "09:00", to: "17:00" };
      }
      setHours(init);
    });
  }, []);

  if (!s) return <div className="card"><h2>الأتمتة وساعات العمل</h2><div className="muted">جارٍ التحميل…</div></div>;

  function num(v: string): number | null {
    return v.trim() === "" ? null : Number(v);
  }

  async function save() {
    if (!s) return;
    setError(null);
    setSaved(false);
    const business_hours: Record<string, [string, string]> = {};
    for (const d of DAYS) {
      const h = hours[d.key];
      if (h?.open) business_hours[d.key] = [h.from, h.to];
    }
    try {
      const r = await api.put<{ settings: OrgSettings }>("/settings/org", { ...s, business_hours });
      setS(r.settings);
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "تعذّر الحفظ");
    }
  }

  return (
    <div className="card">
      <h2>الأتمتة وساعات العمل</h2>

      <label className="checkbox">
        <input type="checkbox" checked={s.welcome_enabled}
          onChange={(e) => setS({ ...s, welcome_enabled: e.target.checked })} />
        رسالة ترحيب عند أول رسالة
      </label>
      <div className="field" style={{ marginTop: 8 }}>
        <textarea className="ta" style={{ minHeight: 60 }} value={s.welcome_text}
          onChange={(e) => setS({ ...s, welcome_text: e.target.value })} />
      </div>

      <label className="checkbox" style={{ marginTop: 14 }}>
        <input type="checkbox" checked={s.auto_assign_enabled}
          onChange={(e) => setS({ ...s, auto_assign_enabled: e.target.checked })} />
        توزيع المحادثات تلقائيًا على الموظفين عند التصعيد
      </label>

      <div className="row" style={{ marginTop: 14 }}>
        <div className="field"><label>المنطقة الزمنية</label>
          <input value={s.timezone} onChange={(e) => setS({ ...s, timezone: e.target.value })} dir="ltr" /></div>
        <div className="field"><label>تنبيه SLA (دقائق، فارغ=معطّل)</label>
          <input type="number" min={0} value={s.sla_minutes ?? ""} dir="ltr"
            onChange={(e) => setS({ ...s, sla_minutes: num(e.target.value) })} /></div>
        <div className="field"><label>إغلاق تلقائي للخامل (دقائق)</label>
          <input type="number" min={0} value={s.auto_close_minutes ?? ""} dir="ltr"
            onChange={(e) => setS({ ...s, auto_close_minutes: num(e.target.value) })} /></div>
        <div className="field"><label>مدة الاحتفاظ (أيام)</label>
          <input type="number" min={0} value={s.retention_days ?? ""} dir="ltr"
            onChange={(e) => setS({ ...s, retention_days: num(e.target.value) })} /></div>
      </div>

      <h2 style={{ marginTop: 18 }}>ساعات العمل</h2>
      <div className="list-rows">
        {DAYS.map((d) => {
          const h = hours[d.key] ?? { open: false, from: "09:00", to: "17:00" };
          return (
            <div key={d.key} className="bar-row" style={{ gridTemplateColumns: "110px auto auto", gap: 12 }}>
              <label className="checkbox">
                <input type="checkbox" checked={h.open}
                  onChange={(e) => setHours({ ...hours, [d.key]: { ...h, open: e.target.checked } })} />
                {d.label}
              </label>
              <input type="time" value={h.from} disabled={!h.open} dir="ltr"
                onChange={(e) => setHours({ ...hours, [d.key]: { ...h, from: e.target.value } })} />
              <input type="time" value={h.to} disabled={!h.open} dir="ltr"
                onChange={(e) => setHours({ ...hours, [d.key]: { ...h, to: e.target.value } })} />
            </div>
          );
        })}
      </div>

      <label className="checkbox" style={{ marginTop: 14 }}>
        <input type="checkbox" checked={s.out_of_hours_enabled}
          onChange={(e) => setS({ ...s, out_of_hours_enabled: e.target.checked })} />
        رسالة تلقائية خارج ساعات العمل
      </label>
      <div className="field" style={{ marginTop: 8 }}>
        <textarea className="ta" style={{ minHeight: 60 }} value={s.out_of_hours_text}
          onChange={(e) => setS({ ...s, out_of_hours_text: e.target.value })} />
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label>رسالة التحويل لموظف (عند التصعيد)</label>
        <textarea className="ta" style={{ minHeight: 60 }} value={s.handoff_text}
          onChange={(e) => setS({ ...s, handoff_text: e.target.value })} />
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label>معرّف جروب تليجرام لإشعارات الأوردرات (اختياري)</label>
        <input value={s.order_notify_telegram_chat_id ?? ""} dir="ltr"
          placeholder="-1001234567890"
          onChange={(e) => setS({ ...s, order_notify_telegram_chat_id: e.target.value })} />
      </div>

      {error && <div className="banner err" style={{ marginTop: 12 }}>{error}</div>}
      <div className="actions" style={{ marginTop: 14 }}>
        <button className="btn sm" onClick={() => void save()}>حفظ</button>
        {saved && <span className="ok">تم الحفظ ✓</span>}
      </div>
    </div>
  );
}
