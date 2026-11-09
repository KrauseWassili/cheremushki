const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Nur serverseitig, Container-zu-Container-URL (niemals mit dem Präfix „NEXT_PUBLIC_“, sodass sie
// zur Laufzeit über „process.env“ gelesen und niemals zur Erstellungszeit in das Client-
// Bundle eingebunden wird). Wird ausschließlich von serverseitigem Code wie Route
// Handler, z. B. src/app/api/avatar-source/route.ts, wo „localhost“
// andernfalls auf den Frontend-Container selbst statt auf das Backend verweisen würde.
const SERVER_API_BASE_URL =
    process.env.API_BASE_URL_INTERNAL ?? "http://localhost:8000";

// Ersatz, wenn die Antwort keine DRF-Fehlermeldung enthält (z. B. 502 vom
// Proxy): response.statusText wäre englisch und unter HTTP/2 meist leer.
export const GENERIC_ERROR_MESSAGE =
    "Что-то пошло не так. Попробуй ещё раз чуть позже.";

export type ApiFieldErrors = Record<string, string[]>;

export class ApiError extends Error {
    constructor(
        message: string,
        public status: number,
        public data?: unknown,
        public fieldErrors: ApiFieldErrors = {},
        public generalErrors: string[] = []
    ) {
        super(message);
        this.name = "ApiError";
    }
}

export function getApiBaseUrl(): string {
    return API_BASE_URL.replace(/\/$/, "");
}

export function getServerApiBaseUrl(): string {
    return SERVER_API_BASE_URL.replace(/\/$/, "");
}

export function extractApiErrors(data: unknown): {
    fieldErrors: ApiFieldErrors;
    generalErrors: string[];
} {
    const fieldErrors: ApiFieldErrors = {};
    const generalErrors: string[] = [];

    if (!data || typeof data !== "object") {
        return {fieldErrors, generalErrors};
    }

    const record = data as Record<string, unknown>;

    if (typeof record.detail === "string") {
        generalErrors.push(record.detail);
    } else if (Array.isArray(record.detail)) {
        generalErrors.push(
            ...record.detail.filter((item): item is string => typeof item === "string"),
        );
    }

    for (const [key, value] of Object.entries(record)) {
        if (key === "detail") continue;

        const messages = normalizeErrorMessages(value);
        if (messages.length === 0) continue;

        if (key === "non_field_errors") {
            generalErrors.push(...messages);
            continue;
        }

        fieldErrors[key] = messages;
    }

    return {fieldErrors, generalErrors};
}

function normalizeErrorMessages(value: unknown): string[] {
    if (typeof value === "string") return [value];
    if (!Array.isArray(value)) return [];

    return value.filter((item): item is string => typeof item === "string");
}

export function getAllApiErrorMessages(data: unknown): string[] {
    const {fieldErrors, generalErrors} = extractApiErrors(data);
    const fieldMessages = Object.values(fieldErrors).flat();
    return [...generalErrors, ...fieldMessages];
}

export async function apiFetch<T>(
    path: string,
    options: RequestInit = {},
    accessToken?: string | null
): Promise<T> {
    const headers = new Headers(options.headers);

    // Bei FormData setzt der Browser Content-Type samt multipart-Boundary
    // selbst; ein fester JSON-Header würde den Upload zerstören.
    if (
        !headers.has("Content-Type") &&
        options.body &&
        !(options.body instanceof FormData)
    ) {
        headers.set("Content-Type", "application/json");
    }

    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }

    const response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...options,
        headers,
    });

    const text = await response.text();
    const body = parseJsonBody(text);

    if (!response.ok) {
        const data = body.isJson ? body.data : null;
        const {fieldErrors, generalErrors} = extractApiErrors(data);
        const allMessages = [...generalErrors, ...Object.values(fieldErrors).flat()];
        const message = allMessages[0] ?? GENERIC_ERROR_MESSAGE;
        throw new ApiError(message, response.status, data, fieldErrors, generalErrors);
    }

    // Erfolg mit Nicht-JSON-Body (z. B. HTML-Seite eines Proxys oder einer
    // falsch konfigurierten API-URL) darf nicht als null-Daten durchrutschen –
    // die Aufrufer würden sonst mit einem leeren Ergebnis weiterarbeiten.
    if (!body.isJson) {
        throw new ApiError(GENERIC_ERROR_MESSAGE, response.status);
    }

    return body.data as T;
}

type ParsedBody = {isJson: true; data: unknown} | {isJson: false};

/**
 * Leerer Body (z. B. 204) gilt als JSON null. Fehlerantworten kommen nicht
 * immer von DRF (z. B. 413/502 als HTML vom Proxy) – dann ohne Body weiter,
 * damit kein SyntaxError den HTTP-Status verdeckt; die Meldung fällt auf
 * GENERIC_ERROR_MESSAGE zurück.
 */
function parseJsonBody(text: string): ParsedBody {
    if (!text.trim()) return {isJson: true, data: null};
    try {
        return {isJson: true, data: JSON.parse(text) as unknown};
    } catch {
        return {isJson: false};
    }
}
