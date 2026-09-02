"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { buttonClassName } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { confirmEmailChange } from "@/lib/auth";
import { useApp } from "@/providers/AppProvider";

function EmailChangeConfirmContent() {
  const { signOutLocally } = useApp();
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid") ?? "";
  const token = searchParams.get("token") ?? "";
  const hasLink = uid.length > 0 && token.length > 0;

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    hasLink ? "loading" : "error",
  );
  const [message, setMessage] = useState(
    hasLink
      ? "Подтверждаем новую почту..."
      : "В ссылке не хватает данных для подтверждения почты. Запросите письмо еще раз.",
  );

  useEffect(() => {
    if (!hasLink) return;

    let cancelled = false;

    async function run() {
      try {
        const result = await confirmEmailChange(uid, token);
        if (cancelled) return;
        signOutLocally();
        setStatus("success");
        setMessage(result.detail);
      } catch (caughtError) {
        if (cancelled) return;
        setStatus("error");
        setMessage(
          caughtError instanceof ApiError
            ? [
                ...caughtError.generalErrors,
                ...Object.values(caughtError.fieldErrors).flat(),
              ].join(" ") || caughtError.message
            : "Не удалось подтвердить новую почту.",
        );
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [hasLink, signOutLocally, token, uid]);

  return (
    <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center py-10">
      <section className="w-full max-w-md rounded-2xl border border-border bg-bg p-6 shadow-sm">
        <div>
          <h1 className="text-2xl font-black">Смена почты</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Подтверждение нового адреса электронной почты для аккаунта.
          </p>
        </div>

        <div className="mt-6">
          {status === "loading" && (
            <p className="rounded-xl border border-border bg-muted/40 px-3 py-2 text-sm text-foreground">
              {message}
            </p>
          )}
          {status === "success" && (
            <p className="rounded-xl bg-success-soft px-3 py-2 text-sm font-bold text-success">
              {message}
            </p>
          )}
          {status === "error" && (
            <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {message}
            </p>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Link href="/" className={buttonClassName()}>
            На главную
          </Link>
        </div>
      </section>
    </div>
  );
}

export default function EmailChangeConfirmPage() {
  return (
    <Suspense>
      <EmailChangeConfirmContent />
    </Suspense>
  );
}
