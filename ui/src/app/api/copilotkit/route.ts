/**
 * CopilotKit API Route with Custom History Client
 * 
 * This demonstrates using the HistoryHydratingAgentRunner with a custom
 * client that talks to a self-hosted FastAPI server.
 */

import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";
import {
  HistoryHydratingAgentRunner,
} from "test-history-agui";
import { createFastAPIHistoryClient } from "@/lib/custom-history-client";

// FastAPI server URL
const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "http://localhost:8123";

// Create the custom history client for FastAPI
const customHistoryClient = createFastAPIHistoryClient(AGENT_URL);

// Service adapter (using empty adapter since we only have one agent)
const serviceAdapter = new ExperimentalEmptyAdapter();

/**
 * Create the CopilotKit runtime with history hydration support.
 * 
 * We create a new runtime per request to ensure clean state.
 */
function createRuntime() {
  // Create the LangGraph HTTP agent that talks to FastAPI
  const agent = new LangGraphHttpAgent({
    url: AGENT_URL,
  });

  // Create the history-hydrating runner with our custom client
  const runner = new HistoryHydratingAgentRunner({
    agent,
    // deploymentUrl and graphId are still needed for agent creation
    deploymentUrl: AGENT_URL,
    graphId: "history_agent",
    // Use custom client for history operations (threads/history, etc.)
    client: customHistoryClient,
    historyLimit: 100,
    debug: process.env.NODE_ENV === "development",
  });

  return new CopilotRuntime({
    agents: {
      history_agent: agent,
    },
    runner,
  });
}

/**
 * Handle POST requests to /api/copilotkit
 */
export const POST = async (req: NextRequest) => {
  const runtime = createRuntime();
  
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};

