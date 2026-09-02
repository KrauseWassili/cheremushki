"use client";

import {
  type Dispatch,
  type FormEvent,
  type SetStateAction,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useApp } from "@/providers/AppProvider";
import { AvatarUpload } from "@/components/members/avatar-upload";
import { TagPicker } from "@/components/members/tag-picker";
import { CustomSelect } from "@/components/ui/custom-select";
import { buttonClassName } from "@/components/ui/button";
import { fieldClassName } from "@/components/ui/text-field";
import { ModalFrame } from "@/components/ui/modal";
import { ApiError } from "@/lib/api";
import { notifyProfileUpdated } from "@/lib/profile-events";
import { useEscapeKey } from "@/lib/use-escape-key";
import {
  changePassword,
  deleteAccount,
  requestEmailChange,
} from "@/lib/auth";
import { getProfileCompletionStatus } from "@/lib/profile";
import {
  dataUrlToBlob,
  fetchMyProfile,
  mapApiProfileToDraft,
  saveMyProfile,
  uploadMyAvatar,
} from "@/lib/profiles";
import type { ProfileDraft } from "@/types/profile";

type AccountSettingsPanel =
  | "name"
  | "email"
  | "password"
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
  const { user, isLoggedIn, logout, updateCurrentUser } = useApp();
  const [draft, setDraft] = useState<ProfileDraft>(initialDraft);
  const [saved, setSaved] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isAvatarDirty, setIsAvatarDirty] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  // Pflichtfeldliste und Einladungsstand kommen aus dem Backend – die Regel
  // wird hier nicht nachgebildet, nur angezeigt (siehe lib/profile.ts).
  const [requiredFields, setRequiredFields] = useState<string[] | undefined>();
  const [inviteSent, setInviteSent] = useState(false);
  const [accountSettingsPanel, setAccountSettingsPanel] =
    useState<AccountSettingsPanel | null>(null);

  useEffect(() => {
    if (!user) return;
    const currentUser = user;

    let cancelled = false;

    async function loadProfile() {
      try {
        const api = await fetchMyProfile();
        if (cancelled) return;
        applyServerState(api);
        setDraft(
          mapApiProfileToDraft(api, {
            firstName: currentUser.first_name,
            lastName: currentUser.last_name,
            email: currentUser.email,
          }),
        );
      } catch {
        if (cancelled) return;
        setDraft((current) => ({
          ...current,
          firstName: currentUser.first_name,
          lastName: currentUser.last_name,
          email: currentUser.email,
        }));
      }
    }

    void loadProfile();
    return () => {
      cancelled = true;
    };
  }, [user]);

  /**
   * Übernimmt die serverseitigen Statusfelder aus einer Profil-Antwort.
   *
   * Jeder Pfad, der das Profil ändert, muss das aufrufen – Laden, Speichern
   * und Avatar-Upload. Sonst bleibt der Einladungsstand stehen und die Seite
   * fordert zum Ausfüllen auf, obwohl die Einladung längst versandt ist.
   */
  function applyServerState(api: {
    required_fields?: string[];
    invite_sent?: boolean;
  }) {
    setRequiredFields(api.required_fields);
    setInviteSent(Boolean(api.invite_sent));
  }

  const requiredStatus = useMemo(
    () => getProfileCompletionStatus(draft, requiredFields),
    [draft, requiredFields],
  );

  useEscapeKey(isAccountMenuOpen, () => {
    setIsAccountMenuOpen(false);
    setAccountSettingsPanel(null);
  });

  function updateField<K extends keyof ProfileDraft>(
    field: K,
    value: ProfileDraft[K],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setSaved(false);
    setSaveSuccess(null);
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
    setDraft((current) => ({
      ...current,
      avatarUrl: crop.avatarUrl ?? current.avatarUrl,
      avatarOriginalUrl: crop.sourceUrl ?? current.avatarOriginalUrl,
      avatarPositionX: crop.x,
      avatarPositionY: crop.y,
      avatarScale: crop.scale,
      avatarCropSize: crop.size,
    }));
    setSaved(false);
    setIsAvatarDirty(true);
    setSaveError(null);
    setSaveSuccess(null);
  }
  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(null);

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

    try {
      let avatarUpload: {
        avatarBlob: Blob;
        originalBlob: Blob | null;
        isRemote: boolean;
      } | null = null;

      if (isAvatarDirty && isDataUrl(nextDraft.avatarUrl)) {
        const avatarBlob = await dataUrlToBlob(nextDraft.avatarUrl);
        const originalBlob = isDataUrl(nextDraft.avatarOriginalUrl)
          ? await dataUrlToBlob(nextDraft.avatarOriginalUrl)
          : null;
        avatarUpload = { avatarBlob, originalBlob, isRemote: false };
      } else if (isAvatarDirty && nextDraft.avatarUrl) {
        try {
          avatarUpload = {
            ...(await createRemoteAvatarUpload(nextDraft)),
            isRemote: true,
          };
        } catch {
          avatarUpload = null;
        }
      }

      if (avatarUpload) {
        try {
          await uploadMyAvatar(
            avatarUpload.avatarBlob,
            {
              x: nextDraft.avatarPositionX,
              y: nextDraft.avatarPositionY,
              scale: nextDraft.avatarScale,
              size: nextDraft.avatarCropSize,
            },
            avatarUpload.originalBlob,
          );
        } catch (error) {
          if (!avatarUpload.isRemote) {
            throw error;
          }
        }
      }
      const api = await saveMyProfile(nextDraft);
      applyServerState(api);
      setDraft(
        mapApiProfileToDraft(api, {
          firstName: nextDraft.firstName || user?.first_name,
          lastName: nextDraft.lastName || user?.last_name,
          email: nextDraft.email || user?.email,
        }),
      );
      setSaved(true);
      setIsAvatarDirty(false);
      notifyProfileUpdated();
      setSaveSuccess(
        api.is_directory_visible
          ? "Профиль сохранён и виден в каталоге участников."
          : "Профиль сохранён. Заполните все обязательные поля и загрузите аватар, чтобы ваш профиль появился в каталоге.",
      );
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : "Не удалось сохранить профиль.",
      );
      setSaved(false);
      setSaveSuccess(null);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveAccountName({
    firstName,
    lastName,
  }: AccountNameValues) {
    const updatedUser = await updateCurrentUser({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
    });

    setDraft((current) => ({
      ...current,
      firstName: updatedUser.first_name,
      lastName: updatedUser.last_name,
    }));
  }

  async function handleDeleteAccount(password: string) {
    await deleteAccount(password);
    await logout();
  }

  if (!isLoggedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="mb-4 text-2xl font-semibold text-foreground">
            Вы не вошли в систему :(
          </p>
          <Link href="/" className={buttonClassName()}>
            На главную
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-6">
      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm">
        <div>
          <h1 className="text-3xl font-bold">Профиль</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Заполните основные поля, чтобы профиль появился в каталоге
            участников.
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            После внесения изменений нажмите «Сохранить» внизу страницы.
          </p>
        </div>
      </section>

      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold">Данные аккаунта</h2>
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

        <div className="grid gap-5 min-[900px]:grid-cols-2">
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

      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold">Основные данные</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Эти поля нужны для минимального профиля.
            </p>
            <p className="mt-2 text-sm font-bold text-foreground">
              Заполнено {requiredStatus.filledCount} из{" "}
              {requiredStatus.totalCount} обязательных полей
            </p>

            {inviteSent ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Приглашение в Telegram-группу уже отправлено на твою почту.
              </p>
            ) : requiredStatus.isComplete ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Сохрани профиль — и придёт приглашение в Telegram-группу.
              </p>
            ) : (
              <p className="mt-2 text-xs text-muted-foreground">
                Осталось заполнить: {requiredStatus.missingLabels.join(", ")}.
                После этого придёт приглашение в Telegram-группу.
              </p>
            )}
          </div>
        </div>

        <div className="grid gap-5 min-[900px]:grid-cols-2">
          <div className="min-[900px]:col-span-2">
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
              label="Заголовок"
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

      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm">
        <h2 className="text-xl font-bold">Дополнительно</h2>
        <div className="mt-5 grid gap-5 min-[900px]:grid-cols-2">
          <label className="grid gap-2 min-[900px]:col-span-2">
            <span className="font-bold">Как с вами связываться</span>
            <CustomSelect
              value={draft.contactMode}
              onChange={(value) =>
                updateField(
                  "contactMode",
                  value as ProfileDraft["contactMode"],
                )
              }
              options={[
                {
                  value: "direct",
                  label: "Показывать прямые контакты",
                },
                {
                  value: "request",
                  label: "Показывать кнопку запроса",
                },
                {
                  value: "group",
                  label: "Предлагать общение в Telegram-группе",
                },
                {
                  value: "closed",
                  label: "Обращения закрыты",
                },
              ]}
            />
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

          <div className="min-[900px]:col-span-2">
            <TagPicker
              value={draft.tags}
              onChange={(tags) => updateField("tags", tags)}
            />
          </div>
        </div>
      </section>

      {saveError && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {saveError}
        </p>
      )}

      {saveSuccess && (
        <p className="rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium text-foreground">
          {saveSuccess}
        </p>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => {
            void handleSave();
          }}
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
          onDeleteAccount={handleDeleteAccount}
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
  onDeleteAccount,
}: {
  panel: AccountSettingsPanel | null;
  draft: ProfileDraft;
  onSelectPanel: Dispatch<SetStateAction<AccountSettingsPanel | null>>;
  onBack: () => void;
  onClose: () => void;
  onSaveName: SaveAccountName;
  onDeleteAccount: (password: string) => Promise<void>;
}) {
  return (
    <ModalFrame label="Настройки аккаунта" className="max-w-lg">
      <div
        aria-label="Настройки аккаунта"
        className="contents"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold">Настройки аккаунта</h3>
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
            <PasswordSettingsForm onBack={onBack} />
          )}

          {panel === "delete" && (
            <DeleteAccountSettingsForm
              onBack={onBack}
              onDeleteAccount={onDeleteAccount}
            />
          )}
        </div>
      </div>
    </ModalFrame>
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
          ? "border-destructive/30 text-destructive hover:bg-danger-soft"
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
      <h4 className="text-lg font-bold">Изменить имя и фамилию</h4>
      <div className="mt-4 grid gap-4 min-[900px]:grid-cols-2">
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
        <p className="mt-4 rounded-xl bg-success-soft px-3 py-2 text-sm font-bold text-success">
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
  const [currentPassword, setCurrentPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextEmail = email.trim().toLowerCase();
    const password = currentPassword.trim();

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

    if (!password) {
      setError("Введите текущий пароль.");
      setMessage(null);
      return;
    }

    setIsSaving(true);
    setError(null);
    setMessage(null);

    try {
      const result = await requestEmailChange(nextEmail, password);
      setEmail("");
      setCurrentPassword("");
      setMessage(result.detail);
    } catch (caughtError) {
      setError(
        getApiErrorMessage(
          caughtError,
          "Не удалось отправить письмо для подтверждения почты.",
        ),
      );
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
      <h4 className="text-lg font-bold">Изменить почту</h4>
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
        <label className="grid gap-2">
          <span className="text-sm font-bold">Текущий пароль</span>
          <input
            type="password"
            value={currentPassword}
            onChange={(event) => {
              setCurrentPassword(event.target.value);
              setError(null);
              setMessage(null);
            }}
            required
            autoComplete="current-password"
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
        <p className="mt-4 rounded-xl bg-success-soft px-3 py-2 text-sm font-bold text-success">
          {message}
        </p>
      )}

      <button
        type="submit"
        disabled={isSaving || !email.trim() || !currentPassword.trim()}
        className={["mt-5", getSecondaryButtonClassName()].join(" ")}
      >
        {isSaving ? "Отправка..." : "Подтвердить"}
      </button>
    </form>
  );
}

