import { MemberDirectory } from "@/components/members/member-directory";
import { mockMembers } from "@/data/mock-members";

export default function MembersPage() {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-4 sm:px-6 sm:py-6">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-5xl">
          Участники
        </h1>

        <p className="mt-5 text-base leading-7 text-muted-foreground sm:text-lg">
          Наше сообщество — это потенциал, сложенный из опыта, знаний и
          возможностей каждого из нас. Вместе мы находим решения, воплощаем идеи
          и открываем друг другу новые пути. Найди тех, с кем хочется говорить,
          действовать и делиться.
        </p>
      </header>

      <MemberDirectory members={mockMembers} />
    </main>
  );
}
