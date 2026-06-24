import { HttpAgent, type AbstractAgent } from "@ag-ui/client";

import { buildAgentHeaders } from "./auth";
import { config } from "./config";

function agentBaseUrl(): string {
  return config.agentEndpoint.replace(/\/+$/u, "");
}

export async function createRuntimeAgent(headers: Headers): Promise<AbstractAgent> {
  return new HttpAgent({
    headers: buildAgentHeaders(headers),
    url: `${agentBaseUrl()}/ag-ui/`,
  });
}

export async function fetchAgent(
  headers: Headers,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const mergedHeaders = new Headers(init.headers);
  for (const [key, value] of Object.entries(buildAgentHeaders(headers))) {
    mergedHeaders.set(key, value);
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return fetch(`${agentBaseUrl()}${normalizedPath}`, {
    ...init,
    headers: mergedHeaders,
  });
}