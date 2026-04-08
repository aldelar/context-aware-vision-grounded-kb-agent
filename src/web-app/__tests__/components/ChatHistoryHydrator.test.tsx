import { render, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ChatHistoryHydrator } from "../../components/ChatHistoryHydrator";

const setMessages = vi.fn();
let currentMessages: Array<Record<string, unknown>> = [];
let currentIsAvailable = true;

vi.mock("@copilotkit/react-core", () => ({
  useCopilotChatInternal: () => ({
    isAvailable: currentIsAvailable,
    messages: currentMessages,
    setMessages,
  }),
}));

describe("ChatHistoryHydrator", () => {
  beforeEach(() => {
    setMessages.mockReset();
    currentMessages = [];
    currentIsAvailable = true;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          messages: [
            {
              id: "assistant-1",
              role: "assistant",
              content: "Restored history",
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
              id: "reasoning-1",
              role: "reasoning",
              content: "Gathering the most relevant sections.",
            },
            {
              id: "tool-1",
              role: "tool",
              toolCallId: "tool-call-1",
              toolName: "search_knowledge_base",
              content: '{"results":[]}',
            },
          ],
        }),
      }),
    );
  });

  it("loads thread history into CopilotKit message state", async () => {
    render(<ChatHistoryHydrator threadId="thread-123" />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/conversations/thread-123/messages",
        expect.objectContaining({
          cache: "no-store",
          signal: expect.any(AbortSignal),
        }),
      );
      expect(setMessages).toHaveBeenCalledWith([
        {
          id: "assistant-1",
          role: "assistant",
          content: "Restored history",
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
          id: "reasoning-1",
          role: "reasoning",
          content: "Gathering the most relevant sections.",
        },
        {
          id: "tool-1",
          role: "tool",
          toolCallId: "tool-call-1",
          toolName: "search_knowledge_base",
          content: '{"results":[]}',
        },
      ]);
    });
  });

  it("clears the visible history when the API response fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
      }),
    );

    render(<ChatHistoryHydrator threadId="thread-404" />);

    await waitFor(() => {
      expect(setMessages).toHaveBeenCalledWith([]);
    });
  });

  it("retries a transient empty history response for persisted threads", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ messages: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            messages: [
              {
                id: "assistant-2",
                role: "assistant",
                content: "Recovered after a delayed session save.",
              },
            ],
          }),
        }),
    );

    render(
      <ChatHistoryHydrator
        expectPersistedHistory
        retryDelaysMs={[1]}
        threadId="thread-delayed"
      />,
    );

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    await waitFor(() => {
      expect(setMessages).toHaveBeenCalledWith([
        {
          id: "assistant-2",
          role: "assistant",
          content: "Recovered after a delayed session save.",
        },
      ]);
    });
    expect(setMessages).toHaveBeenCalledTimes(1);
    expect(setMessages).not.toHaveBeenCalledWith([]);
  });

  it("waits for AG-UI connect before falling back for persisted threads", () => {
    currentIsAvailable = false;

    render(
      <ChatHistoryHydrator
        expectPersistedHistory
        threadId="thread-connect-pending"
      />,
    );

    expect(fetch).not.toHaveBeenCalled();
    expect(setMessages).not.toHaveBeenCalled();
  });

  it("does not overwrite persisted threads once AG-UI already restored messages", () => {
    currentIsAvailable = true;
    currentMessages = [
      {
        id: "assistant-restored",
        role: "assistant",
        content: "Restored by AG-UI connect.",
      },
    ];

    render(
      <ChatHistoryHydrator
        expectPersistedHistory
        threadId="thread-restored"
      />,
    );

    expect(fetch).not.toHaveBeenCalled();
    expect(setMessages).not.toHaveBeenCalled();
  });

  it("falls back to the conversation API after connect settles without restored messages", async () => {
    currentIsAvailable = true;
    currentMessages = [];

    render(
      <ChatHistoryHydrator
        expectPersistedHistory
        threadId="thread-fallback"
      />,
    );

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/conversations/thread-fallback/messages",
        expect.objectContaining({
          cache: "no-store",
          signal: expect.any(AbortSignal),
        }),
      );
    });
  });
});