import Link from "next/link";

export default function Footer() {
  return (
    <footer className="fixed left-0 bottom-0 w-full bg-dark text-lightest py-3">
      <div className="mx-auto flex justify-center px-4 gap-8">
        <span className="opacity-80">
          Cheremushki © 2026. Все права защищены.
        </span>
        <div className="flex items-center gap-4">
          <Link href="/rules">Правила</Link>
          <Link href="/privacy">Конфиденциальность</Link>
          <Link href="/legal">Правовая информация</Link>
        </div>
      </div>
    </footer>
  );
}
