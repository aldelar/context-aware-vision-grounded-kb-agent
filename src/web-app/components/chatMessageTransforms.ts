import { coerceMessageContent } from "../lib/messageContent";
import { SearchCitationImage, SearchCitationResult } from "../lib/types";

const citationMarkerPattern = /\[(Ref #(\d+))\](?!\()/g;
const refSequencePattern = /\bRefs?\s*#\s*\d+(?:\s*(?:,|\/|and|or)\s*#\s*\d+)+/gi;
const anyMarkdownImagePattern = /!\[([^\]]*)\]\(\s*([^\)\s]+)\s*\)/g;
const contentImagePattern = /\[Image:\s*([^\]]+)\]\(images\/([^)]+\.(?:png|jpg|jpeg|gif|svg|webp))\)/gi;
const apiPathPattern = /(?:https?:\/\/[^)\s]+)?\/?api\/images\/([^\s)#?]+)/i;

type CitationLookups = {
  pathLookup: Map<string, string>;
  filenameLookup: Map<string, string>;
};

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

function normalizeSeparator(separator: string): string {
  const trimmed = separator.trim().toLowerCase();
  if (trimmed === "/") {
    return " / ";
  }

  return separator;
}

function stripMarkdownImages(content: string): string {
  return content.replace(contentImagePattern, "").replace(anyMarkdownImagePattern, "");
}

function collapseWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value);
}

