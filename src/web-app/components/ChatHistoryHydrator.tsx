"use client";

import { useCopilotChatInternal } from "@copilotkit/react-core";
import { useEffect } from "react";

import { ConversationMessagesResponse } from "../lib/types";

const EMPTY_HISTORY_RETRY_DELAYS_MS = [150, 400, 900] as const;

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function createAbortError(): Error {
  const error = new Error("The history request was aborted.");
  error.name = "AbortError";
  return error;
}

async function fetchConversationMessages(
  threadId: string,
  signal: AbortSignal,
): Promise<ConversationMessagesResponse> {
  try {
    const response = await fetch(`/api/conversations/${threadId}/messages`, {
      cache: "no-store",
      signal,
    });
    if (!response.ok) {
      return { messages: [] };
    }

    return (await response.json()) as ConversationMessagesResponse;
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }

    return { messages: [] };
  }
}

async function waitForRetry(delayMs: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    throw createAbortError();
  }

  await new Promise<void>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", abortHandler);
      resolve();
    }, delayMs);

    function abortHandler() {
      window.clearTimeout(timeoutId);
      reject(createAbortError());
    }

    signal.addEventListener("abort", abortHandler, { once: true });
  });
}

export function ChatHistoryHydrator({
  threadId,
  expectPersistedHistory = false,
  retryDelaysMs = EMPTY_HISTORY_RETRY_DELAYS_MS,
}: {
  threadId: string;
  expectPersistedHistory?: boolean;
  retryDelaysMs?: readonly number[];
}) {
  const { isAvailable, messages, setMessages } = useCopilotChatInternal();
  const hasMessages = messages.length > 0;

  useEffect(() => {
    if (expectPersistedHistory) {
      // For existing threads, let the AG-UI connect flow restore persisted
      // messages first. Only fall back to the conversation API if connect
      // completed and did not restore anything.
      if (hasMessages || !isAvailable) {
        return;
      }
    }

    const abortController = new AbortController();

    async function hydrateHistory() {
      let attempt = 0;

      while (true) {
        const response = await fetchConversationMessages(threadId, abortController.signal);
        const shouldRetryEmptyHistory =
          expectPersistedHistory &&
          response.messages.length === 0 &&
          attempt < retryDelaysMs.length;

        if (!shouldRetryEmptyHistory) {
          setMessages(response.messages as any);
          return;
        }

        await waitForRetry(retryDelaysMs[attempt] ?? 0, abortController.signal);
        attempt += 1;
      }
    }

    void hydrateHistory().catch((error) => {
      if (!isAbortError(error)) {
        setMessages([] as any);
      }
    });

    return () => {
      abortController.abort();
    };
  }, [expectPersistedHistory, hasMessages, isAvailable, retryDelaysMs, setMessages, threadId]);

  return null;
}