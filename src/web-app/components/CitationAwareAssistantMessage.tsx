"use client";

import {
  AssistantMessage as CopilotAssistantMessage,
} from "@copilotkit/react-ui";
import type { AssistantMessageProps } from "@copilotkit/react-ui";

import { coerceMessageContent } from "../lib/messageContent";
import { linkCitationMarkers } from "./chatMessageTransforms";

export function CitationAwareAssistantMessage(props: AssistantMessageProps) {
  const content = coerceMessageContent(props.message?.content);

  return (
    <CopilotAssistantMessage
      {...props}
      message={{
        ...props.message,
        content: content ? linkCitationMarkers(content) : "",
      }}
    />
  );
}