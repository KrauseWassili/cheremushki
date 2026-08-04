"use client";

import { useEffect, useState } from "react";
import { MemberDirectory } from "@/components/members/member-directory";
import { LoadingState } from "@/components/ui/loading-state";
import { useApp } from "@/providers/AppProvider";
import { fetchMemberProfiles } from "@/lib/profiles";
import type { MemberProfile } from "@/types/member";
import { ApiError } from "@/lib/api";

export default function MembersPage() {
  const { isLoggedIn, authLoading, openLogin } = useApp();
  const [members, setMembers] = useState<MemberProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    if (!isLoggedIn) {
      setLoading(false);
      setMembers([]);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchMemberProfiles();
        if (!cancelled) setMembers(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : "Не удалось загрузить участников.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn, authLoading]);

  if (authLoading || loading) {
    return <LoadingState title="Загрузка участников" />;
  }

  if (!isLoggedIn) {
    return (
      <main className="mx-auto w-full max-w-lg py-16 text-center">
        <h1 className="text-3xl font-black">Участники</h1>
        <p className="mt-4 text-muted-foreground">
          Войдите в аккаунт, чтобы видеть каталог участников.
        </p>
        <button
          type="button"
          onClick={() => openLogin("login")}
          className="button-gray-rounded mt-6"
        >
          Войти
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl py-4">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-black tracking-tight">
          Участники
        </h1>
        <p className="mt-5 text-base leading-7 text-muted-foreground">
          Наше сообщество — это потенциал, сложенный из опыта, знаний и
          возможностей каждого из нас. Вместе мы находим решения, воплощаем идеи
          и открываем друг другу новые пути. Найди тех, с кем хочется говорить,
          действовать и делиться.
        </p>
      </header>

      {error ? (
        <p className="text-center text-destructive">{error}</p>
      ) : (
        <MemberDirectory members={members} />
      )}
    </main>
  );
}
