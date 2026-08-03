
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";

import { adminLogin, adminMe } from "services/endpoints";
import {
  TOKEN_KEY,
  AUTH_EVENT,
  notifyAuthChanged,
  readToken,
  clearToken,
} from "services/authStorage";

const AuthContext = createContext(null);

function AuthProvider({ children }) {
  const [token, setToken] = useState(readToken);
  const [username, setUsername] = useState(null);

  const syncFromStorage = useCallback(() => {
    setToken(readToken());
  }, []);

  useEffect(() => {
    window.addEventListener(AUTH_EVENT, syncFromStorage);
    window.addEventListener("storage", syncFromStorage);
    return () => {
      window.removeEventListener(AUTH_EVENT, syncFromStorage);
      window.removeEventListener("storage", syncFromStorage);
    };
  }, [syncFromStorage]);

  const logout = useCallback(() => {
    clearToken();
    setToken(null);
    setUsername(null);
  }, []);

  useEffect(() => {
    if (!token) {
      setUsername(null);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await adminMe();
        if (!cancelled) setUsername(data?.username || null);
      } catch {
        if (!cancelled) {
          clearToken();
          setToken(null);
          setUsername(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(async (user, password) => {
    const data = await adminLogin(user, password);
    if (!data?.access_token) {
      throw new Error("Login succeeded but no access_token was returned");
    }
    setToken(data.access_token);
    setUsername(user);
    return data;
  }, []);

  const value = useMemo(
    () => ({
      token,
      username,
      isAuthenticated: Boolean(token),
      login,
      logout,
    }),
    [token, username, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() must be used within an AuthProvider");
  }
  return ctx;
}

export { AuthProvider, useAuth, TOKEN_KEY, notifyAuthChanged };
export default AuthContext;
