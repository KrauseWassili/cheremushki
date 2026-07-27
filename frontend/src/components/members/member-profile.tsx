import type { MemberProfile } from "@/types/member";
import {
  getContactModeLabel,
  hasVisibleContactActions,
} from "@/lib/member-contact";
import { MemberContactActions } from "./member-contact-actions";

type MemberProfileViewProps = {
  member: MemberProfile;
};

export function MemberProfileView({
  member,
}: MemberProfileViewProps) {
  const professionalFacts = [
    { label: "Город", value: member.city },
    { label: "Профессия", value: member.profession },
    { label: "Должность", value: member.position },
    { label: "Компания", value: member.company },
    {
      label: "Языки",
      value:
        member.languages.length > 0 ? member.languages.join(", ") : undefined,
    },
    {
      label: "В клубе с",
      value: new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "long",
      }).format(new Date(member.joinedAt)),
    },
  ].filter((fact) => fact.value);

  return (
    <div className="grid gap-6">
      <section className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row">
          {member.avatarUrl ? (
            <img
              src={member.avatarUrl}
              alt={`Аватар ${member.fullName}`}
              className="size-32 rounded-3xl object-cover sm:size-44"
            />
          ) : (
            <div className="flex size-32 items-center justify-center rounded-3xl bg-muted text-4xl font-black sm:size-44">
              {member.fullName.charAt(0)}
            </div>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                  {member.fullName}
                </h1>

                <p className="mt-2 text-lg text-muted-foreground">
                  {member.headline}
                </p>

                <p className="mt-3 text-sm text-muted-foreground">
                  📍 {member.city}
                </p>
              </div>

              <span className="rounded-full bg-muted px-3 py-1.5 text-xs font-bold text-foreground">
                {getContactModeLabel(member)}
              </span>
            </div>

            {member.tags.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-2">
                {member.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-border bg-muted/50 px-3 py-1 text-sm"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-border bg-background p-6 sm:p-8">
        <h2 className="text-xl font-black">О себе</h2>
        <p className="mt-4 whitespace-pre-line leading-7">
          {member.bio}
        </p>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-3xl border border-border bg-background p-6">
          <h2 className="text-lg font-black">Могу помочь</h2>
          <p className="mt-3 leading-7">{member.canHelpWith}</p>
        </section>

        <section className="rounded-3xl border border-border bg-background p-6">
          <h2 className="text-lg font-black">Сейчас интересно</h2>
          <p className="mt-3 leading-7">{member.lookingFor}</p>
        </section>
      </div>

      <section className="rounded-3xl border border-border bg-background p-6 sm:p-8">
        <h2 className="text-xl font-black">Профессиональное</h2>

        <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {professionalFacts.map((fact) => (
            <div
              key={fact.label}
              className="rounded-2xl border border-border bg-muted/30 px-4 py-3"
            >
              <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                {fact.label}
              </dt>
              <dd className="mt-1 font-bold">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {member.achievements.length > 0 && (
        <section className="rounded-3xl border border-border bg-background p-6 sm:p-8">
          <h2 className="text-xl font-black">Вклад в сообщество</h2>

          <div className="mt-5 flex flex-wrap gap-3">
            {member.achievements.map((achievement) => (
              <span
                key={achievement}
                className="rounded-2xl bg-amber-100 px-4 py-2 text-sm font-bold text-amber-900"
              >
                {achievement}
              </span>
            ))}
          </div>
        </section>
      )}

      {hasVisibleContactActions(member) && (
        <section className="rounded-3xl border border-border bg-background p-6 sm:p-8">
          <h2 className="text-xl font-black">Связаться</h2>
          <div className="mt-5">
            <MemberContactActions member={member} />
          </div>
        </section>
      )}
    </div>
  );
}
