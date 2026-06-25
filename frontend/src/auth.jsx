import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  setAuthToken,
  setUnauthorizedHandler,
  login as apiLogin,
  signup as apiSignup,
} from "./api.js";

const STORAGE_KEY = "storysim.auth";

// Restore the saved { user, token } (if any) BEFORE first render and prime
// api.js so the very first requests carry the Bearer token.
function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const a = JSON.parse(raw);
    if (a && a.user && a.token) return a;
  } catch {
    // ignore malformed storage
  }
  return null;
}

const initial = loadStored();
setAuthToken(initial?.token ?? null);

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(initial); // { user, token } | null
  const user = auth?.user ?? null;
  const navigate = useNavigate();

  // Keep api.js + localStorage in sync whenever auth changes.
  useEffect(() => {
    setAuthToken(auth?.token ?? null);
    try {
      if (auth) localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore storage failures
    }
  }, [auth]);

  // If any request comes back 401 (token expired/invalid, or an action needs
  // auth), drop the session and send the user to the login page.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuth(null);
      if (window.location.pathname !== "/login") {
        navigate("/login", {
          replace: true,
          state: { from: window.location.pathname },
        });
      }
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate]);

  const value = useMemo(
    () => ({
      user,
      async login(username, password) {
        const res = await apiLogin(username, password); // { user, token }
        setAuth(res);
        return res.user;
      },
      async signup(username, password) {
        const res = await apiSignup(username, password); // { user, token }
        setAuth(res);
        return res.user;
      },
      logout() {
        setAuth(null);
      },
    }),
    [user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
