import { DELETE, GET as conversationGET, PATCH } from "../../app/api/conversations/[threadId]/route";
import { GET as citationsGET } from "../../app/api/conversations/[threadId]/citations/[toolCallId]/[refNumber]/route";
import { GET as messagesGET } from "../../app/api/conversations/[threadId]/messages/route";
import { GET as listGET, POST } from "../../app/api/conversations/route";
import { resetConversationStoreForTests, seedConversationMessagesForTests } from "../../lib/conversations";

function buildRequest(path: string, init: RequestInit = {}, userId = "user-a"): Request {
  const headers = new Headers(init.headers);
  headers.set("x-ms-client-principal-id", userId);

  return new Request(`http://localhost${path}`, {
    ...init,
    headers,
  });
}

describe("conversation routes", () => {
  beforeEach(() => {
    resetConversationStoreForTests();
    process.env.COSMOS_ENDPOINT = "";
    vi.restoreAllMocks();
  });

  it("creates and lists conversations for the authenticated owner", async () => {
    const createResponse = await POST(
      buildRequest("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "First thread" }),
      }),
    );

    expect(createResponse.status).toBe(201);
    const created = (await createResponse.json()) as { id: string; name: string; userId: string };
    expect(created.name).toBe("First thread");
    expect(created.userId).toBe("user-a");

    const listResponse = await listGET(buildRequest("/api/conversations"));
    const conversations = (await listResponse.json()) as Array<{ id: string; name: string }>;

    expect(conversations).toHaveLength(1);
    expect(conversations[0]).toMatchObject({ id: created.id, name: "First thread" });
  });

  it("applies owner-only updates and hides threads from other users", async () => {
    const createResponse = await POST(
      buildRequest("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "Rename me" }),
      }),
    );
    const created = (await createResponse.json()) as { id: string };

    const patchResponse = await PATCH(
      buildRequest(
        `/api/conversations/${created.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ title: "Renamed thread" }),
        },
        "user-a",
      ),
      { params: Promise.resolve({ threadId: created.id }) },
    );

    expect(patchResponse.status).toBe(200);
    expect(await patchResponse.json()).toMatchObject({ id: created.id, name: "Renamed thread" });

    const otherUserResponse = await conversationGET(
      buildRequest(`/api/conversations/${created.id}`, {}, "user-b"),
      { params: Promise.resolve({ threadId: created.id }) },
    );

    expect(otherUserResponse.status).toBe(404);
  });

  it("returns structured history only for the owning user", async () => {
    const createResponse = await POST(
      buildRequest("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "Resume thread" }),
      }),
    );
    const created = (await createResponse.json()) as { id: string };

    seedConversationMessagesForTests(created.id, {
      id: created.id,
      session: {
        state: {
          messages: [
            {
              id: "assistant-1",
              role: "assistant",
              content: "I searched the index.",
              toolCalls: [
                {
                  id: "tool-call-1",
                  function: {
                    name: "search_knowledge_base",
                    arguments: { query: "azure ai search" },
                  },
                },
              ],
            },
            {
              id: "tool-1",
              role: "tool",
              toolCallId: "tool-call-1",
              toolName: "search_knowledge_base",
              content: { results: [{ title: "Azure AI Search" }] },
            },
          ],
        },
      },
    });

    const historyResponse = await messagesGET(
      buildRequest(`/api/conversations/${created.id}/messages`),
      { params: Promise.resolve({ threadId: created.id }) },
    );

    expect(historyResponse.status).toBe(200);
    expect(await historyResponse.json()).toEqual({
      messages: [
        {
          id: "assistant-1",
          role: "assistant",
          content: "I searched the index.",
          toolCalls: [
            {
              id: "tool-call-1",
              type: "function",
              function: {
                name: "search_knowledge_base",
                arguments: '{"query":"azure ai search"}',
              },
            },
          ],
        },
        {
          id: "tool-1",
          role: "tool",
          toolCallId: "tool-call-1",
          toolName: "search_knowledge_base",
          content: '{"results":[{"title":"Azure AI Search"}]}',
        },
      ],
    });

    const forbiddenResponse = await messagesGET(
      buildRequest(`/api/conversations/${created.id}/messages`, {}, "user-b"),
      { params: Promise.resolve({ threadId: created.id }) },
    );

    expect(forbiddenResponse.status).toBe(404);
  });

  it("deletes only the owner record", async () => {
    const createResponse = await POST(
      buildRequest("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "Delete me" }),
      }),
    );
    const created = (await createResponse.json()) as { id: string };

    const deleteResponse = await DELETE(
      buildRequest(`/api/conversations/${created.id}`, { method: "DELETE" }),
      { params: Promise.resolve({ threadId: created.id }) },
    );

    expect(deleteResponse.status).toBe(204);

    const listResponse = await listGET(buildRequest("/api/conversations"));
    expect(await listResponse.json()).toEqual([]);
  });

  it("proxies transcript-scoped citation enrichment only for the owning user", async () => {
    const createResponse = await POST(
      buildRequest("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "Citation thread" }),
      }),
    );
    const created = (await createResponse.json()) as { id: string };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ready",
          citation: {
            ref_number: 1,
            chunk_id: "article-1_0",
            content: "Full chunk content loaded on demand.",
            content_source: "full",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await citationsGET(
      buildRequest(`/api/conversations/${created.id}/citations/tool-call-1/1`),
      { params: Promise.resolve({ threadId: created.id, toolCallId: "tool-call-1", refNumber: "1" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      status: "ready",
      citation: {
        ref_number: 1,
        chunk_id: "article-1_0",
        content: "Full chunk content loaded on demand.",
        content_source: "full",
      },
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const forbiddenResponse = await citationsGET(
      buildRequest(`/api/conversations/${created.id}/citations/tool-call-1/1`, {}, "user-b"),
      { params: Promise.resolve({ threadId: created.id, toolCallId: "tool-call-1", refNumber: "1" }) },
    );

    expect(forbiddenResponse.status).toBe(404);
  });
});