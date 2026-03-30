---
name: eval-driven-dev
description: |
  Evaluation-driven development for Python LLM applications using the Microsoft
  Evaluations SDK (`azure-ai-evaluation`) and Microsoft Foundry. Use when:
  - Setting up evals, QA, or testing for the KB Agent or any LLM-calling code
  - Running local evaluations with LLM-as-judge evaluators backed by Foundry models
  - Publishing evaluation results to Microsoft Foundry for tracking and comparison
  - Building golden datasets for regression testing
  - Investigating LLM response quality failures
  - Benchmarking prompt changes
compatibility: Python 3.12+, azure-ai-evaluation, azure-ai-projects
---

# Evaluation-Driven Development — Microsoft Evaluations SDK + Foundry

This skill is about doing the work, not describing it. When a user asks you to set up evals, you should be reading their code, editing their files, running commands, and producing a working test pipeline.

## Standard Platform: Microsoft Evaluations SDK + Foundry

> **All evaluations in this project use the Microsoft Evaluations SDK (`azure-ai-evaluation`) as the standard evaluation platform.** Do not introduce third-party eval frameworks (DeepEval, RAGAS, promptfoo, etc.) or build custom scoring logic when the SDK provides an equivalent.

### Why This Stack

| Concern | Solution |
|---------|----------|
| **Local dev-test evals** | `azure-ai-evaluation` runs locally, uses LLM-as-judge evaluators backed by Foundry model deployments (e.g., gpt-4.1) |
| **Publish results to Foundry** | `evaluate()` accepts a Foundry project connection — results appear in the Foundry portal (Evaluate → Runs) for comparison and trending |
| **Built-in evaluators** | Task adherence, coherence, groundedness, relevance, fluency, violence, sexual, self-harm, hate — no custom scoring code needed |
| **Custom evaluators** | Extend with `CodeEvaluator` or `PromptEvaluator` when built-ins don't cover a dimension |
| **Continuous evaluation** | Foundry evaluation rules run against live agent traffic (configured via `azure-ai-projects` SDK) |
| **Scheduled evaluation** | Foundry scheduled evaluations run against curated datasets on a cadence |
| **Red-teaming** | `AdversarialSimulator` from the SDK for automated red-team runs |

### SDK Pattern

```python
from azure.ai.evaluation import evaluate, TaskAdherenceEvaluator, CoherenceEvaluator
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Connect to Foundry project (results published here)
project_client = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint="https://<foundry-project>.services.ai.azure.com/api",
)

# Run evaluation locally — judges use Foundry model deployments
result = evaluate(
    data="evals/data/golden-dataset.jsonl",
    evaluators={
        "task_adherence": TaskAdherenceEvaluator(project_client=project_client),
        "coherence": CoherenceEvaluator(project_client=project_client),
    },
    azure_ai_project=project_client,  # publishes results to Foundry
    evaluation_name="kb-agent-regression-v1",
)
```

This single `evaluate()` call:
1. Runs evaluators **locally** (LLM-as-judge calls go to Foundry model endpoints)
2. **Publishes results** to the Foundry project (visible in portal under Evaluate → Runs)
3. Returns results locally for CI assertions

### Key Dependencies

```
# In src/agent/pyproject.toml [project.optional-dependencies]
eval = [
    "azure-ai-evaluation>=1.0.0",
    "azure-ai-projects>=1.0.0",
]
```

Install with: `uv pip install -e ".[eval]"`

---

## Setup vs. Iteration: When to Stop

### "Setup QA" / "set up evals" / "add tests" (setup intent)

The user wants a **working eval pipeline**. Your job is Stages 0–7: install, understand, instrument, build a run harness, capture real traces, write tests, build dataset, run tests. **Stop after the first test run**, regardless of whether tests pass or fail.

Then ask: _"QA setup is complete. Tests show N/M passing. Want me to investigate the failures and start iterating?"_

### "Fix" / "improve" / "debug" / "why is X failing" (iteration intent)

The user wants you to investigate and fix. Proceed through all stages including Stage 8.

---

## Hard Gates: When to STOP

