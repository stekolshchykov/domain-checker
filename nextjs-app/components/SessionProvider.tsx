"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Brief, DomainIdea, DomainResult } from "@/lib/types";

interface SessionState {
  brief: Brief | null;
  ideas: DomainIdea[] | null;
  results: DomainResult[] | null;
  checkedAt: string | null;
  setBrief: (b: Brief) => void;
  setIdeas: (ideas: DomainIdea[]) => void;
  setResults: (results: DomainResult[], checkedAt: string) => void;
  clearSession: () => void;
}

const SessionContext = createContext<SessionState | null>(null);

const STORAGE_KEY = "nomen-session-v1";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [brief, setBriefState] = useState<Brief | null>(null);
  const [ideas, setIdeasState] = useState<DomainIdea[] | null>(null);
  const [results, setResultsState] = useState<DomainResult[] | null>(null);
  const [checkedAt, setCheckedAtState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.brief) setBriefState(parsed.brief);
        if (parsed.ideas) setIdeasState(parsed.ideas);
        if (parsed.results) setResultsState(parsed.results);
        if (parsed.checkedAt) setCheckedAtState(parsed.checkedAt);
      }
    } catch {
      // ignore
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const payload = JSON.stringify({ brief, ideas, results, checkedAt });
    localStorage.setItem(STORAGE_KEY, payload);
  }, [brief, ideas, results, checkedAt, hydrated]);

  const setBrief = (b: Brief) => setBriefState(b);
  const setIdeas = (ideas: DomainIdea[]) => setIdeasState(ideas);
  const setResults = (results: DomainResult[], checkedAt: string) => {
    setResultsState(results);
    setCheckedAtState(checkedAt);
  };
  const clearSession = () => {
    setBriefState(null);
    setIdeasState(null);
    setResultsState(null);
    setCheckedAtState(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <SessionContext.Provider
      value={{
        brief,
        ideas,
        results,
        checkedAt,
        setBrief,
        setIdeas,
        setResults,
        clearSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
