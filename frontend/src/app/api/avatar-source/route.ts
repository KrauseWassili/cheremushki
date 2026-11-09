import { NextResponse } from "next/server";
import { getApiBaseUrl, getServerApiBaseUrl } from "@/lib/api";

// Der Handler ist ohne Login erreichbar. Deshalb nur exakt die Form, die das
// Backend für öffentliche Avatare erzeugt (avatar_upload_to in
// backend/apps/profiles/models.py: avatars/<uuid4.hex>.<ext>) – keine
// Originale (avatars/originals/ ist nicht öffentlich), keine Query, kein
// anderer Pfad. Sonst wäre das hier ein offener Proxy ins interne Netz.
const AVATAR_PATH_PATTERN = /^\/media\/avatars\/[0-9a-f]{32}\.(jpg|jpeg|png|webp)$/;
const ALLOWED_CONTENT_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
// Entspricht MAX_AVATAR_UPLOAD_BYTES im Backend; gespeicherte Avatare sind
// neu kodiert und deutlich kleiner.
const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
const FETCH_TIMEOUT_MS = 10_000;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const source = searchParams.get("src");

  if (!source) {
    return errorResponse("Missing src", 400);
  }

  const avatarPath = resolveAvatarPath(source);
  if (!avatarPath) {
    return errorResponse("Avatar source is not allowed", 400);
  }

  // Abgerufen wird immer über die interne Basis, auch wenn die URL mit dem
  // öffentlichen Origin kam: Aus dem Container ist der öffentliche Host oft
  // gar nicht (oder nur über einen Umweg über den Proxy) erreichbar.
  let response: Response;
  try {
    response = await fetch(`${getServerApiBaseUrl()}${avatarPath}`, {
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return errorResponse("Avatar source timed out", 504);
    }
    return errorResponse("Avatar source is not available", 502);
  }

  if (response.status === 404) {
    await response.body?.cancel();
    return errorResponse("Avatar not found", 404);
  }

  // Redirects (redirect: "manual" → 3xx bzw. opaqueredirect) gelten als
  // Fehler: Ein Ziel außerhalb der Allowlist darf nicht nachgeladen werden.
  if (!response.ok || response.type === "opaqueredirect") {
    await response.body?.cancel();
    return errorResponse("Avatar source is not available", 502);
  }

  const contentType = parseMediaType(response.headers.get("Content-Type"));
  if (!contentType || !ALLOWED_CONTENT_TYPES.has(contentType)) {
    await response.body?.cancel();
    return errorResponse("Avatar source is not available", 502);
  }

  const declaredLength = Number(response.headers.get("Content-Length"));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_AVATAR_BYTES) {
    await response.body?.cancel();
    return errorResponse("Avatar source is too large", 502);
  }

  // Content-Length kann fehlen (chunked) oder lügen – deshalb beim Lesen
  // mitzählen und abbrechen, statt erst den ganzen Body zu puffern.
  let body: Uint8Array;
  try {
    body = await readLimitedBody(response, MAX_AVATAR_BYTES);
  } catch (error) {
    if (error instanceof BodyTooLargeError) {
      return errorResponse("Avatar source is too large", 502);
    }
    return errorResponse("Avatar source is not available", 502);
  }

  return new NextResponse(body as BodyInit, {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": contentType,
      "Content-Length": String(body.byteLength),
      "X-Content-Type-Options": "nosniff",
    },
  });
}

/**
 * Liefert den Avatar-Pfad, wenn die Quelle erlaubt ist.
 *
 * Relative Pfade werden unverändert geprüft. Absolute URLs kommen aus
 * avatar_url (build_absolute_uri im Backend) und tragen daher den
 * öffentlichen Origin – sie werden akzeptiert, wenn der Origin zur
 * öffentlichen API-/Site-Basis oder zur internen Basis gehört; übernommen
 * wird nur der Pfad.
 */
function resolveAvatarPath(source: string): string | null {
  if (source.startsWith("/")) {
    return AVATAR_PATH_PATTERN.test(source) ? source : null;
  }

  let sourceUrl: URL;
  try {
    sourceUrl = new URL(source);
  } catch {
    return null;
  }

  if (
    !getTrustedOrigins().has(sourceUrl.origin) ||
    sourceUrl.username ||
    sourceUrl.password ||
    sourceUrl.search ||
    sourceUrl.hash
  ) {
    return null;
  }

  return AVATAR_PATH_PATTERN.test(sourceUrl.pathname)
    ? sourceUrl.pathname
    : null;
}

function getTrustedOrigins(): Set<string> {
  const origins = new Set<string>();
  for (const base of [
    getApiBaseUrl(),
    process.env.NEXT_PUBLIC_SITE_URL,
    getServerApiBaseUrl(),
  ]) {
    if (!base) continue;
    try {
      const { origin, protocol } = new URL(base);
      // data:/blob: haben den Origin "null" – nie als vertrauenswürdig zählen.
      if (protocol === "http:" || protocol === "https:") origins.add(origin);
    } catch {
      // Ungültige Basis-URL: einfach nicht vertrauen.
    }
  }
  return origins;
}

function parseMediaType(header: string | null): string | null {
  if (!header) return null;
  return header.split(";", 1)[0].trim().toLowerCase() || null;
}

class BodyTooLargeError extends Error {}

async function readLimitedBody(
  response: Response,
  maxBytes: number,
): Promise<Uint8Array> {
  if (!response.body) throw new Error("Missing body");

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      throw new BodyTooLargeError();
    }
    chunks.push(value);
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

function errorResponse(message: string, status: number) {
  return new NextResponse(message, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}
