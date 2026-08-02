"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useApp } from "@/providers/AppProvider";
import { isProfileReadyForDirectory } from "@/lib/profile";
import { fetchMyProfile, mapApiProfileToDraft } from "@/lib/profiles";
import { LogIn, LogOut, Menu, X } from "lucide-react";

export default function Header() {
  const pathname = usePathname();
  const { isLoggedIn, logout, openLogin } = useApp();
  const [isProfileReady, setIsProfileReady] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoggedIn) {
      setIsProfileReady(false);
      return;
    }

    let cancelled = false;

    async function loadStatus() {
      try {
        const api = await fetchMyProfile();
        const draft = mapApiProfileToDraft(api);
        if (!cancelled) {
          setIsProfileReady(isProfileReadyForDirectory(draft));
        }
      } catch {
        if (!cancelled) setIsProfileReady(false);
      }
    }

    loadStatus();
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn, pathname]);

  useEffect(() => {
    setIsMenuOpen(false);
  }, [pathname, isLoggedIn]);

  const navItems = [
    { href: "/", label: "Приветствие" },
    { href: "/project", label: "О проекте" },
    ...(isLoggedIn ? [{ href: "/members", label: "Участники" }] : []),
  ];

  const getLinkClassName = (href: string) => {
    const isActive = pathname === href;

    return [
      "inline-flex h-9 cursor-pointer items-center whitespace-nowrap rounded-md px-3 text-sm font-medium no-underline transition-colors",
      isActive
        ? "bg-header-active-bg !text-header-active-text"
        : "!text-header-link hover:bg-header-hover-bg hover:!text-header-link-hover",
    ].join(" ");
  };

  const getMobileLinkClassName = (href: string) => {
    const isActive = pathname === href;

    return [
      "block rounded-xl px-3 py-2 text-sm font-bold no-underline transition-colors",
      isActive
        ? "bg-header-active-bg !text-header-active-text"
        : "!text-header-link hover:bg-header-hover-bg hover:!text-header-link-hover",
    ].join(" ");
  };

  return (
    <header className="fixed left-0 top-0 z-40 h-14 w-full bg-header-bg text-header-link-hover">
      <nav className="relative mx-auto h-full w-full px-4">
        <div className="grid h-full grid-cols-[1fr_auto] items-center gap-4 min-[900px]:grid-cols-[auto_minmax(0,1fr)_auto]">
          <div className="flex items-center justify-start">
            <Link
              href="/"
              aria-label="Черемушки"
              className="inline-flex items-center no-underline"
            >
              <img
                src="/brand-mark-transparent.webp"
                alt=""
                className="size-12 object-contain drop-shadow-[0_3px_3px_color-mix(in_srgb,var(--palette-ink)_90%,transparent)]"
              />
            </Link>
          </div>

          <div className="hidden min-w-0 items-center justify-center gap-2 min-[900px]:flex">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={getLinkClassName(item.href)}
              >
                {item.label}
              </Link>
            ))}
          </div>

          <div className="hidden items-center justify-end gap-2 min-[900px]:flex">
            {isLoggedIn ? (
              <>
                <Link href="/profile" className={getLinkClassName("/profile")}>
                  <span className="flex items-center gap-2">
                    <span>Профиль</span>
                    {!isProfileReady && (
                      <span className="rounded-full bg-header-link-hover px-2 text-[10px] uppercase tracking-wide text-header-bg">
                        заполнить
                      </span>
                    )}
                  </span>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    void logout();
                  }}
                  className="button-flat inline-flex h-9 cursor-pointer items-center gap-2 whitespace-nowrap rounded-md px-3 text-sm font-medium !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                >
                  <span>Выйти</span>
                  <LogOut size={16} />
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => openLogin("login")}
                  className="button-flat inline-flex h-9 cursor-pointer items-center gap-2 whitespace-nowrap rounded-md px-3 text-sm font-medium !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                >
                  <span>Войти</span>
                  <LogIn size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => openLogin("register")}
                  className="button-flat h-9 cursor-pointer whitespace-nowrap rounded-md px-3 text-sm font-medium !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                >
                  Зарегистрироваться
                </button>
              </>
            )}
          </div>

          <div className="flex items-center justify-end min-[900px]:hidden">
            <button
              type="button"
              aria-label={isMenuOpen ? "Закрыть меню" : "Открыть меню"}
              aria-expanded={isMenuOpen}
              onClick={() => setIsMenuOpen((current) => !current)}
              className="button-flat inline-flex size-9 items-center justify-center rounded-xl border border-header-link/30 text-header-link transition hover:bg-header-hover-bg hover:text-header-link-hover"
            >
              {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {isMenuOpen && (
          <div className="absolute left-4 right-4 top-full mt-3 rounded-2xl border border-header-link/20 bg-header-bg p-3 shadow-2xl min-[900px]:hidden">
            <div className="grid gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={getMobileLinkClassName(item.href)}
                >
                  {item.label}
                </Link>
              ))}

              <div className="my-2 h-px bg-header-link/20" />

              {isLoggedIn ? (
                <>
                  <Link
                    href="/profile"
                    className={getMobileLinkClassName("/profile")}
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span>Профиль</span>
                      {!isProfileReady && (
                        <span className="rounded-full bg-header-link-hover px-2 text-[10px] uppercase tracking-wide text-header-bg">
                          заполнить
                        </span>
                      )}
                    </span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setIsMenuOpen(false);
                      void logout();
                    }}
                    className="button-flat inline-flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                  >
                    <span>Выйти</span>
                    <LogOut size={16} />
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setIsMenuOpen(false);
                      openLogin("login");
                    }}
                    className="button-flat inline-flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                  >
                    <span>Войти</span>
                    <LogIn size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsMenuOpen(false);
                      openLogin("register");
                    }}
                    className="button-flat cursor-pointer rounded-xl px-3 py-2 text-left text-sm font-bold !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                  >
                    Зарегистрироваться
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
