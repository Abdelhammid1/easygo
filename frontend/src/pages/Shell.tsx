import { useEffect, useState } from "react";
import { useAuth } from "../auth";
import { IconLogout } from "../icons";
import { KillSwitch } from "../components/KillSwitch";
import { NotificationsBell } from "../components/NotificationsBell";
import { ThemeToggle } from "../components/ThemeToggle";
import { NavRail, type View } from "../components/NavRail";
import { Inbox } from "./Inbox";
import { Contacts } from "./Contacts";
import { Knowledge } from "./Knowledge";
import { Reports } from "./Reports";
import { Users } from "./Users";
import { Settings } from "./Settings";

const VIEWS: View[] = ["inbox", "contacts", "knowledge", "reports", "users", "settings"];
function viewFromHash(): View {
  const h = window.location.hash.replace(/^#/, "") as View;
  return VIEWS.includes(h) ? h : "inbox";
}

export function Shell() {
  const { user, logout } = useAuth();
  const [view, setViewState] = useState<View>(viewFromHash);
  const has = (p: string) => !!user?.permissions.includes(p);

  // Keep the active tab in the URL hash so a refresh stays on the same screen.
  const setView = (v: View) => { window.location.hash = v; setViewState(v); };
  useEffect(() => {
    const onHash = () => setViewState(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const canSettings =
    has("ai_settings") || has("manage_channels") || has("manage_users") || has("manage_org_settings");

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo">✦</span>
          <span>محادثاتي <small>الصندوق الموحد</small></span>
        </div>
        <div className="spacer" />
        {has("ai_kill_switch") && <KillSwitch />}
        <NotificationsBell />
        <ThemeToggle />
        <div className="me">
          <span className="av" style={{ background: "#7c5cff" }}>{(user?.name ?? "؟").charAt(0)}</span>
          <span>
            <span className="nm">{user?.name}</span>
            <br />
            <span className="rl">{user?.role}</span>
          </span>
        </div>
        <button className="iconbtn" title="تسجيل الخروج" onClick={() => void logout()}>
          <IconLogout />
        </button>
      </header>

      <div className="body">
        <NavRail view={view} setView={setView} has={has} />
        <main className="content">
          {view === "inbox" && <Inbox />}
          {view === "contacts" && <Contacts />}
          {view === "knowledge" && <Knowledge />}
          {view === "reports" && <Reports />}
          {view === "users" && has("manage_users") && <Users />}
          {view === "settings" && canSettings && <Settings />}
        </main>
      </div>
    </div>
  );
}
