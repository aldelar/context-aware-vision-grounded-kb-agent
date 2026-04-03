import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";

import { ConversationThreadProvider } from "../../components/ConversationThreadContext";
import { SearchToolRenderer } from "../../components/SearchToolRenderer";

describe("SearchToolRenderer", () => {
  it("renders the query and top results", () => {
    render(
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
    expect(screen.getByText("Azure AI Search overview")).toBeInTheDocument();
    expect(screen.getByText("Network isolation")).toBeInTheDocument();
  });

  it("renders citation cards with anchors and proxy-backed images", () => {
    render(
      <SearchToolRenderer
        args={{ query: { type: "text", value: "content understanding" } }}
        result={{
          results: [
            {
              ref_number: 7,
              title: { type: "text", value: "Content Understanding overview" },
              section_header: { type: "text", value: "Image grounding" },
              content: [
                { type: "text", value: "The service returns grounded results." },
                { type: "text", value: "![Grounding diagram](/api/images/contoso/diagram.png)" },
              ],
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("Ref #1")).toBeInTheDocument();
    expect(screen.getByText("Image grounding")).toBeInTheDocument();
    expect(screen.getByText("The service returns grounded results.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Grounding diagram" })).toHaveAttribute(
      "src",
      "/api/images/contoso/diagram.png",
    );
  });

  it("rewrites indexed image refs and relative image urls into proxy-backed images", () => {
    render(
      <SearchToolRenderer
        args={{ query: "architecture" }}
        result={{
          results: [
            {
              ref_number: 2,
              article_id: "contoso-article",
              title: "Architecture guide",
              section_header: "Diagrams",
              content: "See the overview. [Image: architecture](images/arch.png)",
              image_urls: ["images/arch.png"],
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("See the overview.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "architecture" })).toHaveAttribute(
      "src",
      "/api/images/contoso-article/images/arch.png",
    );
  });

  it("renders structured tool payloads without passing objects to React", () => {
    render(
      <SearchToolRenderer
        args={{ query: [{ type: "text", value: "agentic retrieval" }] }}
        result={{
          results: [
            {
              ref_number: "8",
              title: [{ type: "text", value: "Agentic retrieval" }],
              section_header: { type: "text", value: "Execution flow" },
              content: { type: "text", value: "The agent can plan and refine its search steps." },
              images: [
                {
                  url: { type: "text", value: "/api/images/contoso/agentic-flow.png" },
                  alt: { type: "text", value: "Agentic flow" },
                },
              ],
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("agentic retrieval")).toBeInTheDocument();
    expect(screen.getByText("Agentic retrieval")).toBeInTheDocument();
    expect(screen.getByText("Execution flow")).toBeInTheDocument();
    expect(screen.getByText("The agent can plan and refine its search steps.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Agentic flow" })).toHaveAttribute(
      "src",
      "/api/images/contoso/agentic-flow.png",
    );
  });

  it("loads full source excerpts on demand for compact stored citations", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(
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
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ConversationThreadProvider threadId="thread-123">
        <SearchToolRenderer
          args={{ query: "architecture" }}
          result={{
            results: [
              {
                ref_number: 1,
                chunk_id: "article-1_0",
                title: "Architecture guide",
                section_header: "Diagrams",
                summary: "Stored compact summary.",
                content_source: "summary",
              },
            ],
          }}
          status="complete"
          toolCallId="tool-call-1"
        />
      </ConversationThreadProvider>,
    );

    expect(screen.getByText("Stored compact summary.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Load source excerpt" }));

    expect(await screen.findByText("Full chunk content loaded on demand.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/thread-123/citations/tool-call-1/1",
      { cache: "no-store" },
    );
  });
});