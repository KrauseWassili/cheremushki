"use client";

import { Check, Loader2, Search, X } from "lucide-react";
import {
  type KeyboardEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  type ApiProfileTagSuggestion,
  fetchTagSuggestions,
} from "@/lib/profiles";

const MAX_SELECTED_TAGS = 10;
const MAX_VISIBLE_SUGGESTIONS = 30;
const TAG_QUERY_LIMIT = 50;
const QUERY_DEBOUNCE_MS = 180;

type TagPickerProps = {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  description?: string;
};

type TagOption = {
  name: string;
  label: string;
  hashtag: string;
  category: string;
  usageCount: number;
};

type TagsByCategory = {
  category: string;
  options: TagOption[];
};

const suggestionCache = new Map<string, TagOption[]>();

export function TagPicker({
  value,
  onChange,
  label = "Ключевые слова",
  description = "Выберите до 10 тегов из словаря. Они помогут найти вас в каталоге и превратятся в хештеги в Telegram.",
}: TagPickerProps) {
  const inputId = useId();
  const listboxId = `${inputId}-suggestions`;
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selectedTags = useMemo(() => parseTags(value), [value]);
  const selectedSet = useMemo(() => new Set(selectedTags), [selectedTags]);
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [options, setOptions] = useState<TagOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const availableOptions = useMemo(
    () =>
      options
        .filter((option) => !selectedSet.has(option.name))
        .slice(0, MAX_VISIBLE_SUGGESTIONS),
    [options, selectedSet],
  );

  const groupedOptions = useMemo(
    () => groupByCategory(availableOptions),
    [availableOptions],
  );

  const isAtLimit = selectedTags.length >= MAX_SELECTED_TAGS;
  const exactMatch = options.find(
    (option) =>
      option.name.toLowerCase() === query.trim().toLowerCase() ||
      option.label.toLowerCase() === query.trim().toLowerCase() ||
      option.hashtag.toLowerCase() === query.trim().toLowerCase(),
  );

  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const normalizedQuery = query.trim().toLowerCase();
    const cached = suggestionCache.get(normalizedQuery);
    if (cached) {
      setOptions(cached);
      setError(null);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setIsLoading(true);
      setError(null);

      fetchTagSuggestions(normalizedQuery, TAG_QUERY_LIMIT)
        .then((suggestions) => {
          if (cancelled) return;
          const nextOptions = suggestions.map(mapTagSuggestion);
          suggestionCache.set(normalizedQuery, nextOptions);
          setOptions(nextOptions);
          setActiveIndex(0);
        })
        .catch(() => {
          if (cancelled) return;
          setError("Не удалось загрузить словарь тегов. Попробуйте еще раз.");
        })
        .finally(() => {
          if (!cancelled) {
            setIsLoading(false);
          }
        });
    }, normalizedQuery ? QUERY_DEBOUNCE_MS : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, query]);

  function updateSelected(tags: string[]) {
    onChange(tags.join(", "));
  }

  function selectOption(option: TagOption) {
    if (selectedSet.has(option.name) || isAtLimit) return;

    updateSelected([...selectedTags, option.name]);
    setQuery("");
    setIsOpen(true);
    inputRef.current?.focus();
  }

  function removeTag(tag: string) {
    updateSelected(selectedTags.filter((selected) => selected !== tag));
    inputRef.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((current) =>
        availableOptions.length
          ? (current + 1) % availableOptions.length
          : 0,
      );
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((current) =>
        availableOptions.length
          ? (current - 1 + availableOptions.length) % availableOptions.length
          : 0,
      );
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const selectedOption = availableOptions[activeIndex] ?? exactMatch;
      if (selectedOption) {
        selectOption(selectedOption);
      }
    }

    if (event.key === "Backspace" && !query && selectedTags.length > 0) {
      removeTag(selectedTags[selectedTags.length - 1]);
    }

    if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  const helperText = getHelperText({
    selectedCount: selectedTags.length,
    isAtLimit,
    isLoading,
    query,
    hasOptions: availableOptions.length > 0,
    hasExactMatch: Boolean(exactMatch),
    error,
  });

  return (
    <div ref={rootRef} className="grid gap-2">
      <label htmlFor={inputId} className="font-bold">
        {label}
      </label>

      <div
        className={[
          "relative rounded-xl border border-border bg-input-background px-3 py-2 shadow-inner transition",
          "focus-within:border-foreground/40 focus-within:ring-4 focus-within:ring-foreground/5",
        ].join(" ")}
        onClick={() => inputRef.current?.focus()}
      >
        <div className="flex min-h-7 flex-wrap items-center gap-2">
          {selectedTags.map((tag) => (
            <span
              key={tag}
              className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-sm font-bold text-foreground"
            >
              <span className="min-w-0 truncate">{tag}</span>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  removeTag(tag);
                }}
                className="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label={`Удалить тег ${tag}`}
                title={`Удалить тег ${tag}`}
              >
                <X aria-hidden="true" className="size-3.5" />
              </button>
            </span>
          ))}

          <div className="flex min-w-[12rem] flex-1 items-center gap-2">
            <Search aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
            <input
              id={inputId}
              ref={inputRef}
              type="text"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setIsOpen(true);
                setActiveIndex(0);
              }}
              onFocus={() => setIsOpen(true)}
              onKeyDown={handleKeyDown}
              disabled={isAtLimit}
              placeholder={
                selectedTags.length > 0
                  ? "Добавить тег"
                  : "Начните вводить или выберите из списка"
              }
              role="combobox"
              aria-expanded={isOpen}
              aria-controls={listboxId}
              aria-autocomplete="list"
              aria-activedescendant={
                isOpen && availableOptions[activeIndex]
                  ? getOptionId(listboxId, availableOptions[activeIndex])
                  : undefined
              }
              className="h-7 min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            />
          </div>
        </div>

        {isOpen && !isAtLimit && (
          <div
            id={listboxId}
            role="listbox"
            aria-label="Варианты тегов"
            className="absolute left-0 right-0 z-30 mt-3 max-h-80 overflow-auto rounded-xl border border-border bg-surface p-2 shadow-2xl"
          >
            {isLoading && (
              <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                Загружаем варианты...
              </div>
            )}

            {!isLoading && error && (
              <p className="px-3 py-2 text-sm text-destructive">{error}</p>
            )}

            {!isLoading && !error && groupedOptions.length === 0 && (
              <p className="px-3 py-2 text-sm text-muted-foreground">
                Такого тега нет в словаре. Выберите один из предложенных вариантов.
              </p>
            )}

            {!isLoading &&
              !error &&
              groupedOptions.map((group) => (
                <div key={group.category} className="py-1">
                  <div className="px-3 py-1 text-xs font-bold uppercase text-muted-foreground">
                    {group.category}
                  </div>
                  {group.options.map((option) => {
                    const optionIndex = availableOptions.findIndex(
                      (item) => item.name === option.name,
                    );
                    const isActive = optionIndex === activeIndex;

                    return (
                      <button
                        id={getOptionId(listboxId, option)}
                        key={option.name}
                        type="button"
                        role="option"
                        aria-selected={isActive}
                        onMouseEnter={() => setActiveIndex(optionIndex)}
                        onClick={() => selectOption(option)}
                        className={[
                          "flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                          isActive
                            ? "bg-accent-soft text-foreground"
                            : "text-foreground hover:bg-accent-soft",
                        ].join(" ")}
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-bold">
                            {option.label}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {option.hashtag}
                          </span>
                        </span>
                        <Check
                          aria-hidden="true"
                          className="size-4 shrink-0 text-muted-foreground opacity-0"
                        />
                      </button>
                    );
                  })}
                </div>
              ))}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-start justify-between gap-2 text-xs leading-5 text-muted-foreground">
        <span>{helperText}</span>
        <span className={isAtLimit ? "font-bold text-foreground" : ""}>
          {selectedTags.length}/{MAX_SELECTED_TAGS}
        </span>
      </div>

      <p className="text-xs leading-5 text-muted-foreground">{description}</p>
    </div>
  );
}

