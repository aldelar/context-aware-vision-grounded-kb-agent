"use client";

import { useCopilotChatInternal } from "@copilotkit/react-core";
import { useEffect } from "react";

import { ConversationMessagesResponse } from "../lib/types";

async function fetchConversationMessages(threadId: string): Promise<ConversationMessagesResponse> {
  const response = await fetch(`/api/conversations/${threadId}/messages`, { cache: "no-store" });
  if (!response.ok) {
    return { messages: [] };
  }

  return (await response.json()) as ConversationMessagesResponse;
}

export function ChatHistoryHydrator({ threadId }: { threadId: string }) {
  const { setMessages } = useCopilotChatInternal();

  useEffect(() => {
    let cancelled = false;

    async function hydrateHistory() {
      const response = await fetchConversationMessages(threadId);
      if (!cancelled) {
        setMessages(response.messages as any);
      }
    }

    void hydrateHistory();
    return () => {
      cancelled = true;
    };
  }, [setMessages, threadId]);

  return null;
}