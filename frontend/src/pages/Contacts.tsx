import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

interface Contact {
  id: number;
  name: string | null;
  phone: string | null;
  address: string | null;
  notes: string | null;
  is_blocked: boolean;
  custom_fields: Record<string, unknown>;
  identities?: { id: number; channel_id: number; external_id: string; display_name: string | null }[];
}

interface Detail {
  contact: Contact;
  conversations: { id: number; state: string; channel_id: number }[];
}

export function Contacts() {
  const [list, setList] = useState<Contact[]>([]);
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [mergeId, setMergeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  function search() {
    void api
      .get<{ contacts: Contact[] }>(`/contacts${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`)
      .then((r) => setList(r.contacts));
  }
  useEffect(search, []);

  async function open(id: number) {
    setError(null);
    const d = await api.get<Detail>(`/contacts/${id}`);
    setDetail(d);
    setMergeId("");
  }

  function patchField(field: keyof Contact, value: string) {
    setDetail((d) => (d ? { ...d, contact: { ...d.contact, [field]: value } } : d));
  }

  async function save() {
    if (!detail) return;
    const c = detail.contact;
    await api.put(`/contacts/${c.id}`, { name: c.name, phone: c.phone, address: c.address, notes: c.notes });
    search();
  }

  async function toggleBlock() {
    if (!detail) return;
    const r = await api.post<{ contact: Contact }>(`/contacts/${detail.contact.id}/block`, {
      blocked: !detail.contact.is_blocked,
    });
    setDetail({ ...detail, contact: { ...detail.contact, is_blocked: r.contact.is_blocked } });
    search();
  }

  async function merge() {
    if (!detail || !mergeId.trim()) return;
    setError(null);
    try {
      await api.post(`/contacts/${detail.contact.id}/merge`, { source_id: Number(mergeId) });
      await open(detail.contact.id);
      search();
    } catch (e) {
      setError(e instanceof ApiError ? String((e.data as { error?: string })?.error ?? e.message) : "تعذّر الدمج");
    }
  }

  const c = detail?.contact;
  return (
    <div className="page">
      <div className="page-head"><h1>جهات الاتصال</h1></div>
      <div className="split">
        <div className="card" style={{ margin: 0 }}>
          <div className="actions" style={{ marginBottom: 12 }}>
            <input style={{ flex: 1 }} placeholder="بحث بالاسم أو الهاتف…" value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
            <button className="btn sm" onClick={search}>بحث</button>
          </div>
          <div className="list-rows">
            {list.length === 0 && <div className="muted">لا نتائج</div>}
            {list.map((x) => (
              <div key={x.id} className="kb-item" style={{ cursor: "pointer" }} onClick={() => void open(x.id)}>
                <div className="t">
                  <div className="ttl">{x.name ?? "عميل"} {x.is_blocked && <span className="pill error">محظور</span>}</div>
                  <div className="mt">{x.phone ?? ""}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          {!c && <div className="card"><div className="muted">اختر جهة اتصال لعرض تفاصيلها</div></div>}
          {c && (
            <>
              {error && <div className="banner err">{error}</div>}
              <div className="card">
                <h2>تفاصيل العميل <span className="muted">#{c.id}</span></h2>
                <div className="row">
                  <div className="field"><label>الاسم</label>
                    <input value={c.name ?? ""} onChange={(e) => patchField("name", e.target.value)} /></div>
                  <div className="field"><label>الهاتف</label>
                    <input value={c.phone ?? ""} onChange={(e) => patchField("phone", e.target.value)} dir="ltr" /></div>
                </div>
                <div className="field" style={{ marginTop: 12 }}><label>العنوان</label>
                  <input value={c.address ?? ""} onChange={(e) => patchField("address", e.target.value)} /></div>
                <div className="field" style={{ marginTop: 12 }}><label>ملاحظات</label>
                  <textarea className="ta" style={{ minHeight: 70 }} value={c.notes ?? ""}
                    onChange={(e) => patchField("notes", e.target.value)} /></div>
                <div className="actions" style={{ marginTop: 14 }}>
                  <button className="btn sm" onClick={() => void save()}>حفظ</button>
                  <button className={"btn sm " + (c.is_blocked ? "ghost" : "danger")} onClick={() => void toggleBlock()}>
                    {c.is_blocked ? "إلغاء الحظر" : "حظر"}
                  </button>
                </div>
              </div>

              <div className="card">
                <h2>القنوات المرتبطة</h2>
                <div className="list-rows">
                  {(c.identities ?? []).map((i) => (
                    <div key={i.id} className="kb-item">
                      <div className="t"><div className="ttl">{i.display_name ?? i.external_id}</div>
                        <div className="mt" dir="ltr">قناة #{i.channel_id} · {i.external_id}</div></div>
                    </div>
                  ))}
                  {(c.identities ?? []).length === 0 && <div className="muted">لا قنوات</div>}
                </div>
                <h2 style={{ marginTop: 16 }}>دمج جهة اتصال أخرى</h2>
                <div className="actions">
                  <input style={{ width: 160 }} placeholder="رقم جهة الاتصال المصدر" value={mergeId}
                    onChange={(e) => setMergeId(e.target.value)} dir="ltr" />
                  <button className="btn sm ghost" onClick={() => void merge()} disabled={!mergeId.trim()}>دمج فيها</button>
                </div>
                <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                  تُنقَل قنوات ومحادثات المصدر إلى هذه الجهة ثم يُحذف المصدر.
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
