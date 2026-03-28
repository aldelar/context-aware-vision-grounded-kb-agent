import { linkCitationMarkers } from "../../components/chatMessageTransforms";

describe("linkCitationMarkers", () => {
  it("rewrites ref markers into local citation anchors", () => {
    expect(linkCitationMarkers("See [Ref #2] and [Ref #11] for details.")).toBe(
      "See [Ref #2](#citation-ref-2) and [Ref #11](#citation-ref-11) for details.",
    );
  });

  it("does not rewrite markers that are already links", () => {
    expect(linkCitationMarkers("See [Ref #3](#citation-ref-3)."))
      .toBe("See [Ref #3](#citation-ref-3).");
  });
});