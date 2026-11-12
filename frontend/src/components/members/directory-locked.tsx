"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { buttonClassName } from "@/components/ui/button";
import { fetchMyProfile } from "@/lib/profiles";

type InviteStage = "fill-profile" | "invite-pending" | "invite-sent";

/**
 * Hinweis statt Fehlermeldung, wenn das Backend das Verzeichnis mit
 * not_group_member ablehnt. Ob jemand Mitglied ist, entscheidet allein das
 * Backend – hier steht nur, was als Nächstes zu tun ist.
 *
 * Der Stand kommt frisch aus /profiles/user/me/ (directory_ready,
 * invite_sent), nicht aus dem User im AppProvider: Der wird nur beim Login
 * geladen und wüsste nichts von einem gerade vervollständigten Profil.
 */
export function DirectoryLocked() {
  // null: noch nicht geladen oder Laden gescheitert – dann bleibt es bei der
  // allgemeinen Schrittfolge.
  const [stage, setStage] = useState<InviteStage | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchMyProfile()
      .then((profile) => {
        if (cancelled) return;
        if (profile.invite_sent) setStage("invite-sent");
        else if (profile.directory_ready) setStage("invite-pending");
        else setStage("fill-profile");
      })
      .catch(() => {
        // Der Hinweis trägt auch ohne den Stand; ein eigener Fehlerzustand
        // wäre neben dem eigentlichen 403 nur Lärm.
        if (!cancelled) setStage(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="mx-auto w-full max-w-lg py-16 text-center">
      <h2 className="text-2xl font-bold">Каталог пока закрыт</h2>
      <p className="mt-4 text-muted-foreground">
        Каталог участников открыт только для тех, кто уже в нашей
        Telegram-группе.
      </p>
      {stage === "invite-sent" ? (
        <p className="mt-6 text-muted-foreground">
          Приглашение в Telegram-группу уже отправлено тебе на почту. Вступи в
          группу по ссылке из письма — после этого каталог откроется. Если
          письма нет, загляни в папку «Спам».
        </p>
      ) : stage === "invite-pending" ? (
        <p className="mt-6 text-muted-foreground">
          Профиль заполнен — приглашение в Telegram-группу скоро придёт на
          почту. Вступи в группу по ссылке из письма, и каталог откроется.
        </p>
      ) : (
        <ol className="mt-6 space-y-2 text-left text-muted-foreground">
          <li>1. Заполни свой профиль.</li>
          <li>2. На почту придёт приглашение в Telegram-группу.</li>
          <li>3. Вступи в группу — после этого каталог откроется.</li>
        </ol>
      )}
      <Link
        href="/profile"
        className={buttonClassName({ variant: "primary", className: "mt-8" })}
      >
        Перейти к профилю
      </Link>
    </section>
  );
}
