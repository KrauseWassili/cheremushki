export type ApplicationStatus =
  | "under_review"
  | "needs_changes"
  | "approved"
  | "rejected";

export type JoinApplication = {
  email: string;
  fullName: string;
  city: string;
  profession: string;
  position: string;
  company: string;

  bio: string;
  motivation: string;
  contribution: string;
  lookingFor: string;

  linkedinUrl: string;
  websiteUrl: string;
  telegramUsername: string;
  referredBy: string;

  rulesAccepted: boolean;
  privacyAccepted: boolean;
};

export type JoinDemoState = {
  application: JoinApplication;
  status: ApplicationStatus;
  adminMessage: string;
};