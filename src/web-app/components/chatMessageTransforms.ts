const citationMarkerPattern = /\[(Ref #(\d+))\](?!\()/g;

export function linkCitationMarkers(content: string): string {
  return content.replace(citationMarkerPattern, "[$1](#citation-ref-$2)");
}