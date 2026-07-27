import type { ProfileDraft } from "@/types/profile";

export const PROFILE_REQUIRED_FIELDS: Array<keyof ProfileDraft> = [
  "avatarUrl",
  "city",
  "headline",
  "bio",
  "canHelpWith",
  "lookingFor",
];

export function isProfileReadyForDirectory(profile: Partial<ProfileDraft>) {
  return PROFILE_REQUIRED_FIELDS.every((field) => {
    const value = profile[field];
    return typeof value === "string" && value.trim().length > 0;
  });
}

export function getProfileRequiredFieldsStatus(
  profile: Partial<ProfileDraft>,
) {
  const filledCount = PROFILE_REQUIRED_FIELDS.filter((field) => {
    const value = profile[field];
    return typeof value === "string" && value.trim().length > 0;
  }).length;

  return {
    filledCount,
    totalCount: PROFILE_REQUIRED_FIELDS.length,
    isComplete: filledCount === PROFILE_REQUIRED_FIELDS.length,
  };
}
