import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConversationSidebar } from "../../components/ConversationSidebar";
import { ConversationRecord } from "../../lib/types";

const conversations: ConversationRecord[] = [
  {
    id: "thread-1",
    userId: "user-1",
    userIdentifier: "user@example.com",
    name: "What are the network security options for Azure AI Search?",
    createdAt: "2026-03-31T09:19:23Z",
    updatedAt: "2026-03-31T09:20:51Z",
  },
  {
    id: "thread-2",
    userId: "user-1",
    userIdentifier: "user@example.com",
    name: "security question",
    createdAt: "2026-03-31T09:03:14Z",
    updatedAt: "2026-03-31T09:03:14Z",
  },
];

describe("ConversationSidebar", () => {
  it("renders the streamlined rail and active conversation styling", () => {
    render(
      <ConversationSidebar
        activeThreadId="thread-1"
        conversations={conversations}
        onCreateConversation={vi.fn().mockResolvedValue(undefined)}
        onDeleteConversation={vi.fn().mockResolvedValue(undefined)}
        onRenameConversation={vi.fn().mockResolvedValue(undefined)}
        onSelectConversation={vi.fn()}
      />,
    );

    expect(screen.queryByText("Conversations")).not.toBeInTheDocument();
    expect(screen.queryByText("Conversation history")).not.toBeInTheDocument();
    expect(screen.queryByText(/saved threads with restorable AG-UI history/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Active")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New chat" })).toBeInTheDocument();
    expect(screen.getByText(/Powered by the AG‑UI protocol/i)).toBeInTheDocument();
    expect(screen.getByText(conversations[0].name).closest("article")).toHaveClass("active");
  });

  it("renames a conversation through inline editing on double click", async () => {
    const user = userEvent.setup();
    const onRenameConversation = vi.fn().mockResolvedValue(undefined);

    render(
      <ConversationSidebar
        activeThreadId="thread-1"
        conversations={conversations}
        onCreateConversation={vi.fn().mockResolvedValue(undefined)}
        onDeleteConversation={vi.fn().mockResolvedValue(undefined)}
        onRenameConversation={onRenameConversation}
        onSelectConversation={vi.fn()}
      />,
    );

    await user.dblClick(screen.getByText(conversations[0].name));

    const input = screen.getByRole("textbox", { name: `Rename ${conversations[0].name}` });
    await user.clear(input);
    await user.type(input, "Updated Azure AI Search question{enter}");

    expect(onRenameConversation).toHaveBeenCalledWith("thread-1", "Updated Azure AI Search question");
  });

  it("opens a custom confirmation dialog before deleting a conversation", async () => {
    const user = userEvent.setup();
    const onDeleteConversation = vi.fn().mockResolvedValue(undefined);

    render(
      <ConversationSidebar
        activeThreadId="thread-1"
        conversations={conversations}
        onCreateConversation={vi.fn().mockResolvedValue(undefined)}
        onDeleteConversation={onDeleteConversation}
        onRenameConversation={vi.fn().mockResolvedValue(undefined)}
        onSelectConversation={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: `Delete ${conversations[0].name}` }));

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText(`Remove “${conversations[0].name}”?`)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete conversation" }));

    expect(onDeleteConversation).toHaveBeenCalledWith("thread-1");
  });
});