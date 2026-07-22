"use client";

import { usePathname } from "next/navigation";

const steps = [
  {
    href: "/join",
    label: "Email",
  },
  {
    href: "/join/check-email",
    label: "Подтверждение",
  },
  {
    href: "/join/application",
    label: "Анкета",
  },
  {
    href: "/join/submitted",
    label: "Отправлено",
  },
  {
    href: "/join/status",
    label: "Решение",
  },
  {
    href: "/join/activate",
    label: "Пароль",
  },
  {
    href: "/join/activated",
    label: "Готово",
  },
];

export function JoinStepper() {
  const pathname = usePathname();

  const currentIndex = Math.max(
    steps.findIndex((step) => step.href === pathname),
    0,
  );

  return (
    <div className="mb-8">
      <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Этап {currentIndex + 1} из {steps.length}
        </span>

        <span>{steps[currentIndex]?.label}</span>
      </div>

      <div className="flex gap-1.5">
        {steps.map((step, index) => (
          <div
            key={step.href}
            className={`h-1.5 flex-1 rounded-full transition ${
              index <= currentIndex
                ? "bg-foreground"
                : "bg-muted"
            }`}
          />
        ))}
      </div>
    </div>
  );
}