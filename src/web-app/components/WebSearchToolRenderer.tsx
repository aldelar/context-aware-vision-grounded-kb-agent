"use client";

import { useEffect, useMemo, useRef } from "react";
import { coerceMessageContent } from "../lib/messageContent";
import { citationKey, useCitationDialogOptional } from "./CitationDialogContext";
import { useConversationThreadId } from "./ConversationThreadContext";

type WebSearchResult = {
  ref_number?: number;
  title?: string;
  snippet?: string;
  source_url?: string;
  anchor?: string;
};

type WebSearchToolRendererProps = {
  status?: string;
  toolCallId?: string;
  args?: {
    query?: unknown;
  } | null;
  result?: {
    results?: unknown[];
    summary?: string;
  } | null;
};

function getWebPillTitle(row: WebSearchResult): string {
  if (row.title?.trim()) {
    const title = row.title.trim();
    const words = title.split(/\s+/);
    if (words.length <= 5) return title;
    return `${words.slice(0, 5).join(" ")}…`;
  }
  if (row.snippet?.trim()) {
    const words = row.snippet.trim().split(/\s+/);
    return words.length <= 4 ? words.join(" ") : `${words.slice(0, 4).join(" ")}…`;
  }
  return "Web result";
}

function normalizeWebRow(raw: unknown): WebSearchResult {
  if (!raw || typeof raw !== "object") return {};
  const row = raw as Record<string, unknown>;
  return {
    ref_number: typeof row.ref_number === "number" ? row.ref_number : undefined,
    title: typeof row.title === "string" ? row.title : undefined,
    snippet: typeof row.snippet === "string" ? row.snippet : undefined,
    source_url: typeof row.source_url === "string" ? row.source_url : undefined,
    anchor: typeof row.anchor === "string" ? row.anchor : undefined,
  };
}

export function WebSearchToolRenderer({ status, toolCallId, args, result }: WebSearchToolRendererProps) {
  const threadId = useConversationThreadId();
  const citationDialog = useCitationDialogOptional();
  const citationDialogRef = useRef(citationDialog);
  citationDialogRef.current = citationDialog;

  const rawResults = result?.results;
  const rows = useMemo(() => {
    return Array.isArray(rawResults) ? rawResults.map(normalizeWebRow) : [];
  }, [rawResults]);

  const isWorking = status === "inProgress" || status === "executing" || status === "running";
  const query = coerceMessageContent(args?.query) ?? "Searching the web";

  // Register web citations into the dialog system
  useEffect(() => {
    const dialog = citationDialogRef.current;
    if (!dialog || isWorking) return;

    for (const row of rows) {
      if (row.ref_number !== undefined) {
        const key = citationKey(toolCallId, row.ref_number);
        dialog.registerCitation(key, {
          citation: {
            ref_number: row.ref_number,
            title: row.title,
            summary: row.snippet,
            content: row.snippet,
            source_url: row.source_url,
            content_source: "full",
          },
          threadId,
          toolCallId,
          source: "web",
        });
      }
    }
  }, [rows, threadId, toolCallId, isWorking]);

  return (
    <section className="toolCard" data-status={status ?? "idle"}>
      <div className="toolCardHeader">
        <span className="toolCardEyebrow">Web Search</span>
        <span className={`toolCardStatus${isWorking ? " working" : ""}`}>
          {isWorking ? "Searching" : "Completed"}
        </span>
      </div>
      <p className="toolCardQuery">{query}</p>
      {rows.length > 0 ? (
        <div className="citationPillDeck">
          {rows.map((row, index) => {
            const refNumber = row.ref_number ?? index + 1;
            const refLabel = `Ref #${refNumber}`;
            const pillTitle = getWebPillTitle(row);
            const key = citationKey(toolCallId, refNumber);

            return (
              <button
                className="citationPill webCitationPill"
                key={`${refNumber}-${row.title ?? "result"}`}
                onClick={() => citationDialog?.openCitation(key)}
                type="button"
                aria-label={`${refLabel}: ${pillTitle}`}
              >
                <span className="citationBadge webCitationBadge">{refLabel}</span>
                <span className="citationPillTitle">{pillTitle}</span>
              </button>
            );
          })}
        </div>
      ) : isWorking ? (
        <p className="toolCardHint">Searching Microsoft documentation…</p>
      ) : (
        <p className="toolCardHint">No web results found for this query.</p>
      )}
    </section>
  );
}