function parseTags(value: string) {
  const seen = new Set<string>();
  const tags: string[] = [];

  for (const rawTag of value.split(",")) {
    const tag = rawTag.trim().replace(/^#/, "");
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    tags.push(tag);
  }

  return tags.slice(0, MAX_SELECTED_TAGS);
}

function mapTagSuggestion(suggestion: ApiProfileTagSuggestion): TagOption {
  return {
    name: suggestion.name,
    label: suggestion.label || suggestion.name,
    hashtag: suggestion.hashtag || `#${suggestion.name}`,
    category: resolveCategoryLabel(suggestion.category),
    usageCount: suggestion.usage_count ?? 0,
  };
}

function resolveCategoryLabel(category: ApiProfileTagSuggestion["category"]) {
  if (!category) return "Все теги";
  if (typeof category === "string") return category;
  return category.label || category.name || category.slug || "Все теги";
}

function groupByCategory(options: TagOption[]): TagsByCategory[] {
  const groups = new Map<string, TagOption[]>();

  for (const option of options) {
    const group = groups.get(option.category) ?? [];
    group.push(option);
    groups.set(option.category, group);
  }

  return [...groups.entries()].map(([category, groupOptions]) => ({
    category,
    options: groupOptions.sort((first, second) => {
      if (second.usageCount !== first.usageCount) {
        return second.usageCount - first.usageCount;
      }
      return first.label.localeCompare(second.label, "ru");
    }),
  }));
}

function getHelperText({
  selectedCount,
  isAtLimit,
  isLoading,
  query,
  hasOptions,
  hasExactMatch,
  error,
}: {
  selectedCount: number;
  isAtLimit: boolean;
  isLoading: boolean;
  query: string;
  hasOptions: boolean;
  hasExactMatch: boolean;
  error: string | null;
}) {
  if (error) return "Словарь временно недоступен, уже выбранные теги сохранятся.";
  if (isAtLimit) return "Достигнут максимум тегов для профиля и Telegram.";
  if (isLoading) return "Ищем теги в словаре...";
  if (query.trim() && !hasOptions && !hasExactMatch) {
    return "Свободный ввод отключен: можно выбрать только тег из словаря.";
  }
  if (selectedCount === 0) {
    return "Откройте список или начните вводить название сферы, навыка или интереса.";
  }
  return "Enter выбирает подсвеченный тег, Backspace удаляет последний выбранный.";
}

function getOptionId(listboxId: string, option: TagOption) {
  return `${listboxId}-${encodeURIComponent(option.name)}`;
}
