"use client";

import { useEffect, useState, useCallback } from "react";
import ChatPanel from "@/components/chat-panel";
import {
  SavedChat, SavedMessage, loadChats, saveChats,
  getActiveId, setActiveId, generateId, upsertChat,
} from "@/lib/chat-history";

function createEmptyChat(): SavedChat {
  return {
    id: generateId(),
    title: "New chat",
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}

export default function Home() {
  const [chats, setChats] = useState<SavedChat[]>([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mounted, setMounted] = useState(false);

  // Load on mount
  useEffect(() => {
    const saved = loadChats();
    const activeId = getActiveId();

    if (saved.length > 0) {
      setChats(saved);
      const found = activeId && saved.find((c) => c.id === activeId);
      setActiveChatId(found ? activeId! : saved[0].id);
    } else {
      const fresh = createEmptyChat();
      setChats([fresh]);
      setActiveChatId(fresh.id);
      saveChats([fresh]);
    }
    setMounted(true);
  }, []);

  // Persist active ID
  useEffect(() => {
    if (activeChatId) setActiveId(activeChatId);
  }, [activeChatId]);

  const activeChat = chats.find((c) => c.id === activeChatId);

  // Called by ChatPanel when messages change
  const handleMessagesChange = useCallback(
    (msgs: SavedMessage[]) => {
      setChats((prev) => {
        const updated = upsertChat(prev, activeChatId, msgs);
        saveChats(updated);
        return updated;
      });
    },
    [activeChatId]
  );

  const newChat = useCallback(() => {
    const chat = createEmptyChat();
    setChats((prev) => {
      const updated = [chat, ...prev];
      saveChats(updated);
      return updated;
    });
    setActiveChatId(chat.id);
  }, []);

  const switchChat = useCallback((id: string) => {
    setActiveChatId(id);
  }, []);

  const deleteChat = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setChats((prev) => {
        const updated = prev.filter((c) => c.id !== id);
        if (updated.length === 0) {
          const fresh = createEmptyChat();
          saveChats([fresh]);
          setActiveChatId(fresh.id);
          return [fresh];
        }
        saveChats(updated);
        if (id === activeChatId) {
          setActiveChatId(updated[0].id);
        }
        return updated;
      });
    },
    [activeChatId]
  );

  if (!mounted) return null;

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={newChat}>
            + New chat
          </button>
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
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main */}
      <div className="main-area">
        <div className="header">
          <button
            className="toggle-sidebar"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            ☰
          </button>
          <div className="logo">BI</div>
          <h1>BI Agent</h1>
          <div className="badge">Live</div>
        </div>

        {/* key forces full remount when switching chats */}
        {activeChat && (
          <ChatPanel
            key={activeChatId}
            chatId={activeChatId}
            initialMessages={activeChat.messages}
            onMessagesChange={handleMessagesChange}
          />
        )}
      </div>
    </div>
  );
}
