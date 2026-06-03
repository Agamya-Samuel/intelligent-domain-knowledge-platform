"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

/* ── Types ─────────────────────────────────────────────────────────── */

interface Citation {
  source: string;
  page?: number;
  section?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  latencyMs?: number;
  isStreaming?: boolean;
}

/* ── SSE Stream Parser ─────────────────────────────────────────────── */

function parseSSE(text: string): { event: string; data: string }[] {
  const events: { event: string; data: string }[] = [];
  let currentEvent = "";
  const lines = text.split("\n");

  for (const line of lines) {
    if (line.startsWith("event:")) {
      currentEvent = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      const data = line.slice(5).trim();
      if (data) {
        events.push({ event: currentEvent || "message", data });
      }
    } else if (line === "" && currentEvent) {
      currentEvent = "";
    }
  }
  return events;
}

/* ── API Helper ────────────────────────────────────────────────────── */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Extract the Auth.js v5 session token from cookies.
 * Auth.js stores an encrypted JWE in "next-auth.session-token" cookie.
 * The backend decodes this with the shared AUTH_SECRET.
 */
function getSessionToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith("next-auth.session-token="));
  return match ? match.split("=")[1] : undefined;
}

async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getSessionToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${API_URL}${url}`, { ...options, headers, credentials: "include" });
}

/* ── Chat Page Component ───────────────────────────────────────────── */

export default function ChatPage() {
  const { data: session, status } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelVariant, setModelVariant] = useState<"base" | "finetuned">("base");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const sendMessage = useCallback(async () => {
    const query = input.trim();
    if (!query || isStreaming || !session) return;

    setError(null);
    setInput("");

    // Add user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
      citations: [],
    };

    // Add placeholder assistant message
    const assistantMsgId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      citations: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await fetchWithAuth("/api/v1/chat", {
        method: "POST",
        body: JSON.stringify({
          query,
          session_id: activeSessionId,
          model_variant: modelVariant,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw new Error(errBody || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let fullContent = "";
      const citations: Citation[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = parseSSE(buffer);
        // Keep only unprocessed data (incomplete event block)
        const lastNewline = buffer.lastIndexOf("\n\n");
        buffer = lastNewline >= 0 ? buffer.slice(lastNewline + 2) : buffer;

        for (const { event, data: rawData } of events) {
          try {
            const parsed = JSON.parse(rawData);

            switch (event) {
              case "token": {
                if (parsed.content) {
                  fullContent += parsed.content;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMsgId
                        ? { ...m, content: fullContent }
                        : m,
                    ),
                  );
                }
                break;
              }
              case "citation": {
                citations.push({
                  source: parsed.source,
                  page: parsed.page,
                  section: parsed.section,
                });
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, citations: [...citations] }
                      : m,
                  ),
                );
                break;
              }
              case "done": {
                setActiveSessionId(parsed.session_id);
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? {
                          ...m,
                          isStreaming: false,
                          latencyMs: parsed.latency_ms,
                          citations:
                            parsed.citations_count > 0
                              ? citations
                              : m.citations,
                        }
                      : m,
                  ),
                );
                break;
              }
              case "error": {
                setError(parsed.error || "Unknown error");
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, isStreaming: false }
                      : m,
                  ),
                );
                break;
              }
            }
          } catch {
            // Ignore malformed JSON in SSE
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message || "Failed to send message");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, isStreaming: false } : m,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [input, isStreaming, session, activeSessionId, modelVariant]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const stopStreaming = () => {
    abortControllerRef.current?.abort();
  };

  // Auth loading / unauthenticated state
  if (status === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">Sign in required</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            Please sign in to start a conversation with your documents.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Model variant toggle */}
      <div className="flex items-center justify-center gap-3 border-b px-6 py-2">
        <span className={`text-xs ${modelVariant === "base" ? "font-semibold text-primary" : "text-muted-foreground"}`}>
          Base
        </span>
        <button
          type="button"
          onClick={() => setModelVariant(modelVariant === "base" ? "finetuned" : "base")}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
            modelVariant === "finetuned" ? "bg-primary" : "bg-muted"
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
              modelVariant === "finetuned" ? "translate-x-4.5" : "translate-x-0.5"
            }`}
          />
        </button>
        <span className={`text-xs ${modelVariant === "finetuned" ? "font-semibold text-primary" : "text-muted-foreground"}`}>
          Fine-tuned
        </span>
        {modelVariant === "finetuned" && (
          <span className="ml-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
            FT
          </span>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 ? (
            <div className="flex h-full min-h-[50vh] items-center justify-center">
              <Card className="w-full max-w-lg">
                <CardHeader>
                  <CardTitle className="text-center">
                    Start a conversation
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-center text-sm text-muted-foreground">
                    Ask questions about your documents. Responses will be
                    grounded in your knowledge corpus with full citations.
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  {/* Message content */}
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                    {msg.isStreaming && (
                      <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-current" />
                    )}
                  </p>

                  {/* Citations */}
                  {msg.citations.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {msg.citations.map((cite, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 rounded border bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
                          title={`Source: ${cite.source}${cite.page ? ` — Page ${cite.page}` : ""}${cite.section ? ` — ${cite.section}` : ""}`}
                        >
                          <svg
                            className="h-3 w-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                            />
                          </svg>
                          {cite.source}
                          {cite.page && `:${cite.page}`}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Latency */}
                  {msg.latencyMs && (
                    <p className="mt-1 text-[10px] text-muted-foreground/70">
                      {msg.latencyMs}ms
                    </p>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="border-t bg-destructive/10 px-6 py-2 text-center text-sm text-destructive">
          {error}
          <button
            className="ml-2 underline"
            onClick={() => setError(null)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="border-t bg-background px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question..."
            disabled={isStreaming}
            className="flex-1"
          />
          {isStreaming ? (
            <Button variant="outline" size="sm" onClick={stopStreaming}>
              Stop
            </Button>
          ) : (
            <Button size="sm" onClick={sendMessage} disabled={!input.trim()}>
              Send
            </Button>
          )}
        </div>
        {activeSessionId && (
          <p className="mt-2 text-center text-[11px] text-muted-foreground">
            Session: {activeSessionId.slice(0, 8)}...
          </p>
        )}
      </div>
    </div>
  );
}
