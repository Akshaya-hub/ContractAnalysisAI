const TOKEN_KEY = "contractai_auth_token";

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated() {
  return Boolean(getToken());
}
