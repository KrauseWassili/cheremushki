"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { MemberProfilePage } from "@/components/members/member-profile-page";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { useApp } from "@/providers/AppProvider";
import { fetchMemberProfile } from "@/lib/profiles";
import type { MemberProfile } from "@/types/member";
import { ApiError } from "@/lib/api";

export default function MemberPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const { isLoggedIn, authLoading, openLogin } = useApp();
  const [member, setMember] = useState<MemberProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isLoggedIn || !slug) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchMemberProfile(slug);
        if (!cancelled) setMember(data);
      } catch (err) {
        if (!cancelled) {
          setMember(null);
          setError(
            err instanceof ApiError && err.status === 404
              ? "Профиль не найден."
              : err instanceof ApiError
                ? err.message
                : "Не удалось загрузить профиль.",
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
  }, [slug, isLoggedIn, authLoading]);

  if (authLoading || loading) {
    return <LoadingState title="Загрузка профиля" lines={2} />;
  }

  if (!isLoggedIn) {
    return (
      <main className="mx-auto w-full max-w-lg py-16 text-center">
        <p className="text-muted-foreground">
          Войдите, чтобы открыть профиль участника.
        </p>
        <Button
          type="button"
          onClick={() => openLogin("login")}
          variant="primary"
          className="mt-6"
        >
          Войти
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl py-4">
      <Link
        href="/members"
        className="my-5 inline-flex text-base font-bold text-muted-foreground hover:text-foreground"
      >
        ← Все участники
      </Link>

      {error || !member ? (
        <p className="text-center text-muted-foreground">
          {error ?? "Профиль не найден."}
        </p>
      ) : (
        <MemberProfilePage initialMember={member} />
      )}
    </main>
  );
}
