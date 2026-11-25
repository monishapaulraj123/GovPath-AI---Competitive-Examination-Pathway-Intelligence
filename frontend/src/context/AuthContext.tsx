import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, getToken, setToken } from '../api/client';

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  display_name: string;
  is_demo: boolean;
  primary_target_exam: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, primaryExam: string) => Promise<void>;
  loginDemo: () => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
    const onUnauth = () => {
      setUser(null);
    };
    window.addEventListener('govpath:unauthorized', onUnauth);
    return () => window.removeEventListener('govpath:unauthorized', onUnauth);
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
  };

  const register = async (email: string, password: string, fullName: string, primaryExam: string) => {
    const res = await api.register({
      email,
      password,
      full_name: fullName,
      primary_target_exam: primaryExam,
    });
    setToken(res.access_token);
    setUser(res.user);
  };

  const loginDemo = async () => {
    const res = await api.demoLogin();
    setToken(res.access_token);
    setUser(res.user);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginDemo, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
