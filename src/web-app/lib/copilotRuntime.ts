type RepairResult = {
  body: unknown;
  missingToolCallIds?: string[];
  repaired: boolean;
  repairedMessageCount: number;
  requestMessageCount: number;
  threadId?: string;
};

export async function repairCopilotRuntimeRequest(body: unknown, _headers: Headers): Promise<RepairResult> {
  const record = body && typeof body === "object" ? body as Record<string, unknown> : {};
  const messages = Array.isArray(record.messages) ? record.messages : [];

  return {
    body,
    missingToolCallIds: [],
    repaired: false,
    repairedMessageCount: messages.length,
    requestMessageCount: messages.length,
    threadId: typeof record.threadId === "string" ? record.threadId : undefined,
  };
}