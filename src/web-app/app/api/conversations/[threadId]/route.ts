import { NextResponse } from "next/server";

import { resolveUserContext } from "../../../../lib/auth";
import {
  deleteConversationForUser,
  getConversationForUser,
  updateConversationForUser,
} from "../../../../lib/conversations";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  context: { params: Promise<{ threadId: string }> },
): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const { threadId } = await context.params;
  const conversation = await getConversationForUser(user.userId, threadId);
  if (!conversation) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  return NextResponse.json(conversation);
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ threadId: string }> },
): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const { threadId } = await context.params;
  const body = (await request.json().catch(() => ({}))) as { title?: string };
  const conversation = await updateConversationForUser(user.userId, threadId, body);
  if (!conversation) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  return NextResponse.json(conversation);
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ threadId: string }> },
): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const { threadId } = await context.params;
  const deleted = await deleteConversationForUser(user.userId, threadId);
  return deleted
    ? new NextResponse(null, { status: 204 })
    : NextResponse.json({ error: "not_found" }, { status: 404 });
}