import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setCsrfToken } from "./api/client";
import { disconnectSocket } from "./socket";
import type { User } from "./api/types";

interface LoginResponse {
  user: User;
  csrf_token: string;
}

interface MeResponse {
  user: User;
  csrf_token: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<MeResponse>("/auth/me")
      .then((res) => {
        setCsrfToken(res.csrf_token);
        setUser(res.user);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const res = await api.post<LoginResponse>("/auth/login", { email, password });
    setCsrfToken(res.csrf_token);
    setUser(res.user);
  }

  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      disconnectSocket();
      setCsrfToken(null);
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** True if the current user has the given backend permission. */
export function usePermission(perm: string): boolean {
  const { user } = useAuth();
  return !!user?.permissions.includes(perm);
}
