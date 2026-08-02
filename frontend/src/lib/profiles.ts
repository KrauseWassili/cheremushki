import { apiFetch, getApiBaseUrl } from "@/lib/api";
import {
  getAccessToken,
  refreshAccessToken,
} from "@/lib/auth";
import type { ContactMode, MemberProfile } from "@/types/member";
import type { ProfileDraft } from "@/types/profile";

/** Backend snake_case response shape */
type ApiMemberProfile = {
  id: number;
  slug: string;
  full_name: string;
  avatar_url?: string | null;
  avatar_original_url?: string | null;
  avatar_position_x?: number;
  avatar_position_y?: number;
  avatar_scale?: number;
  avatar_crop_size?: number;
  headline: string;
  city: string;
  profession?: string;
  company?: string;
  position?: string;
  bio: string;
  can_help_with: string;
  looking_for: string;
  tags?: string[];
  languages?: string[];
  achievements?: string[];
  email?: string | null;
  telegram_username?: string;
  linkedin_url?: string;
  website_url?: string;
  contact_mode: ContactMode;
  telegram_group_url?: string;
  is_directory_visible?: boolean;
  joined_at: string;
};

type PaginatedProfiles = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ApiMemberProfile[];
};

async function authedFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAccessToken();
  if (!token) throw new Error("Пользователь не авторизован");

  try {
    return await apiFetch<T>(path, options, token);
  } catch (error) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) throw error;
    return apiFetch<T>(path, options, refreshed);
  }
}

export function mapApiProfileToMember(api: ApiMemberProfile): MemberProfile {
  return {
    id: String(api.id),
    slug: api.slug,
    fullName: api.full_name,
    avatarUrl: api.avatar_url ?? undefined,
    avatarOriginalUrl: api.avatar_original_url ?? undefined,
    avatarPositionX: api.avatar_position_x,
    avatarPositionY: api.avatar_position_y,
    avatarScale: api.avatar_scale,
    avatarCropSize: api.avatar_crop_size,
    headline: api.headline || "",
    city: api.city || "",
    profession: api.profession || "",
    company: api.company || "",
    position: api.position || "",
    bio: api.bio || "",
    canHelpWith: api.can_help_with || "",
    lookingFor: api.looking_for || "",
    tags: api.tags ?? [],
    languages: api.languages ?? [],
    email: api.email ?? undefined,
    telegramUsername: api.telegram_username || "",
    linkedinUrl: api.linkedin_url || "",
    websiteUrl: api.website_url || "",
    contactMode: api.contact_mode || "request",
    telegramGroupUrl: api.telegram_group_url || "",
    achievements: api.achievements ?? [],
    joinedAt: api.joined_at,
  };
}

export function mapApiProfileToDraft(
  api: ApiMemberProfile,
  names?: { firstName?: string; lastName?: string; email?: string },
): ProfileDraft {
  return {
    firstName: names?.firstName ?? "",
    lastName: names?.lastName ?? "",
    slug: api.slug || "",
    email: names?.email ?? api.email ?? "",
    city: api.city || "",
    profession: api.profession || "",
    headline: api.headline || "",
    bio: api.bio || "",
    canHelpWith: api.can_help_with || "",
    lookingFor: api.looking_for || "",
    company: api.company || "",
    position: api.position || "",
    telegram: api.telegram_username || "",
    linkedin: api.linkedin_url || "",
    website: api.website_url || "",
    tags: (api.tags ?? []).join(", "),
    contactMode: api.contact_mode || "request",
    avatarUrl: api.avatar_url ?? undefined,
    avatarOriginalUrl: api.avatar_original_url ?? undefined,
    avatarPositionX: api.avatar_position_x ?? 50,
    avatarPositionY: api.avatar_position_y ?? 50,
    avatarScale: api.avatar_scale ?? 1,
    avatarCropSize: api.avatar_crop_size ?? 100,
  };
}

function draftToApiPayload(draft: ProfileDraft) {
  return {
    slug: draft.slug.trim(),
    headline: draft.headline.trim(),
    city: draft.city.trim(),
    profession: draft.profession.trim(),
    company: draft.company.trim(),
    position: draft.position.trim(),
    bio: draft.bio.trim(),
    can_help_with: draft.canHelpWith.trim(),
    looking_for: draft.lookingFor.trim(),
    telegram_username: draft.telegram.trim().replace(/^@/, ""),
    linkedin_url: draft.linkedin.trim(),
    website_url: draft.website.trim(),
    contact_mode: draft.contactMode,
    tags: draft.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    avatar_position_x: draft.avatarPositionX,
    avatar_position_y: draft.avatarPositionY,
    avatar_scale: draft.avatarScale,
    avatar_crop_size: draft.avatarCropSize,
  };
}

export async function fetchMemberProfiles(): Promise<MemberProfile[]> {
  const data = await authedFetch<PaginatedProfiles | ApiMemberProfile[]>(
    "/api/v1/profiles/",
  );
  const results = Array.isArray(data) ? data : data.results;
  return results.map(mapApiProfileToMember);
}

export async function fetchMemberProfile(
  slug: string,
): Promise<MemberProfile> {
  const data = await authedFetch<ApiMemberProfile>(
    `/api/v1/profiles/${encodeURIComponent(slug)}/`,
  );
  return mapApiProfileToMember(data);
}

export async function fetchMyProfile(): Promise<ApiMemberProfile> {
  return authedFetch<ApiMemberProfile>("/api/v1/profiles/user/me/");
}

export async function saveMyProfile(
  draft: ProfileDraft,
): Promise<ApiMemberProfile> {
  return authedFetch<ApiMemberProfile>("/api/v1/profiles/user/me/", {
    method: "PATCH",
    body: JSON.stringify(draftToApiPayload(draft)),
  });
}

export async function uploadMyAvatar(
  file: Blob,
  crop: {
    x: number;
    y: number;
    scale: number;
    size: number;
  },
  original?: Blob | null,
): Promise<ApiMemberProfile> {
  const token = getAccessToken();
  if (!token) throw new Error("Пользователь не авторизован");

  const form = new FormData();
  form.append("avatar", file, "avatar.jpg");
  if (original) {
    form.append("avatar_original", original, "avatar-original.jpg");
  }
  form.append("avatar_position_x", String(crop.x));
  form.append("avatar_position_y", String(crop.y));
  form.append("avatar_scale", String(crop.scale));
  form.append("avatar_crop_size", String(crop.size));

  async function post(access: string) {
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/profiles/user/me/avatar/`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${access}` },
        body: form,
      },
    );
    const text = await response.text();
    const data = text ? (JSON.parse(text) as unknown) : null;
    if (!response.ok) {
      throw new Error(
        typeof data === "object" && data && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : response.statusText,
      );
    }
    return data as ApiMemberProfile;
  }

  try {
    return await post(token);
  } catch (error) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) throw error;
    return post(refreshed);
  }
}

export async function sendContactRequest(
  slug: string,
  message: string,
): Promise<void> {
  await authedFetch(`/api/v1/profiles/${encodeURIComponent(slug)}/contact-request/`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

/** dataURL → Blob für Avatar-Upload */
export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const response = await fetch(dataUrl);
  return response.blob();
}
