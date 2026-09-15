"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { resolvePostAuthPath } from "@/lib/roles";
import type { CandidateRegisterPayload, User } from "@/types/auth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, next?: string | null) => Promise<void>;
  register: (payload: CandidateRegisterPayload, next?: string | null) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const fetchUser = useCallback(async () => {
    if (!api.hasToken()) {
      setLoading(false);
      return;
    }
    try {
      const userData = await api.getMe();
      setUser(userData);
    } catch {
      api.clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email: string, password: string, next?: string | null) => {
    await api.login(email, password);
    const userData = await api.getMe();
    setUser(userData);
    router.push(resolvePostAuthPath(userData, next));
  };

  const register = async (payload: CandidateRegisterPayload, next?: string | null) => {
    await api.register(payload);
    const userData = await api.getMe();
    setUser(userData);
    router.push(resolvePostAuthPath(userData, next));
  };

  const logout = () => {
    api.logout();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
