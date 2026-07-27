import type { MemberProfile } from "@/types/member";
import { MemberProfileView } from "./member-profile";

type MemberProfilePageProps = {
  initialMember: MemberProfile;
};

export function MemberProfilePage({
  initialMember,
}: MemberProfilePageProps) {
  return <MemberProfileView member={initialMember} />;
}
