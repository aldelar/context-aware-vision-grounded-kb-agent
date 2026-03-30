#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <convert|index> <url>" >&2
    exit 20
fi

MODE="$1"
URL="$2"

case "${MODE}" in
    convert|index) ;;
    *)
        echo "Unsupported pipeline mode: ${MODE}" >&2
        exit 20
        ;;
esac

BODY_FILE=$(mktemp)
cleanup() {
    rm -f "${BODY_FILE}"
}
trap cleanup EXIT

CURL_EXIT_CODE=0
HTTP_STATUS=$(curl \
    --silent \
    --show-error \
    --output "${BODY_FILE}" \
    --write-out '%{http_code}' \
    --header 'Content-Type: application/json' \
    --request POST \
    --data '{}' \
    "${URL}" \
    || CURL_EXIT_CODE=$?)

python3 - "$MODE" "$HTTP_STATUS" "$BODY_FILE" "$CURL_EXIT_CODE" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_body(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def print_body(prefix: str, body: str) -> None:
    body = body.strip()
    if not body:
        print(prefix)
        return
    print(prefix)
    print(body)


def main() -> int:
    mode, status_text, body_path, curl_exit_text = sys.argv[1:5]
    status_code = int(status_text) if status_text.isdigit() else 0
    curl_exit_code = int(curl_exit_text)
    body = load_body(body_path)

    if curl_exit_code != 0 or status_code == 0:
        print(f"{mode}: network error while calling endpoint; retrying")
        if body.strip():
            print(body.strip())
        return 10

    if status_code >= 500:
        print_body(f"{mode}: endpoint returned HTTP {status_code}; retrying", body)
        return 10

    if status_code == 404:
        fatal_messages = {
            "convert": "No articles found in staging container",
            "index": "No articles found in serving container",
        }
        fatal_message = fatal_messages[mode]
        if fatal_message in body:
            print_body(f"{mode}: {fatal_message.lower()}.", body)
            return 20
        print_body(f"{mode}: endpoint returned HTTP 404.", body)
        return 10

    if status_code >= 400:
        print_body(f"{mode}: endpoint returned HTTP {status_code}.", body)
        return 20

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        print_body(f"{mode}: endpoint returned HTTP {status_code} with a non-JSON body; retrying", body)
        return 10

    results = payload.get("results")
    if not isinstance(results, list):
        error = payload.get("error")
        if isinstance(error, str) and error:
            print_body(f"{mode}: {error}", body)
            return 20
        print_body(f"{mode}: response did not include a results array; retrying", body)
        return 10

    ok_count = sum(1 for item in results if item.get("status") == "ok")
    error_count = sum(1 for item in results if item.get("status") == "error")

    if ok_count > 0 and error_count == 0:
        print(f"{mode}: {ok_count} article(s) succeeded")
        return 0

    if error_count > 0:
        print_body(
            f"{mode}: received {error_count} article error(s) and {ok_count} success(es); retrying",
            json.dumps(payload, indent=2),
        )
        return 10

    print_body(f"{mode}: no successful article results were returned; retrying", json.dumps(payload, indent=2))
    return 10


raise SystemExit(main())
PY