import { NextResponse } from "next/server";

import { resolveUserContext } from "../../../lib/auth";
import {
  createConversationForUser,
  listConversationsForUser,
} from "../../../lib/conversations";

export const runtime = "nodejs";

export async function GET(request: Request): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const conversations = await listConversationsForUser(user.userId);
  return NextResponse.json(conversations);
}

export async function POST(request: Request): Promise<Response> {
  const user = resolveUserContext(request.headers);
  const body = (await request.json().catch(() => ({}))) as { id?: string; title?: string };
  const conversation = await createConversationForUser(user, body);
  return NextResponse.json(conversation, { status: 201 });
}