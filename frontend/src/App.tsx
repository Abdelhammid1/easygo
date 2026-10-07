import { useAuth } from "./auth";
import { Login } from "./pages/Login";
import { Shell } from "./pages/Shell";

export function App() {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="login-wrap"><div className="sub">جارٍ التحميل…</div></div>;
  }
  return user ? <Shell /> : <Login />;
}
