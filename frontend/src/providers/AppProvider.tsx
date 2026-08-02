"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  clearTokens,
  fetchCurrentUser,
  login as loginRequest,
  logoutRequest,
  register as registerRequest,
  storeTokens,
  updateCurrentUser as updateCurrentUserRequest,
} from "@/lib/auth";
import type { User } from "@/types/user";

type LoginMode = "login" | "register";

interface AppContextValue {
  user: User | null;
  isLoggedIn: boolean;
  authLoading: boolean;
  login: (
    email: string,
    password: string,
    rememberMe?: boolean,
  ) => Promise<void>;
  signUp: (
    email: string,
    firstName: string,
    lastName: string,
    password: string,
    passwordConfirm: string,
  ) => Promise<string>;
  logout: () => Promise<void>;
  updateCurrentUser: (
    data: Pick<User, "first_name" | "last_name">,
  ) => Promise<User>;
  showLogin: boolean;
  loginMode: LoginMode;
  openLogin: (mode?: LoginMode) => void;
  closeLogin: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const [loginMode, setLoginMode] = useState<LoginMode>("login");
  const isLoggedIn = user !== null;

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      try {
        const currentUser = await fetchCurrentUser();
        if (!cancelled) setUser(currentUser);
      } catch {
        if (!cancelled) {
          clearTokens();
          setUser(null);
        }
      } finally {
        if (!cancelled) setAuthLoading(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  const signUp = useCallback(
    async (
      email: string,
      firstName: string,
      lastName: string,
      password: string,
      passwordConfirm: string,
    ) => {
      // Telegram gate: токены не выдаются до активации аккаунта.
      const result = await registerRequest(
        email,
        firstName,
        lastName,
        password,
        passwordConfirm,
      );
      return result.detail;
    },
    [],
  );

  const login = useCallback(
    async (email: string, password: string, rememberMe = true) => {
      const tokens = await loginRequest(email, password);
      storeTokens(tokens, rememberMe);
      const currentUser = await fetchCurrentUser(tokens.access);
      setUser(currentUser);
      setShowLogin(false);
      router.push("/members");
    },
    [router],
  );

  const logout = useCallback(async () => {
    await logoutRequest();
    clearTokens();
    setUser(null);
    router.push("/");
  }, [router]);

  const updateCurrentUser = useCallback(
    async (data: Pick<User, "first_name" | "last_name">) => {
      const updatedUser = await updateCurrentUserRequest(data);
      setUser(updatedUser);
      return updatedUser;
    },
    [],
  );

  return (
    <AppContext.Provider
      value={{
        user,
        isLoggedIn,
        authLoading,
        signUp,
        login,
        logout,
        updateCurrentUser,
        showLogin,
        loginMode,
        openLogin: (mode: LoginMode = "login") => {
          setLoginMode(mode);
          setShowLogin(true);
        },
        closeLogin: () => setShowLogin(false),
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) {
    return {
      user: null,
      isLoggedIn: false,
      authLoading: true,
      signUp: async () => "",
      login: async () => {},
      logout: async () => {},
      updateCurrentUser: async () => {
        throw new Error("App context is not initialized");
      },
      showLogin: false,
      loginMode: "login" as const,
      openLogin: () => {},
      closeLogin: () => {},
    } satisfies AppContextValue;
  }
  return ctx;
}
