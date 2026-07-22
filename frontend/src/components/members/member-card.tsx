import Link from "next/link";
import type { MemberProfile } from "@/types/member";

type MemberCardProps = {
  member: MemberProfile;
};

export function MemberCard({ member }: MemberCardProps) {
  return (
    <article className="rounded-3xl border border-border bg-background p-5 shadow-sm transition hover:border-foreground/20 hover:shadow-md sm:p-7">
      <div className="flex flex-col gap-5 sm:flex-row">
        <Link
          href={`/members/${member.slug}`}
          className="shrink-0 self-start"
          aria-label={`Открыть профиль ${member.fullName}`}
        >
          {member.avatarUrl ? (
            <img
              src={member.avatarUrl}
              alt={`Аватар ${member.fullName}`}
              className="size-24 rounded-2xl object-cover sm:size-32"
            />
          ) : (
            <div className="flex size-24 items-center justify-center rounded-2xl bg-muted text-2xl font-black sm:size-32">
              {member.fullName.charAt(0)}
            </div>
          )}
        </Link>

        <div className="min-w-0 flex-1">
          <div className="flex flex-col justify-between gap-3 sm:flex-row">
            <div>
              <Link
                href={`/members/${member.slug}`}
                className="text-xl font-black hover:underline sm:text-2xl"
              >
                {member.fullName}
              </Link>

              <p className="mt-1 text-base text-muted-foreground">
                {member.headline}
              </p>

              <p className="mt-2 text-sm text-muted-foreground">
                📍 {member.city}
                {member.company ? ` · ${member.company}` : ""}
              </p>
            </div>

            {member.isOpenToContacts && (
              <span className="h-fit w-fit rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                Открыт к общению
              </span>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {member.tags.slice(0, 5).map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-border bg-muted/50 px-3 py-1 text-xs font-medium"
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="mt-5 grid gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                Могу помочь
              </p>
              <p className="mt-1 text-sm leading-6">
                {member.canHelpWith}
              </p>
            </div>

            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                Сейчас интересно
              </p>
              <p className="mt-1 text-sm leading-6">
                {member.lookingFor}
              </p>
            </div>
          </div>

          <div className="mt-5">
            <Link
              href={`/members/${member.slug}`}
              className="inline-flex rounded-xl border border-border px-4 py-2 text-sm font-bold transition hover:bg-muted"
            >
              Открыть профиль
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}