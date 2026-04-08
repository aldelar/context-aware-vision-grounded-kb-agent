import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReactNode } from "react";

import {
  CitationDialogProvider,
  citationKey,
  useCitationDialog,
  useCitationDialogOptional,
} from "../../components/CitationDialogContext";

function wrapper({ children }: { children: ReactNode }) {
  return <CitationDialogProvider>{children}</CitationDialogProvider>;
}

describe("CitationDialogContext", () => {
  it("starts with no open citation", () => {
    const { result } = renderHook(() => useCitationDialog(), { wrapper });
    expect(result.current.openKey).toBeNull();
  });

  it("opens and closes a citation by scoped key", () => {
    const { result } = renderHook(() => useCitationDialog(), { wrapper });
    const key = citationKey("tool-1", 3);

    act(() => result.current.openCitation(key));
    expect(result.current.openKey).toBe(key);

    act(() => result.current.closeCitation());
    expect(result.current.openKey).toBeNull();
  });

  it("registers and retrieves a citation", () => {
    const { result } = renderHook(() => useCitationDialog(), { wrapper });
    const key = citationKey("tool-1", 1);
    const entry = {
      citation: { ref_number: 1, title: "Test" },
      threadId: "thread-1",
      toolCallId: "tool-1",
      source: "internal" as const,
    };

    act(() => result.current.registerCitation(key, entry));
    expect(result.current.getCitation(key)).toEqual(entry);
    expect(result.current.getCitation(citationKey("tool-2", 2))).toBeUndefined();
  });

  it("returns null from useCitationDialogOptional when outside provider", () => {
    const { result } = renderHook(() => useCitationDialogOptional());
    expect(result.current).toBeNull();
  });

  it("throws from useCitationDialog when outside provider", () => {
    expect(() => {
      renderHook(() => useCitationDialog());
    }).toThrow("useCitationDialog must be used within a CitationDialogProvider");
  });
});
