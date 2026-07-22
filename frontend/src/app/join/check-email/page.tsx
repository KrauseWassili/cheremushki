"use client";

import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

export default function CheckEmailPage() {
  const { application } = useJoinDemo();

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 2"
        title="Проверь почту"
        description={`Мы отправили демонстрационное письмо на ${application.email}. В настоящей версии в нём будет одноразовая ссылка для продолжения регистрации.`}
      />

      <div className="mt-8 rounded-2xl border border-border bg-muted/40 p-5">
        <p className="text-sm font-bold">
          Письмо для {application.email}
        </p>

        <div className="mt-4 rounded-xl bg-background p-5 text-sm leading-6 shadow-sm">
          <p className="font-black">
            Подтверди email для вступления в «Черёмушки»
          </p>

          <p className="mt-3">
            Привет! Нажми кнопку ниже, чтобы подтвердить
            адрес и перейти к заполнению анкеты.
          </p>

          <div className="mt-4 inline-flex rounded-xl bg-foreground px-4 py-2 font-bold text-background">
            Подтвердить email
          </div>
        </div>
      </div>

      <p className="mt-5 text-sm text-muted-foreground">
        Для демонстрации просто нажми «Открыть анкету».
      </p>

      <JoinNavigation
        previousHref="/join"
        nextHref="/join/application"
        nextLabel="Открыть анкету"
      />
    </>
  );
}