function PasswordSettingsForm({ onBack }: { onBack: () => void }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);
    setError(null);

    try {
      await changePassword(currentPassword, newPassword, newPasswordConfirm);
      setCurrentPassword("");
      setNewPassword("");
      setNewPasswordConfirm("");
      setMessage("Пароль изменён.");
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, "Не удалось изменить пароль."));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <AccountSettingsBackButton onBack={onBack} />
      <h4 className="text-lg font-bold">Изменить пароль</h4>
      <div className="mt-4 grid gap-4">
        <label className="grid gap-2">
          <span className="text-sm font-bold">Текущий пароль</span>
          <input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            autoComplete="current-password"
            className={getEditableFieldClassName()}
          />
        </label>

        <label className="grid gap-2">
          <span className="text-sm font-bold">Новый пароль</span>
          <input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className={getEditableFieldClassName()}
          />
        </label>

        <label className="grid gap-2">
          <span className="text-sm font-bold">Повторите новый пароль</span>
          <input
            type="password"
            value={newPasswordConfirm}
            onChange={(event) => setNewPasswordConfirm(event.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className={getEditableFieldClassName()}
          />
        </label>
      </div>

      <AccountSettingsFeedback message={message} error={error} />

      <button
        type="submit"
        disabled={
          isSaving ||
          !currentPassword ||
          !newPassword ||
          !newPasswordConfirm
        }
        className={["mt-5", getSecondaryButtonClassName()].join(" ")}
      >
        {isSaving ? "Сохранение…" : "Подтвердить"}
      </button>
    </form>
  );
}

