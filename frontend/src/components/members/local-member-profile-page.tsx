"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { MemberProfile } from "@/types/member";
import type { ProfileDraft } from "@/types/profile";
import { isProfileReadyForDirectory } from "@/lib/profile";
import { MemberProfileView } from "./member-profile";

const STORAGE_KEY = "mock-profile-draft";
const TELEGRAM_GROUP_URL = "https://t.me/+demo-invite-link";

type LocalMemberProfilePageProps = {
  slug: string;
};

export function LocalMemberProfilePage({ slug }: LocalMemberProfilePageProps) {
  const [member, setMember] = useState<MemberProfile | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setIsLoaded(true);
      return;
    }

    try {
      const draft = JSON.parse(stored) as ProfileDraft;
      const draftSlug = draft.slug || "my-profile";

      if (draftSlug !== slug || !isProfileReadyForDirectory(draft)) {
        setIsLoaded(true);
        return;
      }

      setMember({
        id: "local-profile",
        slug: draftSlug,
        fullName:
          [draft.firstName, draft.lastName].filter(Boolean).join(" ").trim() ||
          "Мой профиль",
        avatarUrl: draft.avatarUrl,
        avatarOriginalUrl: draft.avatarOriginalUrl,
        avatarPositionX: draft.avatarPositionX,
        avatarPositionY: draft.avatarPositionY,
        avatarScale: draft.avatarScale,
        avatarCropSize: draft.avatarCropSize,
        headline: draft.headline,
        city: draft.city,
        profession: draft.profession,
        company: draft.company,
        position: draft.position,
        bio: draft.bio,
        canHelpWith: draft.canHelpWith,
        lookingFor: draft.lookingFor,
        tags: draft.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        languages: [],
        email: draft.email,
        telegramUsername: draft.telegram,
        linkedinUrl: draft.linkedin,
        websiteUrl: draft.website,
        contactMode: draft.contactMode || "request",
        telegramGroupUrl: TELEGRAM_GROUP_URL,
        achievements: [],
        joinedAt: new Date().toISOString(),
      });
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    } finally {
      setIsLoaded(true);
    }
  }, [slug]);

  if (!isLoaded) {
    return (
      <div className="rounded-3xl border border-border p-8">
        Загрузка профиля…
      </div>
    );
  }

  if (!member) {
    return (
      <div className="rounded-3xl border border-dashed border-border p-10 text-center">
        <p className="text-lg font-black">Профиль не найден</p>
        <Link
          href="/members"
          className="mt-5 inline-flex rounded-xl border border-border px-4 py-2 text-sm font-bold hover:bg-muted"
        >
          Вернуться в каталог
        </Link>
      </div>
    );
  }

  return <MemberProfileView member={member} />;
}
