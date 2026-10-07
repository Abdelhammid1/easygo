import { useState } from "react";
import type { Conversation, Copilot, Note, Tag } from "../api/types";

function reasonLabel(code: string | null): string {
  const map: Record<string, string> = {
    requested_human: "طلب موظف",
    negative_sentiment: "نبرة استياء",
    low_confidence: "ثقة منخفضة",
    no_kb_answer: "لا إجابة في قاعدة المعرفة",
    sensitive_topic: "موضوع حساس",
    repeated_failure: "تكرار دون حل",
    unreadable_media: "وسائط غير مقروءة",
    ai_error: "عطل تقني",
  };
  return code ? map[code] ?? code : "";
}

interface Props {
  conversation: Conversation;
  copilot: Copilot | null;
  notes: Note[];
  allTags: Tag[];
  onBlock: (blocked: boolean) => void;
  onAddTag: (tagId: number) => void;
  onRemoveTag: (tagId: number) => void;
  onAddNote: (body: string) => void;
  onInsertDraft: (text: string) => void;
}

export function ContextPanel({
  conversation, copilot, notes, allTags, onBlock, onAddTag, onRemoveTag, onAddNote, onInsertDraft,
}: Props) {
  const c = conversation.contact;
  const [note, setNote] = useState("");
  const [showTagPicker, setShowTagPicker] = useState(false);
  const conf = copilot?.confidence ?? null;
  const usedTagIds = new Set((conversation.tags ?? []).map((t) => t.id));
  const availableTags = allTags.filter((t) => !usedTagIds.has(t.id));

  function submitNote() {
    const b = note.trim();
    if (!b) return;
    onAddNote(b);
    setNote("");
  }

  return (
    <aside className="ctx">
      <div className="ctx-sec">
        <div className="contact">
          <span className="av" style={{ background: "#e0724c", width: 52, height: 52, fontSize: 18 }}>
            {(c?.name ?? "؟").charAt(0)}
          </span>
          <div>
            <div className="nm">{c?.name ?? "عميل"}</div>
            <div className="sub">عبر {conversation.channel ?? "—"}</div>
          </div>
        </div>
        <div className="cbtns">
          <button className={c?.is_blocked ? "" : "danger"} onClick={() => onBlock(!c?.is_blocked)}>
            {c?.is_blocked ? "إلغاء الحظر" : "حظر"}
          </button>
        </div>
        {c?.phone && <div className="kv"><span className="k">الهاتف</span><span className="v num" style={{ direction: "ltr" }}>{c.phone}</span></div>}
        {c?.address && <div className="kv"><span className="k">العنوان</span><span className="v">{c.address}</span></div>}
      </div>

      <div className="ctx-sec">
        <div className="ctx-h">الوسوم</div>
        <div className="tags">
          {(conversation.tags ?? []).map((t) => (
            <span key={t.id} className="utag" style={t.color ? { color: t.color } : undefined}>
              {t.name}<button onClick={() => onRemoveTag(t.id)} aria-label="إزالة">×</button>
            </span>
          ))}
          <button className="utag add" onClick={() => setShowTagPicker((v) => !v)}>+ إضافة</button>
        </div>
        {showTagPicker && (
          <div className="tags">
            {availableTags.length === 0 && <span className="muted" style={{ fontSize: 12 }}>لا وسوم متاحة</span>}
            {availableTags.map((t) => (
              <button key={t.id} className="utag" onClick={() => { onAddTag(t.id); setShowTagPicker(false); }}>
                {t.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {copilot && (
        <div className="ctx-sec">
          <div className="ctx-h">✦ مساعد الذكاء الاصطناعي</div>
          <div className="copilot">
            {conf != null && (
              <div>
                <div className="co-row" style={{ marginBottom: 5 }}>
                  <span className="k">درجة الثقة</span>
                  <span className="num" style={{ fontWeight: 700, color: conf < 0.6 ? "var(--warn)" : "var(--good)" }}>
                    {Math.round(conf * 100)}%
                  </span>
                </div>
                <div className="meter"><i className={conf >= 0.6 ? "high" : ""} style={{ width: `${Math.round(conf * 100)}%` }} /></div>
              </div>
            )}
            {copilot.escalation_reason && (
              <div className="co-row"><span className="k">سبب التصعيد</span>
                <span style={{ fontWeight: 600, color: "var(--fg-2)" }}>{reasonLabel(copilot.escalation_reason)}</span></div>
            )}
            {copilot.suggested_reply && (
              <div>
                <div className="ctx-h" style={{ marginBottom: 6 }}>مسودة مقترحة</div>
                <div className="co-draft">{copilot.suggested_reply}</div>
                <button className="mini solid" style={{ marginTop: 8, width: "100%" }}
                  onClick={() => onInsertDraft(copilot.suggested_reply ?? "")}>إدراج في الرد</button>
              </div>
            )}
            {copilot.sources.length > 0 && (
              <div>
                <div className="ctx-h" style={{ marginBottom: 6 }}>المصادر المستخدمة</div>
                <div className="tags">{copilot.sources.map((srcName) => <span key={srcName} className="src-chip">{srcName}</span>)}</div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="ctx-sec">
        <div className="ctx-h">ملاحظات داخلية</div>
        {notes.map((n) => (
          <div key={n.id} className="note">
            {n.body}
            <div className="by">— {n.author ?? "موظف"}{n.at ? ` · ${new Date(n.at).toLocaleString("ar-EG", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}` : ""}</div>
          </div>
        ))}
        <div className="addnote">
          <input placeholder="أضف ملاحظة لا يراها العميل…" value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submitNote(); }} />
        </div>
      </div>
    </aside>
  );
}