function DeleteAccountSettingsForm({
  onBack,
  onDeleteAccount,
}: {
  onBack: () => void;
  onDeleteAccount: (password: string) => Promise<void>;
}) {
  const [password, setPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);

    try {
      await onDeleteAccount(password);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, "Не удалось удалить аккаунт."));
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <AccountSettingsBackButton onBack={onBack} />
      <h4 className="text-lg font-bold">Удалить аккаунт</h4>
      <div className="mt-4 grid gap-4">
        <p className="rounded-xl border border-destructive/30 bg-danger-soft px-3 py-3 text-sm leading-6 text-destructive">
          После подтверждения аккаунт будет деактивирован, а профиль скрыт из каталога.
        </p>

        <label className="grid gap-2">
          <span className="text-sm font-bold">Пароль</span>
          <input
            type="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              setError(null);
            }}
            required
            autoComplete="current-password"
            className={getEditableFieldClassName()}
          />
        </label>
      </div>

      <AccountSettingsFeedback message={null} error={error} />

      <button
        type="submit"
        disabled={isSaving || !password}
        className={["mt-5", getSecondaryButtonClassName(true)].join(" ")}
      >
        {isSaving ? "Удаление…" : "Подтвердить"}
      </button>
    </form>
  );
}

function AccountSettingsBackButton({ onBack }: { onBack: () => void }) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="mb-4 text-sm font-bold text-muted-foreground hover:text-foreground"
    >
      ← Назад
    </button>
  );
}

