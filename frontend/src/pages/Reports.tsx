import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

interface Summary {
  window_days: number;
  conversations_by_channel: Record<string, number>;
  conversations_by_state: Record<string, number>;
  conversations_by_day: { day: string; count: number }[];
  ai: {
    runs: number;
    escalated: number;
    resolved_by_ai: number;
    escalation_rate: number;
    estimated_cost_usd: number;
  };
  escalation_reasons: Record<string, number>;
  avg_first_response_seconds: number | null;
}

interface AgentRow { user_id: number; messages_sent: number; }

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}ث`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}د`;
  return `${(seconds / 3600).toFixed(1)}س`;
}

export function Reports() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    api
      .get<Summary>("/reports/summary")
      .then(setSummary)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setForbidden(true);
      });
    void api.get<{ agents: AgentRow[] }>("/reports/agents").then((r) => setAgents(r.agents));
  }, []);

  const totalConversations = summary
    ? Object.values(summary.conversations_by_state).reduce((a, b) => a + b, 0)
    : 0;
  const maxDay = summary
    ? Math.max(1, ...summary.conversations_by_day.map((d) => d.count))
    : 1;

  return (
    <div className="page">
      <div className="page-head">
        <h1>التقارير</h1>
        <a className="btn sm ghost" href="/api/reports/export/conversations.csv" download>تصدير CSV</a>
      </div>

      {summary && (
        <>
          <div className="tiles">
            <div className="tile"><div className="k">إجمالي المحادثات</div><div className="v num">{totalConversations}</div></div>
            <div className="tile"><div className="k">حُلّت آليًا</div><div className="v num">{summary.ai.resolved_by_ai}</div></div>
            <div className="tile"><div className="k">نسبة التصعيد</div><div className="v num">{Math.round(summary.ai.escalation_rate * 100)}%</div></div>
            <div className="tile"><div className="k">متوسط أول رد</div><div className="v small num">{fmtDuration(summary.avg_first_response_seconds)}</div></div>
            <div className="tile"><div className="k">تكلفة الـ AI التقديرية</div><div className="v small num">${summary.ai.estimated_cost_usd.toFixed(3)}</div></div>
          </div>

          <div className="card">
            <h2>المحادثات حسب اليوم <span className="muted">(آخر {summary.window_days} يومًا)</span></h2>
            <div className="bars">
              {summary.conversations_by_day.length === 0 && <div className="muted">لا بيانات</div>}
              {summary.conversations_by_day.map((d) => (
                <div key={d.day} className="bar-row">
                  <span className="num">{d.day}</span>
                  <span className="bar-track"><span className="bar-fill" style={{ width: `${(d.count / maxDay) * 100}%` }} /></span>
                  <span className="num">{d.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="row">
            <div className="card" style={{ flex: 1, minWidth: 260 }}>
              <h2>حسب الحالة</h2>
              <div className="bars">
                {Object.entries(summary.conversations_by_state).map(([k, v]) => (
                  <div key={k} className="bar-row">
                    <span>{k}</span>
                    <span className="bar-track"><span className="bar-fill" style={{ width: `${(v / Math.max(1, totalConversations)) * 100}%` }} /></span>
                    <span className="num">{v}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card" style={{ flex: 1, minWidth: 260 }}>
              <h2>أسباب التصعيد</h2>
              <div className="bars">
                {Object.keys(summary.escalation_reasons).length === 0 && <div className="muted">لا تصعيدات</div>}
                {Object.entries(summary.escalation_reasons).map(([k, v]) => (
                  <div key={k} className="bar-row">
                    <span>{k}</span>
                    <span className="bar-track"><span className="bar-fill" style={{ width: `${(v / Math.max(1, summary.ai.escalated)) * 100}%` }} /></span>
                    <span className="num">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {forbidden && (
        <div className="card"><div className="muted">الملخص العام متاح للمشرفين فقط — هذه بيانات أدائك.</div></div>
      )}

      <div className="card">
        <h2>أداء الموظفين</h2>
        <table className="tbl">
          <thead><tr><th>الموظف</th><th>رسائل مُرسَلة</th></tr></thead>
          <tbody>
            {agents.length === 0 && <tr><td colSpan={2} className="muted">لا بيانات</td></tr>}
            {agents.map((a) => (
              <tr key={a.user_id}><td className="num">#{a.user_id}</td><td className="num">{a.messages_sent}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
