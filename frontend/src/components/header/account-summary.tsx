import { AccountAvatar } from "./account-avatar";

type AccountSummaryProps = {
  avatarUrl?: string;
  avatarOriginalUrl?: string;
  avatarPositionX?: number;
  avatarPositionY?: number;
  avatarScale?: number;
  avatarCropSize?: number;
  name: string;
  initials: string;
  email?: string;
};

export function AccountSummary({
  avatarUrl,
  avatarOriginalUrl,
  avatarPositionX,
  avatarPositionY,
  avatarScale,
  avatarCropSize,
  name,
  initials,
  email,
}: AccountSummaryProps) {
  return (
    <div className="mb-2 px-3 py-2 text-center">
      <div className="grid grid-cols-[auto_auto] items-center justify-center gap-3">
        <AccountAvatar
          avatarUrl={avatarUrl}
          avatarOriginalUrl={avatarOriginalUrl}
          avatarPositionX={avatarPositionX}
          avatarPositionY={avatarPositionY}
          avatarScale={avatarScale}
          avatarCropSize={avatarCropSize}
          name={name}
          initials={initials}
          sizeClassName="size-9"
          sizePx={36}
          withFrame
        />
        <div className="flex h-9 min-w-0 items-center">
          <span className="max-w-[11rem] truncate whitespace-nowrap text-sm font-bold leading-none text-header-link-hover">
            {name}
          </span>
        </div>
      </div>

      {email && (
        <div className="pt-3 break-all text-center text-xs leading-5 text-header-link">
          {email}
        </div>
      )}
    </div>
  );
}
