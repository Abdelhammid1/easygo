import type { Conversation, ConversationState } from "../api/types";
import { ChannelGlyph, CHANNEL_COLOR, IconSearch } from "../icons";

const STATE_LABEL: Record<ConversationState, string> = {
  open: "مفتوحة",
  needs_human: "⚑ تحتاج موظفًا",
  pending: "قيد الانتظار",
  resolved: "✓ محلولة",
};

const FILTERS: { key: string; label: string }[] = [
  { key: "", label: "الكل" },
  { key: "needs_human", label: "تحتاج موظفًا" },
  { key: "open", label: "مفتوحة" },
  { key: "resolved", label: "محلولة" },
];

const AVATAR_COLORS = ["#e0724c", "#c0498f", "#3b86c7", "#6c8f3a", "#4a8fb0", "#9a6cc0", "#b0894a"];
function avatarColor(id: number): string {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}
function initial(name: string | null | undefined): string {
  return (name ?? "؟").trim().charAt(0) || "؟";
}
function timeLabel(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" });
}

interface Props {
  conversations: Conversation[];
  selectedId: number | null;
  filter: string;
  search: string;
  onSearch: (q: string) => void;
  onFilter: (f: string) => void;
  onSelect: (c: Conversation) => void;
}

export function ConversationList({ conversations, selectedId, filter, search, onSearch, onFilter, onSelect }: Props) {
  const q = search.trim();
  const shown = conversations.filter((c) => {
    if (filter && c.state !== filter) return false;
    if (q && !(c.contact?.name ?? "").includes(q) && !(c.last_message_preview ?? "").includes(q)) return false;
    return true;
  });
  const openCount = conversations.filter((c) => c.state !== "resolved").length;

  return (
    <section className="list">
      <div className="list-head">
        <div className="list-title">
          <h1>الصندوق الموحد</h1>
          <span className="cnt"><b className="num">{openCount}</b> نشطة</span>
        </div>
        <label className="search">
          <IconSearch />
          <input placeholder="بحث في الأسماء والرسائل…" value={search}
            onChange={(e) => onSearch(e.target.value)} />
        </label>
        <div className="chips">
          {FILTERS.map((f) => (
            <button key={f.key || "all"} className={"chip" + (filter === f.key ? " on" : "")}
              onClick={() => onFilter(f.key)}>{f.label}</button>
          ))}
        </div>
      </div>
      <div className="threads">
        {shown.length === 0 && <div className="empty">لا توجد محادثات</div>}
        {shown.map((c) => (
          <div key={c.id}
            className={"citem" + (c.id === selectedId ? " active" : "") + (c.state === "needs_human" ? " alert" : "")}
            onClick={() => onSelect(c)}>
            <div className="chan-av">
              <span className="av" style={{ background: avatarColor(c.id) }}>{initial(c.contact?.name)}</span>
              <span className="chan-badge" style={{ background: CHANNEL_COLOR[c.channel ?? ""] ?? "var(--fg-3)" }}>
                <ChannelGlyph channel={c.channel} />
              </span>
            </div>
            <div className="cbody">
              <div className="crow">
                <span className="cname">{c.contact?.name ?? "عميل"}</span>
                <span className="ctime num">{timeLabel(c.last_message_at)}</span>
              </div>
              <div className="csnip">{c.last_message_preview ?? ""}</div>
              <div className="cmeta">
                <span className={"tag " + c.state}>{STATE_LABEL[c.state]}</span>
                {c.ai_mode === "active" && c.state !== "resolved" && (
                  <span className="ai-pill"><span className="pdot" />يرد آليًا</span>
                )}
                {c.unread_count > 0 && <span className="unread num">{c.unread_count}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
