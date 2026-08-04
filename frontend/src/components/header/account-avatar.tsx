type AccountAvatarProps = {
  avatarUrl?: string;
  name: string;
  initials: string;
  sizeClassName: string;
  withFrame?: boolean;
};

export function AccountAvatar({
  avatarUrl,
  name,
  initials,
  sizeClassName,
  withFrame = false,
}: AccountAvatarProps) {
  const frameClassName = withFrame ? "border-2 border-header-link" : "";

  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={`Аватар ${name}`}
        width={40}
        height={40}
        className={[
          sizeClassName,
          frameClassName,
          "block shrink-0 rounded-full object-cover",
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
