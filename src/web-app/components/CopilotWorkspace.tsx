"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { useEffect, useRef, useState } from "react";

import { ConversationRecord } from "../lib/types";
import { CitationAwareAssistantMessage } from "./CitationAwareAssistantMessage";
import { CitationDialog } from "./CitationDialog";
import { CitationDialogProvider, useCitationDialog } from "./CitationDialogContext";
import { ChatHistoryHydrator } from "./ChatHistoryHydrator";
import { CopilotMessageRenderer } from "./CopilotMessageRenderer";
import { ConversationThreadProvider } from "./ConversationThreadContext";
import { ConversationSidebar } from "./ConversationSidebar";

/** Clears the citation registry when the active thread changes. */
function CitationClearer({ threadId }: { threadId: string | null }) {
  const { clearCitations } = useCitationDialog();
  const prevThreadId = useRef<string | null>(null);

  useEffect(() => {
    if (prevThreadId.current !== null && prevThreadId.current !== threadId) {
      clearCitations();
    }
    prevThreadId.current = threadId;
  }, [threadId, clearCitations]);

  return null;
}

const conversationStarters = [
  {
    title: "Content Understanding",
    message: "What are the key components of Azure Content Understanding?",
  },
  {
    title: "Agentic Retrieval",
    message: "How does agentic retrieval work in Azure AI Search?",
  },
  {
    title: "Cosmos DB",
    message: "What are the partition key strategies for Azure Cosmos DB?",
  },
  {
    title: "Search Security",
    message: "What are the network security options for Azure AI Search?",
  },
];

async function fetchConversations(): Promise<ConversationRecord[]> {
  const response = await fetch("/api/conversations", { cache: "no-store" });
  if (!response.ok) {
    return [];
  }
  return (await response.json()) as ConversationRecord[];
}

async function createConversation(title?: string): Promise<ConversationRecord> {
  const response = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error("Failed to create conversation");
  }
  return (await response.json()) as ConversationRecord;
}

async function updateConversation(threadId: string, title: string): Promise<void> {
  await fetch(`/api/conversations/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

async function deleteConversation(threadId: string): Promise<void> {
  const response = await fetch(`/api/conversations/${threadId}`, {
    method: "DELETE",
  });

  if (!response.ok && response.status !== 204) {
    throw new Error("Failed to delete conversation");
  }
}

export function CopilotWorkspace() {
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const existing = await fetchConversations();
      if (cancelled) {
        return;
      }

      if (existing.length > 0) {
        setConversations(existing);
        setActiveThreadId(existing[0].id);
        setIsReady(true);
        return;
      }

      const created = await createConversation();
      if (cancelled) {
        return;
      }

      setConversations([created]);
      setActiveThreadId(created.id);
      setIsReady(true);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreateConversation(): Promise<void> {
    const created = await createConversation();
    setConversations((current) => [created, ...current]);
    setActiveThreadId(created.id);
  }

  async function handleRenameConversation(threadId: string, nextTitle: string): Promise<void> {
    const currentConversation = conversations.find((conversation) => conversation.id === threadId);
    if (!currentConversation) {
      return;
    }

    const normalizedTitle = nextTitle.trim();
    if (!normalizedTitle || normalizedTitle === currentConversation.name) {
      return;
    }

    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === threadId
          ? {
              ...conversation,
              name: normalizedTitle,
              updatedAt: new Date().toISOString(),
            }
          : conversation,
      ),
    );

    await updateConversation(threadId, normalizedTitle);
  }

  async function handleDeleteConversation(threadId: string): Promise<void> {
    const currentConversation = conversations.find((conversation) => conversation.id === threadId);
    if (!currentConversation) {
      return;
    }

    await deleteConversation(threadId);

    const remaining = conversations.filter((conversation) => conversation.id !== threadId);
    if (remaining.length === 0) {
      const created = await createConversation();
      setConversations([created]);
      setActiveThreadId(created.id);
      return;
    }

    setConversations(remaining);
    if (activeThreadId === threadId) {
      setActiveThreadId(remaining[0].id);
    }
  }

  async function handleSubmitMessage(message: string): Promise<void> {
    if (!activeThreadId) {
      return;
    }

    const title = message.trim().slice(0, 80) || "New conversation";
    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === activeThreadId
          ? {
              ...conversation,
              name: conversation.name === "New conversation" ? title : conversation.name,
              updatedAt: new Date().toISOString(),
            }
          : conversation,
      ),
    );

    await updateConversation(activeThreadId, title);
  }

  const activeConversation = conversations.find((conversation) => conversation.id === activeThreadId) ?? null;

  if (!isReady || !activeThreadId) {
    return (
      <main className="workspaceShell loadingState">
        <div className="loadingCard">
          <p>Preparing the Azure AI knowledge workspace…</p>
        </div>
      </main>
    );
  }

  return (
    <main className="workspaceShell">
      <header className="workspaceHeader">
        <p className="workspaceEyebrow">Reference Implementation</p>
        <h1>Azure AI Knowledge Agent</h1>
        <p className="workspaceDescription">
          Context-Aware Vision Grounded Knowledge Based Agent / built with Azure AI Search, Microsoft Foundry and the Microsoft Agent Framework with the AG-UI protocol
        </p>
      </header>
      <section className="workspaceFrame">
        <ConversationSidebar
          activeThreadId={activeThreadId}
          conversations={conversations}
          onCreateConversation={handleCreateConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          onSelectConversation={setActiveThreadId}
        />
        <section className="chatSurface">
          <ConversationThreadProvider threadId={activeThreadId}>
            <CitationDialogProvider>
            <CitationClearer threadId={activeThreadId} />
            <CopilotKit
              agent="default"
              key={activeThreadId}
              runtimeUrl="/api/copilotkit"
              showDevConsole={false}
              threadId={activeThreadId}
            >
              <ChatHistoryHydrator threadId={activeThreadId} />
              <CopilotChat
                AssistantMessage={CitationAwareAssistantMessage}
                className="copilotCanvas"
                instructions="Answer from the indexed knowledge base, keep citations intact, and preserve any inline /api/images markdown emitted by the agent."
                labels={{
                  title: activeConversation?.name ?? "Azure AI Knowledge Agent",
                  initial: [
                    "Ask me anything about Azure — I can search our internal knowledge base and the web.",
                  ],
                  placeholder: "Ask a question about Azure…",
                }}
                onSubmitMessage={(message) => void handleSubmitMessage(message)}
                RenderMessage={CopilotMessageRenderer as any}
                suggestions={conversationStarters}
              />
            </CopilotKit>
            <CitationDialog />
            </CitationDialogProvider>
          </ConversationThreadProvider>
        </section>
      </section>
    </main>
  );
}