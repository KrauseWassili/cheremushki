"use client";

import {
  type Dispatch,
  type FormEvent,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useApp } from "@/providers/AppProvider";
import { AvatarUpload } from "@/components/members/avatar-upload";
import { ApiError } from "@/lib/api";
import { getProfileRequiredFieldsStatus } from "@/lib/profile";
import type { ProfileDraft } from "@/types/profile";

const STORAGE_KEY = "mock-profile-draft";

type AccountSettingsPanel =
  | "name"
  | "email"
  | "password"
  | "reset-password"
  | "delete";

type AccountNameValues = {
  firstName: string;
  lastName: string;
};

type SaveAccountName = Dispatch<AccountNameValues>;

const initialDraft: ProfileDraft = {
  firstName: "",
  lastName: "",
  slug: "",
  email: "",
  city: "",
  profession: "",
  headline: "",
  bio: "",
  canHelpWith: "",
  lookingFor: "",
  company: "",
  position: "",
  telegram: "",
  linkedin: "",
  website: "",
  tags: "",
  contactMode: "request",
  avatarUrl: undefined,
  avatarOriginalUrl: undefined,
  avatarPositionX: 50,
  avatarPositionY: 50,
  avatarScale: 1,
  avatarCropSize: 100,
};

export default function ProfilePage() {
  const { user, isLoggedIn, updateCurrentUser } = useApp();
  const [draft, setDraft] = useState<ProfileDraft>(initialDraft);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const [accountSettingsPanel, setAccountSettingsPanel] =
    useState<AccountSettingsPanel | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setDraft((current) => ({ ...current, ...JSON.parse(stored) }));
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, []);

  useEffect(() => {
    if (!user) return;

    setDraft((current) => ({
      ...current,
      firstName: user.first_name,
      lastName: user.last_name,
      email: user.email,
    }));
  }, [user]);

  const requiredStatus = useMemo(
    () => getProfileRequiredFieldsStatus(draft),
    [draft],
  );

  function updateField<K extends keyof ProfileDraft>(
    field: K,
    value: ProfileDraft[K],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setSaved(false);
    setSaveError(null);
  }

  function updateAvatarCrop(crop: {
    x: number;
    y: number;
    scale: number;
    size: number;
    avatarUrl?: string;
    sourceUrl?: string;
  }) {
    const nextDraft = {
      ...draft,
      avatarUrl: crop.avatarUrl ?? draft.avatarUrl,
      avatarOriginalUrl: crop.sourceUrl ?? draft.avatarOriginalUrl,
      avatarPositionX: crop.x,
      avatarPositionY: crop.y,
      avatarScale: crop.scale,
      avatarCropSize: crop.size,
    };

    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextDraft));
      window.dispatchEvent(new Event("profile-draft-updated"));
    }

    setDraft(nextDraft);
    setSaved(true);
    setSaveError(null);
  }

  function handleSave() {
    if (typeof window === "undefined") return;

    setIsSaving(true);
    setSaveError(null);

    const nextDraft = {
      ...draft,
      firstName: draft.firstName.trim(),
      lastName: draft.lastName.trim(),
      email: draft.email.trim(),
      slug:
        draft.slug.trim() ||
        createProfileSlug(
          [draft.firstName, draft.lastName].filter(Boolean).join(" "),
        ),
    };

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextDraft));
    window.dispatchEvent(new Event("profile-draft-updated"));
    setDraft(nextDraft);
    setSaved(true);
    setIsSaving(false);
  }

  async function handleSaveAccountName({
    firstName,
    lastName,
  }: AccountNameValues) {
    const updatedUser = await updateCurrentUser({
      email: draft.email,
      first_name: firstName.trim(),
      last_name: lastName.trim(),
    });

    setDraft((current) => {
      const nextDraft = {
        ...current,
        firstName: updatedUser.first_name,
        lastName: updatedUser.last_name,
      };

      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextDraft));
        window.dispatchEvent(new Event("profile-draft-updated"));
      }

      return nextDraft;
    });
  }

  if (!isLoggedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="text-center">
          <p className="mb-4 text-2xl font-semibold text-foreground">
            Вы не вошли в систему :(
          </p>
          <Link href="/" className="button-gray-rounded">
            На главную
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-8">
        <div>
          <h1 className="text-3xl font-black">Профиль</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Заполните основные поля, чтобы профиль появился в каталоге
            участников.
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            После внесения изменений нажмите «Сохранить» внизу страницы.
          </p>
        </div>
      </section>

      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-black">Данные аккаунта</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Эти данные относятся к учетной записи и здесь показываются только
              для просмотра.
            </p>
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setIsAccountMenuOpen(true);
                setAccountSettingsPanel(null);
              }}
              className={getSecondaryButtonClassName()}
            >
              Настройки аккаунта
            </button>
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <label className="grid gap-2">
            <span className="font-bold">Имя</span>
            <input
              value={draft.firstName}
              readOnly
              autoComplete="given-name"
              className={getReadOnlyAccountFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Фамилия</span>
            <input
              value={draft.lastName}
              readOnly
              autoComplete="family-name"
              className={getReadOnlyAccountFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Почта</span>
            <input
              type="email"
              value={draft.email}
              readOnly
              autoComplete="email"
              className={getReadOnlyAccountFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Пароль</span>
            <input
              type="password"
              value="********"
              disabled
              readOnly
              autoComplete="current-password"
              className={getReadOnlyAccountFieldClassName()}
            />
          </label>
        </div>
      </section>

      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-black">Основные данные</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Эти поля нужны для минимального профиля.
            </p>
            <p className="mt-2 text-sm font-bold text-foreground">
              Заполнено {requiredStatus.filledCount} из{" "}
              {requiredStatus.totalCount} обязательных полей
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Учитываются фотография и поля этого блока.
            </p>
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <AvatarUpload
              value={draft.avatarUrl}
              sourceValue={draft.avatarOriginalUrl}
              positionX={draft.avatarPositionX}
              positionY={draft.avatarPositionY}
              scale={draft.avatarScale}
              cropSize={draft.avatarCropSize}
              fullName={
                [draft.firstName, draft.lastName].filter(Boolean).join(" ") ||
                "Профиль"
              }
              required
              onChange={(avatarUrl) =>
                updateField("avatarUrl", avatarUrl ?? "")
              }
              onSourceChange={(avatarOriginalUrl) =>
                updateField("avatarOriginalUrl", avatarOriginalUrl ?? "")
              }
              onCropChange={updateAvatarCrop}
            />
          </div>

          <label className="grid gap-2">
            <RequiredFieldLabel label="Город" isFilled={isFilled(draft.city)} />
            <input
              required
              value={draft.city}
              onChange={(event) => updateField("city", event.target.value)}
              className={getRequiredFieldClassName(draft.city)}
            />
          </label>

          <label className="grid gap-2">
            <RequiredFieldLabel
              label="Профессиональный заголовок"
              isFilled={isFilled(draft.headline)}
            />
            <input
              required
              value={draft.headline}
              onChange={(event) => updateField("headline", event.target.value)}
              className={getRequiredFieldClassName(draft.headline)}
            />
          </label>
        </div>

        <div className="mt-5 grid gap-5">
          <label className="grid gap-2">
            <RequiredFieldLabel
              label="Краткое описание"
              isFilled={isFilled(draft.bio)}
            />
            <textarea
              required
              value={draft.bio}
              onChange={(event) => updateField("bio", event.target.value)}
              className={getRequiredFieldClassName(draft.bio, true)}
            />
          </label>

          <label className="grid gap-2">
            <RequiredFieldLabel
              label="Могу помочь"
              isFilled={isFilled(draft.canHelpWith)}
            />
            <textarea
              required
              value={draft.canHelpWith}
              onChange={(event) =>
                updateField("canHelpWith", event.target.value)
              }
              className={getRequiredFieldClassName(draft.canHelpWith, true)}
            />
          </label>

          <label className="grid gap-2">
            <RequiredFieldLabel
              label="Сейчас интересно"
              isFilled={isFilled(draft.lookingFor)}
            />
            <textarea
              required
              value={draft.lookingFor}
              onChange={(event) =>
                updateField("lookingFor", event.target.value)
              }
              className={getRequiredFieldClassName(draft.lookingFor, true)}
            />
          </label>
        </div>
      </section>

      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-8">
        <h2 className="text-xl font-black">Дополнительно</h2>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <label className="grid gap-2 sm:col-span-2">
            <span className="font-bold">Как с вами связываться</span>
            <select
              value={draft.contactMode}
              onChange={(event) =>
                updateField(
                  "contactMode",
                  event.target.value as ProfileDraft["contactMode"],
                )
              }
              className={getEditableFieldClassName()}
            >
              <option value="direct">Показывать прямые контакты</option>
              <option value="request">Показывать кнопку запроса</option>
              <option value="group">
                Предлагать общение в Telegram-группе
              </option>
              <option value="closed">Обращения закрыты</option>
            </select>
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Slug профиля</span>
            <input
              value={draft.slug}
              onChange={(event) => updateField("slug", event.target.value)}
              placeholder="anna-volkova"
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Профессия</span>
            <input
              value={draft.profession}
              onChange={(event) =>
                updateField("profession", event.target.value)
              }
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Компания</span>
            <input
              value={draft.company}
              onChange={(event) => updateField("company", event.target.value)}
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Должность</span>
            <input
              value={draft.position}
              onChange={(event) => updateField("position", event.target.value)}
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Telegram</span>
            <input
              value={draft.telegram}
              onChange={(event) => updateField("telegram", event.target.value)}
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">LinkedIn</span>
            <input
              value={draft.linkedin}
              onChange={(event) => updateField("linkedin", event.target.value)}
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2">
            <span className="font-bold">Сайт</span>
            <input
              value={draft.website}
              onChange={(event) => updateField("website", event.target.value)}
              className={getEditableFieldClassName()}
            />
          </label>

          <label className="grid gap-2 sm:col-span-2">
            <span className="font-bold">Направления</span>
            <input
              value={draft.tags}
              onChange={(event) => updateField("tags", event.target.value)}
              placeholder="Через запятую: дизайн, Python, карьера"
              className={getEditableFieldClassName()}
            />
          </label>
        </div>
      </section>

      {saveError && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {saveError}
        </p>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className={getSecondaryButtonClassName()}
        >
          {isSaving ? "Сохранение…" : saved ? "Сохранено" : "Сохранить"}
        </button>
      </div>

      {isAccountMenuOpen && (
        <AccountSettingsModal
          panel={accountSettingsPanel}
          draft={draft}
          onSelectPanel={setAccountSettingsPanel}
          onBack={() => setAccountSettingsPanel(null)}
          onClose={() => {
            setIsAccountMenuOpen(false);
            setAccountSettingsPanel(null);
          }}
          onSaveName={handleSaveAccountName}
        />
      )}
    </div>
  );
}

function AccountSettingsModal({
  panel,
  draft,
  onSelectPanel,
  onBack,
  onClose,
  onSaveName,
}: {
  panel: AccountSettingsPanel | null;
  draft: ProfileDraft;
  onSelectPanel: Dispatch<SetStateAction<AccountSettingsPanel | null>>;
  onBack: () => void;
  onClose: () => void;
  onSaveName: SaveAccountName;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-border bg-bg p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-black">Настройки аккаунта</h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            className={getSecondaryButtonClassName()}
          >
            Закрыть
          </button>
        </div>

        <div className="mt-6">
          {!panel && (
            <div className="grid gap-2">
              <AccountSettingsOption
                title="Изменить имя и фамилию"
                description="Обновление имени в учетной записи."
                onClick={() => onSelectPanel("name")}
              />
              <AccountSettingsOption
                title="Изменить почту"
                description="Новая почта обычно подтверждается по ссылке."
                onClick={() => onSelectPanel("email")}
              />
              <AccountSettingsOption
                title="Изменить пароль"
                description="Потребуется текущий пароль и новый пароль."
                onClick={() => onSelectPanel("password")}
              />
              <AccountSettingsOption
                title="Сбросить пароль"
                description="Отправка письма со ссылкой для восстановления."
                onClick={() => onSelectPanel("reset-password")}
              />
              <AccountSettingsOption
                title="Удалить аккаунт"
                description="Запрос на удаление учетной записи."
                danger
                onClick={() => onSelectPanel("delete")}
              />
            </div>
          )}

          {panel === "name" && (
            <NameSettingsForm
              draft={draft}
              onBack={onBack}
              onSaveName={onSaveName}
            />
          )}

          {panel === "email" && (
            <EmailSettingsForm draft={draft} onBack={onBack} />
          )}

          {panel === "password" && (
            <AccountSettingsForm
              title="Изменить пароль"
              actionLabel="Подтвердить"
              onBack={onBack}
            >
              <FormField label="Текущий пароль" type="password" />
              <FormField label="Новый пароль" type="password" />
              <FormField label="Повторите новый пароль" type="password" />
            </AccountSettingsForm>
          )}

          {panel === "reset-password" && (
            <AccountSettingsForm
              title="Сбросить пароль"
              actionLabel="Подтвердить"
              onBack={onBack}
            >
              <FormField
                label="Почта для восстановления"
                defaultValue={draft.email}
                readOnly
              />
              <p className="text-xs leading-5 text-muted-foreground">
                Вам будет отправлено письмо со ссылкой для сброса пароля.
              </p>
            </AccountSettingsForm>
          )}

          {panel === "delete" && (
            <AccountSettingsForm
              title="Удалить аккаунт"
              actionLabel="Подтвердить"
              onBack={onBack}
              danger
            >
              <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-3 text-sm leading-6 text-red-800">
                Вам будет отправлено письмо со ссылкой для подтверждения.
              </p>
              <FormField label="Пароль" type="password" />
            </AccountSettingsForm>
          )}
        </div>
      </div>
    </div>
  );
}

function AccountSettingsOption({
  title,
  description,
  danger = false,
  onClick,
}: {
  title: string;
  description: string;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "rounded-xl border px-4 py-3 text-left transition",
        danger
          ? "border-red-200 text-red-800 hover:bg-red-50"
          : "border-border hover:bg-muted",
      ].join(" ")}
    >
      <span className="block text-sm font-bold">{title}</span>
      <span className="mt-1 block text-xs leading-5 text-muted-foreground">
        {description}
      </span>
    </button>
  );
}

