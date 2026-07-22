"use client";

import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

export default function SubmittedPage() {
  const { application } = useJoinDemo();

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 4"
        title="Заявка отправлена"
        description="Мы получили анкету и постараемся рассмотреть её в ближайшее время."
      />

      <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-950">
        <p className="font-black">
          Письмо отправлено на {application.email}
        </p>

        <p className="mt-2 text-sm leading-6">
          Мы напишем на этот адрес, когда примем решение
          или если понадобится что-то уточнить.
        </p>
      </div>

      <div className="mt-6 rounded-2xl border border-border p-5">
        <p className="text-sm font-bold">
          Что происходит дальше
        </p>

        <ol className="mt-4 grid gap-3 text-sm text-muted-foreground">
          <li>1. Администратор открывает заявку.</li>
          <li>2. Проверяет заполненные данные.</li>
          <li>
            3. Принимает решение или просит внести
            изменения.
          </li>
          <li>4. Результат приходит по email.</li>
        </ol>
      </div>

      <JoinNavigation
        previousHref="/join/application"
        nextHref="/join/status"
        nextLabel="Посмотреть решение"
      />
    </>
  );
}