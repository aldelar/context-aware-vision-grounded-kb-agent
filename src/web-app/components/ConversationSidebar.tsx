"use client";

import { ConversationRecord } from "../lib/types";

type ConversationSidebarProps = {
  activeThreadId: string | null;
  conversations: ConversationRecord[];
  onCreateConversation: () => Promise<void>;
  onSelectConversation: (threadId: string) => void;
};

export function ConversationSidebar({
  activeThreadId,
  conversations,
  onCreateConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  return (
    <aside className="conversationRail">
      <div className="conversationRailHeader">
        <div>
          <p className="conversationRailLabel">Workspace</p>
          <h2 className="conversationRailTitle">Threads</h2>
        </div>
        <button className="conversationCreateButton" onClick={() => void onCreateConversation()} type="button">
          New chat
        </button>
      </div>
      <div className="conversationRailIntro">
        <strong>{conversations.length}</strong>
        <span>Session{conversations.length === 1 ? "" : "s"} with restorable AG-UI history.</span>
      </div>
      <div className="conversationList" role="list">
        {conversations.map((conversation) => (
          <button
            className={`conversationItem${conversation.id === activeThreadId ? " active" : ""}`}
            key={conversation.id}
            onClick={() => onSelectConversation(conversation.id)}
            type="button"
          >
            <span className="conversationItemTitle">{conversation.name}</span>
            <span className="conversationItemMeta">
              <small>{new Date(conversation.updatedAt).toLocaleDateString()}</small>
              {conversation.id === activeThreadId ? <em>Live</em> : null}
            </span>
          </button>
        ))}
      </div>
      <div className="conversationRailFooter">
        <p>Tool activity, search citations, and session turns stay attached to the selected thread.</p>
      </div>
    </aside>
  );
}