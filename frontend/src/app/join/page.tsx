"use client";

import { useJoinDemo } from "@/components/join/join-demo-provider";
import { JoinNavigation } from "@/components/join/join-navigation";
import { JoinPageHeader } from "@/components/join/join-page-header";

export default function JoinPage() {
  const { application, updateApplication } =
    useJoinDemo();

  return (
    <>
      <JoinPageHeader
        eyebrow="Шаг 1"
        title="Начнём с email"
        description="Мы отправим ссылку, по которой можно подтвердить адрес и перейти к заполнению анкеты."
      />

      <div className="mt-8">
        <label className="grid gap-2">
          <span className="font-bold">Email</span>

          <input
            type="email"
            value={application.email}
            onChange={(event) =>
              updateApplication({
                email: event.target.value,
              })
            }
            placeholder="name@example.de"
            className="h-12 rounded-xl border border-border bg-background px-4 outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5"
          />
        </label>

        <p className="mt-3 text-sm text-muted-foreground">
          Адрес не будет отображаться в публичном профиле.
        </p>
      </div>

      <JoinNavigation
        previousHref="/"
        nextHref="/join/check-email"
        previousLabel="На главную"
        nextLabel="Отправить ссылку"
        nextDisabled={!application.email.includes("@")}
      />
    </>
  );
}