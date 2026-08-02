"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { confirmPasswordReset } from "@/lib/auth";

function PasswordResetConfirmContent() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid") ?? "";
  const token = searchParams.get("token") ?? "";
  const hasResetLink = uid.length > 0 && token.length > 0;
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(
    () =>
      hasResetLink &&
      password.trim().length >= 8 &&
      passwordConfirm.trim().length >= 8 &&
      !isSaving,
    [hasResetLink, isSaving, password, passwordConfirm],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);

    if (!hasResetLink) {
      setError("Ссылка для сброса пароля некорректна.");
      return;
    }

    if (password !== passwordConfirm) {
      setError("Пароли не совпадают.");
      return;
    }

    setIsSaving(true);

    try {
      await confirmPasswordReset(uid, token, password, passwordConfirm);
      setPassword("");
      setPasswordConfirm("");
      setMessage("Пароль изменён. Теперь можно войти с новым паролем.");
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? [
              ...caughtError.generalErrors,
              ...Object.values(caughtError.fieldErrors).flat(),
            ].join(" ") || caughtError.message
          : "Не удалось изменить пароль.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center py-10">
      <section className="w-full max-w-md rounded-2xl border border-border bg-bg p-6 shadow-sm">
        <div>
          <h1 className="text-2xl font-black">Сброс пароля</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Введите новый пароль для аккаунта.
          </p>
        </div>

        {!hasResetLink && (
          <p className="mt-5 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            В ссылке не хватает данных для сброса пароля. Запросите письмо ещё раз.
          </p>
        )}

        <form onSubmit={handleSubmit} className="mt-6 grid gap-4">
          <label className="grid gap-2">
            <span className="text-sm font-bold">Новый пароль</span>
            <input
              type="password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setError(null);
                setMessage(null);
              }}
              required
              minLength={8}
              autoComplete="new-password"
              className={getFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="text-sm font-bold">Повторите новый пароль</span>
            <input
              type="password"
              value={passwordConfirm}
              onChange={(event) => {
                setPasswordConfirm(event.target.value);
                setError(null);
                setMessage(null);
              }}
              required
              minLength={8}
              autoComplete="new-password"
              className={getFieldClassName()}
            />
          </label>

          {error && (
            <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          {message && (
            <p className="rounded-xl bg-success-soft px-3 py-2 text-sm font-bold text-success">
              {message}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-bold text-foreground transition hover:bg-muted disabled:opacity-60"
            >
              {isSaving ? "Сохранение…" : "Сохранить пароль"}
            </button>

            <Link
              href="/"
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-bold text-foreground transition hover:bg-muted"
            >
              На главную
            </Link>
          </div>
        </form>
      </section>
    </div>
  );
}

function getFieldClassName() {
  return [
    "h-11 rounded-xl border border-border bg-input-background px-3 text-foreground shadow-inner",
    "focus:border-foreground/40 focus:outline-none focus:ring-4 focus:ring-foreground/5",
  ].join(" ");
}

export default function PasswordResetConfirmPage() {
  return (
    <Suspense>
      <PasswordResetConfirmContent />
    </Suspense>
  );
}
