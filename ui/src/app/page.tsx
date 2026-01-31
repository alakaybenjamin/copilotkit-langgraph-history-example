"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { useState, useCallback, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";

// Sample users for demo - in production, this comes from your auth system
const SAMPLE_USERS = [
  { id: "user_alice", name: "Alice", avatar: "👩" },
  { id: "user_bob", name: "Bob", avatar: "👨" },
  { id: "user_charlie", name: "Charlie", avatar: "🧑" },
];

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "http://localhost:8123";

interface ThreadInfo {
  thread_id: string;
  user_id: string;
  title: string | null;
  created_at: string;
}

/**
 * Get thread ID from URL parameter if present
 */
function getThreadIdFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("threadId");
}

/**
 * User Selector Component - Simulates login
 */
function UserSelector({
  currentUser,
  onSelectUser,
}: {
  currentUser: typeof SAMPLE_USERS[0];
  onSelectUser: (user: typeof SAMPLE_USERS[0]) => void;
}) {
  return (
    <div className="user-selector">
      <h3>👤 Logged in as</h3>
      <div className="user-list">
        {SAMPLE_USERS.map((user) => (
          <button
            key={user.id}
            className={`user-btn ${user.id === currentUser.id ? "active" : ""}`}
            onClick={() => onSelectUser(user)}
          >
            <span className="avatar">{user.avatar}</span>
            <span className="name">{user.name}</span>
          </button>
        ))}
      </div>
      <p className="user-hint">Switch users to see different thread lists</p>
    </div>
  );
}

/**
 * Thread Selector Component
 */
function ThreadSelector({
  currentThreadId,
  threads,
  onSelectThread,
  onNewThread,
  loading,
}: {
  currentThreadId: string | null;
  threads: ThreadInfo[];
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  loading: boolean;
}) {
  const copyThreadLink = () => {
    if (!currentThreadId) return;
    const url = `${window.location.origin}?threadId=${currentThreadId}`;
    navigator.clipboard.writeText(url);
    alert(`Thread link copied!\n\n${url}\n\nShare this link to access the same conversation in another browser.`);
  };

  return (
    <div className="thread-selector">
      <h3>💬 My Threads</h3>
      <button onClick={onNewThread} className="new-thread-btn">
        + New Thread
      </button>
      {currentThreadId && (
        <button onClick={copyThreadLink} className="copy-link-btn" title="Copy shareable link">
          📋 Copy Link
        </button>
      )}
      
      {loading ? (
        <div className="loading">Loading threads...</div>
      ) : threads.length === 0 ? (
        <div className="no-threads">
          <p>No threads yet</p>
          <p className="hint">Click "New Thread" to start</p>
        </div>
      ) : (
        <ul className="thread-list">
          {threads.map((thread) => (
            <li
              key={thread.thread_id}
              className={thread.thread_id === currentThreadId ? "active" : ""}
              onClick={() => onSelectThread(thread.thread_id)}
            >
              <span className="thread-title">{thread.title || thread.thread_id.slice(0, 8) + "..."}</span>
              <span className="thread-date">
                {new Date(thread.created_at).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Main Chat Interface
 */
function ChatInterface({ threadId }: { threadId: string }) {
  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent="history_agent"
      threadId={threadId}
    >
      <div className="chat-container">
        <div className="chat-header">
          <h2>💬 Chat</h2>
          <span className="thread-id">Thread: {threadId.slice(0, 8)}...</span>
        </div>
        <CopilotChat
          labels={{
            title: "Assistant",
            initial: "Hi! I'm an assistant with persistent memory. Try asking about the weather or time, then refresh the page - your conversation will still be here!",
          }}
          className="chat-panel"
        />
      </div>
    </CopilotKit>
  );
}

/**
 * Main Page Component
 */
export default function Home() {
  // Current user (simulated login)
  const [currentUser, setCurrentUser] = useState(SAMPLE_USERS[0]);
  
  // Thread state
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch threads from server when user changes
  const fetchThreads = useCallback(async (userId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${AGENT_URL}/users/${userId}/threads`);
      if (response.ok) {
        const data = await response.json();
        setThreads(data);
        
        // Check URL for threadId parameter
        const urlThreadId = getThreadIdFromUrl();
        if (urlThreadId) {
          // If URL has threadId, select it (and register ownership if needed)
          await registerThread(userId, urlThreadId);
          setThreadId(urlThreadId);
        } else if (data.length > 0) {
          // Otherwise, select the most recent thread
          setThreadId(data[0].thread_id);
        } else {
          setThreadId(null);
        }
      }
    } catch (error) {
      console.error("Failed to fetch threads:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Register a thread for a user
  const registerThread = async (userId: string, newThreadId: string, title?: string) => {
    try {
      const response = await fetch(`${AGENT_URL}/users/${userId}/threads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: newThreadId,
          title: title || `Chat ${new Date().toLocaleString()}`,
        }),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.error("Failed to register thread:", error);
    }
    return null;
  };

  // Create a new thread
  const createNewThread = useCallback(async () => {
    const newThreadId = uuidv4();
    const registered = await registerThread(
      currentUser.id,
      newThreadId,
      `Chat ${new Date().toLocaleString()}`
    );
    
    if (registered) {
      setThreads((prev) => [registered, ...prev]);
      setThreadId(newThreadId);
    }
  }, [currentUser.id]);

  // Select a thread
  const selectThread = useCallback((newThreadId: string) => {
    setThreadId(newThreadId);
  }, []);

  // Switch user (simulates login/logout)
  const switchUser = useCallback((user: typeof SAMPLE_USERS[0]) => {
    setCurrentUser(user);
    setThreadId(null);
    setThreads([]);
    // Threads will be fetched by useEffect
  }, []);

  // Fetch threads on mount and when user changes
  useEffect(() => {
    fetchThreads(currentUser.id);
  }, [currentUser.id, fetchThreads]);

  return (
    <main className="main">
      <div className="header">
        <h1>🔄 CopilotKit + FastAPI History Demo</h1>
        <p>
          Thread ownership demo: Switch users to see different thread lists.
          <br />
          Threads persist in PostgreSQL and follow the user, not the browser!
        </p>
      </div>

      <div className="sidebar">
        <UserSelector
          currentUser={currentUser}
          onSelectUser={switchUser}
        />
      </div>

      <div className="content">
        <ThreadSelector
          currentThreadId={threadId}
          threads={threads}
          onSelectThread={selectThread}
          onNewThread={createNewThread}
          loading={loading}
        />
        
        {threadId ? (
          <ChatInterface key={threadId} threadId={threadId} />
        ) : (
          <div className="chat-container empty">
            <div className="empty-state">
              <h2>👋 Welcome, {currentUser.name}!</h2>
              <p>Select a thread or create a new one to start chatting.</p>
              <button onClick={createNewThread} className="start-btn">
                Start New Conversation
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="footer">
        <p>
          Powered by{" "}
          <a href="https://www.npmjs.com/package/copilotkit-langgraph-history" target="_blank">
            copilotkit-langgraph-history
          </a>
          {" • "}
          <span className="ownership-note">
            Ownership implemented by consumer (not library)
          </span>
        </p>
      </div>
    </main>
  );
}