function AccountSettingsFeedback({
  message,
  error,
}: {
  message: string | null;
  error: string | null;
}) {
  return (
    <>
      {error && (
        <p className="mt-4 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {message && (
        <p className="mt-4 rounded-xl bg-success-soft px-3 py-2 text-sm font-bold text-success">
          {message}
        </p>
      )}
    </>
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

function isDataUrl(value: string | undefined): value is string {
  return Boolean(value?.startsWith("data:"));
}

async function createRemoteAvatarUpload(draft: ProfileDraft) {
  const sourceUrl = draft.avatarOriginalUrl || draft.avatarUrl;
  if (!sourceUrl) {
    throw new Error("Avatar source is missing");
  }

  const originalBlob = await fetchImageBlob(sourceUrl);
  const objectUrl = URL.createObjectURL(originalBlob);

  try {
    const avatarBlob = await createCroppedAvatarBlob(objectUrl, {
      x: draft.avatarPositionX,
      y: draft.avatarPositionY,
      size: draft.avatarCropSize,
    });
    return { avatarBlob, originalBlob };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function fetchImageBlob(source: string) {
  const response = await fetch(
    `/api/avatar-source?src=${encodeURIComponent(source)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error("Avatar source is not available");
  }
  return response.blob();
}

async function createCroppedAvatarBlob(
  source: string,
  crop: { x: number; y: number; size: number },
) {
  const image = await loadImage(source);
  const minSide = Math.min(image.naturalWidth, image.naturalHeight);
  const cropPixelSize = (crop.size / 100) * minSide;
  const sourceX = clamp(
    (crop.x / 100) * image.naturalWidth - cropPixelSize / 2,
    0,
    image.naturalWidth - cropPixelSize,
  );
  const sourceY = clamp(
    (crop.y / 100) * image.naturalHeight - cropPixelSize / 2,
    0,
    image.naturalHeight - cropPixelSize,
  );

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;

  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas is not available");
  }

  context.drawImage(
    image,
    sourceX,
    sourceY,
    cropPixelSize,
    cropPixelSize,
    0,
    0,
    canvas.width,
    canvas.height,
  );

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
          return;
        }
        reject(new Error("Avatar crop is not available"));
      },
      "image/jpeg",
      0.92,
    );
  });
}

function loadImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = source;
  });
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function getApiErrorMessage(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) return fallback;

  return (
    [
      ...error.generalErrors,
      ...Object.values(error.fieldErrors).flat(),
    ].join(" ") || error.message
  );
}

function getReadOnlyAccountFieldClassName() {
  return [
    "h-11 cursor-not-allowed rounded-xl border border-border",
    "bg-surface-muted/80 px-3 text-body shadow-inner",
  ].join(" ");
}

function getEditableFieldClassName(multiline = false) {
  return fieldClassName({ multiline });
}

function getSecondaryButtonClassName(danger = false) {
  return buttonClassName({ variant: danger ? "danger" : "secondary" });
}

function getRequiredFieldClassName(value: string, multiline = false) {
  return [
    getEditableFieldClassName(multiline),
    isFilled(value)
      ? "border-success focus:border-success"
      : "border-warning focus:border-warning",
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
            ? "bg-success-soft text-success"
            : "bg-warning-soft text-warning",
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
