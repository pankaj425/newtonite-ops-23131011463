import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, getToken, setToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [memberships, setMemberships] = useState([]);
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api("/me")
      .then((data) => {
        setUser(data.user);
        setMemberships(data.memberships);
      })
      .catch(() => {
        setToken(null);
        setUser(null);
        setMemberships([]);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const data = await api("/auth/login", { method: "POST", body: { email, password } });
    setToken(data.access_token);
    setUser(data.user);
    setMemberships(data.memberships);
    return data;
  }

  function logout() {
    setToken(null);
    setUser(null);
    setMemberships([]);
  }

  const value = useMemo(
    () => ({ user, memberships, loading, login, logout }),
    [user, memberships, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export function roleForTeam(memberships, teamId) {
  const membership = memberships.find((m) => m.team_id === teamId);
  return membership ? membership.role : null;
}

const RANK = { viewer: 0, member: 1, lead: 2, admin: 3 };

export function atLeast(role, minimum) {
  return !!role && RANK[role] >= RANK[minimum];
}
