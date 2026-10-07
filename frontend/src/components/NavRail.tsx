import type { JSX } from "react";
import {
  IconContacts, IconInbox, IconKB, IconReports, IconSettings, IconUsers,
} from "../icons";

export type View = "inbox" | "contacts" | "knowledge" | "reports" | "users" | "settings";

interface Props {
  view: View;
  setView: (v: View) => void;
  has: (perm: string) => boolean;
}

export function NavRail({ view, setView, has }: Props) {
  const canSettings =
    has("ai_settings") || has("manage_channels") || has("manage_users") || has("manage_org_settings");

  const items: { key: View; label: string; icon: JSX.Element; show: boolean }[] = [
    { key: "inbox", label: "الصندوق", icon: <IconInbox />, show: true },
    { key: "contacts", label: "جهات الاتصال", icon: <IconContacts />, show: has("view_conversations") },
    { key: "knowledge", label: "قاعدة المعرفة", icon: <IconKB />, show: true },
    { key: "reports", label: "التقارير", icon: <IconReports />, show: has("view_reports") },
    { key: "users", label: "المستخدمون", icon: <IconUsers />, show: has("manage_users") },
  ];

  return (
    <nav className="nav">
      {items.filter((i) => i.show).map((i) => (
        <button key={i.key} className={"nitem" + (view === i.key ? " active" : "")}
          title={i.label} onClick={() => setView(i.key)}>
          {i.icon}
        </button>
      ))}
      {canSettings && <>
        <div className="nav-sep" />
        <button className={"nitem" + (view === "settings" ? " active" : "")}
          title="الإعدادات" onClick={() => setView("settings")}>
          <IconSettings />
        </button>
      </>}
    </nav>
  );
}
