import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { Attachment, AssignableUser, Conversation, Copilot, Message } from "../api/types";
import { IconAttach, IconBack, IconCanned, IconImage, IconPlay, IconSend } from "../icons";

function timeLabel(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" });
}

function windowLabel(conv: Conversation): string | null {
  if (!conv.reply_window_expires_at) return null;
  const ms = new Date(conv.reply_window_expires_at).getTime() - Date.now();
  if (ms <= 0) return "انتهت نافذة الرد";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return `نافذة الرد: ${h}:${String(m).padStart(2, "0")}`;
}

function Media({ a }: { a: Attachment }) {
  if (a.type === "image") {
    return <img className="msg-img" src={a.url} alt={a.image_description ?? "صورة"} />;
  }
  if (a.type === "audio") {
    return (
      <div>
        <div className="voice">
          <a className="play" href={a.url} target="_blank" rel="noreferrer"><IconPlay /></a>
          <div className="wave">{Array.from({ length: 22 }).map((_, i) => (
            <span key={i} style={{ height: `${30 + ((i * 37) % 60)}%` }} />
          ))}</div>
        </div>
        {a.transcript && <div className="transcript">{a.transcript}</div>}
      </div>
    );
  }
  return <a className="link" href={a.url} target="_blank" rel="noreferrer">📎 ملف مرفق</a>;
}

interface Props {
  conversation: Conversation;
  messages: Message[];
  copilot: Copilot | null;
  assignables: AssignableUser[];
  canAssign: boolean;
  draft: string;
  setDraft: (text: string) => void;
  onReply: (text: string) => Promise<void>;
  onNote: (text: string) => Promise<void>;
  onBack: () => void;
  onResolve: () => void;
  onAiMode: (mode: "active" | "off") => void;
  onAssign: (userId: number | null) => void;
}

export function ChatThread({
  conversation, messages, copilot, assignables, canAssign, draft, setDraft,
  onReply, onNote, onBack, onResolve, onAiMode, onAssign,
}: Props) {
  const text = draft;
  const setText = setDraft;
  const [mode, setMode] = useState<"reply" | "note">("reply");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [messages]);

  const lastAiId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) if (messages[i].sender_type === "ai") return messages[i].id;
    return null;
  }, [messages]);

  const windowOpen = conversation.reply_window_open;
  const aiActive = conversation.ai_mode === "active";

  async function submit() {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true); setError(null);
    try {
      if (mode === "note") await onNote(body);
      else await onReply(body);
      setText("");
    } catch {
      setError(mode === "note" ? "تعذّر حفظ الملاحظة" : "تعذّر إرسال الرسالة");
    } finally {
      setBusy(false);
    }
  }
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void submit(); }
  }

  const win = windowLabel(conversation);

  return (
    <section className="thread">
      <header className="th-head">
        <button className="iconbtn" onClick={onBack} aria-label="رجوع"><IconBack /></button>
        <div className="th-id">
          <div className="meta">
            <div className="nm">
              {conversation.contact?.name ?? "عميل"}
              <span className={"tag " + conversation.state}>
                {conversation.state === "needs_human" ? "⚑ تحتاج موظفًا"
                  : conversation.state === "resolved" ? "✓ محلولة"
                  : conversation.state === "pending" ? "قيد الانتظار" : "مفتوحة"}
              </span>
            </div>
            <div className="sub">
              عبر {conversation.channel ?? "—"}
              {conversation.escalation_reason ? <> · <span style={{ color: "var(--warn)" }}>{conversation.escalation_reason}</span></> : null}
            </div>
          </div>
        </div>
        <div className="th-actions">
          {win && <span className={"window" + (windowOpen ? " open" : "")}>{win}</span>}
          {canAssign && (
            <span className="assign">
              معيّنة لـ:
              <select value={conversation.assignee_id ?? ""} onChange={(e) => onAssign(e.target.value ? Number(e.target.value) : null)}>
                <option value="">غير معيّنة</option>
                {assignables.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </span>
          )}
          <span className="ai-toggle">الرد الآلي
            <button className="switch" aria-pressed={aiActive} aria-label="تفعيل الرد الآلي"
              onClick={() => onAiMode(aiActive ? "off" : "active")} />
          </span>
          {conversation.state !== "resolved" && (
            <button className="iconbtn" title="تحديد كمحلولة" onClick={onResolve}>✓</button>
          )}
        </div>
      </header>

      <div className="msgs">
        {messages.length === 0 && <div className="empty">لا رسائل بعد</div>}
        {messages.map((m) => {
          if (m.sender_type === "system" && m.type === "system") {
            return <div key={m.id} className="escalate">{m.body}</div>;
          }
          const out = m.direction === "outbound";
          const kind = m.sender_type;
          const showAiFoot = kind === "ai" && m.id === lastAiId && copilot;
          return (
            <div key={m.id} className={"msg " + (out ? "out " + kind : "in")}>
              {out && (kind === "ai" || kind === "agent") && (
                <span className={"sender " + kind}>{kind === "ai" ? "✦ الذكاء الاصطناعي" : "موظف"}</span>
              )}
              <div className="bubble">
                {m.attachments.map((a) => <div key={a.id} style={{ marginBottom: m.body ? 6 : 0 }}><Media a={a} /></div>)}
                {m.body}
              </div>
              {showAiFoot && copilot && (
                <div className="ai-foot">
                  {copilot.confidence != null && (
                    <span className={"conf" + (copilot.confidence < 0.6 ? " low" : "")}>
                      ● الثقة {Math.round(copilot.confidence * 100)}%
                    </span>
                  )}
                  {copilot.sources.map((srcName) => <span key={srcName} className="src-chip">{srcName}</span>)}
                </div>
              )}
              <div className="m-meta">
                <span className="num">{timeLabel(m.created_at)}</span>
                {m.send_status === "read" && <span className="ticks">✓✓</span>}
                {m.send_status === "failed" && <span style={{ color: "var(--danger)" }}>فشل الإرسال</span>}
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <div className="composer">
        {error && <div className="banner err">{error}</div>}
        {mode === "reply" && copilot?.suggested_reply && (
          <div className="suggest">
            <div className="txt">
              <div className="hd">✦ اقتراح رد من الذكاء الاصطناعي</div>
              {copilot.suggested_reply}
            </div>
            <button className="mini solid" onClick={() => setText(copilot.suggested_reply ?? "")}>إدراج</button>
          </div>
        )}
        <div className="cmode">
          <button className={mode === "reply" ? "on" : ""} onClick={() => setMode("reply")}>رد على العميل</button>
          <button className={mode === "note" ? "on" : ""} onClick={() => setMode("note")}>📝 ملاحظة داخلية</button>
        </div>
        {mode === "reply" && !windowOpen ? (
          <div className="blocked">انتهت نافذة الرد (24 ساعة) — لا يمكن الإرسال الآن.</div>
        ) : (
          <div className={"inputbar" + (mode === "note" ? " note" : "")}>
            <textarea rows={1}
              placeholder={mode === "note" ? "ملاحظة لا يراها العميل…" : "اكتب رسالتك…"}
              value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKeyDown} />
            <div className="ctools">
              {mode === "reply" && <>
                <button className="ctool" title="إرفاق ملف"><IconAttach /></button>
                <button className="ctool" title="صورة"><IconImage /></button>
                <button className="ctool" title="ردود جاهزة"><IconCanned /></button>
              </>}
              <button className="send" onClick={() => void submit()} disabled={busy || !text.trim()}>
                {mode === "note" ? "حفظ" : "إرسال"} <IconSend />
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
