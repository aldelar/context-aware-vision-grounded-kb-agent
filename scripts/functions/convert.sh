#!/usr/bin/env bash
# scripts/functions/convert.sh — Run fn-convert for each article in kb/staging/
#
# Usage:
#   bash scripts/functions/convert.sh content-understanding
#   bash scripts/functions/convert.sh mistral-doc-ai
#   bash scripts/functions/convert.sh markitdown
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING_DIR="$REPO_ROOT/kb/staging"
SERVING_DIR="$REPO_ROOT/kb/serving"

# --- Determine which convert module to use ---
ANALYZER="${1:-}"
case "$ANALYZER" in
    content-understanding)
        MODULE="fn_convert_cu"
        ;;
    mistral-doc-ai)
        MODULE="fn_convert_mistral"
        ;;
    markitdown)
        MODULE="fn_convert_markitdown"
        ;;
    *)
        echo "Error: analyzer argument is required." >&2
        echo "Usage:" >&2
        echo "  bash $0 content-understanding" >&2
        echo "  bash $0 mistral-doc-ai" >&2
        echo "  bash $0 markitdown" >&2
        exit 1
        ;;
esac

if [ ! -d "$STAGING_DIR" ] || [ -z "$(ls -A "$STAGING_DIR" 2>/dev/null)" ]; then
    echo "No articles found in kb/staging/. Add article folders first."
    exit 1
fi

# Ensure serving directory exists
mkdir -p "$SERVING_DIR"

echo "Using analyzer: $ANALYZER (module: $MODULE)"

for dept_dir in "$STAGING_DIR"/*/; do
    department="$(basename "$dept_dir")"
    for article_dir in "$dept_dir"*/; do
        article_id="$(basename "$article_dir")"
        echo ""
        echo "=== fn-convert ($ANALYZER): $department/$article_id ==="
        output_dir="$SERVING_DIR/$article_id"
        mkdir -p "$output_dir"
        (cd "$REPO_ROOT/src/functions" && uv run python -m "$MODULE" "$article_dir" "$output_dir")
        # Write metadata.json with department (and any future fields)
        echo "{\"department\": \"$department\"}" > "$output_dir/metadata.json"
    done
done

echo ""
echo "Done. Processed articles are in kb/serving/."
