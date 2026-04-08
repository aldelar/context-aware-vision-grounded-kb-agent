"use client";

import { useEffect, useMemo, useRef } from "react";

import { citationKey, useCitationDialogOptional } from "./CitationDialogContext";
import { useConversationThreadId } from "./ConversationThreadContext";
import { SearchCitationResult } from "../lib/types";
import { coerceMessageContent } from "../lib/messageContent";
import {
  canonicalizeCitations,
  normalizeCitationRow,
} from "./chatMessageTransforms";

type SearchToolRendererProps = {
  status?: string;
  toolCallId?: string;
  turnNumber?: number;
  args?: {
    query?: unknown;
  } | null;
  result?: {
    results?: unknown[];
  } | null;
};

export function getPillTitle(row: SearchCitationResult): string {
  if (row.section_header?.trim()) {
    return row.section_header.trim();
  }

  const raw = row.content ?? row.summary ?? "";
  const cleaned = raw
    .replace(/!\[([^\]]*)\]\([^\)]+\)/g, "")
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
    .replace(/^#{1,6}\s+/u, "")
    .replace(/[*_`~]/g, "")
    .trim();

  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return row.title?.trim() || "Reference";
  }

  if (words.length <= 3) {
    return words.join(" ");
  }

  return `${words.slice(0, 3).join(" ")}…`;
}

export function SearchToolRenderer({ status, toolCallId, args, result, turnNumber }: SearchToolRendererProps) {
  const threadId = useConversationThreadId();
  const citationDialog = useCitationDialogOptional();
  const citationDialogRef = useRef(citationDialog);
  citationDialogRef.current = citationDialog;

  const rawResults = result?.results;
  const { citations: rows } = useMemo(() => {
    const rawRows = Array.isArray(rawResults) ? rawResults.map((row) => normalizeCitationRow(row)) : [];
    return canonicalizeCitations(rawRows);
  }, [rawResults]);

  const isWorking = status === "inProgress" || status === "executing" || status === "running";
  const query = coerceMessageContent(args?.query) ?? "Preparing search request";

  useEffect(() => {
    const dialog = citationDialogRef.current;
    if (!dialog || isWorking) {
      return;
    }

    for (const row of rows) {
      if (row.ref_number !== undefined) {
        const key = citationKey(toolCallId, row.ref_number);
        const t = turnNumber ?? 1;
        dialog.registerCitation(key, {
          citation: row,
          threadId,
          toolCallId,
          source: "internal",
          displayLabel: `Ref ${t}.${row.ref_number}`,
          turnNumber: t,
        });
      }
    }
  }, [rows, threadId, toolCallId, isWorking]);

  return (
    <section className="toolCard" data-status={status ?? "idle"}>
      <div className="toolCardHeader">
        <span className="toolCardEyebrow">Knowledge Search</span>
        <span className={`toolCardStatus${isWorking ? " working" : ""}`}>
          {isWorking ? "Searching" : "Completed"}
        </span>
      </div>
      <p className="toolCardQuery">{query}</p>
      {rows.length > 0 ? (
        <div className="citationPillDeck">
          {rows.map((row, index) => {
            const refNumber = row.ref_number ?? index + 1;
            const t = turnNumber ?? 1;
            const refLabel = `Ref ${t}.${refNumber}`;
            const pillTitle = getPillTitle(row);
            const key = citationKey(toolCallId, refNumber);

            return (
              <button
                className="citationPill"
                key={`${refNumber}-${row.title ?? "result"}`}
                onClick={() => citationDialog?.openCitation(key)}
                type="button"
                aria-label={`${refLabel}: ${pillTitle}`}
              >
                <span className="citationBadge">{refLabel}</span>
                <span className="citationPillTitle">{pillTitle}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <p className="toolCardHint">The agent is collecting article matches and ranking the best sections.</p>
      )}
    </section>
  );
}