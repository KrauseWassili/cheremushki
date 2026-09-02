import { NextResponse } from "next/server";
import { getApiBaseUrl } from "@/lib/api";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const source = searchParams.get("src");

  if (!source) {
    return new NextResponse("Missing src", { status: 400 });
  }

  const sourceUrl = resolveImageSource(source);
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

function resolveImageSource(source: string) {
  if (source.startsWith("/")) {
    return `${getApiBaseUrl()}${source}`;
  }

  const apiBaseUrl = getApiBaseUrl();
  const sourceUrl = new URL(source);
  const apiUrl = new URL(apiBaseUrl);

  if (sourceUrl.origin !== apiUrl.origin) {
    throw new Error("Avatar source origin is not allowed");
  }

  return sourceUrl.toString();
}
