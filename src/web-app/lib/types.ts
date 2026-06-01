export interface UserContext {
  userId: string;
  userIdentifier: string;
  groups: string[];
}

export interface ConversationRecord {
  id: string;
  userId: string;
  userIdentifier: string;
  name: string;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationCreateRequest {
  id?: string;
  title?: string;
}

export interface ConversationUpdateRequest {
  title?: string;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content?: unknown;
  toolCalls?: unknown[];
  toolCallId?: string;
  toolName?: string;
  name?: string;
  encryptedValue?: string;
}

export interface ConversationMessagesResponse {
  messages: ConversationMessage[];
}

export interface SearchCitationImage {
  alt?: string;
  name?: string;
  url: string;
}

export interface SearchCitationResult {
  chunk_id?: string;
  article_id?: string;
  chunk_index?: number;
  indexed_at?: string;
  ref_number?: number;
  title?: string;
  section_header?: string;
  summary?: string;
  content?: string;
  content_source?: "summary" | "full";
  image_urls?: string[];
  images?: SearchCitationImage[];
  source_url?: string;
}

export interface SearchCitationEnrichmentResponse {
  status: "ready" | "stale" | "missing";
  citation?: SearchCitationResult;
}

export interface DownloadedBlob {
  data: Uint8Array;
  contentType: string;
}