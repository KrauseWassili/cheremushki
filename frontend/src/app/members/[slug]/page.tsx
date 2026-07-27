import Link from "next/link";
import { LocalMemberProfilePage } from "@/components/members/local-member-profile-page";
import { MemberProfilePage } from "@/components/members/member-profile-page";
import { mockMembers } from "@/data/mock-members";

type MemberPageProps = {
  params: Promise<{
    slug: string;
  }>;
};

export function generateStaticParams() {
  return mockMembers.map((member) => ({
    slug: member.slug,
  }));
}

export default async function MemberPage({
  params,
}: MemberPageProps) {
  const { slug } = await params;

  const member = mockMembers.find(
    (candidate) => candidate.slug === slug,
  );

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-4 sm:px-6 sm:py-6">
      <Link
        href="/members"
        className="mb-7 inline-flex text-sm font-bold text-muted-foreground hover:text-foreground"
      >
        ← Все участники
      </Link>

      {member ? (
        <MemberProfilePage initialMember={member} />
      ) : (
        <LocalMemberProfilePage slug={slug} />
      )}
    </main>
  );
}
