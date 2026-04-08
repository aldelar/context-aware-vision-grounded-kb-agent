"use client";

import {
  AssistantMessage as CopilotAssistantMessage,
} from "@copilotkit/react-ui";
import type { AssistantMessageProps } from "@copilotkit/react-ui";
import { useMemo } from "react";

import { useCitationDialogOptional } from "./CitationDialogContext";
import { coerceMessageContent } from "../lib/messageContent";
import { linkCitationMarkers } from "./chatMessageTransforms";

const citationRefPattern = /^#citation-ref-(?:(\d+)-)?(\d+)$/;

export function CitationAwareAssistantMessage(props: AssistantMessageProps) {
  const content = coerceMessageContent(props.message?.content);
  const citationDialog = useCitationDialogOptional();

  const markdownTagRenderers = useMemo(() => {
    const existingRenderers = (props as any).markdownTagRenderers ?? {};
    return {
      ...existingRenderers,
      a: ({ node, href, children, ...rest }: any) => {
        const match = typeof href === "string" ? href.match(citationRefPattern) : null;
        if (match && citationDialog) {
          const turnNumber = match[1] ? Number(match[1]) : undefined;
          const refNumber = Number(match[2]);
          return (
            <button
              {...rest}
              className="citationInlineRef"
              onClick={(event: React.MouseEvent) => {
                event.preventDefault();
                const key = citationDialog.findKeyByRefNumber(refNumber, turnNumber);
                if (key) {
                  citationDialog.openCitation(key);
                }
              }}
              type="button"
            >
              {children}
            </button>
          );
        }

        const isInPageLink = typeof href === "string" && href.startsWith("#");
        return (
          <a
            {...rest}
            href={href}
            {...(isInPageLink ? {} : { rel: "noreferrer", target: "_blank" })}
          >
            {children}
          </a>
        );
      },
    };
  }, [citationDialog, props]);

  return (
    <CopilotAssistantMessage
      {...props}
      markdownTagRenderers={markdownTagRenderers}
      message={{
        ...props.message,
        content: content ? linkCitationMarkers(content) : "",
      }}
    />
  );
}