import { NextResponse } from "next/server";

import { resolveUserContext } from "../../../../../lib/auth";
import { fetchConversationMessagesForUser } from "../../../../../lib/conversations";
import { ConversationMessagesResponse } from "../../../../../lib/types";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  context: { params: Promise<{ threadId: string }> },
): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const { threadId } = await context.params;
  const messages = await fetchConversationMessagesForUser(user.userId, threadId);
  if (messages === null) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const body: ConversationMessagesResponse = { messages };
  return NextResponse.json(body);
}