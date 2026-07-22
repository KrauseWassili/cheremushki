"use client";

import { useState } from "react";
import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

export default function ActivatePage() {
  const { application } = useJoinDemo();

  const [password, setPassword] =
    useState("demo-password");

  const [passwordConfirmation, setPasswordConfirmation] =
    useState("demo-password");

  const isValid =
    password.length >= 8 &&
    password === passwordConfirmation;

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 6"
        title="Активируй аккаунт"
        description={`Заявка для ${application.email} одобрена. Осталось придумать пароль для личного кабинета.`}
      />

      <div className="mt-8 grid gap-5">
        <label className="grid gap-2">
          <span className="font-bold">Пароль</span>

          <input
            type="password"
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
            className="h-12 rounded-xl border border-border bg-background px-4 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5"
          />
        </label>

        <label className="grid gap-2">
          <span className="font-bold">
            Повтори пароль
          </span>

          <input
            type="password"
            value={passwordConfirmation}
            onChange={(event) =>
              setPasswordConfirmation(event.target.value)
            }
            className="h-12 rounded-xl border border-border bg-background px-4 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5"
          />
        </label>

        {!isValid && (
          <p className="text-sm text-red-700">
            Пароль должен содержать не менее восьми
            символов, а оба значения должны совпадать.
          </p>
        )}
      </div>

      <JoinNavigation
        previousHref="/join/status"
        nextHref="/join/activated"
        nextLabel="Создать аккаунт"
        nextDisabled={!isValid}
      />
    </>
  );
}