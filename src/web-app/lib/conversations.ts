import { randomUUID } from "node:crypto";
import { Agent as HttpsAgent } from "node:https";

import { CosmosClient, type Container, type CosmosClientOptions, type SqlQuerySpec } from "@azure/cosmos";
import { DefaultAzureCredential } from "@azure/identity";

import { config } from "./config";
import {
  ConversationCreateRequest,
  ConversationMessage,
  ConversationRecord,
  ConversationUpdateRequest,
  UserContext,
} from "./types";

type SessionDocument = {
  id: string;
  session?: unknown;
  state?: unknown;
};

const memoryConversations = new Map<string, ConversationRecord>();
const memorySessionDocuments = new Map<string, SessionDocument>();
let cosmosClient: CosmosClient | null = null;

function normalizeTitle(title?: string): string {
  const trimmed = title?.trim();
  return trimmed ? trimmed.slice(0, 80) : "New conversation";
}

function shouldUseCosmos(): boolean {
  return Boolean(config.cosmosEndpoint);
}

function isCosmosEmulatorEndpoint(): boolean {
  try {
    const hostname = new URL(config.cosmosEndpoint).hostname.toLowerCase();
    return hostname === "cosmos-emulator" || hostname === "localhost" || hostname === "127.0.0.1";
  } catch {
    return false;
  }
}

function getCosmosClient(): CosmosClient {
  if (cosmosClient) {
    return cosmosClient;
  }

  cosmosClient = new CosmosClient(buildCosmosClientOptions());
  return cosmosClient;
}

export function buildCosmosClientOptions(): CosmosClientOptions {
  const options: CosmosClientOptions = {
    endpoint: config.cosmosEndpoint,
    userAgentSuffix: "kb-agent-web-app",
  };

  if (config.cosmosKey) {
    options.key = config.cosmosKey;
  } else {
    options.aadCredentials = new DefaultAzureCredential();
  }

  if (!config.cosmosVerifyCert && config.cosmosEndpoint.startsWith("https://")) {
    options.agent = new HttpsAgent({ rejectUnauthorized: false }) as CosmosClientOptions["agent"];
  }

  if (isCosmosEmulatorEndpoint()) {
    options.connectionPolicy = {
      enableEndpointDiscovery: false,
    };
  }

  return options;
}

function getContainer(containerName: string): Container {
  return getCosmosClient()
    .database(config.cosmosDatabaseName)
    .container(containerName);
}

function conversationsContainer(): Container {
  return getContainer(config.cosmosConversationsContainer);
}

function sessionsContainer(): Container {
  return getContainer(config.cosmosSessionsContainer);
}

function ownedMemoryConversations(userId: string): ConversationRecord[] {
  return [...memoryConversations.values()]
    .filter((conversation) => conversation.userId === userId)
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}

function messageContentToString(value: unknown): string | undefined {
  if (value === undefined) {
    return undefined;
  }

  return typeof value === "string" ? value : JSON.stringify(value);
}

function normalizeToolCalls(value: unknown): unknown[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  return value.map((toolCall) => {
    if (!toolCall || typeof toolCall !== "object") {
      return toolCall;
    }

    const record = toolCall as Record<string, unknown>;
    const functionRecord = record.function && typeof record.function === "object"
      ? record.function as Record<string, unknown>
      : undefined;

    return {
      ...record,
      type: record.type ?? "function",
      function: functionRecord
        ? {
            ...functionRecord,
            arguments: messageContentToString(functionRecord.arguments) ?? "{}",
          }
        : undefined,
    };
  });
}

function normalizeMessage(value: unknown): ConversationMessage | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;
  const id = typeof record.id === "string" ? record.id : randomUUID();
  const role = typeof record.role === "string" ? record.role : null;
  if (!role) {
    return null;
  }

  return {
    content: messageContentToString(record.content),
    encryptedValue: typeof record.encryptedValue === "string" ? record.encryptedValue : undefined,
    id,
    name: typeof record.name === "string" ? record.name : undefined,
    role,
    toolCallId: typeof record.toolCallId === "string" ? record.toolCallId : undefined,
    toolCalls: normalizeToolCalls(record.toolCalls),
    toolName: typeof record.toolName === "string" ? record.toolName : undefined,
  };
}

