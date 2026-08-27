/**
 * Anzeige der Profil-Vollständigkeit.
 *
 * Was "vollständig" bedeutet, entscheidet ausschließlich das Backend
 * (`DIRECTORY_REQUIRED_FIELDS` in apps/profiles/models.py). Der Endpunkt
 * `/api/v1/profiles/user/me/` liefert drei Felder mit:
 *
 *   - required_fields die vollständige Pflichtfeldliste
 *   - missing_fields die aktuell leeren davon
 *   - directory_ready das maßgebliche Urteil (schließt user.is_active ein)
 */

import type {ProfileDraft} from "@/types/profile";

/** Backend Feldname. Beschriftung für das Mitglied. */
export const REQUIRED_FIELD_LABELS: Record<string, string> = {
    avatar: "Фотография",
    city: "Город",
    headline: "Коротко о себе",
    bio: "О себе",
    can_help_with: "Чем могу помочь",
    looking_for: "Что мне интересно",
};

/**
 * Backend Feldname. Schlüssel im lokalen Entwurf.
 *
 * Nötig, weil die API snake_case spricht und der Entwurf camelCase. Fehlt ein
 * Eintrag, gilt das Feld beim Live-Zählen als leer und der Zähler bleibt dann
 * hinter dem Server zurück, statt fälschlich Vollständigkeit zu behaupten.
 */
const DRAFT_KEY_BY_FIELD: Record<string, keyof ProfileDraft> = {
    avatar: "avatarUrl",
    city: "city",
    headline: "headline",
    bio: "bio",
    can_help_with: "canHelpWith",
    looking_for: "lookingFor",
};

export type ProfileCompletionStatus = {
    filledCount: number;
    totalCount: number;
    isComplete: boolean;
    missingLabels: string[];
};

export function labelForField(field: string): string {
    return REQUIRED_FIELD_LABELS[field] ?? field;
}

function isFilledInDraft(draft: Partial<ProfileDraft>, field: string): boolean {
    const key = DRAFT_KEY_BY_FIELD[field];
    if (!key) return false;
    const value = draft[key];
    return typeof value === "string" && value.trim().length > 0;
}

/**
 * Zählt den Fortschritt live gegen die Pflichtfeldliste des Backends.
 *
 * Der Zähler soll sich beim Tippen bewegen,
 * nicht erst beim Speichern. Er ist damit eine Vorschau.
 */
export function getProfileCompletionStatus(
    draft: Partial<ProfileDraft>,
    requiredFields: string[] | undefined,
): ProfileCompletionStatus {
    const fields = requiredFields ?? Object.keys(REQUIRED_FIELD_LABELS);
    const missing = fields.filter((field) => !isFilledInDraft(draft, field));

    return {
        filledCount: fields.length - missing.length,
        totalCount: fields.length,
        isComplete: missing.length === 0,
        missingLabels: missing.map(labelForField),
    };
}
