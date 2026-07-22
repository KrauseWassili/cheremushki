"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
} from "react";
import { initialJoinDemoState } from "@/data/mock-join";
import type {
  ApplicationStatus,
  JoinApplication,
} from "@/types/join";

type JoinDemoContextValue = {
  application: JoinApplication;
  status: ApplicationStatus;
  adminMessage: string;

  updateApplication: (
    values: Partial<JoinApplication>,
  ) => void;

  setStatus: (status: ApplicationStatus) => void;
  resetDemo: () => void;
};

const JoinDemoContext =
  createContext<JoinDemoContextValue | null>(null);

type JoinDemoProviderProps = {
  children: React.ReactNode;
};

export function JoinDemoProvider({
  children,
}: JoinDemoProviderProps) {
  const [application, setApplication] = useState(
    initialJoinDemoState.application,
  );

  const [status, setStatus] =
    useState<ApplicationStatus>(
      initialJoinDemoState.status,
    );

  function updateApplication(
    values: Partial<JoinApplication>,
  ) {
    setApplication((current) => ({
      ...current,
      ...values,
    }));
  }

  function resetDemo() {
    setApplication(initialJoinDemoState.application);
    setStatus(initialJoinDemoState.status);
  }

  const value = useMemo(
    () => ({
      application,
      status,
      adminMessage: initialJoinDemoState.adminMessage,
      updateApplication,
      setStatus,
      resetDemo,
    }),
    [application, status],
  );

  return (
    <JoinDemoContext.Provider value={value}>
      {children}
    </JoinDemoContext.Provider>
  );
}

export function useJoinDemo() {
  const context = useContext(JoinDemoContext);

  if (!context) {
    throw new Error(
      "useJoinDemo must be used inside JoinDemoProvider",
    );
  }

  return context;
}