### Missing API keys or credentials

If the app or evaluators need API keys or Foundry credentials and they're not set, tell the user exactly what's missing. The evaluators need a Foundry project connection (`azure-ai-projects` client with `DefaultAzureCredential`) — verify this is available.

### Cannot run the app from a script

If you cannot figure out how to invoke the app's core LLM-calling function from a standalone script, stop and ask the user.

### App errors during run harness execution

If the run harness errors out and you can't fix it after two attempts, stop and share the error.

---

## The Eval Boundary

**Eval-driven development focuses on LLM-dependent behaviour.**

### In scope (evaluate this)
- LLM response quality: factual accuracy, relevance, format compliance, safety
- Agent routing decisions: did the LLM choose the right tool/handoff/action?
- Prompt effectiveness: does the prompt produce the desired behaviour?
- Multi-turn coherence: does the agent maintain context across turns?

### Out of scope (do NOT evaluate with evals)
- **Tool implementations** (database queries, API calls, business logic) — test with unit tests
- **Infrastructure** (authentication, rate limiting, caching) — governance via APIM/Foundry
- **Deterministic post-processing** (formatting, filtering, sorting)

---

## Stage 0: Ensure Dependencies and Foundry Connection

Check that the Microsoft Evaluations SDK is installed and Foundry credentials are available:

```bash
# Verify SDK is installed
python -c "from azure.ai.evaluation import evaluate; print('OK')"

# Verify Foundry connection (DefaultAzureCredential must work)
python -c "from azure.ai.projects import AIProjectClient; from azure.identity import DefaultAzureCredential; print('OK')"
```

Required environment variables (from `azd -C infra/azure env get-values` → `.env`):
- `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` — Foundry project endpoint for eval publishing
- Azure credentials via `DefaultAzureCredential` (az login for local dev, managed identity in CI)

## Stage 1: Understand the Application

Before touching any code, read the source. For the KB Agent (`src/agent/`):
- Identify the eval-boundary function
- Map all inputs to LLM calls (system prompts, user queries, tool outputs, search results)
- Document intermediate steps (tool calls, search, image analysis)
- Write findings to a MEMORY.md file

## Stage 2: Decide What to Evaluate

Choose from **SDK built-in evaluators** first:

| Evaluator | Measures | Use When |
|-----------|----------|----------|
| `TaskAdherenceEvaluator` | Did the response accomplish the task? | Always — primary quality gate |
| `CoherenceEvaluator` | Is the response logically consistent? | Multi-turn or complex responses |
| `GroundednessEvaluator` | Is the response grounded in provided context? | RAG / search-based answers |
| `RelevanceEvaluator` | Is the response relevant to the query? | Open-ended queries |
| `FluencyEvaluator` | Is the language natural and well-formed? | User-facing text quality |
| `ViolenceEvaluator` | Does the response contain violent content? | Safety baseline |
| `SexualEvaluator` | Does the response contain sexual content? | Safety baseline |
| `SelfHarmEvaluator` | Does the response contain self-harm content? | Safety baseline |
| `HateUnfairnessEvaluator` | Does the response contain hate/unfairness? | Safety baseline |

Only build a `CodeEvaluator` or `PromptEvaluator` if no built-in covers your dimension.

This project's **MVP baseline** (per Epic 006): Task Adherence, Coherence, Violence.

## Stage 3: Instrument the Application

Add instrumentation to the **existing production code**. Never create separate functions for testing. The Agent Framework + OTel already emits traces — evaluations connect to those traces via the Foundry project.

## Stage 4: Create a Run Harness and Verify Traces

Create a script that calls the eval-boundary function, bypassing external infrastructure. **Do not proceed until you have real traces.**

## Stage 5: Write the Eval Test File

Write the test file using `azure-ai-evaluation`'s `evaluate()`. The data file should be JSONL with fields matching the evaluator input schema.

