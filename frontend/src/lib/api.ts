const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export function extractApiErrors(data: unknown): {
  fieldErrors: ApiFieldErrors;
  generalErrors: string[];
} {
  const fieldErrors: ApiFieldErrors = {};
  const generalErrors: string[] = [];

  if (!data || typeof data !== "object") {
    return { fieldErrors, generalErrors };
  }

  const record = data as Record<string, unknown>;

  if (typeof record.detail === "string") {
    generalErrors.push(record.detail);
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

  return { fieldErrors, generalErrors };
}

function normalizeErrorMessages(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (!Array.isArray(value)) return [];

  return value.filter((item): item is string => typeof item === "string");
}

export function getAllApiErrorMessages(data: unknown): string[] {
  const { fieldErrors, generalErrors } = extractApiErrors(data);
  const fieldMessages = Object.values(fieldErrors).flat();
  return [...generalErrors, ...fieldMessages];
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null
): Promise<T> {
  const headers = new Headers(options.headers);

  if (!headers.has("Content-Type") && options.body) {
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
  const data = text ? (JSON.parse(text) as unknown) : null;

  if (!response.ok) {
    const { fieldErrors, generalErrors } = extractApiErrors(data);
    const allMessages = [...generalErrors, ...Object.values(fieldErrors).flat()];
    const message = allMessages[0] ?? response.statusText;
    throw new ApiError(message, response.status, data, fieldErrors, generalErrors);
  }

  return data as T;
}
