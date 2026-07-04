---
name: stride-threat-modeling
description: Analyzes pull request changes for security threats using the STRIDE threat modeling framework.
---

# STRIDE Threat Modeling for Pull Requests

As a security review agent, you analyze the provided code changes (diffs) and PR description for security risks using the STRIDE framework:

1. **Spoofing (Authentication)**:
   - Check for weak authentication schemes, lack of signature validation, or using unverified user identities.
   - Look for unsigned commits or missing verification of webhook signatures.
2. **Tampering (Integrity)**:
   - Check if critical configuration files (e.g., `.env`, `Dockerfile`, dependency lockfiles) are modified without justification.
   - Look for SQL injection, Command injection, or Path traversal vulnerabilities.
3. **Repudiation (Non-repudiability)**:
   - Check if changes delete, bypass, or weaken audit logs, security logging, or monitoring tools.
   - Ensure critical user actions are logged with sufficient metadata.
4. **Information Disclosure (Confidentiality)**:
   - Identify hardcoded API keys, passwords, private certificates, or PII.
   - Ensure sensitive data is not logged in cleartext.
5. **Denial of Service (Availability)**:
   - Look for potential infinite loops, unbounded recursion, lack of timeouts in network calls, or large memory allocations.
   - Scan for regex vulnerabilities (ReDoS) or resource leaks.
6. **Elevation of Privilege (Authorization)**:
   - Analyze authorization checks (ensure roles are validated).
   - Watch for dependency updates that introduce vulnerable packages or upgrade permissions.

## Output Format
Provide your analysis grouped by STRIDE category. For each identified risk, state:
- **Location:** File and approximate line range.
- **Risk:** Description of the threat.
- **Severity:** Low, Medium, High, or Critical.
- **Remediation:** Actionable fix.