```python
# Example: src/agent/evals/test_quality.py
from azure.ai.evaluation import evaluate, TaskAdherenceEvaluator, CoherenceEvaluator
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

def test_agent_quality_baseline():
    project_client = AIProjectClient(
        credential=DefaultAzureCredential(),
        endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    )
    result = evaluate(
        data="src/agent/evals/data/golden-dataset.jsonl",
        evaluators={
            "task_adherence": TaskAdherenceEvaluator(project_client=project_client),
            "coherence": CoherenceEvaluator(project_client=project_client),
        },
        azure_ai_project=project_client,
        evaluation_name=f"kb-agent-regression-{datetime.now().strftime('%Y%m%d-%H%M')}",
    )
    # Assert minimum quality thresholds
    metrics = result.get("metrics", {})
    assert metrics.get("task_adherence.score", 0) >= 4.0, f"Task adherence too low: {metrics}"
    assert metrics.get("coherence.score", 0) >= 4.0, f"Coherence too low: {metrics}"
```

## Stage 6: Build the Dataset

Populate the dataset by **actually running the app** with representative inputs. Store as JSONL in `src/agent/evals/data/`. **Never fabricate `eval_output` values.**

Dataset fields should match evaluator expectations:
```jsonl
{"query": "What is agentic retrieval?", "response": "...", "context": "..."}
```

## Stage 7: Run the Tests

Run evals and report results. Results are published to Foundry automatically when `azure_ai_project` is passed to `evaluate()`. If the user's intent was "setup" — **STOP** and report.

Check results in Foundry portal: **Evaluate → Runs** — compare across runs to track quality over time.

## Stage 8: Investigate Failures

For each failing case:
1. Get detailed test output (per-row scores are in `result["rows"]`)
2. Inspect the trace data in Foundry Control Plane (Operate → Traces)
3. Root-cause analysis (LLM failure vs non-LLM failure)
4. Document findings in MEMORY.md
5. Fix and re-run — compare runs in Foundry

---

## Evaluation Modes

The SDK supports three modes — all publish to the same Foundry project for unified tracking:

| Mode | When | How |
|------|------|-----|
| **Local dev-test** | During development, prompt iteration | `evaluate()` in pytest or standalone script; judges call Foundry models |
| **Continuous evaluation** | Against live agent traffic | Foundry evaluation rules (`azure-ai-projects` SDK), sampling dev traffic |
| **Scheduled evaluation** | Regression on curated dataset | Foundry scheduled evaluation with `RecurrenceTrigger` |

All three modes are defined in [Epic 006](docs/epics/006-foundry-agent-evaluations.md).

---

## Anti-Patterns: What NOT to Do

| Anti-Pattern | Why | Instead |
|-------------|-----|---------|
| Custom scoring functions with regex/heuristics | Fragile, doesn't generalize | Use SDK built-in evaluators (LLM-as-judge) |
| Third-party eval frameworks (DeepEval, RAGAS, promptfoo) | Fragments tooling, results don't publish to Foundry | Use `azure-ai-evaluation` |
| Building a custom eval dashboard | Duplicates Foundry portal | Use Foundry Evaluate → Runs for comparison and trending |
| Hardcoded pass/fail thresholds without baseline | Arbitrary, causes false failures | Establish baseline from first run, then set thresholds |
| Running evals against mocked LLM responses | Doesn't test real model behaviour | Always use real Foundry model endpoints as judges |

---

## Project Context

| Component | Location | Purpose |
|-----------|----------|---------|
| **Agent** | `src/agent/` | FastAPI + Microsoft Agent Framework |
| **Agent tools** | KB search (Azure AI Search), image analysis, Cosmos DB memory | Tool behavior tested via unit tests, not evals |
| **Eval code** | `src/agent/evals/` | Eval scripts, datasets, and config |
| **Eval epic** | `docs/epics/006-foundry-agent-evaluations.md` | Full eval automation plan (continuous, scheduled, red-team, alerting) |
| **Foundry project** | `infra/azure/infra/modules/foundry-project.bicep` | Hosts traces, eval runs, model deployments |
| **MVP evaluators** | Task Adherence, Coherence, Violence | Baseline quality + safety gate |
| **Test convention** | `make dev-test` runs the current repo-wide test suite, pytest three-tier strategy | Evals are a separate tier — `make eval-run` |
