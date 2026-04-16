"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import type { Brief, DomainIdea, DomainResult } from "@/lib/types";

interface SessionState {
  brief: Brief | null;
  ideas: DomainIdea[] | null;
  results: DomainResult[] | null;
  checkedAt: string | null;
  colorPalette: string[] | null;
  logos: string[] | null;
  hydrated: boolean;
  setBrief: (b: Brief) => void;
  setIdeas: (ideas: DomainIdea[]) => void;
  setResults: (results: DomainResult[], checkedAt: string) => void;
  setGenerationExtras: (palette: string[], logos: string[]) => void;
  clearSession: () => void;
}

const STORAGE_KEY = "nomen-session-v1";

const SessionContext = createContext<SessionState | null>(null);

function getSnapshot(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function getServerSnapshot(): null {
  return null;
}

function subscribe(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  const handler = () => callback();
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

function parseSession(raw: string | null) {
  if (!raw) {
    return {
      brief: null,
      ideas: null,
      results: null,
      checkedAt: null,
      colorPalette: null,
      logos: null,
    };
  }
  try {
    const parsed = JSON.parse(raw);
    return {
      brief: parsed.brief ?? null,
      ideas: parsed.ideas ?? null,
      results: parsed.results ?? null,
      checkedAt: parsed.checkedAt ?? null,
      colorPalette: parsed.colorPalette ?? null,
      logos: parsed.logos ?? null,
    };
  } catch {
    return {
      brief: null,
      ideas: null,
      results: null,
      checkedAt: null,
      colorPalette: null,
      logos: null,
    };
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const raw = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const session = useMemo(() => parseSession(raw), [raw]);

  const persist = useCallback((next: Partial<ReturnType<typeof parseSession>>) => {
    if (typeof window === "undefined") return;
    const current = parseSession(localStorage.getItem(STORAGE_KEY));
    const updated = { ...current, ...next };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    // Dispatch a synthetic storage event so other tabs and the store subscription update
    window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY }));
  }, []);

  const setBrief = useCallback(
    (b: Brief) => persist({ brief: b }),
    [persist]
  );
  const setIdeas = useCallback(
    (ideas: DomainIdea[]) => persist({ ideas }),
    [persist]
  );
  const setResults = useCallback(
    (results: DomainResult[], checkedAt: string) =>
      persist({ results, checkedAt }),
    [persist]
  );
  const setGenerationExtras = useCallback(
    (colorPalette: string[], logos: string[]) =>
      persist({ colorPalette, logos }),
    [persist]
  );
  const clearSession = useCallback(() => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY }));
  }, []);

  const value = useMemo(
    () => ({
      ...session,
      hydrated: typeof window !== "undefined",
      setBrief,
      setIdeas,
      setResults,
      setGenerationExtras,
      clearSession,
    }),
    [session, setBrief, setIdeas, setResults, setGenerationExtras, clearSession]
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
