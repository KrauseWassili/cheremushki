import { CroppedAvatar } from "@/components/members/cropped-avatar";

type AccountAvatarProps = {
  avatarUrl?: string;
  avatarOriginalUrl?: string;
  avatarPositionX?: number;
  avatarPositionY?: number;
  avatarScale?: number;
  avatarCropSize?: number;
  name: string;
  initials: string;
  sizeClassName: string;
  sizePx?: number;
  withFrame?: boolean;
};

export function AccountAvatar({
  avatarUrl,
  avatarOriginalUrl,
  avatarPositionX,
  avatarPositionY,
  avatarScale,
  avatarCropSize,
  name,
  initials,
  sizeClassName,
  sizePx = 40,
  withFrame = false,
}: AccountAvatarProps) {
  const frameClassName = withFrame ? "border-2 border-header-link" : "";

  if (avatarUrl) {
    return (
      <CroppedAvatar
        src={avatarUrl}
        originalSrc={avatarOriginalUrl}
        alt={`Аватар ${name}`}
        width={sizePx}
        height={sizePx}
        positionX={avatarPositionX}
        positionY={avatarPositionY}
        scale={avatarScale}
        cropSize={avatarCropSize}
        className={[
          sizeClassName,
          frameClassName,
          "rounded-full",
        ].join(" ")}
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      className={[
        sizeClassName,
        frameClassName,
        "inline-flex shrink-0 items-center justify-center rounded-full bg-header-link-hover text-sm font-black leading-none text-header-bg",
      ].join(" ")}
    >
      {initials}
    </span>
  );
}