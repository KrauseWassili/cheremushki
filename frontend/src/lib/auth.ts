import {apiFetch} from "@/lib/api";
import { TokenPair, User } from "@/types/user";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

type StorageKind = "local" | "session";

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

export function storeTokens(
    tokens: TokenPair,
    rememberMe: boolean
): void {
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

export async function login(
    email: string,
    password: string
): Promise<TokenPair> {
    return apiFetch<TokenPair>("/api/v1/login/", {
        method: "POST",
        body: JSON.stringify({email, password}),
    });
}

export async function register(
    email: string,
    firstName: string,
    lastName: string,
    password: string,
    passwordConfirm: string
): Promise<TokenPair> {
    return apiFetch<TokenPair>("/api/v1/accounts/sign-up/", {
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

export async function refreshAccessToken(): Promise<string | null> {
    const refresh = getRefreshToken();
    const storage = getActiveStorage();
    if (!refresh || !storage) return null;

    try {
        const data = await apiFetch<{ access: string; refresh?: string }>(
            "/api/v1/login/refresh/",
            {
                method: "POST",
                body: JSON.stringify({refresh}),
            }
        );

        storage.setItem(ACCESS_TOKEN_KEY, data.access);
        if (data.refresh) {
            storage.setItem(REFRESH_TOKEN_KEY, data.refresh);
        }

        return data.access;
    } catch {
        clearTokens();
        return null;
    }
}

export async function fetchCurrentUser(
    accessToken?: string | null
): Promise<User> {
    const token = accessToken ?? getAccessToken();
    if (!token) {
        throw new Error("Nicht angemeldet");
    }

    try {
        return await apiFetch<User>("/api/v1/accounts/user/me/", {method: "GET"}, token);
    } catch (error) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) throw error;
        return apiFetch<User>("/api/v1/accounts/user/me/", {method: "GET"}, refreshed);
    }
}

export async function updateCurrentUser(
    data: Pick<User, "email" | "first_name" | "last_name">
): Promise<User> {
    const token = getAccessToken();
    if (!token) {
        throw new Error("Nicht angemeldet");
    }

    try {
        return await apiFetch<User>(
            "/api/v1/accounts/user/me/",
            {
                method: "PATCH",
                body: JSON.stringify(data),
            },
            token
        );
    } catch (error) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) throw error;
        return apiFetch<User>(
            "/api/v1/accounts/user/me/",
            {
                method: "PATCH",
                body: JSON.stringify(data),
            },
            refreshed
        );
    }
}
