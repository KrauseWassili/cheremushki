"use client";

import type {
  ApplicationStatus,
} from "@/types/join";
import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

const statusOptions: Array<{
  value: ApplicationStatus;
  label: string;
}> = [
  {
    value: "under_review",
    label: "На рассмотрении",
  },
  {
    value: "needs_changes",
    label: "Нужно исправить",
  },
  {
    value: "approved",
    label: "Одобрено",
  },
  {
    value: "rejected",
    label: "Отклонено",
  },
];

export default function ApplicationStatusPage() {
  const {
    status,
    setStatus,
    adminMessage,
  } = useJoinDemo();

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 5"
        title="Решение по заявке"
        description="На этой демонстрационной странице можно вручную переключать решение администратора."
      />

      <div className="mt-8">
        <p className="text-sm font-bold">
          Выбери состояние для демонстрации
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {statusOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setStatus(option.value)}
              className={`rounded-xl border px-4 py-2 text-sm font-bold transition ${
                status === option.value
                  ? "border-foreground bg-foreground text-background"
                  : "border-border hover:bg-muted"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-7">
        <StatusContent
          status={status}
          adminMessage={adminMessage}
        />
      </div>

      <JoinNavigation
        previousHref={
          status === "needs_changes"
            ? "/join/application"
            : "/join/submitted"
        }
        previousLabel={
          status === "needs_changes"
            ? "Исправить анкету"
            : "Назад"
        }
        nextHref="/join/activate"
        nextLabel="Перейти к активации"
        nextDisabled={status !== "approved"}
      />
    </>
  );
}

function StatusContent({
  status,
  adminMessage,
}: {
  status: ApplicationStatus;
  adminMessage: string;
}) {
  if (status === "needs_changes") {
    return (
      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-6 text-amber-950">
        <p className="text-lg font-black">
          Нужно дополнить заявку
        </p>

        <p className="mt-3 leading-7">
          {adminMessage}
        </p>

        <p className="mt-4 text-sm">
          Нажми «Исправить анкету», чтобы вернуться к
          предзаполненной форме.
        </p>
      </div>
    );
  }

  if (status === "approved") {
    return (
      <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-6 text-emerald-950">
        <p className="text-lg font-black">
          Заявка одобрена
        </p>

        <p className="mt-3 leading-7">
          Добро пожаловать! Теперь можно активировать
          аккаунт и установить пароль.
        </p>
      </div>
    );
  }

  if (status === "rejected") {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-950">
        <p className="text-lg font-black">
          Заявка отклонена
        </p>

        <p className="mt-3 leading-7">
          К сожалению, сейчас мы не можем одобрить
          вступление в клуб.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-blue-200 bg-blue-50 p-6 text-blue-950">
      <p className="text-lg font-black">
        Заявка на рассмотрении
      </p>

      <p className="mt-3 leading-7">
        Администратор уже получил анкету. Когда появится
        решение, мы отправим письмо.
      </p>
    </div>
  );
}