import type { ReactNode } from "react";

type ModalFrameProps = {
  label: string;
  children: ReactNode;
  className?: string;
};

export function ModalFrame({
  label,
  children,
  className,
}: ModalFrameProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className={[
          "w-full rounded-2xl border border-border bg-bg p-6 shadow-2xl",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {children}
      </div>
    </div>
  );
}
