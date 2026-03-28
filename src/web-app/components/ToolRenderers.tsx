"use client";

import { useDefaultTool, useRenderToolCall } from "@copilotkit/react-core";

import { coerceMessageContent } from "../lib/messageContent";
import { SearchToolRenderer } from "./SearchToolRenderer";

export function ToolRenderers() {
  useRenderToolCall(
    {
      name: "search_knowledge_base",
      description: "Search the knowledge base for relevant articles and excerpts.",
      parameters: [
        {
          name: "query",
          type: "string",
          description: "The search query to run against the knowledge base.",
          required: true,
        },
      ],
      render: (props: any) => (
        <SearchToolRenderer args={props.args} result={props.result} status={props.status} />
      ),
    } as any,
    [],
  );

  useDefaultTool(
    {
      render: (props: any) => {
        const toolLabel = coerceMessageContent(props.name ?? props.toolName) ?? "Agent tool";

        return (
          <section className="toolCard fallbackTool">
            <div className="toolCardHeader">
              <span className="toolCardEyebrow">Tool Activity</span>
              <span className="toolCardStatus">{props.status ?? "complete"}</span>
            </div>
            <p className="toolCardQuery">{toolLabel}</p>
          </section>
        );
      },
    },
    [],
  );

  return null;
}