function NameSettingsForm({
  draft,
  onBack,
  onSaveName,
}: {
  draft: ProfileDraft;
  onBack: () => void;
  onSaveName: SaveAccountName;
}) {
  const [firstName, setFirstName] = useState(draft.firstName);
  const [lastName, setLastName] = useState(draft.lastName);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);
    setError(null);

    try {
      await onSaveName({ firstName, lastName });
      setMessage("Имя и фамилия сохранены.");
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(
          [
            ...caughtError.generalErrors,
            ...Object.values(caughtError.fieldErrors).flat(),
          ].join(" ") || caughtError.message,
        );
      } else {
        setError("Не удалось сохранить имя и фамилию.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <button
        type="button"
        onClick={onBack}
        className="mb-4 text-sm font-bold text-muted-foreground hover:text-foreground"
      >
        ← Назад
      </button>
      <h4 className="text-lg font-black">Изменить имя и фамилию</h4>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="grid gap-2">
          <span className="text-sm font-bold">Имя</span>
          <input
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            required
            maxLength={30}
            autoComplete="given-name"
            className={getEditableFieldClassName()}
          />
        </label>

        <label className="grid gap-2">
          <span className="text-sm font-bold">Фамилия</span>
          <input
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            required
            maxLength={30}
            autoComplete="family-name"
            className={getEditableFieldClassName()}
          />
        </label>
      </div>

      {message && (
        <p className="mt-4 rounded-xl bg-emerald-100 px-3 py-2 text-sm font-bold text-emerald-800">
          {message}
        </p>
      )}

      {error && (
        <p className="mt-4 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={isSaving || !firstName.trim() || !lastName.trim()}
        className={["mt-5", getSecondaryButtonClassName()].join(" ")}
      >
        {isSaving ? "Сохранение…" : "Сохранить"}
      </button>
    </form>
  );
}

function EmailSettingsForm({
  draft,
  onBack,
}: {
  draft: ProfileDraft;
  onBack: () => void;
}) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextEmail = email.trim().toLowerCase();

    if (!nextEmail) {
      setError("Введите новую почту.");
      setMessage(null);
      return;
    }

    if (!isValidEmail(nextEmail)) {
      setError("Введите корректный адрес электронной почты.");
      setMessage(null);
      return;
    }

    if (nextEmail === draft.email.trim().toLowerCase()) {
      setError("Новая почта совпадает с текущей.");
      setMessage(null);
      return;
    }

    setError(null);
    setMessage(
      "Почта принята. Вам будет отправлено письмо со ссылкой для подтверждения.",
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <button
        type="button"
        onClick={onBack}
        className="mb-4 text-sm font-bold text-muted-foreground hover:text-foreground"
      >
        ← Назад
      </button>
      <h4 className="text-lg font-black">Изменить почту</h4>
      <div className="mt-4 grid gap-4">
        <FormField label="Текущая почта" defaultValue={draft.email} readOnly />
        <label className="grid gap-2">
          <span className="text-sm font-bold">Новая почта</span>
          <input
            type="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setError(null);
              setMessage(null);
            }}
            required
            autoComplete="email"
            className={getEditableFieldClassName()}
          />
        </label>
        <p className="text-xs leading-5 text-muted-foreground">
          Вам будет отправлено письмо со ссылкой для подтверждения.
        </p>
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {message && (
        <p className="mt-4 rounded-xl bg-emerald-100 px-3 py-2 text-sm font-bold text-emerald-800">
          {message}
        </p>
      )}

      <button
        type="submit"
        className={["mt-5", getSecondaryButtonClassName()].join(" ")}
      >
        Подтвердить
      </button>
    </form>
  );
}

