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
  register as registerRequest,
  storeTokens,
  updateCurrentUser as updateCurrentUserRequest,
} from "@/lib/auth";
import type { User } from "@/types/user";

type LoginMode = "login" | "register";

interface AppContextValue {
  // Auth
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
  ) => Promise<void>;

  logout: () => void;
  updateCurrentUser: (
    data: Pick<User, "email" | "first_name" | "last_name">,
  ) => Promise<User>;

  // Login modal
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
      const tokens = await registerRequest(
        email,
        firstName,
        lastName,
        password,
        passwordConfirm,
      );
      storeTokens(tokens, true);
      const currentUser = await fetchCurrentUser(tokens.access);
      setUser(currentUser);
      setShowLogin(false);
      router.push("/members");
    },
    [router],
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

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const updateCurrentUser = useCallback(
    async (data: Pick<User, "email" | "first_name" | "last_name">) => {
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
  // During SSR the context may not be initialized yet — return a safe no-op
  // fallback so the server render doesn't crash. Hydration fixes it client-side.
  if (!ctx) {
    return {
      user: null,
      isLoggedIn: false,
      authLoading: true,
      signUp: async () => {},
      login: async () => {},
      logout: () => {},
      updateCurrentUser: async () => {
        throw new Error("App context is not initialized");
      },
      showLogin: false,
      loginMode: "login",
      openLogin: () => {},
      closeLogin: () => {},
    } satisfies AppContextValue;
  }
  return ctx;
}
