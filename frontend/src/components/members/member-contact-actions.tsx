"use client";

import { useState } from "react";
import { hasVisibleContactActions } from "@/lib/member-contact";
import { sendContactRequest } from "@/lib/profiles";
import { ApiError } from "@/lib/api";
import type { MemberProfile } from "@/types/member";

type MemberContactActionsProps = {
  member: MemberProfile;
  compact?: boolean;
};

export function MemberContactActions({
  member,
  compact = false,
}: MemberContactActionsProps) {
  const [isRequestOpen, setIsRequestOpen] = useState(false);
  const [requestText, setRequestText] = useState("");
  const [isRequestSent, setIsRequestSent] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const buttonClassName = compact
    ? "rounded-xl border border-border px-4 py-2 text-sm font-bold transition hover:bg-muted"
    : "rounded-xl border border-border px-4 py-2.5 text-sm font-bold transition hover:bg-muted";

  if (member.contactMode === "closed") {
    return (
      <p className="text-sm text-muted-foreground">
        Участник сейчас закрыл обращения.
      </p>
    );
  }

  if (member.contactMode === "group") {
    if (!member.telegramGroupUrl) {
      return (
        <p className="text-sm text-muted-foreground">
          Ссылка на группу пока не указана.
        </p>
      );
    }

    return (
      <a
        href={member.telegramGroupUrl}
        target="_blank"
        rel="noreferrer"
        className={buttonClassName}
      >
        Написать в Telegram-группе
      </a>
    );
  }

  if (member.contactMode === "request") {
    return (
      <>
        <button
          type="button"
          onClick={() => {
            setIsRequestOpen(true);
            setIsRequestSent(false);
            setSendError(null);
          }}
          className={buttonClassName}
        >
          Запросить контакт
        </button>

        {isRequestOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-2xl border border-border bg-bg p-6 shadow-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-black">Запрос контакта</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Сообщение будет отправлено участнику по email.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setIsRequestOpen(false)}
                  className="rounded-xl border border-border px-3 py-1.5 text-sm font-bold hover:bg-muted"
                >
                  Закрыть
                </button>
              </div>

              {isRequestSent ? (
                <p className="mt-5 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm font-bold">
                  Запрос отправлен.
                </p>
              ) : (
                <>
                  <textarea
                    value={requestText}
                    onChange={(event) => setRequestText(event.target.value)}
                    placeholder={`Коротко напишите, зачем хотите связаться с ${member.fullName}`}
                    className="mt-5 min-h-36 w-full rounded-xl border border-border bg-input-background px-3 py-3 shadow-inner outline-none focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5"
                  />

                  {sendError && (
                    <p className="mt-3 text-sm text-destructive">{sendError}</p>
                  )}

                  <div className="mt-4 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setIsRequestOpen(false)}
                      className="rounded-xl border border-border px-4 py-2.5 text-sm font-bold hover:bg-muted"
                    >
                      Отмена
                    </button>

                    <button
                      type="button"
                      disabled={!requestText.trim() || isSending}
                      onClick={async () => {
                        setIsSending(true);
                        setSendError(null);
                        try {
                          await sendContactRequest(
                            member.slug,
                            requestText.trim(),
                          );
                          setIsRequestSent(true);
                        } catch (err) {
                          setSendError(
                            err instanceof ApiError
                              ? err.message
                              : "Не удалось отправить запрос.",
                          );
                        } finally {
                          setIsSending(false);
                        }
                      }}
                      className="rounded-xl bg-foreground px-4 py-2.5 text-sm font-bold text-background disabled:opacity-50"
                    >
                      {isSending ? "Отправка…" : "Отправить запрос"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </>
    );
  }

  if (!hasVisibleContactActions(member)) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-3">
      {member.email && (
        <a href={`mailto:${member.email}`} className={buttonClassName}>
          Email
        </a>
      )}

      {member.telegramUsername && (
        <a
          href={`https://t.me/${member.telegramUsername.replace(/^@/, "")}`}
          target="_blank"
          rel="noreferrer"
          className={buttonClassName}
        >
          Telegram
        </a>
      )}

      {member.linkedinUrl && (
        <a
          href={member.linkedinUrl}
          target="_blank"
          rel="noreferrer"
          className={buttonClassName}
        >
          LinkedIn
        </a>
      )}

      {member.websiteUrl && (
        <a
          href={member.websiteUrl}
          target="_blank"
          rel="noreferrer"
          className={buttonClassName}
        >
          Сайт
        </a>
      )}
    </div>
  );
}
