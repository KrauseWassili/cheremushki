"use client";

import { AppProvider } from "@/providers/AppProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return <AppProvider>{children}</AppProvider>;
}