function findMessages(value: unknown): unknown[] {
  if (!value || typeof value !== "object") {
    return [];
  }

  const record = value as Record<string, unknown>;
  if (Array.isArray(record.messages)) {
    return record.messages;
  }

  if (record.state && typeof record.state === "object") {
    const state = record.state as Record<string, unknown>;
    if (Array.isArray(state.messages)) {
      return state.messages;
    }

    if (state.in_memory && typeof state.in_memory === "object") {
      const inMemory = state.in_memory as Record<string, unknown>;
      if (Array.isArray(inMemory.messages)) {
        return inMemory.messages;
      }
    }
  }

  return [];
}

function normalizeSessionMessages(document: SessionDocument | null | undefined): ConversationMessage[] {
  if (!document) {
    return [];
  }

  const candidates = [document.session, document.state, document];
  for (const candidate of candidates) {
    const messages = findMessages(candidate)
      .map((message) => normalizeMessage(message))
      .filter((message): message is ConversationMessage => message !== null);
    if (messages.length > 0) {
      return messages;
    }
  }

  return [];
}

export async function listConversationsForUser(userId: string): Promise<ConversationRecord[]> {
  if (!shouldUseCosmos()) {
    return ownedMemoryConversations(userId);
  }

  const query: SqlQuerySpec = {
    parameters: [{ name: "@userId", value: userId }],
    query: "SELECT * FROM c WHERE c.userId = @userId ORDER BY c.updatedAt DESC",
  };
  const { resources } = await conversationsContainer()
    .items.query<ConversationRecord>(query, { partitionKey: userId })
    .fetchAll();

  return resources;
}

export async function createConversationForUser(
  user: UserContext,
  request: ConversationCreateRequest = {},
): Promise<ConversationRecord> {
  const now = new Date().toISOString();
  const conversation: ConversationRecord = {
    createdAt: now,
    id: request.id?.trim() || randomUUID(),
    name: normalizeTitle(request.title),
    updatedAt: now,
    userId: user.userId,
    userIdentifier: user.userIdentifier,
  };

  if (!shouldUseCosmos()) {
    memoryConversations.set(conversation.id, conversation);
    return conversation;
  }

  await conversationsContainer().items.upsert(conversation);
  return conversation;
}

export async function getConversationForUser(
  userId: string,
  threadId: string,
): Promise<ConversationRecord | null> {
  if (!shouldUseCosmos()) {
    const conversation = memoryConversations.get(threadId);
    return conversation?.userId === userId ? conversation : null;
  }

  try {
    const { resource } = await conversationsContainer().item(threadId, userId).read<ConversationRecord>();
    return resource ?? null;
  } catch {
    return null;
  }
}

export async function updateConversationForUser(
  userId: string,
  threadId: string,
  request: ConversationUpdateRequest,
): Promise<ConversationRecord | null> {
  const conversation = await getConversationForUser(userId, threadId);
  if (!conversation) {
    return null;
  }

  const updated: ConversationRecord = {
    ...conversation,
    name: normalizeTitle(request.title ?? conversation.name),
    updatedAt: new Date().toISOString(),
  };

  if (!shouldUseCosmos()) {
    memoryConversations.set(updated.id, updated);
    return updated;
  }

  await conversationsContainer().items.upsert(updated);
  return updated;
}

export async function deleteConversationForUser(userId: string, threadId: string): Promise<boolean> {
  const conversation = await getConversationForUser(userId, threadId);
  if (!conversation) {
    return false;
  }

  if (!shouldUseCosmos()) {
    memoryConversations.delete(threadId);
    memorySessionDocuments.delete(threadId);
    return true;
  }

  await conversationsContainer().item(threadId, userId).delete();
  return true;
}

export async function fetchConversationMessagesForUser(
  userId: string,
  threadId: string,
): Promise<ConversationMessage[] | null> {
  const conversation = await getConversationForUser(userId, threadId);
  if (!conversation) {
    return null;
  }

  if (!shouldUseCosmos()) {
    return normalizeSessionMessages(memorySessionDocuments.get(threadId));
  }

  try {
    const { resource } = await sessionsContainer().item(threadId, threadId).read<SessionDocument>();
    return normalizeSessionMessages(resource);
  } catch {
    return [];
  }
}

export function resetConversationStoreForTests(): void {
  memoryConversations.clear();
  memorySessionDocuments.clear();
  cosmosClient = null;
}

export function seedConversationMessagesForTests(threadId: string, document: SessionDocument): void {
  memorySessionDocuments.set(threadId, document);
}