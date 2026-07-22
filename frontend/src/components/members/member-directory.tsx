"use client";

import { useMemo, useState } from "react";
import type { MemberProfile } from "@/types/member";
import { MemberCard } from "./member-card";

type MemberDirectoryProps = {
  members: MemberProfile[];
};

export function MemberDirectory({ members }: MemberDirectoryProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [selectedTag, setSelectedTag] = useState("");

  const cities = useMemo(
    () =>
      [...new Set(members.map((member) => member.city))].sort((a, b) =>
        a.localeCompare(b, "ru"),
      ),
    [members],
  );

  const tags = useMemo(
    () =>
      [...new Set(members.flatMap((member) => member.tags))].sort((a, b) =>
        a.localeCompare(b, "ru"),
      ),
    [members],
  );

  const filteredMembers = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ru");

    return members.filter((member) => {
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

      const matchesTag =
        !selectedTag || member.tags.includes(selectedTag);

      return matchesQuery && matchesCity && matchesTag;
    });
  }, [members, query, city, selectedTag]);

  const hasFilters = Boolean(query || city || selectedTag);

  function resetFilters() {
    setQuery("");
    setCity("");
    setSelectedTag("");
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[260px_minmax(0,760px)] lg:items-start lg:justify-center">
      <aside className="rounded-3xl border border-border bg-background p-5 lg:sticky lg:top-6">
        <h2 className="font-black">Фильтры</h2>

        <div className="mt-5 grid gap-5">
          <label className="grid gap-2">
            <span className="text-sm font-bold">Город</span>
            <select
              value={city}
              onChange={(event) => setCity(event.target.value)}
              className="h-11 rounded-xl border border-border bg-background px-3"
            >
              <option value="">Все города</option>

              {cities.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-2">
            <span className="text-sm font-bold">Направление</span>
            <select
              value={selectedTag}
              onChange={(event) => setSelectedTag(event.target.value)}
              className="h-11 rounded-xl border border-border bg-background px-3"
            >
              <option value="">Все направления</option>

              {tags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
          </label>

          {hasFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-xl border border-border px-4 py-2 text-sm font-bold hover:bg-muted"
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