import { useSyncExternalStore } from "react";

/**
 * The visitor's past runs, remembered by this browser only (no accounts). Each entry points to a result kept on the
 * server, so its link works anywhere. Storage can be unavailable (private windows, blocked site data): then the
 * history is simply empty.
 */
export interface HistoryEntry {
  id: string;  // result id
  kind: "optimise" | "backtest";
  title: string;
  market: string;
  detail: string;
  createdAt: string;  // ISO time
}

const KEY = "qapital.history.v1";
const LIMIT = 40;
const listeners = new Set<() => void>();
let cache: HistoryEntry[] | null = null;

function read(): HistoryEntry[] {
  if (cache) return cache;
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    cache = Array.isArray(parsed) ? (parsed as HistoryEntry[]) : [];
  } catch {
    cache = [];
  }
  return cache;
}

function write(entries: HistoryEntry[]): void {
  cache = entries;
  try {
    localStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // storage blocked or full: keep the list for this visit only
  }
  for (const listener of listeners) listener();
}

export function addToHistory(entry: HistoryEntry): void {
  write([entry, ...read().filter((e) => e.id !== entry.id)].slice(0, LIMIT));
}

export function removeFromHistory(id: string): void {
  write(read().filter((e) => e.id !== id));
}

export function clearHistory(): void {
  write([]);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === KEY) {
      cache = null;
      listener();
    }
  };
  addEventListener("storage", onStorage);  // another tab changed it
  return () => {
    listeners.delete(listener);
    removeEventListener("storage", onStorage);
  };
}

export function useHistory(): HistoryEntry[] {
  return useSyncExternalStore(subscribe, read, () => []);
}
