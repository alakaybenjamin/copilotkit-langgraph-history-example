/**
 * Custom History Client for FastAPI Server
 * 
 * This implements the HistoryClientInterface to connect to the FastAPI
 * server's history endpoints.
 */

import type {
  HistoryClientInterface,
  HistoryRun,
  HistoryStreamChunk,
  ThreadState,
} from "test-history-agui";

/**
 * Creates a custom history client that talks to the FastAPI server.
 * 
 * @param baseUrl - The base URL of the FastAPI server (e.g., "http://localhost:8123")
 * @returns HistoryClientInterface implementation
 */
export function createFastAPIHistoryClient(baseUrl: string): HistoryClientInterface {
  // Normalize URL (remove trailing slash)
  const url = baseUrl.replace(/\/$/, "");

  return {
    threads: {
      /**
       * Fetch checkpoint history for a thread.
       */
      async getHistory(threadId: string, options?: { limit?: number }): Promise<ThreadState[]> {
        const limit = options?.limit ?? 100;
        const response = await fetch(
          `${url}/threads/${encodeURIComponent(threadId)}/history?limit=${limit}`
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch history: ${response.statusText}`);
        }

        return response.json();
      },

      /**
       * Get the current state of a thread.
       */
      async getState(threadId: string): Promise<ThreadState> {
        const response = await fetch(
          `${url}/threads/${encodeURIComponent(threadId)}/state`
        );

        if (!response.ok) {
          if (response.status === 404) {
            // Return empty state for new threads
            return {
              values: { messages: [] },
              next: [],
              tasks: [],
            } as ThreadState;
          }
          throw new Error(`Failed to fetch state: ${response.statusText}`);
        }

        return response.json();
      },
    },

    runs: {
      /**
       * List runs for a thread.
       */
      async list(threadId: string): Promise<HistoryRun[]> {
        const response = await fetch(
          `${url}/runs?thread_id=${encodeURIComponent(threadId)}`
        );

        if (!response.ok) {
          throw new Error(`Failed to list runs: ${response.statusText}`);
        }

        return response.json();
      },

      /**
       * Join an active run's stream.
       * 
       * This returns an async iterable that yields stream chunks from the
       * FastAPI server's SSE endpoint.
       */
      async *joinStream(
        threadId: string,
        runId: string,
        options?: { streamMode?: string[] }
      ): AsyncIterable<HistoryStreamChunk> {
        const response = await fetch(
          `${url}/runs/${encodeURIComponent(runId)}/join?thread_id=${encodeURIComponent(threadId)}`,
          {
            method: "POST",
            headers: {
              Accept: "text/event-stream",
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              streamMode: options?.streamMode ?? ["events", "values", "updates", "custom"],
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to join stream: ${response.statusText}`);
        }

        if (!response.body) {
          return;
        }

        // Parse SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              break;
            }

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE events
            const lines = buffer.split("\n");
            buffer = lines.pop() || ""; // Keep incomplete line in buffer

            let currentEvent = "";
            let currentData = "";

            for (const line of lines) {
              if (line.startsWith("event: ")) {
                currentEvent = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                currentData = line.slice(6);
              } else if (line === "" && currentData) {
                // End of event - yield it
                try {
                  const data = JSON.parse(currentData);
                  yield {
                    event: currentEvent || "message",
                    data,
                  };
                } catch {
                  // Skip malformed JSON
                }
                currentEvent = "";
                currentData = "";
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      },
    },
  };
}


