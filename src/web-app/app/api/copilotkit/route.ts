import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";

import { createRuntimeAgent } from "../../../lib/agent";

export const runtime = "nodejs";

async function handleCopilotRequest(request: Request): Promise<Response> {
  const runtimeInstance = new CopilotRuntime({
    agents: {
      default: await createRuntimeAgent(request.headers),
    },
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    endpoint: "/api/copilotkit",
    runtime: runtimeInstance,
    serviceAdapter: new ExperimentalEmptyAdapter(),
  });

  return handleRequest(request);
}

export async function GET(request: Request): Promise<Response> {
  return handleCopilotRequest(request);
}

export async function POST(request: Request): Promise<Response> {
  return handleCopilotRequest(request);
}