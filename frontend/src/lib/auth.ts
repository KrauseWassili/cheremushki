import { ApiError, apiFetch } from "@/lib/api";
import type { RegisterResponse, TokenPair, User } from "@/types/user";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const AUTH_SYNC_CHANNEL_NAME = "cheremushki-auth";
const AUTH_SYNC_STORAGE_KEY = "cheremushki-auth-event";

type StorageKind = "local" | "session";
type AuthSyncEvent = {
  type: "logout";
  issuedAt: number;
  nonce: string;
  senderId: string;
};

// Kennung dieses Tabs (pro JS-Realm einmal erzeugt). BroadcastChannel stellt
// Nachrichten auch an andere Channel-Instanzen im selben Tab zu; ohne Absender
// würde der eigene Subscriber den Logout wiederholen und auf "/" umleiten.
const AUTH_SYNC_TAB_ID = Math.random().toString(36).slice(2);

let refreshRequest: Promise<string | null> | null = null;

export function isAuthError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

function getStorage(kind: StorageKind): Storage {
  return kind === "local" ? localStorage : sessionStorage;
}

function getActiveStorageKind(): StorageKind | null {
  if (typeof window === "undefined") return null;
  if (localStorage.getItem(ACCESS_TOKEN_KEY)) return "local";
  if (sessionStorage.getItem(ACCESS_TOKEN_KEY)) return "session";
  return null;
}

function getActiveStorage(): Storage | null {
  const kind = getActiveStorageKind();
  return kind ? getStorage(kind) : null;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    localStorage.getItem(ACCESS_TOKEN_KEY) ??
    sessionStorage.getItem(ACCESS_TOKEN_KEY)
  );
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    localStorage.getItem(REFRESH_TOKEN_KEY) ??
    sessionStorage.getItem(REFRESH_TOKEN_KEY)
  );
}

export function hasAuthTokens(): boolean {
  return Boolean(getAccessToken() || getRefreshToken());
}

export function storeTokens(tokens: TokenPair, rememberMe: boolean): void {
  clearTokens();
  const storage = getStorage(rememberMe ? "local" : "session");
  storage.setItem(ACCESS_TOKEN_KEY, tokens.access);
  storage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem(ACCESS_TOKEN_KEY);
    storage.removeItem(REFRESH_TOKEN_KEY);
  }
}

export function notifyAuthLogout(): void {
  if (typeof window === "undefined") return;

  const event: AuthSyncEvent = {
    type: "logout",
    issuedAt: Date.now(),
    nonce: Math.random().toString(36).slice(2),
    senderId: AUTH_SYNC_TAB_ID,
  };

  if ("BroadcastChannel" in window) {
    const channel = new BroadcastChannel(AUTH_SYNC_CHANNEL_NAME);
    channel.postMessage(event);
    channel.close();
  }

  localStorage.setItem(AUTH_SYNC_STORAGE_KEY, JSON.stringify(event));
}

export function subscribeToAuthLogout(handler: () => void): () => void {
  if (typeof window === "undefined") return () => {};

  let channel: BroadcastChannel | null = null;
  // Andere Tabs bekommen dasselbe Ereignis zweimal – per BroadcastChannel und
  // per storage-Event. Die Nonce macht daraus einen einzigen Aufruf.
  let lastHandledNonce: string | null = null;

  function handleMessage(data: unknown) {
    if (!isAuthSyncLogout(data) || data.senderId === AUTH_SYNC_TAB_ID) return;
    if (data.nonce === lastHandledNonce) return;
    lastHandledNonce = data.nonce;
    handler();
  }

  if ("BroadcastChannel" in window) {
    channel = new BroadcastChannel(AUTH_SYNC_CHANNEL_NAME);
    channel.onmessage = (event) => handleMessage(event.data);
  }

  function handleStorage(event: StorageEvent) {
    if (event.key !== AUTH_SYNC_STORAGE_KEY || !event.newValue) return;

    try {
      handleMessage(JSON.parse(event.newValue) as unknown);
    } catch {
      // Ignore malformed cross-tab events.
    }
  }

  window.addEventListener("storage", handleStorage);

  return () => {
    channel?.close();
    window.removeEventListener("storage", handleStorage);
  };
}

function isAuthSyncLogout(value: unknown): value is AuthSyncEvent {
  if (!value || typeof value !== "object") return false;
  return (value as { type?: unknown }).type === "logout";
}

export async function login(
  email: string,
  password: string,
): Promise<TokenPair> {
  return apiFetch<TokenPair>("/api/v1/accounts/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(
  email: string,
  firstName: string,
  lastName: string,
  password: string,
  passwordConfirm: string,
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>("/api/v1/accounts/sign-up/", {
    method: "POST",
    body: JSON.stringify({
      email,
      first_name: firstName,
      last_name: lastName,
      password,
      password_confirm: passwordConfirm,
    }),
  });
}

export async function logoutRequest(): Promise<void> {
  const refresh = getRefreshToken();
  const access = getAccessToken();
  if (!refresh || !access) return;

  try {
    await apiFetch(
      "/api/v1/accounts/logout/",
      {
        method: "POST",
        body: JSON.stringify({ refresh }),
      },
      access,
    );
  } catch {
    // Токен уже может быть недействительным, но локально всё равно выходим.
  }
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshRequest) return refreshRequest;

  refreshRequest = refreshAccessTokenOnce().finally(() => {
    refreshRequest = null;
  });

  return refreshRequest;
}

