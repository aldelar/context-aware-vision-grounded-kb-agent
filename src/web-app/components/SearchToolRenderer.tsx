"use client";

import { startTransition, useState } from "react";

import { useConversationThreadId } from "./ConversationThreadContext";
import { SearchCitationEnrichmentResponse, SearchCitationResult } from "../lib/types";
import { coerceMessageContent } from "../lib/messageContent";
import {
  canonicalizeCitations,
  extractInlineCitationImages,
  getCitationImages,
  normalizeCitationRow,
} from "./chatMessageTransforms";

type SearchToolRendererProps = {
  status?: string;
  toolCallId?: string;
  args?: {
    query?: unknown;
  } | null;
  result?: {
    results?: unknown[];
  } | null;
};

type EnrichmentState = {
  citation?: SearchCitationResult;
  status: "idle" | "loading" | "ready" | "stale" | "missing" | "error";
};

function mergeCitation(base: SearchCitationResult, override?: SearchCitationResult): SearchCitationResult {
  return override ? { ...base, ...override } : base;
}

export function SearchToolRenderer({ status, toolCallId, args, result }: SearchToolRendererProps) {
  const threadId = useConversationThreadId();
  const [enrichments, setEnrichments] = useState<Record<string, EnrichmentState>>({});
  const rawRows = Array.isArray(result?.results) ? result.results.map((row) => normalizeCitationRow(row)) : [];
  const { citations: rows } = canonicalizeCitations(rawRows);
  const isWorking = status === "inProgress" || status === "executing" || status === "running";
  const query = coerceMessageContent(args?.query) ?? "Preparing search request";
  const displayRows = rows.map((row, index) => {
    const key = String(row.ref_number ?? index + 1);
    return mergeCitation(row, enrichments[key]?.citation);
  });

  async function loadCitation(refNumber: number): Promise<void> {
    if (!threadId || !toolCallId) {
      return;
    }

    const key = String(refNumber);
    setEnrichments((current) => ({
      ...current,
      [key]: { ...current[key], status: "loading" },
    }));

    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(threadId)}/citations/${encodeURIComponent(toolCallId)}/${encodeURIComponent(String(refNumber))}`,
        { cache: "no-store" },
      );

      let payload: SearchCitationEnrichmentResponse = { status: "missing" };
      if (response.ok) {
        payload = (await response.json()) as SearchCitationEnrichmentResponse;
      }

      startTransition(() => {
        setEnrichments((current) => ({
          ...current,
          [key]: {
            citation: payload.citation,
            status: payload.status === "ready" || payload.status === "stale" ? payload.status : "missing",
          },
        }));
      });
    } catch {
      startTransition(() => {
        setEnrichments((current) => ({
          ...current,
          [key]: { ...current[key], status: "error" },
        }));
      });
    }
  }

  return (
    <section className="toolCard" data-status={status ?? "idle"}>
      <div className="toolCardHeader">
        <span className="toolCardEyebrow">Knowledge Search</span>
        <span className={`toolCardStatus${isWorking ? " working" : ""}`}>
          {isWorking ? "Searching" : "Completed"}
        </span>
      </div>
      <p className="toolCardQuery">{query}</p>
      {displayRows.length > 0 ? (
        <div className="citationDeck">
          {displayRows.map((row, index) => {
            const key = String(row.ref_number ?? index + 1);
            const enrichment = enrichments[key];
            const { content, images: inlineImages } = extractInlineCitationImages(row.content ?? row.summary ?? "", row, displayRows);
            const rowImages = getCitationImages(row, displayRows);
            const citationImages = rowImages.concat(
              inlineImages.filter((image) => !rowImages.some((entry) => entry.url === image.url)),
            );
            const refLabel = row.ref_number ? `Ref #${row.ref_number}` : `Result ${index + 1}`;
            const canEnrich = Boolean(
              !isWorking
              && threadId
              && toolCallId
              && row.ref_number
              && row.chunk_id
              && row.content_source !== "full",
            );

            return (
              <article
                id={row.ref_number ? `citation-ref-${row.ref_number}` : undefined}
                className="citationCard"
                key={`${row.ref_number ?? index}-${row.title ?? "result"}`}
              >
                <div className="citationCardHeader">
                  <span className="citationBadge">{refLabel}</span>
                  <div>
                    <strong>{row.title ?? "Knowledge base result"}</strong>
                    <span>{row.section_header ?? "Relevant section"}</span>
                  </div>
                </div>
                {content ? <p className="citationPreview">{content}</p> : null}
                {canEnrich ? (
                  <div className="citationActions">
                    {enrichment?.status === "ready" || enrichment?.status === "stale" ? null : (
                      <button
                        className="citationLoadButton"
                        disabled={enrichment?.status === "loading"}
                        onClick={() => void loadCitation(row.ref_number as number)}
                        type="button"
                      >
                        {enrichment?.status === "loading" ? "Loading source…" : "Load source excerpt"}
                      </button>
                    )}
                    {enrichment?.status === "missing" ? (
                      <p className="citationStatus">Original source excerpt is unavailable; showing the stored summary.</p>
                    ) : null}
                    {enrichment?.status === "error" ? (
                      <p className="citationStatus">Source lookup failed; showing the stored summary.</p>
                    ) : null}
                    {enrichment?.status === "stale" ? (
                      <p className="citationStatus">Source content was reloaded, but the indexed chunk has changed since this reply.</p>
                    ) : null}
                  </div>
                ) : null}
                {citationImages.length > 0 ? (
                  <div className="citationImageStrip">
                    {citationImages.map((image, imageIndex) => (
                      <img
                        alt={image.alt || `${refLabel} image ${imageIndex + 1}`}
                        className="citationImage"
                        key={`${image.url}-${imageIndex}`}
                        loading="lazy"
                        src={image.url}
                      />
                    ))}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="toolCardHint">The agent is collecting article matches and ranking the best sections.</p>
      )}
    </section>
  );
}