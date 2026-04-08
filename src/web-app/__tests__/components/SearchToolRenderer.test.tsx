import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CitationDialogProvider } from "../../components/CitationDialogContext";
import { ConversationThreadProvider } from "../../components/ConversationThreadContext";
import { SearchToolRenderer, getPillTitle } from "../../components/SearchToolRenderer";

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <ConversationThreadProvider threadId="thread-1">
      <CitationDialogProvider>{ui}</CitationDialogProvider>
    </ConversationThreadProvider>,
  );
}

describe("getPillTitle", () => {
  it("returns section_header when present", () => {
    expect(getPillTitle({ section_header: "Network security perimeter" })).toBe(
      "Network security perimeter",
    );
  });

  it("returns first 3 words of content with ellipsis when no section_header", () => {
    expect(
      getPillTitle({ content: "The service returns grounded documentation for search." }),
    ).toBe("The service returns…");
  });

  it("returns full text when content has 3 or fewer words", () => {
    expect(getPillTitle({ content: "Quick overview" })).toBe("Quick overview");
  });

  it("falls back to summary when no content", () => {
    expect(getPillTitle({ summary: "Summary of the article and its details." })).toBe(
      "Summary of the…",
    );
  });

  it("falls back to title when no content or summary", () => {
    expect(getPillTitle({ title: "Architecture guide" })).toBe("Architecture guide");
  });

  it("returns Reference when nothing is available", () => {
    expect(getPillTitle({})).toBe("Reference");
  });

  it("strips markdown formatting from content before extracting words", () => {
    expect(
      getPillTitle({ content: "## Security in Azure AI Search" }),
    ).toBe("Security in Azure…");
  });
});

describe("SearchToolRenderer", () => {
  it("renders the query and pill titles from section_header", () => {
    renderWithProviders(
      <SearchToolRenderer
        args={{ query: "azure ai search" }}
        result={{
          results: [
            { title: "Azure AI Search overview", section_header: "What it does" },
            { title: "Search security", section_header: "Network isolation" },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("azure ai search")).toBeInTheDocument();
    expect(screen.getByText("What it does")).toHaveClass("citationPillTitle");
    expect(screen.getByText("Network isolation")).toHaveClass("citationPillTitle");
  });

  it("renders pill title from first 3 words when no section_header", () => {
    renderWithProviders(
      <SearchToolRenderer
        args={{ query: "content understanding" }}
        result={{
          results: [
            {
              ref_number: 1,
              title: "Content Understanding overview",
              content: "The service returns grounded documentation.",
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("Ref 1.1")).toBeInTheDocument();
    expect(screen.getByText("The service returns…")).toHaveClass("citationPillTitle");
  });

  it("renders pills in a horizontal deck", () => {
    renderWithProviders(
      <SearchToolRenderer
        args={{ query: "test" }}
        result={{
          results: [
            { ref_number: 1, title: "First", section_header: "Section A" },
            { ref_number: 2, title: "Second", section_header: "Section B" },
            { ref_number: 3, title: "Third", section_header: "Section C" },
          ],
        }}
        status="complete"
      />,
    );

    const pills = screen.getAllByRole("button");
    expect(pills).toHaveLength(3);
    expect(pills[0].closest(".citationPillDeck")).toBeTruthy();
  });

  it("renders structured tool payloads without passing objects to React", () => {
    renderWithProviders(
      <SearchToolRenderer
        args={{ query: [{ type: "text", value: "agentic retrieval" }] }}
        result={{
          results: [
            {
              ref_number: "8",
              title: [{ type: "text", value: "Agentic retrieval" }],
              section_header: { type: "text", value: "Execution flow" },
              content: { type: "text", value: "The agent can plan and refine its search steps." },
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("agentic retrieval")).toBeInTheDocument();
    expect(screen.getByText("Execution flow")).toHaveClass("citationPillTitle");
  });

  it("shows the searching status while in progress", () => {
    renderWithProviders(
      <SearchToolRenderer
        args={{ query: "test query" }}
        result={null}
        status="inProgress"
      />,
    );

    expect(screen.getByText("Searching")).toBeInTheDocument();
    expect(screen.getByText("test query")).toBeInTheDocument();
  });

  it("shows hint text when no results", () => {
    renderWithProviders(
      <SearchToolRenderer
        args={{ query: "test" }}
        result={{ results: [] }}
        status="complete"
      />,
    );

    expect(
      screen.getByText("The agent is collecting article matches and ranking the best sections."),
    ).toBeInTheDocument();
  });
});
