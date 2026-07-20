"use client";

import { useApp } from "@/providers/AppProvider";
import { LogIn } from "lucide-react";
import Link from "next/link";

export default function ProfilePage() {
  const { user, isLoggedIn } = useApp();

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-2xl font-semibold text-foreground mb-4">
            Вы не вошли в систему :(
          </p>
          <Link href="/" className="button-gray-rounded">
            На главную
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="bg-card border border-border rounded-3xl p-8 max-w-xl w-full shadow-xl">
        <h1 className="text-3xl font-bold mb-4">Профиль</h1>
        <p className="mb-2">
          <strong>Имя:</strong> {user?.first_name ?? "—"}
        </p>
        <p className="mb-2">
          <strong>Фамилия:</strong> {user?.last_name ?? "—"}
        </p>
        <p className="mb-2">
          <strong>E-mail:</strong> {user?.email ?? "—"}
        </p>        
      </div>
    </div>
  );
};

