import { MemberDirectory } from "@/components/members/member-directory";
import { mockMembers } from "@/data/mock-members";

export default function MembersPage() {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 sm:py-16">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <p className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
          Сообщество
        </p>

        <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-5xl">
          Наши люди
        </h1>

        <p className="mt-5 text-base leading-7 text-muted-foreground sm:text-lg">
          Здесь можно найти человека с нужным опытом, предложить помощь
          или просто познакомиться с кем-то поблизости.
        </p>
      </header>

      <MemberDirectory members={mockMembers} />
    </main>
  );
}