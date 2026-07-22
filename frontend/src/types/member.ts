export type ContactPreference =
  | "telegram"
  | "linkedin"
  | "website"
  | "club_intro";

export type MemberProfile = {
  id: string;
  slug: string;

  fullName: string;
  avatarUrl?: string;
  headline: string;

  city: string;
  company?: string;
  position?: string;

  bio: string;
  canHelpWith: string;
  lookingFor: string;

  tags: string[];
  languages: string[];

  telegramUsername?: string;
  linkedinUrl?: string;
  websiteUrl?: string;
  contactPreference: ContactPreference;

  achievements: string[];

  joinedAt: string;
  isOpenToContacts: boolean;
};