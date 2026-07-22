"use client";

import type {
  JoinApplication,
} from "@/types/join";
import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

const inputClassName =
  "h-12 w-full rounded-xl border border-border bg-background px-4 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5";

const textareaClassName =
  "min-h-32 w-full resize-y rounded-xl border border-border bg-background px-4 py-3 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5";

export default function ApplicationPage() {
  const {
    application,
    status,
    adminMessage,
    updateApplication,
  } = useJoinDemo();

  function updateField<K extends keyof JoinApplication>(
    field: K,
    value: JoinApplication[K],
  ) {
    updateApplication({
      [field]: value,
    });
  }

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 3"
        title={
          status === "needs_changes"
            ? "Дополнение заявки"
            : "Расскажи о себе"
        }
        description="Эта информация поможет нам познакомиться с тобой и понять, чем клуб может быть полезен."
      />

      {status === "needs_changes" && (
        <div className="mt-7 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
          <p className="font-black">
            Администратор попросил дополнить заявку
          </p>

          <p className="mt-2 leading-6">
            {adminMessage}
          </p>
        </div>
      )}

      <form className="mt-8 grid gap-10">
        <FormSection
          title="Основная информация"
          description="Имя, город и профессиональная деятельность."
        >
          <Field label="Имя и фамилия">
            <input
              value={application.fullName}
              onChange={(event) =>
                updateField(
                  "fullName",
                  event.target.value,
                )
              }
              className={inputClassName}
            />
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Город">
              <input
                value={application.city}
                onChange={(event) =>
                  updateField("city", event.target.value)
                }
                className={inputClassName}
              />
            </Field>

            <Field label="Профессиональное направление">
              <input
                value={application.profession}
                onChange={(event) =>
                  updateField(
                    "profession",
                    event.target.value,
                  )
                }
                className={inputClassName}
              />
            </Field>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Должность или занятие">
              <input
                value={application.position}
                onChange={(event) =>
                  updateField(
                    "position",
                    event.target.value,
                  )
                }
                className={inputClassName}
              />
            </Field>

            <Field
              label="Компания"
              hint="Необязательно"
            >
              <input
                value={application.company}
                onChange={(event) =>
                  updateField(
                    "company",
                    event.target.value,
                  )
                }
                className={inputClassName}
              />
            </Field>
          </div>
        </FormSection>

        <FormSection
          title="О тебе"
          description="Несколько предложений для будущего профиля."
        >
          <Field label="Кратко расскажи о себе">
            <textarea
              value={application.bio}
              onChange={(event) =>
                updateField("bio", event.target.value)
              }
              className={textareaClassName}
            />
          </Field>

          <Field label="Почему ты хочешь вступить?">
            <textarea
              value={application.motivation}
              onChange={(event) =>
                updateField(
                  "motivation",
                  event.target.value,
                )
              }
              className={textareaClassName}
            />
          </Field>

          <Field label="Чем ты можешь помочь другим участникам?">
            <textarea
              value={application.contribution}
              onChange={(event) =>
                updateField(
                  "contribution",
                  event.target.value,
                )
              }
              className={textareaClassName}
            />
          </Field>

          <Field label="Что тебе сейчас интересно или нужно?">
            <textarea
              value={application.lookingFor}
              onChange={(event) =>
                updateField(
                  "lookingFor",
                  event.target.value,
                )
              }
              className={textareaClassName}
            />
          </Field>
        </FormSection>

        <FormSection
          title="Ссылки и контакты"
          description="Все поля в этом разделе необязательные."
        >
          <Field label="LinkedIn">
            <input
              type="url"
              value={application.linkedinUrl}
              onChange={(event) =>
                updateField(
                  "linkedinUrl",
                  event.target.value,
                )
              }
              className={inputClassName}
            />
          </Field>

          <Field label="Личный сайт">
            <input
              type="url"
              value={application.websiteUrl}
              onChange={(event) =>
                updateField(
                  "websiteUrl",
                  event.target.value,
                )
              }
              className={inputClassName}
            />
          </Field>

          <Field label="Telegram username">
            <input
              value={application.telegramUsername}
              onChange={(event) =>
                updateField(
                  "telegramUsername",
                  event.target.value.replace(/^@/, ""),
                )
              }
              className={inputClassName}
            />
          </Field>

          <Field label="Кто рассказал о клубе?">
            <input
              value={application.referredBy}
              onChange={(event) =>
                updateField(
                  "referredBy",
                  event.target.value,
                )
              }
              className={inputClassName}
            />
          </Field>
        </FormSection>

        <FormSection
          title="Правила и данные"
          description="В рабочей версии согласия будут обязательными."
        >
          <CheckboxField
            checked={application.rulesAccepted}
            onChange={(checked) =>
              updateField("rulesAccepted", checked)
            }
          >
            Я ознакомился с правилами клуба
          </CheckboxField>

          <CheckboxField
            checked={application.privacyAccepted}
            onChange={(checked) =>
              updateField("privacyAccepted", checked)
            }
          >
            Я ознакомился с политикой конфиденциальности
          </CheckboxField>
        </FormSection>
      </form>

      <JoinNavigation
        previousHref="/join/check-email"
        nextHref="/join/submitted"
        nextLabel={
          status === "needs_changes"
            ? "Отправить повторно"
            : "Отправить заявку"
        }
        nextDisabled={
          !application.fullName ||
          !application.city ||
          !application.motivation ||
          !application.rulesAccepted ||
          !application.privacyAccepted
        }
      />
    </>
  );
}

type FormSectionProps = {
  title: string;
  description: string;
  children: React.ReactNode;
};

function FormSection({
  title,
  description,
  children,
}: FormSectionProps) {
  return (
    <section>
      <div className="mb-5 border-b border-border pb-4">
        <h2 className="text-xl font-black">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {description}
        </p>
      </div>

      <div className="grid gap-5">{children}</div>
    </section>
  );
}

type FieldProps = {
  label: string;
  hint?: string;
  children: React.ReactNode;
};

function Field({
  label,
  hint,
  children,
}: FieldProps) {
  return (
    <label className="grid gap-2">
      <span className="font-bold">{label}</span>
      {children}

      {hint && (
        <span className="text-xs text-muted-foreground">
          {hint}
        </span>
      )}
    </label>
  );
}

type CheckboxFieldProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: React.ReactNode;
};

function CheckboxField({
  checked,
  onChange,
  children,
}: CheckboxFieldProps) {
  return (
    <label className="flex items-start gap-3 rounded-2xl border border-border p-4">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) =>
          onChange(event.target.checked)
        }
        className="mt-1 size-4"
      />

      <span className="text-sm leading-6">
        {children}
      </span>
    </label>
  );
}