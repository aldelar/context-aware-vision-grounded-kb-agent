.PHONY: help install deploy run compare all clean

.DEFAULT_GOAL := help

install: ## Install dependencies + Playwright Chromium
	uv sync && uv run playwright install chromium

deploy: ## Deploy mistral-document-ai-2512 model (one-time)
	bash deploy_model.sh

run: ## Run the full pipeline (staging → serving-spike-002)
	uv run python run.py

compare: ## Compare Mistral output vs CU output
	uv run python compare.py

all: run compare ## Run pipeline then compare

clean: ## Remove serving-spike-002 output for a fresh re-run
	rm -rf ../../../kb/serving-spike-002

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{ printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }'
