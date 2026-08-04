import Link from "next/link";
import { LogOut } from "lucide-react";
import { AccountAvatar } from "./account-avatar";
import { AccountSummary } from "./account-summary";

type AccountDropdownProps = {
  avatarUrl?: string;
  name: string;
  initials: string;
  email?: string;
  isOpen: boolean;
  isProfileReady: boolean;
  onToggle: () => void;
  onLogout: () => void;
  getMenuLinkClassName: (href: string) => string;
};

export function AccountDropdown({
  avatarUrl,
  name,
  initials,
  email,
  isOpen,
  isProfileReady,
  onToggle,
  onLogout,
  getMenuLinkClassName,
}: AccountDropdownProps) {
  const avatarButtonClassName = [
    "button-flat flex size-10 cursor-pointer items-center justify-center overflow-hidden rounded-full bg-header-hover-bg outline outline-2 outline-offset-0",
    isProfileReady
      ? "outline-header-link"
      : "outline-warning",
  ].join(" ");

  return (
    <>
      <div className="flex items-center gap-3">
        {!isProfileReady && (
          <Link
            href="/profile"
            className="rounded-full bg-warning px-3 py-1 text-xs font-bold leading-none !text-header-bg no-underline shadow-sm"
          >
            Заполнить профиль
          </Link>
        )}

        <button
          type="button"
          aria-label={`Меню аккаунта ${name}`}
          aria-expanded={isOpen}
          onClick={onToggle}
          className={avatarButtonClassName}
        >
          <AccountAvatar
            avatarUrl={avatarUrl}
            name={name}
            initials={initials}
            sizeClassName="size-full"
          />
        </button>
      </div>

      {isOpen && (
        <div className="absolute right-0 top-full mt-3 w-max min-w-56 max-w-[min(calc(100vw-2rem),24rem)] rounded-2xl border border-header-link/20 bg-header-bg p-3 shadow-2xl">
          <AccountSummary
            avatarUrl={avatarUrl}
            name={name}
            initials={initials}
            email={email}
          />

          <div className="my-3 h-px bg-header-link/20" />

          <Link href="/profile" className={getMenuLinkClassName("/profile")}>
            Профиль
          </Link>

          <button
            type="button"
            onClick={onLogout}
            className="button-flat mt-1 inline-flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-left text-base !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
          >
            <span>Выйти</span>
            <LogOut size={16} />
          </button>
        </div>
      )}
    </>
  );
}
