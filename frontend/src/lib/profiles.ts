import {ApiError, apiFetch, GENERIC_ERROR_MESSAGE, getApiBaseUrl} from "@/lib/api";
import {withAuthRetry} from "@/lib/auth";
import type {ContactMode, MemberProfile} from "@/types/member";
import type {ProfileDraft} from "@/types/profile";
import type {RequiredField} from "@/lib/profile";

/** Backend snake_case response shape */
type ApiMemberProfile = {
    id: number;
    slug: string;
    full_name: string;
    avatar_url?: string | null;
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
    // Nur auf /profiles/user/me/ – das öffentliche Verzeichnis liefert das nicht.
    directory_ready?: boolean;
    // Backend Feldnamen der noch leeren Pflichtfelder, in Formularreihenfolge.
    missing_fields?: string[];
    // Vollständige Pflichtfeldliste – Grundlage des Live-Zählers im Formular.
    required_fields?: string[];
    // Ist die Telegram-Einladung versandt? Kommt mit jedes Request mit.
    invite_sent?: boolean;
    // Nur auf /profiles/user/me/: Darf das Mitglied das Verzeichnis sehen?
    // Die Regel (Telegram-Gruppe beigetreten) entscheidet allein das Backend.
    can_view_directory?: boolean;
    // Nur auf /profiles/user/me/: Liegt ein unbeschnittenes Original vor? Es
    // ist nicht öffentlich, siehe fetchMyAvatarOriginal().
    has_avatar_original?: boolean;
};

// Fehlercode im 403 des Verzeichnisses, solange das Mitglied der
// Telegram-Gruppe noch nicht beigetreten ist (apps/profiles/permissions.py).
const NOT_GROUP_MEMBER_CODE = "not_group_member";

/** Ist der Fehler das Verzeichnis-Gate „noch nicht in der Gruppe“? */
export function isNotGroupMemberError(err: unknown): boolean {
    if (!(err instanceof ApiError) || err.status !== 403) return false;
    const data = err.data;
    return (
        typeof data === "object" &&
        data !== null &&
        (data as Record<string, unknown>).code === NOT_GROUP_MEMBER_CODE
    );
}

export type ApiProfileTagSuggestion = {
    name: string;
    label: string;
    hashtag: string;
    usage_count?: number;
    category?: string | {
        name?: string;
        label?: string;
        slug?: string;
        sort_order?: number;
    } | null;
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
    return withAuthRetry((token) => apiFetch<T>(path, options, token));
}

export function mapApiProfileToMember(api: ApiMemberProfile): MemberProfile {
    return {
        id: String(api.id),
        slug: api.slug,
        fullName: api.full_name,
        avatarUrl: api.avatar_url ?? undefined,
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

/**
 * Backend-Pflichtfeld → Schlüssel im lokalen Entwurf, für den Live-Zähler in
 * lib/profile.ts. Liegt hier, weil dies die einzige Stelle für das
 * snake_case↔camelCase-Mapping ist. Fehlt ein Eintrag, meldet tsc das über
 * den Record-Typ; der Zähler bliebe sonst hinter dem Server zurück.
 */
export const DRAFT_KEY_BY_REQUIRED_FIELD: Record<RequiredField, keyof ProfileDraft> = {
    avatar: "avatarUrl",
    city: "city",
    headline: "headline",
    bio: "bio",
    can_help_with: "canHelpWith",
    looking_for: "lookingFor",
};

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
        // Kommt nicht mit der Profilantwort, sondern separat per
        // fetchMyAvatarOriginal() – die Profilseite lädt es nach.
        avatarOriginalUrl: undefined,
        avatarPositionX: api.avatar_position_x ?? 50,
        avatarPositionY: api.avatar_position_y ?? 50,
        avatarScale: api.avatar_scale ?? 1,
        avatarCropSize: api.avatar_crop_size ?? 100,
    };
}

function draftToApiPayload(draft: ProfileDraft) {
    const slug = draft.slug.trim();
    return {
        // Leer gar nicht senden: Ein "" würde einen vorhandenen Slug
        // überschreiben und neu erzeugen, geteilte Links brächen. Ohne Slug
        // vergibt das Backend beim Speichern selbst einen (ensure_unique_slug).
        ...(slug ? {slug} : {}),
        headline: draft.headline.trim(),
        city: draft.city.trim(),
        profession: draft.profession.trim(),
        company: draft.company.trim(),
        position: draft.position.trim(),
        bio: draft.bio.trim(),
        can_help_with: draft.canHelpWith.trim(),
        looking_for: draft.lookingFor.trim(),
        // Kanonisierung (@, t.me-Links, Kleinschreibung) macht das Backend in
        // apps/profiles/telegram.py hier nur trimmen, damit die Regel nicht an
        // zwei Stellen gepflegt werden muss.
        telegram_username: draft.telegram.trim(),
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

export async function fetchTagSuggestions(
    query = "",
    limit = 50,
): Promise<ApiProfileTagSuggestion[]> {
    const params = new URLSearchParams({
        limit: String(limit),
    });
    const trimmedQuery = query.trim();
    if (trimmedQuery) {
        params.set("q", trimmedQuery);
    }

    return authedFetch<ApiProfileTagSuggestion[]>(
        `/api/v1/profiles/tags/?${params.toString()}`,
    );
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
    const form = new FormData();
    form.append("avatar", file, "avatar.jpg");
    if (original) {
        form.append("avatar_original", original, "avatar-original.jpg");
    }
    form.append("avatar_position_x", String(crop.x));
    form.append("avatar_position_y", String(crop.y));
    form.append("avatar_scale", String(crop.scale));
    form.append("avatar_crop_size", String(crop.size));

    // Ohne avatar_original behält das Backend das gespeicherte Original.
    // Fehler (400 mit Feldfehlern, 429) kommen als ApiError aus apiFetch.
    return authedFetch<ApiMemberProfile>("/api/v1/profiles/user/me/avatar/", {
        method: "POST",
        body: form,
    });
}

export async function sendContactRequest(
    slug: string,
    message: string,
): Promise<void> {
    await authedFetch(`/api/v1/profiles/${encodeURIComponent(slug)}/contact-request/`, {
        method: "POST",
        body: JSON.stringify({message}),
    });
}

/**
 * Lädt das unbeschnittene Original des eigenen Avatars als data:-URL.
 *
 * Das Original liegt nicht unter /media/ (dort öffentlich ohne Login),
 * sondern nur hinter dem Bearer-Token. Ein <img src> kann keinen
 * Authorization-Header mitschicken, deshalb der Umweg über fetch → Blob →
 * data:-URL; Zuschnitt und erneuter Upload arbeiten ohnehin mit data:-URLs.
 */
export async function fetchMyAvatarOriginal(): Promise<string> {
    async function load(access: string): Promise<Blob> {
        const response = await fetch(
            `${getApiBaseUrl()}/api/v1/profiles/user/me/avatar/original/`,
            {
                headers: {Authorization: `Bearer ${access}`},
                cache: "no-store",
            },
        );
        if (!response.ok) {
            throw new ApiError(GENERIC_ERROR_MESSAGE, response.status);
        }
        return response.blob();
    }

    const blob = await withAuthRetry(load);
    return blobToDataUrl(blob);
}

function blobToDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(blob);
    });
}

// dataURL. Blob für Avatar-Upload
export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
    const response = await fetch(dataUrl);
    return response.blob();
}
