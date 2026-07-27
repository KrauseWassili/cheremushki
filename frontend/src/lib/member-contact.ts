import type { MemberProfile } from "@/types/member";

export function hasVisibleContactActions(member: MemberProfile) {
  if (member.contactMode !== "direct") {
    return true;
  }

  return Boolean(
    member.email ||
      member.telegramUsername ||
      member.linkedinUrl ||
      member.websiteUrl,
  );
}

export function getContactModeLabel(member: MemberProfile) {
  switch (member.contactMode) {
    case "direct":
      return "Можно писать напрямую";
    case "request":
      return "Контакт по запросу";
    case "group":
      return "Через Telegram-группу";
    case "closed":
      return "Обращения закрыты";
  }
}
