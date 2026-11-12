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

import {DRAFT_KEY_BY_REQUIRED_FIELD} from "@/lib/profiles";
import type {ProfileDraft} from "@/types/profile";

/**
 * Backend Feldname. Beschriftung für das Mitglied.
 *
 * Einzige Quelle für die Beschriftung der Pflichtfelder: Das Formular auf
 * /profile und der Hinweis "Осталось заполнить" lesen beide von hier. Weichen
 * die Texte voneinander ab, findet das Mitglied das fehlende Feld nicht.
 */
export const REQUIRED_FIELD_LABELS = {
    avatar: "Фотография",
    city: "Город",
    headline: "Заголовок",
    bio: "Краткое описание",
    can_help_with: "Могу помочь",
    looking_for: "Сейчас интересно",
} as const satisfies Record<string, string>;

export type RequiredField = keyof typeof REQUIRED_FIELD_LABELS;

/**
 * DOM-ID des Eingabeelements eines Pflichtfelds, damit der Hinweis
 * "Осталось заполнить" direkt dorthin springen kann.
 */
export function requiredFieldElementId(field: string): string {
    return `profile-field-${field}`;
}

export type ProfileCompletionStatus = {
    filledCount: number;
    totalCount: number;
    isComplete: boolean;
    missingFields: { field: string; label: string }[];
};

function isRequiredField(field: string): field is RequiredField {
    return Object.hasOwn(REQUIRED_FIELD_LABELS, field);
}

export function labelForField(field: string): string {
    return isRequiredField(field) ? REQUIRED_FIELD_LABELS[field] : field;
}

function isFilledInDraft(draft: Partial<ProfileDraft>, field: string): boolean {
    if (!isRequiredField(field)) return false;
    const key = DRAFT_KEY_BY_REQUIRED_FIELD[field];
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
        missingFields: missing.map((field) => ({
            field,
            label: labelForField(field),
        })),
    };
}
