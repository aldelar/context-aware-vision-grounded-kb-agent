"use client";

import type { Message } from "@copilotkit/shared";
import { ReactNode } from "react";

import { coerceMessageContent } from "../lib/messageContent";
import { canonicalizeCitations, normalizeCitationRow, transformAssistantContent } from "./chatMessageTransforms";
import { SearchToolRenderer } from "./SearchToolRenderer";
import { WebSearchToolRenderer } from "./WebSearchToolRenderer";

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
  encryptedValue?: string;
  name?: string;
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

function getTurnBounds(messages: AgUiMessageLike[], index: number): { start: number; end: number } {
  let start = index;
  while (start > 0 && messages[start - 1]?.role !== "user") {
    start -= 1;
  }

  let end = index;
  while (end + 1 < messages.length && messages[end + 1]?.role !== "user") {
    end += 1;
  }

  return { start, end };
}

function getAssistantSearchCitations(message: AgUiMessageLike, messages: AgUiMessageLike[], index: number) {
  const { start, end } = getTurnBounds(messages, index);
  const toolCalls = messages
    .slice(start, end + 1)
    .filter((candidate) => candidate.role === "assistant")
    .flatMap((candidate) => Array.isArray(candidate.toolCalls) ? candidate.toolCalls : []);

  return toolCalls.flatMap((toolCall) => {
    if (toolCall.function?.name !== "search_knowledge_base") {
      return [];
    }

    const toolResultMessage = findToolResultMessage(messages, toolCall.id);
    const parsedResult = parseJsonPayload(toolResultMessage?.content) as { results?: unknown[] } | undefined;
    return Array.isArray(parsedResult?.results) ? parsedResult.results.map((row) => normalizeCitationRow(row)) : [];
  });
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

function renderReasoningCard({
  content,
  id,
  label,
  meta,
  transient = false,
}: {
  content: string;
  id: string;
  label: string;
  meta?: string;
  transient?: boolean;
}): ReactNode {
  return (
    <section
      className={transient ? "reasoningCard reasoningCardTransient" : "reasoningCard"}
      data-message-id={id}
    >
      <div className="reasoningCardHeader">
        <span className="reasoningCardEyebrow">{label}</span>
        {meta ? <span className="reasoningCardMeta">{meta}</span> : null}
      </div>
      <p className="reasoningCardContent">{content}</p>
    </section>
  );
}

function renderTransientThinkingMessage(id: string, content = "Working on a response…"): ReactNode {
  return renderReasoningCard({
    content,
    id,
    label: "Thinking",
    meta: "Live",
    transient: true,
  });
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
    return <SearchToolRenderer args={args} result={parsedResult as any} status={status} toolCallId={toolCall.id} />;
  }

  if (toolName === "web_search") {
    return <WebSearchToolRenderer args={args} result={parsedResult as any} status={status} toolCallId={toolCall.id} />;
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

function renderReasoningMessage(message: AgUiMessageLike, inProgress: boolean): ReactNode {
  if (!inProgress) {
    return null;
  }

  const content = coerceMessageContent(message.content);
  if (!content) {
    return null;
  }

  return renderReasoningCard({
    content,
    id: message.id,
    label: "Thinking",
    meta: message.encryptedValue ? "Protected trace" : undefined,
  });
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
    if (inProgress && isCurrentMessage && AssistantMessage) {
      return (
        <AssistantMessage
          key={`${index}-awaiting`}
          rawData={message}
          message={{ ...message, role: "assistant", content: "" } as any}
          messages={messages as Message[]}
          isLoading={true}
          isGenerating={false}
          isCurrentMessage={true}
        />
      );
    }
    return null;
  }

  if (message.role === "user") {
    const userMessage = UserMessage ? (
      <UserMessage key={index} rawData={message} message={message} ImageRenderer={ImageRenderer} />
    ) : null;

    return inProgress && isCurrentMessage ? (
      <>
        {userMessage}
        {renderTransientThinkingMessage(`${message.id}-thinking`)}
      </>
    ) : userMessage;
  }

  if (message.role === "reasoning") {
    return renderReasoningMessage(message, inProgress);
  }

  if (message.role !== "assistant") {
    return null;
  }

  const visibleContent = coerceMessageContent(message.content)?.trim();
  const searchCitations = getAssistantSearchCitations(message, messages, index);
  const transformedContent = visibleContent ? transformAssistantContent(visibleContent, searchCitations) : visibleContent;
  const toolCalls = Array.isArray(message.toolCalls) ? message.toolCalls : [];
  const isLoading = inProgress && isCurrentMessage && !visibleContent && toolCalls.length === 0;
  const shouldRenderAssistantMessage = Boolean(visibleContent) || Boolean(message.generativeUI) || isLoading;

  const assistantContent = shouldRenderAssistantMessage && AssistantMessage ? (
    <AssistantMessage
      key={index}
      subComponent={message.generativeUI?.()}
      rawData={{ ...message, content: transformedContent ?? message.content }}
      message={{ ...message, content: transformedContent ?? message.content } as Message}
      messages={messages as Message[]}
      isLoading={isLoading}
      isGenerating={inProgress && isCurrentMessage && !!visibleContent}
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

  if (toolCalls.length === 0) {
    return <>{assistantContent}</>;
  }

  const allToolCallsComplete = toolCalls.every(
    (toolCall) => findToolResultMessage(messages, toolCall.id) !== undefined,
  );
  const isAwaitingAnswer = inProgress && isCurrentMessage && allToolCallsComplete && !visibleContent;

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
      {isAwaitingAnswer && AssistantMessage ? (
        <AssistantMessage
          key={`${index}-loading`}
          rawData={message}
          message={{ ...message, content: "" } as Message}
          messages={messages as Message[]}
          isLoading={true}
          isGenerating={false}
          isCurrentMessage={true}
        />
      ) : null}
    </>
  );
}