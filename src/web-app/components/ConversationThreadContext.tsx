"use client";

import { createContext, ReactNode, useContext } from "react";

const ConversationThreadContext = createContext<string | null>(null);

export function ConversationThreadProvider({
  children,
  threadId,
}: {
  children: ReactNode;
  threadId: string | null;
}) {
  return (
    <ConversationThreadContext.Provider value={threadId}>
      {children}
    </ConversationThreadContext.Provider>
  );
}

export function useConversationThreadId(): string | null {
  return useContext(ConversationThreadContext);
}