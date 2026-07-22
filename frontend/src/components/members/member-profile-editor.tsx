"use client";

import { useState } from "react";
import type { MemberProfile } from "@/types/member";
import { AvatarUpload } from "./avatar-upload";

type MemberProfileEditorProps = {
  member: MemberProfile;
  onSave: (member: MemberProfile) => void;
  onCancel: () => void;
};

const inputClassName =
  "h-11 w-full rounded-xl border border-border bg-background px-3 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5";

const textareaClassName =
  "min-h-32 w-full resize-y rounded-xl border border-border bg-background px-3 py-3 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5";

export function MemberProfileEditor({
  member,
  onSave,
  onCancel,
}: MemberProfileEditorProps) {
  const [form, setForm] = useState(member);
  const [tags, setTags] = useState(member.tags.join(", "));
  const [languages, setLanguages] = useState(member.languages.join(", "));

  function updateField<K extends keyof MemberProfile>(
    field: K,
    value: MemberProfile[K],
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    onSave({
      ...form,
      tags: tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      languages: languages
        .split(",")
        .map((language) => language.trim())
        .filter(Boolean),
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-8"
    >
      <div>
        <h1 className="text-3xl font-black">Редактирование профиля</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Эти данные будут видны другим участникам клуба.
        </p>
      </div>

      <div className="mt-8 grid gap-6">
        <Field label="Имя">
          <input
            required
            value={form.fullName}
            onChange={(event) => updateField("fullName", event.target.value)}
            className={inputClassName}
          />
        </Field>

        <AvatarUpload
          value={form.avatarUrl}
          fullName={form.fullName}
          onChange={(avatarUrl) => updateField("avatarUrl", avatarUrl)}
        />

        <Field
          label="Профессиональный заголовок"
          hint="Например: Backend-разработчик, Python и платёжные системы"
        >
          <input
            required
            value={form.headline}
            onChange={(event) => updateField("headline", event.target.value)}
            className={inputClassName}
          />
        </Field>

        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Город">
            <input
              required
              value={form.city}
              onChange={(event) => updateField("city", event.target.value)}
              className={inputClassName}
            />
          </Field>

          <Field label="Компания">
            <input
              value={form.company || ""}
              onChange={(event) => updateField("company", event.target.value)}
              className={inputClassName}
            />
          </Field>
        </div>

        <Field label="Должность или занятие">
          <input
            value={form.position || ""}
            onChange={(event) => updateField("position", event.target.value)}
            className={inputClassName}
          />
        </Field>

        <Field label="О себе">
          <textarea
            required
            value={form.bio}
            onChange={(event) => updateField("bio", event.target.value)}
            className={textareaClassName}
          />
        </Field>

        <Field label="Чем ты можешь помочь">
          <textarea
            required
            value={form.canHelpWith}
            onChange={(event) => updateField("canHelpWith", event.target.value)}
            className={textareaClassName}
          />
        </Field>

        <Field label="Что тебе сейчас интересно">
          <textarea
            required
            value={form.lookingFor}
            onChange={(event) => updateField("lookingFor", event.target.value)}
            className={textareaClassName}
          />
        </Field>

        <Field
          label="Профессиональные направления"
          hint="Перечисли через запятую"
        >
          <input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            className={inputClassName}
          />
        </Field>

        <Field label="Языки" hint="Перечисли через запятую">
          <input
            value={languages}
            onChange={(event) => setLanguages(event.target.value)}
            className={inputClassName}
          />
        </Field>

        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Telegram">
            <input
              value={form.telegramUsername || ""}
              onChange={(event) =>
                updateField(
                  "telegramUsername",
                  event.target.value.replace(/^@/, ""),
                )
              }
              placeholder="username без @"
              className={inputClassName}
            />
          </Field>

          <Field label="LinkedIn">
            <input
              type="url"
              value={form.linkedinUrl || ""}
              onChange={(event) =>
                updateField("linkedinUrl", event.target.value)
              }
              className={inputClassName}
            />
          </Field>
        </div>

        <Field label="Личный сайт">
          <input
            type="url"
            value={form.websiteUrl || ""}
            onChange={(event) => updateField("websiteUrl", event.target.value)}
            className={inputClassName}
          />
        </Field>

        <label className="flex items-start gap-3 rounded-2xl border border-border p-4">
          <input
            type="checkbox"
            checked={form.isOpenToContacts}
            onChange={(event) =>
              updateField("isOpenToContacts", event.target.checked)
            }
            className="mt-1 size-4"
          />

          <span>
            <span className="block font-bold">Открыт к общению</span>
            <span className="mt-1 block text-sm text-muted-foreground">
              Другие участники увидят доступные способы связи.
            </span>
          </span>
        </label>
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <button
          type="submit"
          className="rounded-xl bg-foreground px-5 py-2.5 text-sm font-bold text-background"
        >
          Сохранить
        </button>

        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl border border-border px-5 py-2.5 text-sm font-bold hover:bg-muted"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}

type FieldProps = {
  label: string;
  hint?: string;
  children: React.ReactNode;
};

function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="grid gap-2">
      <span className="font-bold">{label}</span>
      {children}

      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}
