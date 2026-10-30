import { useEffect } from "react";
import { useAuth } from "./auth";
import { Login } from "./pages/Login";
import { Shell } from "./pages/Shell";
import { Landing } from "./pages/Landing";

export function App() {
  const { user, loading } = useAuth();
  useEffect(() => {
    if (user && window.location.pathname === "/login") {
      window.history.replaceState(null, "", "/");
    }
  }, [user]);
  if (loading) {
    return <div className="login-wrap"><div className="sub">جارٍ التحميل…</div></div>;
  }
  if (user) return <Shell />;
  return window.location.pathname === "/login" ? <Login /> : <Landing />;
}
