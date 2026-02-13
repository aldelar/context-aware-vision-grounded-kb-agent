# Azure Knowledge Base Ingestion Accelerator

## Overview

This solution accelerator helps organizations transform HTML-based knowledge base (KB) articles into AI-searchable content powered by **Azure AI Search**. It bridges the gap between legacy KB systems — where articles are stored as HTML pages with embedded images — and modern AI-powered search experiences where an agent can retrieve precise, context-aware answers along with their associated visual content.

## The Problem

Enterprise knowledge bases often store thousands of technical articles as HTML files, each bundled with supporting images (screenshots, diagrams, UI captures). These articles are rich in information but difficult to search semantically. Traditional keyword search misses context, and the images — which often carry critical information — are completely invisible to search systems.

## What This Accelerator Does

This accelerator provides an end-to-end pipeline that:

1. **Ingests HTML KB articles** — each article is a folder containing an HTML file and its associated images (see [kb/](kb/) for examples)

2. **Converts articles to clean Markdown** — leverages [Azure Content Understanding](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview) to extract high-quality text, tables, and document structure from HTML, while separately analyzing each image to generate detailed AI-powered descriptions

3. **Produces image-aware Markdown** — the resulting Markdown preserves the full article structure with AI-generated image descriptions placed in context, each linking back to the original image file

4. **Generates context-aware chunks** — splits the Markdown into semantically meaningful chunks (by section/heading), where each chunk carries references to 0–N related images

5. **Indexes into Azure AI Search** — embeds each chunk using Azure AI embedding models and indexes them with their associated image URLs into an AI Search index, enabling both text and image retrieval

## Key Outcomes

- **Semantic search over KB content** — find answers based on meaning, not just keywords
- **Image-aware results** — search results include links to the actual source images (stored in Azure Blob Storage) when they are relevant to the matched text
- **Agent-ready index** — the search index is designed for AI agents/copilots to consume, returning both answer text and supporting visuals to end users
- **No manual content conversion** — the pipeline automates the transformation from raw HTML articles to a fully searchable index

## Why Images Matter for AI Agents

Linking source images to search chunks is not just a convenience for end users — it directly improves the quality of AI agent responses. Modern LLMs are highly capable at interpreting images within the context of a question, making the original screenshots and diagrams a rich source of grounding information for the agent itself. Relying solely on alt text or AI-generated image descriptions loses significant fidelity; the actual image often contains UI details, spatial relationships, and visual cues that text alone cannot fully capture. By serving the source images alongside the text chunks, agents can reason over the full visual context and deliver more accurate, complete answers.

## Who Is This For

Teams and organizations that:

- Have existing KB article repositories in HTML format and want to make them searchable with AI
- Are building AI agents or copilots that need to retrieve knowledge articles with supporting images
- Want to evaluate Azure Content Understanding as a document processing engine for their content

## Project Structure

```
├── .github/             GitHub config (Copilot instructions)
├── docs/
│   ├── ards/            Architecture Decision Records
│   ├── epics/           Epic and story tracking
│   ├── research/        Spike results and research notes
│   └── specs/           Architecture and design specs
├── infra/               Bicep modules and infrastructure-as-code
├── kb/
│   ├── staging/         Source articles (HTML + images), one folder per article
│   └── serving/         Processed articles (MD + images), one folder per article
├── scripts/
│   ├── dev-setup.sh     Dev environment setup
│   └── functions/       Shell scripts to run fn-convert / fn-index locally
├── src/
│   ├── functions/       Azure Functions project (fn-convert, fn-index, shared utils)
│   │   ├── fn_convert/  Stage 1 — HTML → Markdown + images
│   │   ├── fn_index/    Stage 2 — Markdown → AI Search index
│   │   ├── shared/      Shared config, blob helpers, CU client
│   │   └── tests/       pytest test suite
│   └── spikes/          Spike/prototype scripts (research, not production)
├── analyzers/           CU custom analyzer definitions (kb-image-analyzer.json)
├── Makefile             Dev workflow targets (local + Azure)
└── README.md
```

## Getting Started

See [docs/research/spike-content-understanding.md](docs/research/spike-content-understanding.md) for prerequisites, setup instructions, and usage details.
