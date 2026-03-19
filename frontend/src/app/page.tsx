"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

const SUGGESTIONS = [
  "How's our pipeline looking?",
  "Revenue breakdown by sector",
  "What deals are at risk?",
  "Work order status summary",
];

export default function Home() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const { messages, input, handleInputChange, handleSubmit, isLoading, setInput, append } =
    useChat({
      api: `${apiUrl}/api/stream`,
    });

  const chatRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

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

  const useSuggestion = (text: string) => {
    append({ role: "user", content: text });
  };

  const showWelcome = messages.length === 0;

  return (
    <>
      <div className="header">
        <div className="logo">BI</div>
        <h1>BI Agent</h1>
        <div className="badge">Live</div>
      </div>

      <div className="chat-area" ref={chatRef}>
        {showWelcome && (
          <div className="welcome">
            <h2>Monday.com Business Intelligence</h2>
            <p>
              Ask questions about your deals, work orders, pipeline health,
              revenue, sector performance, and more. Every query hits live
              Monday.com data.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion" onClick={() => useSuggestion(s)}>
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
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              handleInputChange(e);
              autoResize(e.target);
            }}
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
