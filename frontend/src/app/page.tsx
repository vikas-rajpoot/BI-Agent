"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect, useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import {
  SavedChat, loadChats, saveChats, getActiveId, setActiveId,
  generateId, titleFromMessage,
} from "@/lib/chat-history";

const SUGGESTIONS = [
  "How's our pipeline looking?",
  "Revenue breakdown by sector",
  "What deals are at risk?",
  "Work order status summary",
];

export default function Home() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const [chats, setChats] = useState<SavedChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string>("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mounted, setMounted] = useState(false);

  // Load history on mount
  useEffect(() => {
    const saved = loadChats();
    const activeId = getActiveId();
    if (saved.length > 0) {
      setChats(saved);
      const found = activeId && saved.find((c) => c.id === activeId);
      setActiveChatId(found ? activeId! : saved[0].id);
    } else {
      const newChat: SavedChat = {
        id: generateId(), title: "New chat", messages: [],
        createdAt: Date.now(), updatedAt: Date.now(),
      };
      setChats([newChat]);
      setActiveChatId(newChat.id);
      saveChats([newChat]);
    }
    setMounted(true);
  }, []);

  const activeChat = chats.find((c) => c.id === activeChatId);

  const {
    messages, input, handleInputChange, handleSubmit, isLoading, append, setMessages,
  } = useChat({
    api: `${apiUrl}/api/stream`,
    id: activeChatId,
    initialMessages: activeChat?.messages?.map((m) => ({
      id: m.id, role: m.role as "user" | "assistant", content: m.content,
    })) || [],
  });

  // Persist messages when they change
  useEffect(() => {
    if (!mounted || !activeChatId || messages.length === 0) return;
    setChats((prev) => {
      const updated = prev.map((c) => {
        if (c.id !== activeChatId) return c;
        const title = c.messages.length === 0 && messages.length > 0
          ? titleFromMessage(messages[0].content)
          : c.title;
        return {
          ...c, title,
          messages: messages.map((m) => ({ id: m.id, role: m.role, content: m.content })),
          updatedAt: Date.now(),
        };
      });
      saveChats(updated);
      return updated;
    });
  }, [messages, activeChatId, mounted]);

  // Track active chat in localStorage
  useEffect(() => {
    if (activeChatId) setActiveId(activeChatId);
  }, [activeChatId]);

  const chatRef = useRef<HTMLDivElement>(null);

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

  const newChat = useCallback(() => {
    const chat: SavedChat = {
      id: generateId(), title: "New chat", messages: [],
      createdAt: Date.now(), updatedAt: Date.now(),
    };
    setChats((prev) => {
      const updated = [chat, ...prev];
      saveChats(updated);
      return updated;
    });
    setActiveChatId(chat.id);
    setMessages([]);
  }, [setMessages]);

  const switchChat = useCallback((id: string) => {
    const chat = chats.find((c) => c.id === id);
    if (!chat) return;
    setActiveChatId(id);
    setMessages(
      chat.messages.map((m) => ({
        id: m.id, role: m.role as "user" | "assistant", content: m.content,
      }))
    );
  }, [chats, setMessages]);

  const deleteChat = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChats((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      if (updated.length === 0) {
        const fresh: SavedChat = {
          id: generateId(), title: "New chat", messages: [],
          createdAt: Date.now(), updatedAt: Date.now(),
        };
        saveChats([fresh]);
        setActiveChatId(fresh.id);
        setMessages([]);
        return [fresh];
      }
      saveChats(updated);
      if (id === activeChatId) {
        setActiveChatId(updated[0].id);
        setMessages(
          updated[0].messages.map((m) => ({
            id: m.id, role: m.role as "user" | "assistant", content: m.content,
          }))
        );
      }
      return updated;
    });
  }, [activeChatId, setMessages]);

  const showWelcome = messages.length === 0;

  if (!mounted) return null;

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={newChat}>+ New chat</button>
        </div>
        <div className="sidebar-list">
          {chats.map((c) => (
            <div
              key={c.id}
              className={`sidebar-item ${c.id === activeChatId ? "active" : ""}`}
              onClick={() => switchChat(c.id)}
            >
              <span className="sidebar-item-title">{c.title}</span>
              <button
                className="sidebar-item-delete"
                onClick={(e) => deleteChat(c.id, e)}
                aria-label="Delete chat"
              >×</button>
            </div>
          ))}
        </div>
      </div>

      {/* Main */}
      <div className="main-area">
        <div className="header">
          <button className="toggle-sidebar" onClick={() => setSidebarOpen(!sidebarOpen)}>
            ☰
          </button>
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
                revenue, sector performance, and more.
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
      </div>
    </div>
  );
}
