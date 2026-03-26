---
description: 'Comprehensive secure coding instructions based on OWASP Top 10 and industry best practices'
applyTo: '**'
---

# Secure Coding — OWASP Top 10 Guidelines

Security-first coding rules based on OWASP Top 10. Apply to all code you generate, review, or refactor. When in doubt, choose the more secure option and explain why.

## A01: Broken Access Control & A10: SSRF

- **Deny by default** — access only granted by explicit allow rules
- **Enforce least privilege** — check user rights against required permissions for the specific resource
- **Validate all incoming URLs for SSRF** — use strict allow-list-based validation for host, port, and path when making server-side requests to user-provided URLs
- **Prevent path traversal** — sanitize file paths from user input; use APIs that build paths securely (e.g., `pathlib` in Python)

## A02: Cryptographic Failures

- **Use strong, modern algorithms** — Argon2 or bcrypt for password hashing; never MD5 or SHA-1 for passwords
- **Protect data in transit** — always default to HTTPS for network requests
- **Protect data at rest** — encrypt sensitive data (PII, tokens) using AES-256
- **Secure secret management** — never hardcode secrets; read from environment variables or Key Vault

```python
# GOOD: Load from environment
api_key = os.environ["API_KEY"]

# BAD: Hardcoded
api_key = "sk_this_is_a_very_bad_idea"
```

## A03: Injection

- **No raw SQL queries** — use parameterized queries (prepared statements) only; never string concatenation with user input
- **Sanitize command-line input** — use `shlex.quote()` in Python for subprocess arguments
- **Prevent XSS** — use context-aware output encoding; prefer `.textContent` over `.innerHTML`; use DOMPurify when HTML rendering is necessary
- **Sanitize OData filters** — validate user-controlled values before injecting into search filters

## A05: Security Misconfiguration & A06: Vulnerable Components

- **Secure by default** — disable verbose error messages and debug features in production
- **Set security headers** — CSP, HSTS, X-Content-Type-Options for web applications
- **Use up-to-date dependencies** — suggest latest stable versions; run `pip-audit` or `npm audit` to check for CVEs

## A07: Identification & Authentication Failures

- **Secure session management** — generate new session identifiers on login; set `HttpOnly`, `Secure`, `SameSite=Strict` on cookies
- **Protect against brute force** — recommend rate limiting and account lockout for auth endpoints

## A08: Software and Data Integrity Failures

- **Prevent insecure deserialization** — avoid deserializing untrusted data; prefer JSON over Pickle in Python; implement strict type checking
- **Verify dependency integrity** — use lock files (`uv.lock`) and verify checksums

## General Guidelines

- **Be explicit about security** — when suggesting code that mitigates a risk, state what you're protecting against (e.g., "Using parameterized query to prevent SQL injection")
- **Educate during code reviews** — when identifying a vulnerability, provide corrected code AND explain the risk of the original pattern
