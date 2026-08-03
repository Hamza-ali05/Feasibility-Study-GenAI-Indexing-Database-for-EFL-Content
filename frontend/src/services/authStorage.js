
const TOKEN_KEY = "efl_admin_token";
const AUTH_EVENT = "efl-auth-changed";

function notifyAuthChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_EVENT));
  }
}

function readToken() {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function writeToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
  notifyAuthChanged();
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  notifyAuthChanged();
}

export { TOKEN_KEY, AUTH_EVENT, notifyAuthChanged, readToken, writeToken, clearToken };
