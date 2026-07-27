export type ContactMode = "direct" | "request" | "group" | "closed";

export type MemberProfile = {
  id: string;
  slug: string;

  fullName: string;
  avatarUrl?: string;
  avatarOriginalUrl?: string;
  avatarPositionX?: number;
  avatarPositionY?: number;
  avatarScale?: number;
  avatarCropSize?: number;
  headline: string;

  city: string;
  profession?: string;
  company?: string;
  position?: string;

  bio: string;
  canHelpWith: string;
  lookingFor: string;

  tags: string[];
  languages: string[];

  email?: string;
  telegramUsername?: string;
  linkedinUrl?: string;
  websiteUrl?: string;
  contactMode: ContactMode;
  telegramGroupUrl?: string;

  achievements: string[];

  joinedAt: string;
};
