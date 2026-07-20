"use client";

import { signIn, signOut, useSession } from "next-auth/react";
import { LogIn, LogOut } from "lucide-react";

export default function GoogleSignIn() {
  // useSession - для получения сессии в клиентском компоненте
  const { data: session } = useSession();

  return (
    <div>
      {session ? (
        <button
          type="button"
          onClick={() => signOut()}
          className="p-2 border-2 rounded-2xl flex gap-2 hover:text-background"
        >
          <span>Sign out</span>
          <LogOut />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => signIn("google")}
          className="p-2 border-2 rounded-2xl flex gap-2 hover:text-background"
        >
          <span>Sign in</span>
          <LogIn />
        </button>
      )}
    </div>
  );
}
