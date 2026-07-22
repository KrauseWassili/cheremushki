"use client";

import Link from "next/link";
import { useApp } from "@/providers/AppProvider";
import { LogOut } from "lucide-react";

export default function Header() {
  const { user, isLoggedIn, logout } = useApp();

  return (
    <header
      className="fixed left-0 top-0 w-full
        bg-dark
        text-lightest
        py-2 
        text-center
      "
    >
      <nav>
        <div className="flex items-center justify-between w-full px-4">
          <Link href="/" className="flex items-center ">
            Cheremushki
          </Link>

          <div className="flex items-center space-x-8">
            <Link
              href="/"
              className="text-secondary text-xl hover:text-foreground transition-colors font-medium"
            >
              Главная
            </Link>
            <Link
              href="/project"
              className="text-secondary text-xl hover:text-foreground transition-colors font-medium"
            >
              О проекте
            </Link>
            <Link
              href="/members"
              className="text-secondary text-xl hover:text-foreground transition-colors font-medium"
            >
              Участники
            </Link>
          </div>

          <div className="flex items-center space-x-8">
            {isLoggedIn ? (
              <Link
                href="/profile"
                className="text-secondary text-xl hover:text-foreground transition-colors font-medium"
              >
                Личный кабинет
              </Link>
            ) : (
              <Link
                href="/profile"
                className="invisible text-secondary text-xl hover:text-foreground transition-colors font-medium"
              >
                Личный кабинет
              </Link>
            )}
            {isLoggedIn ? (
              <button
                type="button"
                onClick={() => logout()}
                className="button-logout"
              >
                Выйти
                <LogOut />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => logout()}
                className="invisible button-logout"
              >
                Выйти
                <LogOut />
              </button>
            )}
          </div>
        </div>
      </nav>
    </header>
  );
}
