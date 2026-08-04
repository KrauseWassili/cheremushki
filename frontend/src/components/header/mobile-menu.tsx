import Link from "next/link";
import { LogIn, LogOut } from "lucide-react";
import { AccountSummary } from "./account-summary";
import type { HeaderNavItem } from "./types";

type MobileMenuProps = {
  avatarUrl?: string;
  name: string;
  initials: string;
  email?: string;
  isLoggedIn: boolean;
  isProfileReady: boolean;
  navItems: HeaderNavItem[];
  onLogin: () => void;
  onRegister: () => void;
  onLogout: () => void;
  getMenuLinkClassName: (href: string) => string;
};

export function MobileMenu({
  avatarUrl,
  name,
  initials,
  email,
  isLoggedIn,
  isProfileReady,
  navItems,
  onLogin,
  onRegister,
  onLogout,
  getMenuLinkClassName,
}: MobileMenuProps) {
  return (
    <div className="absolute right-4 top-full mt-3 w-max min-w-56 max-w-[calc(100vw-2rem)] rounded-2xl border border-header-link/20 bg-header-bg p-3 shadow-2xl min-[900px]:hidden">
      <div className="grid gap-1">
        {isLoggedIn && (
          <>
            <AccountSummary
              avatarUrl={avatarUrl}
              name={name}
              initials={initials}
              email={email}
            />
            <div className="my-2 h-px bg-header-link/20" />
          </>
        )}

        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={getMenuLinkClassName(item.href)}
          >
            {item.label}
          </Link>
        ))}

        <div className="my-2 h-px bg-header-link/20" />

        {isLoggedIn ? (
          <>
            <Link href="/profile" className={getMenuLinkClassName("/profile")}>
              Профиль
            </Link>
            <button
              type="button"
              onClick={onLogout}
              className="button-flat inline-flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-base !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
            >
              <span>Выйти</span>
              <LogOut size={16} />
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={onLogin}
              className="button-flat inline-flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-base !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
            >
              <span>Войти</span>
              <LogIn size={16} />
            </button>
            <button
              type="button"
              onClick={onRegister}
              className="button-flat cursor-pointer rounded-xl px-3 py-2 text-left text-base !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
            >
              Зарегистрироваться
            </button>
          </>
        )}
      </div>
    </div>
  );
}
