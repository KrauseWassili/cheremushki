"use client";

import { LogIn } from "lucide-react";
import { signIn, useSession } from "next-auth/react";
import Link from "next/link";

export default function Buttons() {
  const { data: session } = useSession();
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        gap: "30px",
        marginTop: "20px",
      }}
    >
      {session ? (
        <button type="button">
          <Link href={`/decks`} className="mt-4 px-6 py-2">
            Start Training
          </Link>{" "}
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
