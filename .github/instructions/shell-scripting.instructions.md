---
description: 'Shell scripting best practices for bash scripts in scripts/'
applyTo: '**/*.sh'
---

# Shell Scripting Guidelines

## General Principles

- Write clean, simple, and concise scripts
- Add comments where helpful for understanding script logic
- Use shellcheck for static analysis when available
- Double-quote variable references (`"$var"`) to prevent word splitting
- Use `${var}` for clarity and `[[ ]]` for conditional tests

## Error Handling & Safety

- **Always** enable `set -euo pipefail` at the top of scripts
- Validate all required parameters before execution
- Provide clear error messages with context
- Use `trap` to clean up temporary resources on exit
- Declare immutable values with `readonly`
- Use `mktemp` for temporary files and ensure cleanup

## Script Structure

```bash
#!/bin/bash
# ============================================================================
# Script Description
# ============================================================================

set -euo pipefail

cleanup() {
    if [[ -n "${TEMP_DIR:-}" && -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# Default values
RESOURCE_GROUP=""
readonly SCRIPT_NAME="$(basename "$0")"

# Functions
usage() {
    echo "Usage: $SCRIPT_NAME [OPTIONS]"
    echo "Options:"
    echo "  -g, --resource-group   Resource group (required)"
    echo "  -h, --help             Show this help"
    exit 0
}

validate_requirements() {
    if [[ -z "$RESOURCE_GROUP" ]]; then
        echo "Error: Resource group is required" >&2
        exit 1
    fi
}

main() {
    validate_requirements
    echo "============================================"
    echo "Script Execution Started"
    echo "============================================"
    # Main logic here
    echo "============================================"
    echo "Script Execution Completed"
    echo "============================================"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

main "$@"
```

## Working with JSON

- Prefer `jq` for JSON parsing over `grep`/`awk`/shell string splitting
- Quote jq filters to prevent shell expansion
- Use `--raw-output` for plain strings
- Fail fast if `jq` is required but not installed

## Project Conventions

Scripts live in `scripts/` and include:
- Azure resource configuration scripts
- Development setup (`dev-setup.sh`)
- Entra auth setup (`setup-entra-auth.sh`)
- Storage/Cosmos access scripts

All scripts should work with `azd` environment values and `DefaultAzureCredential`.
