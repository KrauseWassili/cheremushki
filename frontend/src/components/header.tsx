"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useApp } from "@/providers/AppProvider";
import { isProfileReadyForDirectory } from "@/lib/profile";
import { LogIn, LogOut } from "lucide-react";

export default function Header() {
  const pathname = usePathname();
  const { isLoggedIn, logout, openLogin } = useApp();
  const [isProfileReady, setIsProfileReady] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    function updateProfileStatus() {
      const stored = window.localStorage.getItem("mock-profile-draft");
      if (!stored) {
        setIsProfileReady(false);
        return;
      }

      try {
        const draft = JSON.parse(stored);
        setIsProfileReady(isProfileReadyForDirectory(draft));
      } catch {
        setIsProfileReady(false);
      }
    }

    updateProfileStatus();
    window.addEventListener("profile-draft-updated", updateProfileStatus);

    return () => {
      window.removeEventListener("profile-draft-updated", updateProfileStatus);
    };
  }, []);

  const navItems = [
    { href: "/", label: "Приветствие" },
    { href: "/project", label: "О проекте" },
    ...(isLoggedIn ? [{ href: "/members", label: "Участники" }] : []),
  ];

  const getLinkClassName = (href: string) => {
    const isActive = pathname === href;

    return [
      "cursor-pointer rounded-md px-3 py-2 text-sm font-medium transition-colors",
      isActive
        ? "bg-white/10 text-foreground"
        : "text-secondary hover:bg-white/10 hover:text-foreground",
    ].join(" ");
  };

  return (
    <header className="fixed left-0 top-0 w-full bg-dark py-3 text-lightest">
      <nav className="mx-auto w-full max-w-7xl px-4">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div className="flex items-center justify-start">
            <Link href="/" className="text-lg font-semibold text-lightest">
              Черемушки
            </Link>
          </div>

          <div className="flex items-center justify-center gap-2 sm:gap-4">
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

          <div className="flex items-center justify-end gap-2 sm:gap-4">
            {isLoggedIn ? (
              <>
                <Link href="/profile" className={getLinkClassName("/profile")}>
                  <span className="flex items-center gap-2">
                    <span>Профиль</span>
                    {!isProfileReady && (
                      <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                        заполнить
                      </span>
                    )}
                  </span>
                </Link>
                <button
                  type="button"
                  onClick={() => logout()}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-secondary transition-colors hover:bg-white/10 hover:text-foreground"
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
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-secondary transition-colors hover:bg-white/10 hover:text-foreground"
                >
                  <span>Войти</span>
                  <LogIn size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => openLogin("register")}
                  className="cursor-pointer rounded-md px-3 py-2 text-sm font-medium text-secondary transition-colors hover:bg-white/10 hover:text-foreground"
                >
                  Зарегистрироваться
                </button>
              </>
            )}
          </div>
        </div>
      </nav>
    </header>
  );
}
