"use client";

import { LoginModal } from "@/components/LoginModal";
import { AppProvider } from "@/providers/AppProvider";
import { useApp } from "@/providers/AppProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      {children}
      <GlobalLoginModal />
    </AppProvider>
  );
}

function GlobalLoginModal() {
  const { showLogin, loginMode, closeLogin, login, signUp } = useApp();

  if (!showLogin) {
    return null;
  }

  return (
    <LoginModal
      initialMode={loginMode}
      onClose={closeLogin}
      onLogin={login}
      onRegister={signUp}
    />
  );
}
