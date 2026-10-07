import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

interface ManagedUser {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  last_login_at: string | null;
}

const ROLES = ["admin", "supervisor", "agent"];

export function Users() {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("agent");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    void api.get<{ users: ManagedUser[] }>("/users").then((r) => setUsers(r.users));
  }
  useEffect(reload, []);

  async function create() {
    setError(null);
    try {
      await api.post("/users", { name, email, password, role });
      setName(""); setEmail(""); setPassword(""); setRole("agent");
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? String((e.data as { error?: string })?.error ?? e.message) : "تعذّر الإنشاء");
    }
  }

  async function patch(id: number, body: Record<string, unknown>) {
    setError(null);
    try {
      await api.put(`/users/${id}`, body);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? String((e.data as { error?: string })?.error ?? e.message) : "تعذّر التعديل");
    }
  }

  async function resetPassword(u: ManagedUser) {
    const pw = window.prompt(`كلمة مرور جديدة لـ ${u.name} (٨ أحرف على الأقل):`);
    if (pw) await patch(u.id, { password: pw });
  }

  return (
    <div className="page">
      <div className="page-head"><h1>المستخدمون والأدوار</h1></div>

      {error && <div className="banner err">{error}</div>}

      <div className="card">
        <h2>إضافة مستخدم</h2>
        <div className="row">
          <div className="field"><label>الاسم</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div className="field"><label>البريد</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} dir="ltr" /></div>
          <div className="field"><label>كلمة المرور</label><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} dir="ltr" /></div>
          <div className="field"><label>الدور</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 14 }}>
          <button className="btn sm" onClick={() => void create()}
            disabled={!name.trim() || !email.trim() || password.length < 8}>إنشاء</button>
          <span className="muted">كلمة المرور ٨ أحرف على الأقل</span>
        </div>
      </div>

      <div className="card">
        <h2>المستخدمون ({users.length})</h2>
        <table className="tbl">
          <thead><tr><th>الاسم</th><th>البريد</th><th>الدور</th><th>الحالة</th><th></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td dir="ltr">{u.email}</td>
                <td>
                  <select value={u.role} onChange={(e) => void patch(u.id, { role: e.target.value })}>
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td>
                  <button className={"pill " + (u.status === "active" ? "connected" : "disconnected")}
                    onClick={() => void patch(u.id, { status: u.status === "active" ? "disabled" : "active" })}>
                    {u.status === "active" ? "مفعّل" : "موقوف"}
                  </button>
                </td>
                <td><button className="btn sm ghost" onClick={() => void resetPassword(u)}>كلمة مرور</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
