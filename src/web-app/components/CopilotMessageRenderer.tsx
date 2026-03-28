"use client";

import { ReactNode } from "react";

import { coerceMessageContent } from "../lib/messageContent";
import { SearchToolRenderer } from "./SearchToolRenderer";

type ToolCallLike = {
  id: string;
  type?: string;
  function?: {
    name?: string;
    arguments?: unknown;
  };
};

type AgUiMessageLike = {
  id: string;
  role: string;
  content?: unknown;
  toolCalls?: ToolCallLike[];
  toolCallId?: string;
  toolName?: string;
  generativeUI?: () => ReactNode;
  image?: unknown;
};

type CopilotMessageRendererProps = {
  message: AgUiMessageLike;
  messages: AgUiMessageLike[];
  inProgress: boolean;
  index: number;
  isCurrentMessage: boolean;
  AssistantMessage?: React.ComponentType<any>;
  UserMessage?: React.ComponentType<any>;
  ImageRenderer?: React.ComponentType<any>;
  onRegenerate?: (messageId: string) => void;
  onCopy?: (message: string) => void;
  onThumbsUp?: (message: AgUiMessageLike) => void;
  onThumbsDown?: (message: AgUiMessageLike) => void;
  messageFeedback?: Record<string, "thumbsUp" | "thumbsDown">;
  markdownTagRenderers?: Record<string, React.ComponentType<any>>;
};

function parseJsonPayload(value: unknown): unknown {
  if (typeof value !== "string") {
    return value;
  }

  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function parseToolArgs(toolCall: ToolCallLike): Record<string, unknown> | undefined {
  const parsed = parseJsonPayload(toolCall.function?.arguments);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return undefined;
  }

  return parsed as Record<string, unknown>;
}

function findToolResultMessage(messages: AgUiMessageLike[], toolCallId: string): AgUiMessageLike | undefined {
  return messages.find((message) => message.role === "tool" && message.toolCallId === toolCallId);
}

function formatToolResultPreview(result: unknown): string | null {
  const normalized = coerceMessageContent(result);
  if (normalized) {
    return normalized;
  }

  if (result && typeof result === "object") {
    try {
      return JSON.stringify(result, null, 2);
    } catch {
      return null;
    }
  }

  return null;
}

function renderToolCall(
  toolCall: ToolCallLike,
  messages: AgUiMessageLike[],
  isInProgress: boolean,
): ReactNode {
  const toolName = toolCall.function?.name ?? "unknown_tool";
  const args = parseToolArgs(toolCall);
  const toolResultMessage = findToolResultMessage(messages, toolCall.id);
  const parsedResult = parseJsonPayload(toolResultMessage?.content);
  const status = toolResultMessage ? "complete" : isInProgress ? "executing" : "inProgress";

  if (toolName === "search_knowledge_base") {
    return <SearchToolRenderer args={args} result={parsedResult as any} status={status} />;
  }

  const toolLabel = coerceMessageContent(toolName) ?? "Agent tool";
  const resultPreview = formatToolResultPreview(parsedResult);

  return (
    <section className="toolCard fallbackTool" data-status={status}>
      <div className="toolCardHeader">
        <span className="toolCardEyebrow">Tool Activity</span>
        <span className={`toolCardStatus${status !== "complete" ? " working" : ""}`}>
          {status === "complete" ? "Completed" : "Running"}
        </span>
      </div>
      <p className="toolCardQuery">{toolLabel}</p>
      {resultPreview ? <pre className="toolCardPayload">{resultPreview}</pre> : null}
    </section>
  );
}

export function CopilotMessageRenderer({
  message,
  messages,
  inProgress,
  index,
  isCurrentMessage,
  AssistantMessage,
  UserMessage,
  ImageRenderer,
  onRegenerate,
  onCopy,
  onThumbsUp,
  onThumbsDown,
  messageFeedback,
  markdownTagRenderers,
}: CopilotMessageRendererProps) {
  if (message.role === "tool") {
    return null;
  }

  if (message.role === "user") {
    return UserMessage ? (
      <UserMessage key={index} rawData={message} message={message} ImageRenderer={ImageRenderer} />
    ) : null;
  }

  if (message.role !== "assistant") {
    return null;
  }

  const assistantContent = AssistantMessage ? (
    <AssistantMessage
      key={index}
      subComponent={message.generativeUI?.()}
      rawData={message}
      message={message}
      messages={messages}
      isLoading={inProgress && isCurrentMessage && !message.content}
      isGenerating={inProgress && isCurrentMessage && !!message.content}
      isCurrentMessage={isCurrentMessage}
      onRegenerate={() => onRegenerate?.(message.id)}
      onCopy={onCopy}
      onThumbsUp={onThumbsUp}
      onThumbsDown={onThumbsDown}
      feedback={messageFeedback?.[message.id] ?? null}
      markdownTagRenderers={markdownTagRenderers}
      ImageRenderer={ImageRenderer}
    />
  ) : null;

  const toolCalls = Array.isArray(message.toolCalls) ? message.toolCalls : [];
  if (toolCalls.length === 0) {
    return assistantContent;
  }

  return (
    <>
      {assistantContent}
      <div className="toolCallStack">
        {toolCalls.map((toolCall) => (
          <div className="toolCallStackItem" key={toolCall.id}>
            {renderToolCall(toolCall, messages, inProgress && isCurrentMessage)}
          </div>
        ))}
      </div>
    </>
  );
}