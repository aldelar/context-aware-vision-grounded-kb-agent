"""Compare CU pipeline output vs Mistral spike output side by side."""

import difflib
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CU_SERVING = PROJECT_ROOT / "kb" / "serving"
MISTRAL_SERVING = PROJECT_ROOT / "kb" / "serving-spike-002"


def compare():
    print("=" * 80)
    print("CU Pipeline vs Mistral Spike Comparison")
    print("=" * 80)

    for article_dir in sorted(CU_SERVING.iterdir()):
        if not article_dir.is_dir():
            continue

        article_id = article_dir.name
        print(f"\n--- {article_id} ---")

        mistral_article = MISTRAL_SERVING / article_id / "article.md"
        if not mistral_article.exists():
            print("  Mistral: MISSING")
            continue

        cu_text = (article_dir / "article.md").read_text(encoding="utf-8")
        mistral_text = mistral_article.read_text(encoding="utf-8")

        cu_lines = cu_text.splitlines(keepends=True)
        mistral_lines = mistral_text.splitlines(keepends=True)

        print(f"  CU      — chars: {len(cu_text):>6}  lines: {len(cu_lines):>4}")
        print(f"  Mistral — chars: {len(mistral_text):>6}  lines: {len(mistral_lines):>4}")

        cu_images = cu_text.count("[Image:")
        mistral_images = mistral_text.count("[Image:")
        print(f"  Image blocks   — CU: {cu_images}  Mistral: {mistral_images}")

        link_pattern = re.compile(r"\[([^\]]+)\]\(http")
        cu_links = len(link_pattern.findall(cu_text))
        mistral_links = len(link_pattern.findall(mistral_text))
        print(f"  Hyperlinks     — CU: {cu_links}  Mistral: {mistral_links}")

        diff = list(difflib.unified_diff(
            cu_lines,
            mistral_lines,
            fromfile=f"cu/{article_id}/article.md",
            tofile=f"mistral/{article_id}/article.md",
            n=3,
        ))

        diff_path = MISTRAL_SERVING / f"{article_id}.diff"
        diff_path.write_text("".join(diff), encoding="utf-8")
        print(f"  Diff written   — {len(diff)} lines -> {diff_path.name}")


if __name__ == "__main__":
    compare()
