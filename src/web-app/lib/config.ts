export interface AppConfig {
  environment: string;
  agentEndpoint: string;
  servingBlobEndpoint: string;
  servingContainerName: string;
  azuriteConnectionString: string;
  cosmosEndpoint: string;
  cosmosKey: string;
  cosmosDatabaseName: string;
  cosmosConversationsContainer: string;
  cosmosSessionsContainer: string;
  cosmosVerifyCert: boolean;
  localUserId: string;
  localUserName: string;
  localUserGroups: string[];
}

function optionalEnv(name: string, fallback = ""): string {
  return process.env[name]?.trim() || fallback;
}

function booleanEnv(name: string, fallback: boolean): boolean {
  const value = process.env[name]?.trim().toLowerCase();
  if (!value) {
    return fallback;
  }

  return value === "1" || value === "true" || value === "yes";
}

function listEnv(name: string, fallback: string[]): string[] {
  const value = process.env[name];
  if (!value) {
    return fallback;
  }

  const entries = value.split(",").map((entry) => entry.trim()).filter(Boolean);
  return entries.length > 0 ? entries : fallback;
}

export const config: AppConfig = {
  environment: optionalEnv("ENVIRONMENT", "dev"),
  agentEndpoint: optionalEnv("AGENT_ENDPOINT", "http://localhost:8088"),
  servingBlobEndpoint: optionalEnv("SERVING_BLOB_ENDPOINT"),
  servingContainerName: optionalEnv("SERVING_CONTAINER_NAME", "serving"),
  azuriteConnectionString: optionalEnv("AZURITE_CONNECTION_STRING"),
  cosmosEndpoint: optionalEnv("COSMOS_ENDPOINT"),
  cosmosKey: optionalEnv("COSMOS_KEY"),
  cosmosDatabaseName: optionalEnv("COSMOS_DATABASE_NAME", "kb-agent"),
  cosmosConversationsContainer: optionalEnv("COSMOS_CONVERSATIONS_CONTAINER", "conversations"),
  cosmosSessionsContainer: optionalEnv("COSMOS_SESSIONS_CONTAINER", "agent-sessions"),
  cosmosVerifyCert: booleanEnv("COSMOS_VERIFY_CERT", true),
  localUserId: optionalEnv("LOCAL_USER_ID", "local-user"),
  localUserName: optionalEnv("LOCAL_USER_NAME", "Local Developer"),
  localUserGroups: listEnv("LOCAL_USER_GROUPS", ["dev-group-guid"]),
};

export function isLocalEnvironment(): boolean {
  return config.environment.toLowerCase() === "dev";
}