"use client";

import { ChevronDown } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useId, useRef, useState } from "react";

export type CustomSelectOption = {
  value: string;
  label: string;
};

type CustomSelectProps = {
  value: string;
  options: CustomSelectOption[];
  placeholder?: string;
  onChange: (value: string) => void;
  id?: string;
  disabled?: boolean;
};

export function CustomSelect({
  value,
  options,
  placeholder = "Выберите значение",
  onChange,
  id,
  disabled = false,
}: CustomSelectProps) {
  const generatedId = useId();
  const buttonId = id ?? generatedId;
  const listboxId = `${buttonId}-listbox`;
  const rootRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(() =>
    Math.max(
      0,
      options.findIndex((option) => option.value === value),
    ),
  );

  const selectedOption = options.find((option) => option.value === value);

  useEffect(() => {
    const selectedIndex = options.findIndex((option) => option.value === value);
    if (selectedIndex >= 0) {
      setActiveIndex(selectedIndex);
    }
  }, [options, value]);

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

  function selectOption(option: CustomSelectOption) {
    onChange(option.value);
    setIsOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (disabled) return;

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((current) => {
        const direction = event.key === "ArrowDown" ? 1 : -1;
        return (current + direction + options.length) % options.length;
      });
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isOpen) {
        selectOption(options[activeIndex]);
      } else {
        setIsOpen(true);
      }
    }

    if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        id={buttonId}
        type="button"
        role="combobox"
        aria-controls={listboxId}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => setIsOpen((current) => !current)}
        onKeyDown={handleKeyDown}
        className="flex h-11 w-full items-center justify-between gap-3 rounded-xl border border-border bg-input-background px-3 text-left text-sm text-foreground shadow-inner outline-none transition focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span
          className={[
            "min-w-0 truncate",
            selectedOption ? "" : "text-muted-foreground",
          ].join(" ")}
        >
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={[
            "size-4 shrink-0 text-muted-foreground transition-transform",
            isOpen ? "rotate-180" : "",
          ].join(" ")}
        />
      </button>

      {isOpen && (
        <div
          id={listboxId}
          role="listbox"
          aria-labelledby={buttonId}
          className="absolute z-30 mt-2 max-h-64 w-full overflow-auto rounded-xl border border-border bg-surface p-1 shadow-2xl"
        >
          {options.map((option, index) => {
            const isSelected = option.value === value;
            const isActive = index === activeIndex;

            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectOption(option)}
                className={[
                  "flex w-full cursor-pointer items-center rounded-lg px-3 py-2 text-left text-sm transition-colors",
                  isSelected
                    ? "bg-primary text-surface"
                    : isActive
                      ? "bg-accent-soft text-foreground"
                      : "text-foreground hover:bg-accent-soft",
                ].join(" ")}
              >
                <span className="min-w-0 truncate">{option.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
