"use client";

import { useState } from "react";
import { hasVisibleContactActions } from "@/lib/member-contact";
import { sendContactRequest } from "@/lib/profiles";
import { ApiError } from "@/lib/api";
import { useEscapeKey } from "@/lib/use-escape-key";
import { Button, buttonClassName } from "@/components/ui/button";
import { TextArea } from "@/components/ui/text-field";
import { ModalFrame } from "@/components/ui/modal";
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

  const actionButtonClassName = buttonClassName({
    size: compact ? "sm" : "md",
  });

  useEscapeKey(isRequestOpen, () => setIsRequestOpen(false));

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
        className={actionButtonClassName}
      >
        Написать в Telegram-группе
      </a>
    );
  }

  if (member.contactMode === "request") {
    return (
      <>
        <Button
          type="button"
          size={compact ? "sm" : "md"}
          onClick={() => {
            setIsRequestOpen(true);
            setIsRequestSent(false);
            setSendError(null);
          }}
        >
          Запросить контакт
        </Button>

        {isRequestOpen && (
          <ModalFrame label="Запрос контакта" className="max-w-lg">
            <div
              className="contents"
              aria-label="Запрос контакта"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-bold">Запрос контакта</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Сообщение будет отправлено участнику по email.
                  </p>
                </div>

                <Button
                  type="button"
                  onClick={() => setIsRequestOpen(false)}
                  size="sm"
                >
                  Закрыть
                </Button>
              </div>

              {isRequestSent ? (
                <p className="mt-5 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm font-bold">
                  Запрос отправлен.
                </p>
              ) : (
                <>
                  <TextArea
                    value={requestText}
                    onChange={(event) => setRequestText(event.target.value)}
                    placeholder={`Коротко напишите, зачем хотите связаться с ${member.fullName}`}
                    className="mt-5 min-h-36"
                  />

                  {sendError && (
                    <p className="mt-3 text-sm text-destructive">{sendError}</p>
                  )}

                  <div className="mt-4 flex justify-end gap-3">
                    <Button
                      type="button"
                      onClick={() => setIsRequestOpen(false)}
                    >
                      Отмена
                    </Button>

                    <Button
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
                      variant="solid"
                    >
                      {isSending ? "Отправка…" : "Отправить запрос"}
                    </Button>
                  </div>
                </>
              )}
            </div>
          </ModalFrame>
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
        <a href={`mailto:${member.email}`} className={actionButtonClassName}>
          Email
        </a>
      )}

      {member.telegramUsername && (
        <a
          href={`https://t.me/${member.telegramUsername.replace(/^@/, "")}`}
          target="_blank"
          rel="noreferrer"
          className={actionButtonClassName}
        >
          Telegram
        </a>
      )}

      {member.linkedinUrl && (
        <a
          href={member.linkedinUrl}
          target="_blank"
          rel="noreferrer"
          className={actionButtonClassName}
        >
          LinkedIn
        </a>
      )}

      {member.websiteUrl && (
        <a
          href={member.websiteUrl}
          target="_blank"
          rel="noreferrer"
          className={actionButtonClassName}
        >
          Сайт
        </a>
      )}
    </div>
  );
}
