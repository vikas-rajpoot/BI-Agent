export interface SavedChat {
  id: string;
  title: string;
  messages: { id: string; role: string; content: string }[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = "bi-agent-chats";
const ACTIVE_KEY = "bi-agent-active-chat";

export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

export function loadChats(): SavedChat[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveChats(chats: SavedChat[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
}

export function getActiveId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveId(id: string) {
  localStorage.setItem(ACTIVE_KEY, id);
}

export function titleFromMessage(content: string): string {
  const clean = content.replace(/\n/g, " ").trim();
  return clean.length > 40 ? clean.slice(0, 40) + "…" : clean;
}
