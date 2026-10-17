import { useQueryClient } from "@tanstack/react-query";
import { createContext, use, useEffect, useMemo, useState, type ReactNode } from "react";
import { createLiveApi, createSavedApi, type LiveApi, type ReadApi } from "./client";

/**
 * Which API the site is using:
 * - "checking": asking the live API whether it is up (a moment, on first load)
 * - "live":     the live API answers; runs can start
 * - "waking":   the live API didn't answer yet (free hosting sleeps when idle); saved runs are shown meanwhile
 * - "saved":    no live API is configured, or it stayed asleep; saved runs only
 */
export type ConnectionState = "checking" | "live" | "waking" | "saved";

export interface Connection {
  state: ConnectionState;
  /** What pages read from: the live API when it is up, otherwise the saved runs. */
  api: ReadApi;
  /** Set only when the live API is up. */
  live: LiveApi | null;
  saved: ReturnType<typeof createSavedApi>;
  /** Try the live API again (after it stayed asleep). */
  retry(): void;
}

const FIRST_TRY_MS = 4000;
const WAKE_TRY_MS = 20000;
const WAKE_GIVE_UP_MS = 4 * 60 * 1000;
const PAUSE_MS = 3000;

const ConnectionContext = createContext<Connection | null>(null);

export function ConnectionProvider({ apiUrl, children }: { apiUrl: string | undefined; children: ReactNode }) {
  const queryClient = useQueryClient();
  const saved = useMemo(() => createSavedApi(), []);
  const live = useMemo(() => (apiUrl ? createLiveApi(apiUrl) : null), [apiUrl]);
  const [state, setState] = useState<ConnectionState>(live ? "checking" : "saved");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!live) return undefined;
    let stopped = false;
    const started = Date.now();
    (async () => {
      for (let tries = 0; !stopped; tries++) {
        try {
          await live.health(tries === 0 ? FIRST_TRY_MS : WAKE_TRY_MS);
          if (stopped) return;
          setState("live");
          queryClient.invalidateQueries();  // re-read everything from the live API
          return;
        } catch {
          if (stopped) return;
          if (Date.now() - started > WAKE_GIVE_UP_MS) {
            setState("saved");
            return;
          }
          setState("waking");
          await new Promise((resolve) => setTimeout(resolve, PAUSE_MS));
        }
      }
    })();
    return () => {
      stopped = true;
    };
  }, [live, attempt, queryClient]);

  const value = useMemo<Connection>(() => ({
    state,
    api: state === "live" && live ? live : saved,
    live: state === "live" ? live : null,
    saved,
    retry: () => {
      setState("checking");
      setAttempt((n) => n + 1);
    },
  }), [state, live, saved]);

  return <ConnectionContext value={value}>{children}</ConnectionContext>;
}

export function useConnection(): Connection {
  const connection = use(ConnectionContext);
  if (!connection) throw new Error("useConnection needs a ConnectionProvider above it.");
  return connection;
}
