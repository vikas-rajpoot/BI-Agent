"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import type { SavedMessage } from "@/lib/chat-history";

const SUGGESTIONS = [
  "How's our pipeline looking?",
  "Revenue breakdown by sector",
  "What deals are at risk?",
  "Work order status summary",
];

interface ChatPanelProps {
  chatId: string;
  initialMessages: SavedMessage[];
  onMessagesChange: (msgs: SavedMessage[]) => void;
}

export default function ChatPanel({ chatId, initialMessages, onMessagesChange }: ChatPanelProps) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  const { messages, input, handleInputChange, handleSubmit, isLoading, append } =
    useChat({
      api: `${apiUrl}/api/stream`,
      id: chatId,
      initialMessages: initialMessages.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
      })),
    });

  const chatRef = useRef<HTMLDivElement>(null);
  const prevLenRef = useRef(initialMessages.length);

  // Sync messages back to parent only when they actually change
  useEffect(() => {
    if (messages.length === 0) return;
    if (messages.length === prevLenRef.current) return;
    prevLenRef.current = messages.length;
    onMessagesChange(
      messages.map((m) => ({ id: m.id, role: m.role, content: m.content }))
    );
  }, [messages, onMessagesChange]);

  // Also sync when streaming finishes (content of last message changes)
  const lastMsg = messages[messages.length - 1];
  const lastContentRef = useRef(lastMsg?.content || "");
  useEffect(() => {
    if (!lastMsg || isLoading) return;
    if (lastMsg.content !== lastContentRef.current) {
      lastContentRef.current = lastMsg.content;
      onMessagesChange(
        messages.map((m) => ({ id: m.id, role: m.role, content: m.content }))
      );
    }
  }, [lastMsg?.content, isLoading, messages, onMessagesChange]);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, lastMsg?.content]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const autoResize = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  const showWelcome = messages.length === 0;

  return (
    <>
      <div className="chat-area" ref={chatRef}>
        {showWelcome && (
          <div className="welcome">
            <h2>Monday.com Business Intelligence</h2>
            <p>
              Ask questions about your deals, work orders, pipeline health,
              revenue, sector performance, and more.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="suggestion"
                  onClick={() => append({ role: "user", content: s })}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="bubble">
              {m.role === "assistant" ? (
                <ReactMarkdown>{m.content}</ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}

        {isLoading && messages[messages.length - 1]?.role === "user" && (
          <div className="loading">
            <div className="loading-dots">
              <span /><span /><span />
            </div>
            <div className="loading-text">Querying Monday.com &amp; analyzing...</div>
          </div>
        )}
      </div>

      <div className="input-bar">
        <form className="input-row" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(e) => { handleInputChange(e); autoResize(e.target); }}
            onKeyDown={handleKeyDown}
            placeholder="Ask a business question..."
            rows={1}
          />
          <button type="submit" className="send-btn" disabled={isLoading || !input.trim()}>
            ↑
          </button>
        </form>
      </div>
    </>
  );
}
