import { createContext, useContext, useEffect, useState } from "react";

import { apiClient, setAuthToken } from "../services/api";

const AuthContext = createContext(null);
const TOKEN_KEY = "ai_data_analyst_access_token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setAuthToken(null);
      setLoading(false);
      return;
    }

    setAuthToken(token);
    apiClient
      .get("/auth/me")
      .then(({ data }) => setUser(data))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function login(credentials) {
    const { data } = await apiClient.post("/auth/login", credentials);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }

  async function register(details) {
    const { data } = await apiClient.post("/auth/register", details);
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: Boolean(user), login, register, logout }}>
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
