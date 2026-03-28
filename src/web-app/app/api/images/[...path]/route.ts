import { NextResponse } from "next/server";

import { downloadServingImage } from "../../../../lib/blob";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  if (!path || path.length < 2) {
    return NextResponse.json({ error: "invalid_path" }, { status: 400 });
  }

  const [articleId, ...imageParts] = path;
  const blob = await downloadServingImage(articleId, imageParts.join("/"));
  if (!blob) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const body = Uint8Array.from(blob.data);

  return new Response(body, {
    status: 200,
    headers: {
      "Cache-Control": "public, max-age=3600",
      "Content-Type": blob.contentType,
    },
  });
}