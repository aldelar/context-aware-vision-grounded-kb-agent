"use client";

import { coerceMessageContent } from "../lib/messageContent";
import { SearchCitationImage, SearchCitationResult } from "../lib/types";

type SearchToolRendererProps = {
  status?: string;
  args?: {
    query?: unknown;
  } | null;
  result?: {
    results?: unknown[];
  } | null;
};

const markdownImagePattern = /!\[([^\]]*)\]\((\/api\/images\/[^)]+)\)/g;

function normalizeCitationImage(value: unknown): SearchCitationImage | null {
  if (typeof value === "string") {
    return value ? { url: value } : null;
  }

  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;
  const url = coerceMessageContent(record.url);
  if (!url) {
    return null;
  }

  const alt = coerceMessageContent(record.alt) ?? undefined;
  return { alt, url };
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((entry) => coerceMessageContent(entry))
    .filter((entry): entry is string => Boolean(entry));
}

function normalizeCitationRow(value: unknown): SearchCitationResult {
  if (!value || typeof value !== "object") {
    return {};
  }

  const record = value as Record<string, unknown>;
  const refNumber =
    typeof record.ref_number === "number"
      ? record.ref_number
      : typeof record.ref_number === "string" && Number.isFinite(Number(record.ref_number))
        ? Number(record.ref_number)
        : undefined;

  return {
    ref_number: refNumber,
    title: coerceMessageContent(record.title) ?? undefined,
    section_header: coerceMessageContent(record.section_header) ?? undefined,
    content: coerceMessageContent(record.content) ?? undefined,
    image_urls: normalizeStringArray(record.image_urls),
    images: Array.isArray(record.images)
      ? record.images
          .map((image) => normalizeCitationImage(image))
          .filter((image): image is SearchCitationImage => image !== null)
      : undefined,
  };
}

function extractInlineCitationImages(content: string): {
  content: string;
  images: SearchCitationImage[];
} {
  const images: SearchCitationImage[] = [];
  const normalizedContent = content.replace(markdownImagePattern, (_match, alt, url) => {
    images.push({ alt, url });
    return "";
  });

  return {
    content: normalizedContent.replace(/\n{3,}/g, "\n\n").trim(),
    images,
  };
}

function getCitationImages(row: SearchCitationResult, inlineImages: SearchCitationImage[]): SearchCitationImage[] {
  const deduped = new Map<string, SearchCitationImage>();
  for (const image of row.images ?? []) {
    if (image.url) {
      deduped.set(image.url, image);
    }
  }

  for (const imageUrl of row.image_urls ?? []) {
    if (imageUrl) {
      deduped.set(imageUrl, { url: imageUrl });
    }
  }

  for (const image of inlineImages) {
    deduped.set(image.url, image);
  }

  return [...deduped.values()];
}

export function SearchToolRenderer({ status, args, result }: SearchToolRendererProps) {
  const rows = Array.isArray(result?.results) ? result.results.map((row) => normalizeCitationRow(row)) : [];
  const isWorking = status === "inProgress" || status === "executing" || status === "running";
  const query = coerceMessageContent(args?.query) ?? "Preparing search request";

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
        <div className="citationDeck">
          {rows.map((row, index) => {
            const { content, images: inlineImages } = extractInlineCitationImages(row.content ?? "");
            const citationImages = getCitationImages(row, inlineImages);
            const refLabel = row.ref_number ? `Ref #${row.ref_number}` : `Result ${index + 1}`;

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