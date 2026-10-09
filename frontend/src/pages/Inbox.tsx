import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type {
  AssignableUser, Conversation, ConversationPatch, Copilot, Message, MessageEvent, Note, Tag,
} from "../api/types";
import { useAuth } from "../auth";
import { getSocket } from "../socket";
import { ConversationList } from "../components/ConversationList";
import { ChatThread } from "../components/ChatThread";
import { ContextPanel } from "../components/ContextPanel";

interface ListResponse { conversations: Conversation[]; }
interface MessagesResponse { conversation: Conversation; messages: Message[]; }
interface ReplyResponse { message: Message; }
interface ConvResponse { conversation: Conversation; }

export function Inbox() {
  const { user } = useAuth();
  const canAssign = !!user?.permissions.includes("assign_conversations");

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [copilot, setCopilot] = useState<Copilot | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [draft, setDraft] = useState("");
  const [assignables, setAssignables] = useState<AssignableUser[]>([]);
  const [allTags, setAllTags] = useState<Tag[]>([]);

  const selectedId = selected?.id ?? null;
  const selectedRef = useRef<number | null>(null);
  selectedRef.current = selectedId;

  const upsert = useCallback((patch: ConversationPatch) => {
    setConversations((prev) => {
      const idx = prev.findIndex((c) => c.id === patch.id);
      if (idx === -1) {
        void api.get<ListResponse>("/conversations").then((r) => setConversations(r.conversations));
        return prev;
      }
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
    setSelected((cur) => (cur && cur.id === patch.id ? { ...cur, ...patch } : cur));
  }, []);

  const addMessage = useCallback((m: Message) => {
    setMessages((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
  }, []);

  const loadCopilot = useCallback((id: number) => {
    void api.get<{ run: Copilot | null }>(`/conversations/${id}/copilot`).then((r) => setCopilot(r.run));
  }, []);

  // Initial load + socket wiring + reference data.
  useEffect(() => {
    void api.get<ListResponse>("/conversations").then((r) => setConversations(r.conversations));
    void api.get<{ users: AssignableUser[] }>("/conversations/assignable").then((r) => setAssignables(r.users));
    void api.get<{ tags: Tag[] }>("/catalog/tags").then((r) => setAllTags(r.tags)).catch(() => undefined);

    const socket = getSocket();
    const onInbox = (p: ConversationPatch) => upsert(p);
    const onConvUpdate = (p: ConversationPatch) => upsert(p);
    const onMessage = (e: MessageEvent) => {
      if (e.conversation_id === selectedRef.current) {
        addMessage({
          ...e, sender_user_id: null, send_status: null, attachments: [],
          ai_confidence: e.ai_confidence ?? null, ai_sources: e.ai_sources ?? [],
        });
        if (e.sender_type === "ai") loadCopilot(e.conversation_id);
      }
      if (e.body) upsert({ id: e.conversation_id, last_message_preview: e.body });
    };
    socket.on("inbox:update", onInbox);
    socket.on("conversation:update", onConvUpdate);
    socket.on("message:new", onMessage);
    return () => {
      socket.off("inbox:update", onInbox);
      socket.off("conversation:update", onConvUpdate);
      socket.off("message:new", onMessage);
    };
  }, [upsert, addMessage, loadCopilot]);

  const openConversation = useCallback(async (c: Conversation) => {
    setSelected(c);
    setMessages([]);
    setCopilot(null);
    setNotes([]);
    setDraft("");
    getSocket().emit("conversation:open", { conversation_id: c.id });
    const res = await api.get<MessagesResponse>(`/conversations/${c.id}/messages`);
    setSelected(res.conversation);
    setMessages(res.messages);
    setConversations((prev) => prev.map((x) => (x.id === c.id ? { ...x, unread_count: 0 } : x)));
    loadCopilot(c.id);
    void api.get<{ notes: Note[] }>(`/conversations/${c.id}/notes`).then((r) => setNotes(r.notes));
  }, [loadCopilot]);

  async function reply(text: string) {
    if (!selected) return;
    const res = await api.post<ReplyResponse>(`/conversations/${selected.id}/reply`, { text });
    addMessage(res.message);
  }

  async function addNote(body: string) {
    if (!selected) return;
    const res = await api.post<{ note: Note }>(`/conversations/${selected.id}/notes`, { body });
    setNotes((prev) => [res.note, ...prev]);
  }

  async function act(path: string, body: unknown) {
    if (!selected) return;
    const res = await api.post<ConvResponse>(`/conversations/${selected.id}/${path}`, body);
    setSelected(res.conversation);
    upsert(res.conversation);
  }

  async function addTag(tagId: number) {
    if (!selected) return;
    const res = await api.post<ConvResponse>(`/conversations/${selected.id}/tags`, { tag_id: tagId });
    setSelected(res.conversation);
    upsert(res.conversation);
  }
  async function removeTag(tagId: number) {
    if (!selected) return;
    const res = await api.del<ConvResponse>(`/conversations/${selected.id}/tags/${tagId}`);
    setSelected(res.conversation);
    upsert(res.conversation);
  }

  async function block(blocked: boolean) {
    if (!selected?.contact) return;
    await api.post(`/contacts/${selected.contact.id}/block`, { blocked });
    setSelected((cur) => (cur && cur.contact ? { ...cur, contact: { ...cur.contact, is_blocked: blocked } } : cur));
  }

  return (
    <div className={"inbox" + (selected ? " has-sel" : "")}>
      <ConversationList
        conversations={conversations}
        selectedId={selectedId}
        filter={filter}
        search={search}
        onSearch={setSearch}
        onFilter={setFilter}
        onSelect={(c) => void openConversation(c)}
      />
      {selected ? (
        <ChatThread
          conversation={selected}
          messages={messages}
          copilot={copilot}
          assignables={assignables}
          canAssign={canAssign}
          draft={draft}
          setDraft={setDraft}
          onReply={reply}
          onNote={addNote}
          onBack={() => setSelected(null)}
          onResolve={() => void act("state", { state: "resolved" })}
          onAiMode={(m) => void act("ai-mode", { mode: m })}
          onAssign={(uid) => void act("assign", { assignee_id: uid })}
        />
      ) : (
        <section className="thread"><div className="empty">اختر محادثة لعرضها</div></section>
      )}
      {selected && (
        <ContextPanel
          conversation={selected}
          copilot={copilot}
          notes={notes}
          allTags={allTags}
          onBlock={(b) => void block(b)}
          onAddTag={(id) => void addTag(id)}
          onRemoveTag={(id) => void removeTag(id)}
          onAddNote={(b) => void addNote(b)}
          onInsertDraft={(t) => setDraft(t)}
        />
      )}
    </div>
  );
}
