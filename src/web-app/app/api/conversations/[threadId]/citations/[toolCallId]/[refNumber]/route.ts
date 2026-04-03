import { NextResponse } from "next/server";

import { fetchAgent } from "../../../../../../../lib/agent";
import { resolveUserContext } from "../../../../../../../lib/auth";
import { getConversationForUser } from "../../../../../../../lib/conversations";
import { SearchCitationEnrichmentResponse } from "../../../../../../../lib/types";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  context: {
    params: Promise<{ threadId: string; toolCallId: string; refNumber: string }>;
  },
): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const { threadId, toolCallId, refNumber } = await context.params;

  const conversation = await getConversationForUser(user.userId, threadId);
  if (!conversation) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const upstreamResponse = await fetchAgent(
    request.headers,
    `/citations/${encodeURIComponent(threadId)}/${encodeURIComponent(toolCallId)}/${encodeURIComponent(refNumber)}`,
    { cache: "no-store" },
  );

  if (upstreamResponse.status === 404) {
    const body: SearchCitationEnrichmentResponse = { status: "missing" };
    return NextResponse.json(body);
  }

  if (!upstreamResponse.ok) {
    return NextResponse.json({ error: "agent_lookup_failed" }, { status: 502 });
  }

  const body = (await upstreamResponse.json()) as SearchCitationEnrichmentResponse;
  return NextResponse.json(body);
}