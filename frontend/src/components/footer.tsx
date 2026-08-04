import Link from "next/link";

export default function Footer() {
  return (
    <footer
      className="fixed bottom-0 left-0 w-full py-3"
      style={{
        backgroundColor: "var(--color-header-bg)",
        color: "var(--color-header-link-hover)",
      }}
    >
      <div className="mx-auto flex flex-col flex-wrap items-center justify-center gap-x-8 gap-y-2 px-4 text-center min-[900px]:flex-row">
        <span>
          Cheremushki © 2026. Все права защищены.
        </span>
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
          <Link
            href="/rules"
            className="!text-header-link no-underline hover:!text-header-link-hover"
          >
            Правила
          </Link>
          <Link
            href="/privacy"
            className="!text-header-link no-underline hover:!text-header-link-hover"
          >
            Конфиденциальность
          </Link>
          <Link
            href="/legal"
            className="!text-header-link no-underline hover:!text-header-link-hover"
          >
            Правовая информация
          </Link>
        </div>
      </div>
    </footer>
  );
}
