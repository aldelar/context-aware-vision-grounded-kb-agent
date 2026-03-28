import { render, screen } from "@testing-library/react";

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

    expect(screen.getByText("Ref #7")).toBeInTheDocument();
    expect(screen.getByText("Image grounding")).toBeInTheDocument();
    expect(screen.getByText("The service returns grounded results.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Grounding diagram" })).toHaveAttribute(
      "src",
      "/api/images/contoso/diagram.png",
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
});