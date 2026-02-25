"use client";
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface User {
  id: string;
  email: string;
  display_name: string;
  tier: string;
  role?: string;
  totp_enabled?: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  isAdmin: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<{ requires_2fa: boolean; temp_token?: string }>;
  login2FA: (email: string, password: string, code: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refresh, setRefresh] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const isAdmin = user?.role === "admin";

  // Persist tokens
  const saveTokens = (access: string, refreshToken: string) => {
    setToken(access);
    setRefresh(refreshToken);
    localStorage.setItem("tv_access_token", access);
    localStorage.setItem("tv_refresh_token", refreshToken);
  };

  const clearTokens = () => {
    setToken(null);
    setRefresh(null);
    setUser(null);
    localStorage.removeItem("tv_access_token");
    localStorage.removeItem("tv_refresh_token");
  };

  // Fetch user profile with token
  const fetchMe = useCallback(async (accessToken: string): Promise<User | null> => {
    try {
      const resp = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (resp.ok) return await resp.json();
      return null;
    } catch {
      return null;
    }
  }, []);

  // On mount — check stored tokens
  useEffect(() => {
    const init = async () => {
      const stored = localStorage.getItem("tv_access_token");
      const storedRefresh = localStorage.getItem("tv_refresh_token");
      if (stored) {
        const me = await fetchMe(stored);
        if (me) {
          setToken(stored);
          setRefresh(storedRefresh);
          setUser(me);
        } else if (storedRefresh) {
          // Try refresh
          try {
            const resp = await fetch(`${API_BASE}/api/auth/refresh?refresh_token=${encodeURIComponent(storedRefresh)}`, {
              method: "POST",
            });
            if (resp.ok) {
              const data = await resp.json();
              saveTokens(data.access_token, data.refresh_token);
              const me2 = await fetchMe(data.access_token);
              if (me2) setUser(me2);
            } else {
              clearTokens();
            }
          } catch {
            clearTokens();
          }
        } else {
          clearTokens();
        }
      }
      setLoading(false);
    };
    init();
  }, [fetchMe]);

  const login = async (email: string, password: string): Promise<{ requires_2fa: boolean; temp_token?: string }> => {
    const resp = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail);
    }
    const data = await resp.json();
    if (data.requires_2fa) {
      return { requires_2fa: true, temp_token: data.temp_token };
    }

    saveTokens(data.access_token, data.refresh_token);
    const me = await fetchMe(data.access_token);
    if (me) setUser(me);
    return { requires_2fa: false };
  };

  const login2FA = async (email: string, password: string, code: string) => {
    const resp = await fetch(`${API_BASE}/api/auth/login/2fa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, totp_code: code }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "2FA verification failed" }));
      throw new Error(err.detail);
    }
    const data = await resp.json();
    saveTokens(data.access_token, data.refresh_token);
    const me = await fetchMe(data.access_token);
    if (me) setUser(me);
  };

  const register = async (email: string, password: string, displayName?: string) => {
    const resp = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName || "" }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Registration failed" }));
      throw new Error(err.detail);
    }
    const data = await resp.json();
    saveTokens(data.access_token, data.refresh_token);
    const me = await fetchMe(data.access_token);
    if (me) setUser(me);
  };

  const logout = () => {
    clearTokens();
  };

  const refreshTokenFn = async () => {
    if (!refresh) return;
    try {
      const resp = await fetch(`${API_BASE}/api/auth/refresh?refresh_token=${encodeURIComponent(refresh)}`, {
        method: "POST",
      });
      if (resp.ok) {
        const data = await resp.json();
        saveTokens(data.access_token, data.refresh_token);
      } else {
        clearTokens();
      }
    } catch {
      clearTokens();
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, isAdmin, login, login2FA, register, logout, refreshToken: refreshTokenFn }}>
      {children}
    </AuthContext.Provider>
  );
}
