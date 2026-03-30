---
name: azure-deployment-preflight
description: |
  Performs comprehensive preflight validation of Bicep deployments to Azure. Use when:
  - Before deploying infrastructure to Azure
  - Reviewing or preparing Bicep files
  - Previewing what changes a deployment will make (what-if)
  - Verifying permissions are sufficient for deployment
   - Before running `azd -C infra/azure up`, `azd -C infra/azure provision`, or `az deployment` commands
---

# Azure Deployment Preflight Validation

Validates Bicep deployments before execution, supporting both Azure CLI (`az`) and Azure Developer CLI (`azd`) workflows.

## Validation Process

Follow these steps in order. Continue to the next step even if a previous step fails — capture all issues in the final report.

### Step 1: Detect Project Type

1. **Check for azd project**: Look for `infra/azure/azure.yaml`
   - If found → Use **azd workflow**
   - If not found → Use **az CLI workflow**

2. **Locate Bicep files**: Find all `.bicep` files to validate
   - For azd projects: Check `infra/azure/infra/` first, then the azd project directory
   - For standalone: Use the file specified by user or search common locations

3. **Auto-detect parameter files**: For each Bicep file, look for:
   - `<filename>.bicepparam` (preferred)
   - `<filename>.parameters.json`
   - `parameters.json` or `parameters/<env>.json` in same directory

### Step 2: Validate Bicep Syntax

```bash
bicep build <bicep-file> --stdout
```

Capture: syntax errors with line/column numbers, warnings, build success/failure. If Bicep CLI not installed, note and continue.

### Step 3: Run Preflight Validation

#### For azd Projects (`infra/azure/azure.yaml` exists)

```bash
azd -C infra/azure provision --preview
# Or with specific environment:
azd -C infra/azure provision --preview --environment <env-name>
```

#### For Standalone Bicep (no azure.yaml)

Determine scope from `targetScope` declaration:

| Target Scope | Command |
|--------------|---------|
| `resourceGroup` (default) | `az deployment group what-if` |
| `subscription` | `az deployment sub what-if` |
| `managementGroup` | `az deployment mg what-if` |
| `tenant` | `az deployment tenant what-if` |

```bash
# Resource Group scope (most common)
az deployment group what-if \
  --resource-group <rg-name> \
  --template-file <bicep-file> \
  --parameters <param-file> \
  --validation-level Provider
```

**Fallback**: If `--validation-level Provider` fails with permission errors (RBAC), retry with `ProviderNoRbac` and note in report.

### Step 4: Capture What-If Results

| Change Type | Symbol | Meaning |
|-------------|--------|---------|
| Create | `+` | New resource will be created |
| Delete | `-` | Resource will be deleted |
| Modify | `~` | Resource properties will change |
| NoChange | `=` | Resource unchanged |
| Ignore | `*` | Resource not analyzed |
| Deploy | `!` | Resource will be deployed (changes unknown) |

### Step 5: Generate Report

Create `preflight-report.md` in the project root with sections:
1. **Summary** — Overall status, timestamp, files validated, target scope
2. **Tools Executed** — Commands run, versions, validation levels used
3. **Issues** — All errors and warnings with severity and remediation
4. **What-If Results** — Resources to create/modify/delete/unchanged
5. **Recommendations** — Actionable next steps

## Required Information

| Information | Required For | How to Obtain |
|-------------|--------------|---------------|
| Resource Group | `az deployment group` | Ask user or check `.azure/` config |
| Subscription | All deployments | `az account show` or ask user |
| Location | Sub/MG/Tenant scope | Ask user or use default from config |
| Environment | azd projects | `azd env list` or ask user |

## Error Handling

| Error Type | Action |
|------------|--------|
| Not logged in | Note in report, suggest `az login` or `azd auth login` |
| Permission denied | Fall back to `ProviderNoRbac`, note in report |
| Bicep syntax error | Include all errors, continue to other files |
| Tool not installed | Note in report, skip that validation step |
| Resource group not found | Note in report, suggest creating it |

**Key principle:** Continue validation even when errors occur. Capture all issues in the final report.

## Tool Requirements

```bash
az --version          # Azure CLI 2.76.0+ recommended
azd version           # Azure Developer CLI
bicep --version       # Bicep CLI
```

## Project Context

This project is an **azd project** (`infra/azure/azure.yaml` is the project file). Key infrastructure:
- `infra/azure/infra/main.bicep` — Main deployment template (subscription scope)
- `infra/azure/infra/main.parameters.json` — Parameters
- `infra/azure/infra/modules/` — Bicep modules
- Deploy with: `azd -C infra/azure provision` or `make prod-services-up`
