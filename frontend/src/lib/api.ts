const API_BASE = "/api";

interface ApiOptions extends RequestInit {
  token?: string;
}

/**
 * Decode a JWT and check if it's expired.
 * Returns true if the token is valid (not expired), false otherwise.
 */
export function isTokenValid(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    // exp is in seconds, Date.now() in ms
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { token, ...fetchOptions } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(error.detail || resp.statusText);
  }

  return resp.json();
}

export async function login(email: string, password: string): Promise<string> {
  const resp = await fetch(`${API_BASE}/auth/jwt/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (!resp.ok) throw new Error("Login failed");
  const data = await resp.json();
  return data.access_token;
}
