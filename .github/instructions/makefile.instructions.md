---
description: 'Best practices for authoring GNU Make Makefiles'
applyTo: '**/Makefile,**/makefile,**/*.mk'
---

# Makefile Development

## General Principles

- Use descriptive target names that clearly indicate their purpose
- Keep the default goal (first target) as the most common operation
- Prioritize readability over brevity
- Add comments to explain complex rules or non-obvious behavior
- Use `.PHONY` for all non-file targets

## Naming Conventions

- Name your makefile `Makefile` (recommended for visibility)
- Use uppercase for variable names (`CC`, `CFLAGS`)
- Use descriptive target names reflecting their action (`clean`, `install`, `test`)

## File Structure

```makefile
# Variables at the top
VARIABLE ?= default-value

# Default goal first
.PHONY: all
all: build

# Group related targets logically
.PHONY: build test clean
build:
	@echo "Building..."

test:
	@echo "Testing..."

clean:
	@echo "Cleaning..."
```

## Variables

- Use `?=` for defaults that can be overridden from command line
- Use `:=` for immediate evaluation (faster)
- Reference variables with `$(VARIABLE)` not `$VARIABLE`
- Use `$(shell ...)` sparingly — prefer Make functions

## Recipes

- Start every recipe line with a **tab character** (not spaces)
- Use `@` prefix to suppress command echoing
- Use `-` prefix to ignore errors (sparingly)
- Combine related commands with `&&` on the same line

## Anti-Patterns to Avoid

- Don't start recipe lines with spaces instead of tabs
- Don't use `$(shell ls ...)` — use `$(wildcard ...)` instead
- Don't forget to declare phony targets
- Avoid recursive make unless necessary
- Don't hardcode file lists when wildcards work

## Project-Specific Context

This project's `Makefile` is the primary automation surface:
- Local development: `make dev-up`, `make dev-test`, `make dev-test-ui`
- Azure operations: `make prod-up`, `make prod-services-up`, `make prod-pipeline`, `make prod-clean`
- Per-environment target groups are split into `dev-*` and `prod-*`
- Run `make help` to see all available targets
- See `docs/setup-and-makefile.md` for full documentation
