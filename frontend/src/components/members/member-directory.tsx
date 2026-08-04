"use client";

import type { MemberProfile } from "@/types/member";
import { MemberCard } from "./member-card";
import { MemberFilterSelect } from "./member-filter-select";
import { useMemo, useState } from "react";
import { isProfileReadyForDirectory } from "@/lib/profile";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";

type MemberDirectoryProps = {
  members: MemberProfile[];
};

export function MemberDirectory({ members }: MemberDirectoryProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [selectedTag, setSelectedTag] = useState("");

  const cities = useMemo(
    () =>
      [...new Set(members.map((member) => member.city).filter(Boolean))].sort(
        (a, b) => a.localeCompare(b, "ru"),
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
  }, [members, query, city, selectedTag]);

  const hasFilters = Boolean(query || city || selectedTag);

  function resetFilters() {
    setQuery("");
    setCity("");
    setSelectedTag("");
  }

  return (
    <div className="grid gap-8 min-[1100px]:ml-[-292px] min-[1100px]:w-[calc(100%+292px)] min-[1100px]:grid-cols-[260px_minmax(0,1fr)] min-[1100px]:items-start">
      <aside className="rounded-3xl border border-border bg-background p-5 shadow-sm min-[1100px]:sticky min-[1100px]:top-6">
        <h3 className="font-bold">Фильтры</h3>

        <div className="mt-5 grid gap-4 min-[1100px]:grid-cols-1">
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
            label="Ключевое слово"
            value={selectedTag}
            options={tags}
            placeholder="Все ключевые слова"
            onChange={setSelectedTag}
          />

          {hasFilters && (
            <Button
              type="button"
              onClick={resetFilters}
              size="sm"
            >
              Очистить фильтры
            </Button>
          )}
        </div>
      </aside>

      <div className="min-w-0">
        <div className="mb-6">
          <label htmlFor="members-search" className="sr-only">
            Поиск участников
          </label>

          <TextField
            id="members-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Имя, профессия, компания, навык или ключевое слово"
            fieldSize="lg"
            className="rounded-2xl px-5 text-base"
          />

          <p className="mt-3 text-sm text-muted-foreground">
            Найдено:{" "}
            <strong className="text-foreground">{filteredMembers.length}</strong>
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
            <p className="text-lg font-bold">Никого не нашли</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Попробуй изменить запрос или сбросить фильтры.
            </p>

            <Button
              type="button"
              onClick={resetFilters}
              variant="solid"
              className="mt-5"
            >
              Показать всех
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
