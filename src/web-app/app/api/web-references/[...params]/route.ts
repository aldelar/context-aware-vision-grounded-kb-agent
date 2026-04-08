import { NextRequest, NextResponse } from "next/server";

/**
 * Web references proxy API.
 *
 * Fetches and returns a section of a web page referenced by a web search citation.
 * Route: GET /api/web-references/:sourceUrl/:anchor?
 *
 * The sourceUrl is URL-encoded in the path parameter.
 */

const MAX_SNIPPET_LENGTH = 2000;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ params: string[] }> },
) {
  const resolvedParams = await params;
  const segments = resolvedParams.params;

  if (!segments || segments.length < 1) {
    return NextResponse.json(
      { status: "missing", error: "Source URL is required" },
      { status: 400 },
    );
  }

  const sourceUrl = decodeURIComponent(segments[0]);
  const anchor = segments[1] ? decodeURIComponent(segments[1]) : "";

  // Validate URL is from an allowed domain
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(sourceUrl);
  } catch {
    return NextResponse.json(
      { status: "missing", error: "Invalid source URL" },
      { status: 400 },
    );
  }

  const allowedDomains = ["learn.microsoft.com"];
  const isAllowed = allowedDomains.some(
    (domain) =>
      parsedUrl.hostname === domain ||
      parsedUrl.hostname.endsWith(`.${domain}`),
  );

  if (!isAllowed) {
    return NextResponse.json(
      { status: "missing", error: "Domain not in allowed list" },
      { status: 403 },
    );
  }

  try {
    const response = await fetch(sourceUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; KBAgent/1.0)",
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      return NextResponse.json(
        { status: "missing", error: `Upstream returned ${response.status}` },
        { status: 502 },
      );
    }

    const html = await response.text();

    // Extract text content  — simple extraction for citation display
    const textContent = html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, MAX_SNIPPET_LENGTH);

    return NextResponse.json({
      status: "ready",
      citation: {
        source_url: sourceUrl,
        anchor,
        content: textContent,
        title: parsedUrl.pathname.split("/").pop() || "",
      },
    });
  } catch (error) {
    return NextResponse.json(
      { status: "missing", error: "Failed to fetch source page" },
      { status: 502 },
    );
  }
}
