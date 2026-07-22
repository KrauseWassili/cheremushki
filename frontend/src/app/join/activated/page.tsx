"use client";

import Link from "next/link";
import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

export default function ActivatedPage() {
  const { application, resetDemo } =
    useJoinDemo();

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 7"
        title={`Добро пожаловать, ${application.fullName.split(" ")[0]}!`}
        description="Аккаунт создан. Теперь можно заполнить профиль и вступить в закрытую Telegram-группу."
      />

      <div className="mt-8 grid gap-4">
        <a
          href="https://t.me/+demo-invite-link"
          target="_blank"
          rel="noreferrer"
          className="rounded-2xl bg-[#229ED9] p-5 text-white transition hover:opacity-90"
        >
          <p className="font-black">
            Вступить в Telegram-группу
          </p>

          <p className="mt-1 text-sm text-white/80">
            В рабочей версии здесь будет персональная
            пригласительная ссылка.
          </p>
        </a>

        <Link
          href="/members/anna-volkova"
          className="rounded-2xl border border-border p-5 transition hover:bg-muted"
        >
          <p className="font-black">
            Открыть личный профиль
          </p>

          <p className="mt-1 text-sm text-muted-foreground">
            Добавить аватар, проверить данные и настроить
            видимость контактов.
          </p>
        </Link>
      </div>

      <div className="mt-8 rounded-2xl border border-border bg-muted/40 p-5 text-sm leading-6">
        На адрес <strong>{application.email}</strong> также
        будет отправлено приветственное письмо со ссылками
        на личный кабинет и Telegram.
      </div>

      <JoinNavigation
        previousHref="/join/activate"
        previousLabel="Назад"
      />

      <button
        type="button"
        onClick={resetDemo}
        className="mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-bold text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        Сбросить демонстрационные данные
      </button>
    </>
  );
}