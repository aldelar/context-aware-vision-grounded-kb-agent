"use client";

import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";

import { SearchCitationResult } from "../lib/types";

export type RegisteredCitation = {
  citation: SearchCitationResult;
  threadId: string | null;
  toolCallId: string | undefined;
  /** "internal" for search_knowledge_base, "web" for web_search */
  source: "internal" | "web";
  /** Display label like "Ref 1.3" */
  displayLabel?: string;
  /** Turn number this citation belongs to */
  turnNumber?: number;
};

/** Build a scoped key that prevents collisions across tool calls and turns. */
export function citationKey(toolCallId: string | undefined, refNumber: number): string {
  return `${toolCallId ?? "unknown"}:${refNumber}`;
}

type CitationDialogState = {
  /** The composite key currently open in the dialog, or null if closed. */
  openKey: string | null;
  /** Open the dialog for a given scoped citation key. */
  openCitation: (key: string) => void;
  /** Close the dialog. */
  closeCitation: () => void;
  /** Register a citation with a scoped key. */
  registerCitation: (key: string, entry: RegisteredCitation) => void;
  /** Look up a registered citation by scoped key. */
  getCitation: (key: string) => RegisteredCitation | undefined;
  /** Find the first registered key matching a ref number (for inline [Ref #N] clicks). */
  findKeyByRefNumber: (refNumber: number, turnNumber?: number) => string | null;
  /** Clear all registered citations (call on thread switch). */
  clearCitations: () => void;
};

const CitationDialogContext = createContext<CitationDialogState | null>(null);

export function CitationDialogProvider({ children }: { children: ReactNode }) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [registry, setRegistry] = useState<Map<string, RegisteredCitation>>(new Map());

  const registerCitation = useCallback((key: string, entry: RegisteredCitation) => {
    setRegistry((current) => {
      const existing = current.get(key);
      if (
        existing &&
        existing.citation === entry.citation &&
        existing.threadId === entry.threadId &&
        existing.toolCallId === entry.toolCallId
      ) {
        return current;
      }

      const next = new Map(current);
      next.set(key, entry);
      return next;
    });
  }, []);

  const getCitation = useCallback(
    (key: string) => registry.get(key),
    [registry],
  );

  const openCitation = useCallback((key: string) => {
    setOpenKey(key);
  }, []);

  const closeCitation = useCallback(() => {
    setOpenKey(null);
  }, []);

  const clearCitations = useCallback(() => {
    setRegistry(new Map());
    setOpenKey(null);
  }, []);

  const findKeyByRefNumber = useCallback(
    (refNumber: number, turnNumber?: number): string | null => {
      const suffix = `:${refNumber}`;
      // If turnNumber is provided, prefer entries from that turn
      if (turnNumber !== undefined) {
        for (const [key, entry] of registry.entries()) {
          if (key.endsWith(suffix) && entry.turnNumber === turnNumber) {
            return key;
          }
        }
      }
      // Fallback: return the last key matching this ref number
      // (last registered = most recent turn)
      let lastKey: string | null = null;
      for (const key of registry.keys()) {
        if (key.endsWith(suffix)) {
          lastKey = key;
        }
      }
      return lastKey;
    },
    [registry],
  );

  const value = useMemo<CitationDialogState>(
    () => ({ openKey, openCitation, closeCitation, registerCitation, getCitation, findKeyByRefNumber, clearCitations }),
    [openKey, openCitation, closeCitation, registerCitation, getCitation, findKeyByRefNumber, clearCitations],
  );

  return (
    <CitationDialogContext.Provider value={value}>
      {children}
    </CitationDialogContext.Provider>
  );
}

export function useCitationDialog(): CitationDialogState {
  const context = useContext(CitationDialogContext);
  if (!context) {
    throw new Error("useCitationDialog must be used within a CitationDialogProvider");
  }
  return context;
}

export function useCitationDialogOptional(): CitationDialogState | null {
  return useContext(CitationDialogContext);
}
