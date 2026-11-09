import { NextResponse } from "next/server";
import { getServerApiBaseUrl } from "@/lib/api";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const source = searchParams.get("src");

  if (!source) {
    return new NextResponse("Missing src", { status: 400 });
  }

  // Ungültige oder fremde Quellen (auch data:-URLs, deren origin "null" ist)
  // sind ein Client-Fehler – kein 500 und kein Fetch.
  const sourceUrl = resolveImageSource(source);
  if (!sourceUrl) {
    return new NextResponse("Avatar source is not allowed", { status: 400 });
  }

  const response = await fetch(sourceUrl, { cache: "no-store" });

  if (!response.ok) {
    return new NextResponse("Avatar source is not available", {
      status: response.status,
    });
  }

  return new NextResponse(response.body, {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": response.headers.get("Content-Type") ?? "image/jpeg",
    },
  });
}

function resolveImageSource(source: string): string | null {
  const apiBaseUrl = getServerApiBaseUrl();

  if (source.startsWith("/")) {
    return `${apiBaseUrl}${source}`;
  }

  let sourceUrl: URL;
  try {
    sourceUrl = new URL(source);
  } catch {
    return null;
  }

  if (sourceUrl.origin !== new URL(apiBaseUrl).origin) {
    return null;
  }

  return sourceUrl.toString();
}
