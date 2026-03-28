"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { useEffect, useState } from "react";

import { ConversationRecord } from "../lib/types";
import { CitationAwareAssistantMessage } from "./CitationAwareAssistantMessage";
import { ChatHistoryHydrator } from "./ChatHistoryHydrator";
import { CopilotMessageRenderer } from "./CopilotMessageRenderer";
import { ConversationSidebar } from "./ConversationSidebar";

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
          <p>Preparing the Copilot workspace…</p>
        </div>
      </main>
    );
  }

  return (
    <main className="workspaceShell">
      <div className="workspaceBackdrop" />
      <header className="workspaceTopbar">
        <div className="workspaceBrand">
          <div className="workspaceBrandMark">KB</div>
          <div>
            <p className="workspaceKicker">Contoso Robotics</p>
            <h1>Knowledge Copilot</h1>
            <p className="workspaceTopbarCopy">
              Chat-first workspace with AG-UI traces, persistent session memory, and inline citations.
            </p>
          </div>
        </div>
        <div className="workspaceTopbarMeta" aria-label="Workspace status">
          <div className="workspaceMetaCard accent">
            <span className="workspaceMetaLabel">Transport</span>
            <strong>AG-UI live</strong>
          </div>
          <div className="workspaceMetaCard">
            <span className="workspaceMetaLabel">Active thread</span>
            <strong>{activeConversation?.name ?? "New conversation"}</strong>
          </div>
        </div>
      </header>
      <section className="workspaceFrame">
        <ConversationSidebar
          activeThreadId={activeThreadId}
          conversations={conversations}
          onCreateConversation={handleCreateConversation}
          onSelectConversation={setActiveThreadId}
        />
        <div className="chatSurface">
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
                title: activeConversation?.name ?? "Knowledge Copilot",
                initial: [
                  "Ask about Azure AI Search, Content Understanding, or the Contoso Robotics knowledge base.",
                ],
                placeholder: "Ask a question about the knowledge base…",
              }}
              onSubmitMessage={(message) => void handleSubmitMessage(message)}
              RenderMessage={CopilotMessageRenderer as any}
              suggestions={conversationStarters}
            />
          </CopilotKit>
        </div>
      </section>
    </main>
  );
}