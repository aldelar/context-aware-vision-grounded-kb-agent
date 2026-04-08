import userEvent from "@testing-library/user-event";
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import React, { useEffect } from "react";

import { CitationDialog } from "../../components/CitationDialog";
import { CitationDialogProvider, citationKey, useCitationDialog } from "../../components/CitationDialogContext";

function SetupCitation({
  refNumber,
  citation,
  threadId,
  toolCallId,
  autoOpen,
}: {
  refNumber: number;
  citation: any;
  threadId?: string;
  toolCallId?: string;
  autoOpen?: boolean;
}) {
  const ctx = useCitationDialog();

  useEffect(() => {
    const key = citationKey(toolCallId, refNumber);
    ctx.registerCitation(key, {
      citation,
      threadId: threadId ?? null,
      toolCallId,
      source: "internal",
    });
    if (autoOpen) {
      ctx.openCitation(key);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

function renderDialog(props: Parameters<typeof SetupCitation>[0]) {
  return render(
    <CitationDialogProvider>
      <SetupCitation {...props} />
      <CitationDialog />
    </CitationDialogProvider>,
  );
}

describe("CitationDialog", () => {
  it("renders nothing when no citation is open", () => {
    render(
      <CitationDialogProvider>
        <CitationDialog />
      </CitationDialogProvider>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the dialog with citation content when opened", () => {
    renderDialog({
      refNumber: 1,
      citation: {
        ref_number: 1,
        title: "Security in Azure AI Search",
        section_header: "Network security",
        content: "Azure AI Search supports network security perimeters.",
        content_source: "full",
      },
      autoOpen: true,
    });

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Ref #1")).toBeInTheDocument();
    expect(screen.getByText("Security in Azure AI Search")).toBeInTheDocument();
    expect(screen.getByText("Network security")).toBeInTheDocument();
    expect(screen.getByText("Azure AI Search supports network security perimeters.")).toBeInTheDocument();
  });

  it("closes the dialog when the close button is clicked", async () => {
    const user = userEvent.setup();

    renderDialog({
      refNumber: 2,
      citation: {
        ref_number: 2,
        title: "Test article",
        content: "Test content.",
        content_source: "full",
      },
      autoOpen: true,
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the dialog on Escape key", async () => {
    const user = userEvent.setup();

    renderDialog({
      refNumber: 3,
      citation: {
        ref_number: 3,
        title: "Escape test",
        content: "Content here.",
        content_source: "full",
      },
      autoOpen: true,
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("loads enrichment for summary-only citations", async () => {
    let resolveResponse: ((response: Response) => void) | null = null;
    const fetchMock = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderDialog({
      refNumber: 1,
      citation: {
        ref_number: 1,
        chunk_id: "article-1_0",
        title: "Architecture guide",
        summary: "Stored compact summary.",
        content_source: "summary",
      },
      threadId: "thread-123",
      toolCallId: "tool-call-1",
      autoOpen: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/thread-123/citations/tool-call-1/1",
      { cache: "no-store" },
    );
    expect(screen.getByText("Loading source excerpt…")).toBeInTheDocument();

    await act(async () => {
      resolveResponse?.(
        new Response(
          JSON.stringify({
            status: "ready",
            citation: {
              ref_number: 1,
              chunk_id: "article-1_0",
              content: "Full chunk content loaded on demand.",
              content_source: "full",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });

    expect(await screen.findByText("Full chunk content loaded on demand.")).toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});
