import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { usePermission } from "../auth";

interface KBItem {
  id: number;
  title: string;
  category: string | null;
  is_active: boolean;
  source_type: string | null;
  chunk_count: number;
  updated_at: string | null;
  content: string | null;
}

interface Draft {
  id: number; // 0 = new
  title: string;
  category: string;
  content: string;
  is_active: boolean;
}

interface Suggestion { question: string; confidence: number | null; at: string | null; }

interface PlaygroundResult {
  reply: string | null;
  confidence: number | null;
  escalate: boolean;
  used_chunks: { id: number; item_id: number; content: string }[];
}

const EMPTY: Draft = { id: 0, title: "", category: "", content: "", is_active: true };

export function Knowledge() {
  const canManage = usePermission("manage_kb");
  const [items, setItems] = useState<KBItem[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [query, setQuery] = useState("");
  const [pg, setPg] = useState<PlaygroundResult | null>(null);
  const [pgBusy, setPgBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function reload() {
    void api.get<{ items: KBItem[] }>("/knowledge").then((r) => setItems(r.items));
  }

  useEffect(() => {
    reload();
    if (canManage) {
      void api.get<{ suggestions: Suggestion[] }>("/knowledge/suggestions")
        .then((r) => setSuggestions(r.suggestions))
        .catch(() => undefined);
    }
  }, [canManage]);

  async function save() {
    if (!draft) return;
    setError(null);
    try {
      if (draft.id === 0) {
        await api.post("/knowledge", {
          title: draft.title, category: draft.category || null,
          content: draft.content, is_active: draft.is_active,
        });
      } else {
        await api.put(`/knowledge/${draft.id}`, {
          title: draft.title, category: draft.category || null,
          content: draft.content, is_active: draft.is_active,
        });
      }
      setDraft(null);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "تعذّر الحفظ");
    }
  }

  async function remove(id: number) {
    await api.del(`/knowledge/${id}`);
    reload();
  }

  async function doUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      await api.upload("/knowledge/upload", form);
      if (fileRef.current) fileRef.current.value = "";
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? String((e.data as { error?: string })?.error ?? e.message) : "تعذّر الرفع");
    }
  }

  async function runPlayground() {
    if (!query.trim()) return;
    setPgBusy(true);
    setPg(null);
    try {
      const r = await api.post<{ result: PlaygroundResult }>("/knowledge/playground", { query });
      setPg(r.result);
    } catch {
      setError("تعذّر تشغيل الاختبار (تحقق من مفتاح الذكاء الاصطناعي)");
    } finally {
      setPgBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>قاعدة المعرفة</h1>
        {canManage && (
          <div className="actions">
            <button className="btn sm" onClick={() => setDraft({ ...EMPTY })}>+ عنصر جديد</button>
          </div>
        )}
      </div>

      {error && <div className="banner err">{error}</div>}

      {canManage && draft && (
        <div className="card">
          <h2>{draft.id === 0 ? "عنصر جديد" : "تعديل العنصر"}</h2>
          <div className="row">
            <div className="field">
              <label>العنوان</label>
              <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            </div>
            <div className="field">
              <label>التصنيف</label>
              <input value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} />
            </div>
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label>المحتوى</label>
            <textarea className="ta" value={draft.content}
              onChange={(e) => setDraft({ ...draft, content: e.target.value })} />
          </div>
          <label className="checkbox" style={{ marginTop: 12 }}>
            <input type="checkbox" checked={draft.is_active}
              onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
            مُفعّل
          </label>
          <div className="actions" style={{ marginTop: 14 }}>
            <button className="btn sm" onClick={() => void save()} disabled={!draft.title.trim()}>حفظ</button>
            <button className="btn sm ghost" onClick={() => setDraft(null)}>إلغاء</button>
          </div>
        </div>
      )}

      {canManage && (
        <div className="card">
          <h2>رفع ملف <span className="muted">(PDF, Word, Excel, CSV, نص)</span></h2>
          <div className="actions">
            <input ref={fileRef} type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md" />
            <button className="btn sm" onClick={() => void doUpload()}>رفع واستخراج</button>
          </div>
        </div>
      )}

      {canManage && (
        <div className="card">
          <h2>اختبار الذكاء الاصطناعي <span className="muted">(Playground)</span></h2>
          <div className="actions">
            <input style={{ flex: 1, minWidth: 220 }} placeholder="اكتب سؤال عميل…"
              value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="btn sm" onClick={() => void runPlayground()} disabled={pgBusy || !query.trim()}>
              {pgBusy ? "…" : "تشغيل"}
            </button>
          </div>
          {pg && (
            <div className="pg-result">
              <div><b>الرد:</b> {pg.reply ?? "—"}</div>
              <div className="muted" style={{ marginTop: 6 }}>
                الثقة: {pg.confidence != null ? Math.round(pg.confidence * 100) + "%" : "—"}
                {pg.escalate ? " · سيُصعَّد لموظف" : ""}
              </div>
              {pg.used_chunks.length > 0 && (
                <div className="actions" style={{ marginTop: 8 }}>
                  {pg.used_chunks.map((c) => <span key={c.id} className="chip-src">#{c.item_id}</span>)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2>العناصر <span className="muted">({items.length})</span></h2>
        <div className="list-rows">
          {items.length === 0 && <div className="muted">لا عناصر بعد</div>}
          {items.map((it) => (
            <div key={it.id} className="kb-item">
              <div className="t">
                <div className="ttl">{it.title} {!it.is_active && <span className="muted">(معطّل)</span>}</div>
                <div className="mt">
                  {it.category ? it.category + " · " : ""}{it.chunk_count} مقطع
                  {it.source_type && it.source_type !== "text" ? " · " + it.source_type : ""}
                </div>
              </div>
              {canManage && (
                <div className="actions">
                  <button className="btn sm ghost" onClick={() => setDraft({
                    id: it.id, title: it.title, category: it.category ?? "",
                    content: it.content ?? "", is_active: it.is_active,
                  })}>تعديل</button>
                  <button className="btn sm danger" onClick={() => void remove(it.id)}>حذف</button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {canManage && suggestions.length > 0 && (
        <div className="card">
          <h2>أسئلة لم يجد لها الذكاء الاصطناعي إجابة</h2>
          <div className="list-rows">
            {suggestions.map((s, i) => (
              <div key={i} className="kb-item">
                <div className="t"><div className="ttl">{s.question}</div></div>
                {canManage && (
                  <button className="btn sm ghost" onClick={() => setDraft({
                    ...EMPTY, title: s.question.slice(0, 80), content: "",
                  })}>أضف للقاعدة</button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