function AccountSettingsForm({
  title,
  children,
  actionLabel,
  danger = false,
  onBack,
}: {
  title: string;
  children: ReactNode;
  actionLabel: string;
  danger?: boolean;
  onBack: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-4 text-sm font-bold text-muted-foreground hover:text-foreground"
      >
        ← Назад
      </button>
      <h4 className="text-lg font-black">{title}</h4>
      <div className="mt-4 grid gap-4">{children}</div>
      <button
        type="button"
        className={["mt-5", getSecondaryButtonClassName(danger)].join(" ")}
      >
        {actionLabel}
      </button>
    </div>
  );
}

function FormField({
  label,
  type = "text",
  defaultValue = "",
  readOnly = false,
}: {
  label: string;
  type?: string;
  defaultValue?: string;
  readOnly?: boolean;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-bold">{label}</span>
      <input
        type={type}
        defaultValue={defaultValue}
        readOnly={readOnly}
        className={
          readOnly
            ? getReadOnlyAccountFieldClassName()
            : getEditableFieldClassName()
        }
      />
    </label>
  );
}

function isFilled(value: string | undefined) {
  return typeof value === "string" && value.trim().length > 0;
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function getReadOnlyAccountFieldClassName() {
  return [
    "h-11 cursor-not-allowed rounded-xl border border-slate-300",
    "bg-slate-200/70 px-3 text-slate-500 shadow-inner",
  ].join(" ");
}

function getEditableFieldClassName(multiline = false) {
  return [
    multiline
      ? "min-h-28 rounded-xl border px-3 py-3"
      : "h-11 rounded-xl border px-3",
    "border-slate-200 bg-slate-50 text-foreground",
    "focus:border-foreground/40 focus:outline-none focus:ring-4 focus:ring-foreground/5",
  ].join(" ");
}

function getSecondaryButtonClassName(danger = false) {
  return [
    "rounded-xl border px-4 py-2.5 text-sm font-bold transition disabled:opacity-60",
    danger
      ? "border-red-200 text-red-700 hover:bg-red-50"
      : "border-border text-foreground hover:bg-muted",
  ].join(" ");
}

function getRequiredFieldClassName(value: string, multiline = false) {
  return [
    getEditableFieldClassName(multiline),
    isFilled(value)
      ? "border-emerald-300 focus:border-emerald-500"
      : "border-amber-300 focus:border-amber-500",
  ].join(" ");
}

function RequiredFieldLabel({
  label,
  isFilled,
}: {
  label: string;
  isFilled: boolean;
}) {
  return (
    <span className="flex items-center justify-between gap-3">
      <span className="font-bold">{label}</span>
      <span
        className={[
          "rounded-full px-2 py-0.5 text-[11px] font-bold",
          isFilled
            ? "bg-emerald-100 text-emerald-800"
            : "bg-amber-100 text-amber-800",
        ].join(" ")}
      >
        {isFilled ? "Заполнено" : "Обязательно"}
      </span>
    </span>
  );
}

function createProfileSlug(value: string) {
  const fallback = "my-profile";
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/giu, "-")
    .replace(/^-+|-+$/g, "");

  return slug || fallback;
}