function extractFilename(value: string): string | null {
  const cleaned = value.split(/[?#]/, 1)[0].trim();
  if (!cleaned) {
    return null;
  }

  const filename = cleaned.split("/").filter(Boolean).at(-1);
  return filename || null;
}

function toProxyImageUrl(articleId: string, imagePath: string): string {
  return `/api/images/${encodePathSegment(articleId)}/${imagePath.replace(/^\/+/, "")}`;
}

function buildCitationLookups(citations: SearchCitationResult[]): CitationLookups {
  const pathLookup = new Map<string, string>();
  const filenameLookup = new Map<string, string>();

  const remember = (key: string | null | undefined, url: string | null) => {
    if (!key || !url || pathLookup.has(key)) {
      return;
    }

    pathLookup.set(key, url);
  };

  const rememberFilename = (filename: string | null, url: string | null) => {
    if (!filename || !url || filenameLookup.has(filename)) {
      return;
    }

    filenameLookup.set(filename, url);
  };

  for (const citation of citations) {
    const articleId = citation.article_id;

    for (const rawImageUrl of citation.image_urls ?? []) {
      const proxyUrl = resolveImageUrl(rawImageUrl, articleId, { pathLookup, filenameLookup });
      const normalizedKey = rawImageUrl.replace(/^attachment:/i, "").replace(/^\/+/, "");
      remember(normalizedKey, proxyUrl);
      rememberFilename(extractFilename(rawImageUrl), proxyUrl);
    }

    for (const image of citation.images ?? []) {
      const proxyUrl = resolveImageUrl(image.url, articleId, { pathLookup, filenameLookup });
      const normalizedKey = image.url.replace(/^attachment:/i, "").replace(/^\/+/, "");
      remember(normalizedKey, proxyUrl);
      rememberFilename(extractFilename(image.url), proxyUrl);
    }

    const content = citation.content ?? "";
    for (const match of content.matchAll(contentImagePattern)) {
      const imagePath = `images/${match[2]}`;
      const proxyUrl = resolveImageUrl(imagePath, articleId, { pathLookup, filenameLookup });
      remember(imagePath, proxyUrl);
      rememberFilename(extractFilename(imagePath), proxyUrl);
    }
  }

  return { pathLookup, filenameLookup };
}

function resolveImageUrl(
  rawUrl: string,
  articleId?: string,
  lookups?: CitationLookups,
): string | null {
  const strippedUrl = rawUrl.replace(/^attachment:/i, "").trim();
  if (!strippedUrl) {
    return null;
  }

  const apiMatch = strippedUrl.match(apiPathPattern);
  if (apiMatch) {
    return `/api/images/${apiMatch[1].replace(/^\/+/, "")}`;
  }

  const normalizedPath = strippedUrl.replace(/^\/+/, "");
  const exactMatch = lookups?.pathLookup.get(normalizedPath) ?? lookups?.pathLookup.get(strippedUrl);
  if (exactMatch) {
    return exactMatch;
  }

  if (/^images\//i.test(normalizedPath) && articleId) {
    return toProxyImageUrl(articleId, normalizedPath);
  }

  const filename = extractFilename(strippedUrl);
  if (filename) {
    const filenameMatch = lookups?.filenameLookup.get(filename);
    if (filenameMatch) {
      return filenameMatch;
    }

    if (articleId && !filename.includes("/")) {
      return toProxyImageUrl(articleId, `images/${filename}`);
    }
  }

  return null;
}

function getCitationDedupKey(citation: SearchCitationResult): string {
  const imageSignature = [...new Set([...(citation.image_urls ?? []), ...(citation.images ?? []).map((image) => image.url)])]
    .map((value) => collapseWhitespace(value))
    .sort()
    .join("|");

  return [citation.title, citation.section_header, stripMarkdownImages(citation.content ?? ""), imageSignature]
    .map((value) => collapseWhitespace(value ?? ""))
    .join("||");
}

function extractMentionedRefNumbers(content: string): Set<number> {
  const mentions = new Set<number>();

  for (const match of content.matchAll(/Ref\s*#\s*(\d+)/gi)) {
    mentions.add(Number(match[1]));
  }

  for (const match of content.matchAll(/#citation-ref-(\d+)/gi)) {
    mentions.add(Number(match[1]));
  }

  return mentions;
}

function canonicalizeRefSequence(sequence: string): string {
  const numbers = [...sequence.matchAll(/#\s*(\d+)/g)].map((match) => match[1]);
  const separators = [...sequence.matchAll(/#\s*\d+(\s*(?:,|\/|and|or)\s*)?/gi)].map((match) => match[1] ?? "");

  return numbers
    .map((number, index) => `Ref #${number}${normalizeSeparator(separators[index] ?? "")}`)
    .join("")
    .trim();
}

function normalizeRefMentions(content: string): string {
  return content
    .replace(/\bRefs?\s*#?\s*(\d+)/gi, "Ref #$1")
    .replace(refSequencePattern, (sequence) => canonicalizeRefSequence(sequence));
}

function remapRefNumbers(content: string, refNumberMap: Map<number, number>): string {
  if (refNumberMap.size === 0) {
    return content;
  }

  return content
    .replace(/Ref\s*#\s*(\d+)/gi, (match, rawRefNumber) => {
      const mappedRefNumber = refNumberMap.get(Number(rawRefNumber));
      return mappedRefNumber ? `Ref #${mappedRefNumber}` : match;
    })
    .replace(/#citation-ref-(\d+)/gi, (match, rawRefNumber) => {
      const mappedRefNumber = refNumberMap.get(Number(rawRefNumber));
      return mappedRefNumber ? `#citation-ref-${mappedRefNumber}` : match;
    });
}

function rewriteIndexedImageRefs(
  content: string,
  citations: SearchCitationResult[],
  articleId?: string,
): string {
  const lookups = buildCitationLookups(citations);

  return content.replace(contentImagePattern, (_match, alt, imageName) => {
    const proxyUrl = resolveImageUrl(`images/${imageName}`, articleId, lookups);
    if (!proxyUrl) {
      return `*[Image: ${alt}]*`;
    }

    return `![${alt}](${proxyUrl})`;
  });
}

function normalizeInlineImages(
  content: string,
  citations: SearchCitationResult[],
  articleId?: string,
): string {
  const lookups = buildCitationLookups(citations);

  return content.replace(anyMarkdownImagePattern, (_match, alt, rawUrl) => {
    const proxyUrl = resolveImageUrl(rawUrl, articleId, lookups);
    if (!proxyUrl) {
      return `*[Image: ${alt || extractFilename(rawUrl) || "Image"}]*`;
    }

    return `![${alt}](${proxyUrl})`;
  });
}

function appendMissingReferenceTokens(content: string, citations: SearchCitationResult[]): string {
  const mentionedRefs = extractMentionedRefNumbers(content);
  const missingRefs = citations
    .map((citation) => citation.ref_number)
    .filter((refNumber): refNumber is number => typeof refNumber === "number" && !mentionedRefs.has(refNumber))
    .map((refNumber) => `[Ref #${refNumber}](#citation-ref-${refNumber})`);

  if (missingRefs.length === 0) {
    return content;
  }

  const trimmedContent = content.trim();
  const suffix = `Sources: ${missingRefs.join(" ")}`;
  return trimmedContent ? `${trimmedContent}\n\n${suffix}` : suffix;
}

function appendInlineImageFallbacks(content: string, citations: SearchCitationResult[]): string {
  if (content.match(anyMarkdownImagePattern)) {
    return content;
  }

  const mentionedRefs = extractMentionedRefNumbers(content);
  const sourceCitations = mentionedRefs.size
    ? citations.filter((citation) => citation.ref_number && mentionedRefs.has(citation.ref_number))
    : citations;

  const fallbackImages = sourceCitations.flatMap((citation) => {
    const images = getCitationImages(citation, citations);
    if (images.length === 0) {
      return [];
    }

    return [
      {
        image: images[0],
        refNumber: citation.ref_number,
      },
    ];
  });

  if (fallbackImages.length === 0) {
    return content;
  }

  const fallbackMarkdown = fallbackImages
    .map(({ image, refNumber }, index) => {
      const alt = image.alt || (refNumber ? `Ref #${refNumber} image` : `Citation image ${index + 1}`);
      return `![${alt}](${image.url})`;
    })
    .join("\n\n");

  const trimmedContent = content.trim();
  return trimmedContent ? `${trimmedContent}\n\n${fallbackMarkdown}` : fallbackMarkdown;
}

export function normalizeCitationRow(value: unknown): SearchCitationResult {
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

  const chunkIndex =
    typeof record.chunk_index === "number"
      ? record.chunk_index
      : typeof record.chunk_index === "string" && Number.isFinite(Number(record.chunk_index))
        ? Number(record.chunk_index)
        : undefined;
  const summary = coerceMessageContent(record.summary) ?? undefined;
  const content = coerceMessageContent(record.content) ?? summary;
  const explicitContentSource = coerceMessageContent(record.content_source);
  const contentSource = explicitContentSource === "summary" || explicitContentSource === "full"
    ? explicitContentSource
    : summary && (!record.content || content === summary)
      ? "summary"
      : content
        ? "full"
        : undefined;

  return {
    chunk_id: coerceMessageContent(record.chunk_id ?? record.id) ?? undefined,
    article_id: coerceMessageContent(record.article_id) ?? undefined,
    chunk_index: chunkIndex,
    indexed_at: coerceMessageContent(record.indexed_at) ?? undefined,
    ref_number: refNumber,
    title: coerceMessageContent(record.title) ?? undefined,
    section_header: coerceMessageContent(record.section_header) ?? undefined,
    summary,
    content,
    content_source: contentSource,
    image_urls: normalizeStringArray(record.image_urls),
    images: Array.isArray(record.images)
      ? record.images
          .map((image) => normalizeCitationImage(image))
          .filter((image): image is SearchCitationImage => image !== null)
      : undefined,
  };
}

export function canonicalizeCitations(citations: SearchCitationResult[]): {
  citations: SearchCitationResult[];
  refNumberMap: Map<number, number>;
} {
  const canonicalCitations: SearchCitationResult[] = [];
  const refNumberMap = new Map<number, number>();
  const deduplicationMap = new Map<string, number>();

  for (const citation of citations) {
    const dedupKey = getCitationDedupKey(citation);
    const existingRefNumber = deduplicationMap.get(dedupKey);
    if (existingRefNumber) {
      if (citation.ref_number !== undefined && !refNumberMap.has(citation.ref_number)) {
        refNumberMap.set(citation.ref_number, existingRefNumber);
      }
      continue;
    }

    const canonicalRefNumber = canonicalCitations.length + 1;
    deduplicationMap.set(dedupKey, canonicalRefNumber);
    if (citation.ref_number !== undefined && !refNumberMap.has(citation.ref_number)) {
      refNumberMap.set(citation.ref_number, canonicalRefNumber);
    }

    canonicalCitations.push({
      ...citation,
      ref_number: canonicalRefNumber,
    });
  }

  return {
    citations: canonicalCitations,
    refNumberMap,
  };
}

export function getCitationImages(
  citation: SearchCitationResult,
  citations: SearchCitationResult[],
): SearchCitationImage[] {
  const lookups = buildCitationLookups(citations);
  const deduplicatedImages = new Map<string, SearchCitationImage>();

  const remember = (image: SearchCitationImage | null) => {
    if (!image) {
      return;
    }

    deduplicatedImages.set(image.url, image);
  };

  for (const image of citation.images ?? []) {
    const proxyUrl = resolveImageUrl(image.url, citation.article_id, lookups);
    remember(proxyUrl ? { alt: image.alt, url: proxyUrl } : null);
  }

  for (const imageUrl of citation.image_urls ?? []) {
    const proxyUrl = resolveImageUrl(imageUrl, citation.article_id, lookups);
    remember(proxyUrl ? { url: proxyUrl } : null);
  }

  for (const match of (citation.content ?? "").matchAll(contentImagePattern)) {
    const alt = match[1];
    const proxyUrl = resolveImageUrl(`images/${match[2]}`, citation.article_id, lookups);
    remember(proxyUrl ? { alt, url: proxyUrl } : null);
  }

  for (const match of (citation.content ?? "").matchAll(anyMarkdownImagePattern)) {
    const alt = match[1];
    const proxyUrl = resolveImageUrl(match[2], citation.article_id, lookups);
    remember(proxyUrl ? { alt, url: proxyUrl } : null);
  }

  return [...deduplicatedImages.values()];
}

export function extractInlineCitationImages(
  content: string,
  citation: SearchCitationResult,
  citations: SearchCitationResult[],
): {
  content: string;
  images: SearchCitationImage[];
} {
  const normalizedContent = normalizeInlineImages(
    rewriteIndexedImageRefs(content, citations, citation.article_id),
    citations,
    citation.article_id,
  );
  const images: SearchCitationImage[] = [];

  const strippedContent = normalizedContent.replace(anyMarkdownImagePattern, (_match, alt, url) => {
    images.push({ alt, url });
    return "";
  });

  return {
    content: strippedContent.replace(/\n{3,}/g, "\n\n").trim(),
    images,
  };
}

export function linkCitationMarkers(content: string): string {
  const linkedBracketedMarkers = content.replace(citationMarkerPattern, "[$1](#citation-ref-$2)");
  return linkedBracketedMarkers.replace(/\bRef #(\d+)\b/g, (match, refNumber, offset, value) => {
    const previousCharacter = value[offset - 1];
    const followingCharacters = value.slice(offset + match.length, offset + match.length + 2);
    if (previousCharacter === "[" || followingCharacters === "](") {
      return match;
    }

    return `[Ref #${refNumber}](#citation-ref-${refNumber})`;
  });
}

export function transformAssistantContent(content: string, rawCitations: SearchCitationResult[]): string {
  const { citations, refNumberMap } = canonicalizeCitations(rawCitations);

  let transformedContent = normalizeRefMentions(content);
  transformedContent = remapRefNumbers(transformedContent, refNumberMap);
  transformedContent = normalizeInlineImages(
    rewriteIndexedImageRefs(transformedContent, citations),
    citations,
  );
  transformedContent = linkCitationMarkers(transformedContent);
  transformedContent = appendMissingReferenceTokens(transformedContent, citations);
  transformedContent = appendInlineImageFallbacks(transformedContent, citations);
  return transformedContent;
}