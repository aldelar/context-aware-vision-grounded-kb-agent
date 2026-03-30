---
name: secret-scanning
description: |
  Guide for configuring and managing GitHub secret scanning, push protection,
  custom patterns, and alert remediation. Use when:
  - Enabling or configuring secret scanning for a repository
  - Setting up push protection to block secrets before push
  - Defining custom secret patterns with regular expressions
  - Resolving a blocked push from the command line
  - Triaging or remediating secret scanning alerts
---

# Secret Scanning

Procedural guidance for configuring GitHub secret scanning — detecting leaked credentials, preventing secret pushes, defining custom patterns, and managing alerts.

## Core Workflow — Enable Secret Scanning

### Step 1: Enable Secret Protection

1. Navigate to repository **Settings** → **Advanced Security**
2. Click **Enable** next to "Secret Protection"
3. Confirm by clicking **Enable Secret Protection**

For organizations, use security configurations to enable at scale.

### Step 2: Enable Push Protection

Push protection blocks secrets during the push process — before they reach the repository.

1. Settings → **Advanced Security**
2. Enable "Push protection" under Secret Protection

Blocks secrets in: command line pushes, GitHub UI commits, file uploads, REST API requests.

### Step 3: Configure Exclusions (Optional)

Create `.github/secret_scanning.yml`:

```yaml
paths-ignore:
  - "docs/**"
  - "test/fixtures/**"
  - "**/*.example"
```

Limits: max 1,000 entries, file must be under 1 MB. Excluded paths also skip push protection.

### Step 4: Enable Additional Features (Optional)

- **Non-provider patterns**: Detect private keys, connection strings, generic API keys
- **AI-powered generic detection**: Uses Copilot to detect unstructured secrets
- **Validity checks**: Verify if detected secrets are still active (shows `active`, `inactive`, `unknown`)

## Resolving Blocked Pushes

### Option A: Remove the Secret

**Latest commit:**
```bash
# Remove the secret from the file, then:
git commit --amend --all
git push
```

**Earlier commit:**
```bash
git log                          # Find earliest commit with secret
git rebase -i <COMMIT-ID>~1     # Change 'pick' to 'edit'
# Remove the secret, then:
git add .
git commit --amend
git rebase --continue
git push
```

### Option B: Bypass Push Protection

1. Visit the URL returned in the push error
2. Select bypass reason: "used in tests", "false positive", or "I'll fix it later"
3. Click **Allow me to push this secret**
4. Re-push within 3 hours

### Option C: Request Bypass Privileges

If delegated bypass is enabled and you lack privileges:
1. Visit the URL from the push error
2. Add a comment explaining why
3. Submit request and wait for approval

## Custom Patterns

Define organization-specific patterns using regular expressions:

1. Settings → Advanced Security → Custom patterns → **New pattern**
2. Enter pattern name and regex
3. Add test string, click **Save and dry run** (up to 1,000 results)
4. Review for false positives
5. **Publish pattern**
6. Optionally enable push protection for the pattern

Custom patterns can be defined at repository, organization, or enterprise level.

## Alert Management

### Alert Types

| Type | Description |
|------|-------------|
| **User alerts** | Secrets found in repository — visible in Security tab |
| **Push protection alerts** | Secrets pushed via bypass (filter: `bypassed: true`) |
| **Partner alerts** | Secrets reported to provider (not shown in repo) |

### Remediation Priority

1. **Rotate the credential immediately** — this is the critical action
2. Review the alert for context (location, commit, author)
3. Check validity status: `active` (urgent), `inactive` (lower priority)
4. Remove from Git history if needed (often unnecessary after rotation)

### Dismissing Alerts

Dismiss with a documented reason: **False positive**, **Revoked**, or **Used in tests**.

## Project Context

This project follows these security rules (see `.github/instructions/security.instructions.md`):
- **Never** commit secrets, connection strings, API keys, or tokens
- Use Azure Managed Identity for all service-to-service auth
- Use Key Vault references where managed identity isn't available
- `.env` files are gitignored — they contain local dev credentials from `azd -C infra/azure env get-values`
