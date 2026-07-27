"use client";

import { useMemo, useState } from "react";
import type { MemberProfile } from "@/types/member";
import type { ProfileDraft } from "@/types/profile";
import { isProfileReadyForDirectory } from "@/lib/profile";
import { MemberCard } from "./member-card";
import { MemberFilterSelect } from "./member-filter-select";

type MemberDirectoryProps = {
  members: MemberProfile[];
};

const TELEGRAM_GROUP_URL = "https://t.me/+demo-invite-link";

export function MemberDirectory({ members }: MemberDirectoryProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [selectedTag, setSelectedTag] = useState("");

  const directoryMembers = useMemo(() => {
    if (typeof window === "undefined") return members;

    const stored = window.localStorage.getItem("mock-profile-draft");
    if (!stored) return members;

    try {
      const draft = JSON.parse(stored) as ProfileDraft;

      if (!isProfileReadyForDirectory(draft)) return members;

      const syntheticMember: MemberProfile = {
        id: "local-profile",
        slug: draft.slug || "my-profile",
        fullName:
          [draft.firstName, draft.lastName].filter(Boolean).join(" ").trim() ||
          "Мой профиль",
        avatarUrl: draft.avatarUrl,
        avatarOriginalUrl: draft.avatarOriginalUrl,
        avatarPositionX: draft.avatarPositionX,
        avatarPositionY: draft.avatarPositionY,
        avatarScale: draft.avatarScale,
        avatarCropSize: draft.avatarCropSize,
        headline: draft.headline || "Профиль в процессе заполнения",
        city: draft.city || "Не указан",
        profession: draft.profession || "",
        company: draft.company || "",
        position: draft.position || "",
        bio: draft.bio || "",
        canHelpWith: draft.canHelpWith || "",
        lookingFor: draft.lookingFor || "",
        tags:
          draft.tags
            ?.split(",")
            .map((tag) => tag.trim())
            .filter(Boolean) || [],
        languages: [],
        email: draft.email || "",
        telegramUsername: draft.telegram || "",
        linkedinUrl: draft.linkedin || "",
        websiteUrl: draft.website || "",
        contactMode: draft.contactMode || "request",
        telegramGroupUrl: TELEGRAM_GROUP_URL,
        achievements: [],
        joinedAt: new Date().toISOString(),
      };

      return [syntheticMember, ...members];
    } catch {
      return members;
    }
  }, [members]);

  const cities = useMemo(
    () =>
      [...new Set(directoryMembers.map((member) => member.city))].sort((a, b) =>
        a.localeCompare(b, "ru"),
      ),
    [directoryMembers],
  );

  const tags = useMemo(
    () =>
      [...new Set(directoryMembers.flatMap((member) => member.tags))].sort(
        (a, b) => a.localeCompare(b, "ru"),
      ),
    [directoryMembers],
  );

  const filteredMembers = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ru");

    return directoryMembers.filter((member) => {
      if (
        !isProfileReadyForDirectory({
          avatarUrl: member.avatarUrl,
          firstName: member.fullName,
          city: member.city,
          headline: member.headline,
          bio: member.bio,
          canHelpWith: member.canHelpWith,
          lookingFor: member.lookingFor,
        })
      ) {
        return false;
      }
      const searchableText = [
        member.fullName,
        member.headline,
        member.city,
        member.company,
        member.position,
        member.bio,
        member.canHelpWith,
        member.lookingFor,
        ...member.tags,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("ru");

      const matchesQuery =
        !normalizedQuery || searchableText.includes(normalizedQuery);

      const matchesCity = !city || member.city === city;

      const matchesTag = !selectedTag || member.tags.includes(selectedTag);

      return matchesQuery && matchesCity && matchesTag;
    });
  }, [directoryMembers, query, city, selectedTag]);

  const hasFilters = Boolean(query || city || selectedTag);

  function resetFilters() {
    setQuery("");
    setCity("");
    setSelectedTag("");
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[260px_minmax(0,760px)] lg:items-start lg:justify-center">
      <aside className="rounded-3xl border border-border bg-background p-5 lg:sticky lg:top-6">
        <h3 className="font-black">Фильтры</h3>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <MemberFilterSelect
            id="filter-city"
            label="Город"
            value={city}
            options={cities}
            placeholder="Все города"
            onChange={setCity}
          />

          <MemberFilterSelect
            id="filter-tag"
            label="Направление"
            value={selectedTag}
            options={tags}
            placeholder="Все направления"
            onChange={setSelectedTag}
          />

          {hasFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-xl border border-border px-4 py-2 text-sm font-bold hover:bg-muted sm:col-span-2 lg:col-span-1"
            >
              Очистить фильтры
            </button>
          )}
        </div>
      </aside>

      <div className="min-w-0">
        <div className="mb-6">
          <label htmlFor="members-search" className="sr-only">
            Поиск участников
          </label>

          <input
            id="members-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Имя, профессия, компания, навык или ключевое слово"
            className="h-14 w-full rounded-2xl border border-border bg-background px-5 text-base outline-none transition placeholder:text-muted-foreground focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5"
          />

          <p className="mt-3 text-sm text-muted-foreground">
            Найдено:{" "}
            <strong className="text-foreground">
              {filteredMembers.length}
            </strong>
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            В каталоге показываются профили, где заполнены все основные данные.
          </p>
        </div>

        {filteredMembers.length > 0 ? (
          <div className="grid gap-5">
            {filteredMembers.map((member) => (
              <MemberCard key={member.id} member={member} />
            ))}
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-border p-10 text-center">
            <p className="text-lg font-black">Никого не нашли</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Попробуй изменить запрос или сбросить фильтры.
            </p>

            <button
              type="button"
              onClick={resetFilters}
              className="mt-5 rounded-xl bg-foreground px-5 py-2.5 text-sm font-bold text-background"
            >
              Показать всех
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
