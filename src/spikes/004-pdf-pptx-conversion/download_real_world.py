#!/usr/bin/env python3
"""Download real-world public domain documents for conversion quality testing.

These documents stress-test the conversion pipeline with real complexity:
multi-column layouts, real photographs/diagrams, extensive hyperlinks,
cross-page tables, and diverse formatting.

Usage:
    python download_real_world.py

Documents are saved to samples/real-world/.

Note: Some URLs may require direct internet access. If downloads fail in a
sandboxed environment, run this script locally and commit the files.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent / "samples" / "real-world"

# Each entry: (filename, url, description, format, complexity notes)
DOCUMENTS = [
    # --- PDF ---
    (
        "owasp-asvs-4.0.3.pdf",
        "https://github.com/OWASP/ASVS/raw/master/4.0/"
        "OWASP%20Application%20Security%20Verification%20Standard%204.0.3-en.pdf",
        "OWASP Application Security Verification Standard 4.0.3",
        "PDF",
        "71 pages, complex tables (security controls matrix), "
        "extensive hyperlinks (162+ in first 10 pages), embedded images, "
        "multi-level headings, bullet lists, cross-references",
    ),
    (
        "nist-csf-2.0.pdf",
        "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "NIST Cybersecurity Framework 2.0",
        "PDF",
        "Government whitepaper with diagrams, tables, hyperlinks, "
        "multi-column layout, cross-references, appendices",
    ),
    # --- PPTX ---
    (
        "ms-fabric-unified-analytics.pptx",
        "https://raw.githubusercontent.com/microsoft/Fabric-Readiness/"
        "31af5096374dc6bf2434713ed7be72d736ae2628/"
        "presentations/01.%20Introducing%20Unified%20Analytics.pptx",
        "Microsoft Fabric: Introducing Unified Analytics",
        "PPTX",
        "Microsoft conference deck with diagrams, screenshots, "
        "speaker notes (expected), product architecture slides",
    ),
    (
        "ms-knowledge-mining.pptx",
        "https://raw.githubusercontent.com/microsoft/microhacks-knowledge-mining-ai/"
        "241e26f8b468f2f36c6004a4faa60e36016c5d21/"
        "docs/Microhack%20Deck%20-%20Knowledge%20Mining.pptx",
        "Microsoft Microhack: Knowledge Mining with AI",
        "PPTX",
        "Workshop deck with architecture diagrams, step-by-step instructions, "
        "screenshots, and technical content",
    ),
    # --- DOCX ---
    (
        "section508-word-guide.docx",
        "https://assets.section508.gov/assets/files/"
        "MS%20Word%202016%20Basic%20Authoring%20and%20Testing%20Guide-AED%20COP.docx",
        "Section 508: MS Word Authoring & Testing Guide",
        "DOCX",
        "Government accessibility guide with complex tables, images, "
        "hyperlinks, headings hierarchy, numbered/bulleted lists",
    ),
]


def download_all() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    for filename, url, description, fmt, notes in DOCUMENTS:
        path = SAMPLES_DIR / filename
        if path.exists():
            print(f"  ✅ Already exists: {filename} ({path.stat().st_size:,} bytes)")
            continue

        print(f"  Downloading: {description}")
        print(f"    URL: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Spike004/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                path.write_bytes(resp.read())
            print(f"    ✅ Saved: {filename} ({path.stat().st_size:,} bytes)")
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            print(f"    Download manually and place in: {SAMPLES_DIR / filename}")


def main() -> None:
    print("Downloading real-world documents for Spike 004...")
    print(f"Target directory: {SAMPLES_DIR}\n")
    download_all()
    print("\nDone. Run test_real_world.py to analyze conversion quality.")


if __name__ == "__main__":
    main()