type AuthRetryOptions = {
  // Explizit übergebenes Token (z. B. direkt nach dem Login) statt des
  // gespeicherten; es wird nicht auf Ablauf geprüft.
  accessToken?: string | null;
  // Fehlt das gespeicherte Token oder ist es abgelaufen, zuerst erneuern –
  // spart beim App-Start den sicher scheiternden ersten Request.
  refreshIfStale?: boolean;
};

/**
 * Führt einen authentifizierten Request aus; bei 401 einmal den Token
 * erneuern und wiederholen.
 *
 * Der Refresh läuft über refreshAccessToken(), parallele 401er teilen sich
 * also denselben Refresh-Request. Hat ein anderer Request (oder Tab) das
 * Token inzwischen schon erneuert, wird direkt mit dem neuen wiederholt: Ein
 * zweiter Refresh mit dem dann bereits rotierten (und geblacklisteten)
 * Refresh-Token würde scheitern und die Sitzung beenden. `request` muss
 * mehrfach aufrufbar sein (Body nicht als Stream übergeben).
 */
export async function withAuthRetry<T>(
  request: (accessToken: string) => Promise<T>,
  options: AuthRetryOptions = {},
): Promise<T> {
  let token = options.accessToken ?? getAccessToken();
  if (
    options.refreshIfStale &&
    (!token || (!options.accessToken && isJwtExpired(token)))
  ) {
    token = await refreshAccessToken();
  }
  if (!token) throw new Error("Пользователь не авторизован");

  try {
    return await request(token);
  } catch (error) {
    if (!isAuthError(error)) throw error;
    const storedToken = getAccessToken();
    const retryToken =
      storedToken && storedToken !== token
        ? storedToken
        : await refreshAccessToken();
    if (!retryToken) throw error;
    return request(retryToken);
  }
}

async function refreshAccessTokenOnce(): Promise<string | null> {
  const refresh = getRefreshToken();
  const storage = getActiveStorage();
  if (!refresh || !storage) return null;

  try {
    const data = await apiFetch<{ access: string; refresh?: string }>(
      "/api/v1/accounts/login/refresh/",
      {
        method: "POST",
        body: JSON.stringify({ refresh }),
      },
    );

    storage.setItem(ACCESS_TOKEN_KEY, data.access);
    if (data.refresh) {
      storage.setItem(REFRESH_TOKEN_KEY, data.refresh);
    }

    return data.access;
  } catch {
    if (getRefreshToken() === refresh) {
      clearTokens();
    }
    return null;
  }
}

export async function fetchCurrentUser(
  accessToken?: string | null,
): Promise<User> {
  return withAuthRetry(
    (token) =>
      apiFetch<User>("/api/v1/accounts/user/me/", { method: "GET" }, token),
    { accessToken, refreshIfStale: true },
  );
}

function isJwtExpired(token: string): boolean {
  try {
    const [, payload] = token.split(".");
    if (!payload) return false;

    const normalizedPayload = payload
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(payload.length / 4) * 4, "=");
    const data = JSON.parse(atob(normalizedPayload)) as { exp?: number };

    return typeof data.exp === "number" && data.exp * 1000 <= Date.now();
  } catch {
    return false;
  }
}

export async function updateCurrentUser(
  data: Pick<User, "first_name" | "last_name">,
): Promise<User> {
  return withAuthRetry((token) =>
    apiFetch<User>(
      "/api/v1/accounts/user/me/",
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
      token,
    ),
  );
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
  newPasswordConfirm: string,
): Promise<void> {
  const options = {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      new_password_confirm: newPasswordConfirm,
    }),
  };

  await withAuthRetry((token) =>
    apiFetch("/api/v1/accounts/password/change/", options, token),
  );
}

export async function requestEmailChange(
  newEmail: string,
  currentPassword: string,
): Promise<{ detail: string }> {
  const options = {
    method: "POST",
    body: JSON.stringify({
      new_email: newEmail,
      current_password: currentPassword,
    }),
  };

  return withAuthRetry((token) =>
    apiFetch<{ detail: string }>(
      "/api/v1/accounts/email/change/",
      options,
      token,
    ),
  );
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiFetch("/api/v1/accounts/password/reset/", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(
  uid: string,
  token: string,
  newPassword: string,
  newPasswordConfirm: string,
): Promise<void> {
  await apiFetch("/api/v1/accounts/password/reset/confirm/", {
    method: "POST",
    body: JSON.stringify({
      uid,
      token,
      new_password: newPassword,
      new_password_confirm: newPasswordConfirm,
    }),
  });
}

export async function activateAccount(
  uid: string,
  token: string,
): Promise<{ detail: string; already_active?: boolean }> {
  return apiFetch("/api/v1/accounts/activate/", {
    method: "POST",
    body: JSON.stringify({ uid, token }),
  });
}

export async function confirmEmailChange(
  uid: string,
  token: string,
): Promise<{ detail: string }> {
  return apiFetch("/api/v1/accounts/email/confirm/", {
    method: "POST",
    body: JSON.stringify({ uid, token }),
  });
}

export async function deleteAccount(password: string): Promise<void> {
  const options = {
    method: "POST",
    body: JSON.stringify({ password }),
  };

  await withAuthRetry((token) =>
    apiFetch("/api/v1/accounts/delete/", options, token),
  );
}
