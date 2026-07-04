---
name: pr-executive-summary
description: Generates an executive summary of pull request changes, including business impact, complexity, risk assessment, and key security findings.
---

# Pull Request Executive Summary

As a code reviewer, generate a concise, high-level executive summary of the pull request:

1. **High-Level Purpose**:
   - Summarize what this pull request achieves in 2-3 sentences.
2. **Impact & Complexity**:
   - Assess how complex these changes are (Low, Medium, High).
   - Summarize the business/functional impact (e.g. database migrations, API changes, frontend adjustments).
3. **Security Posture Summary**:
   - Give a quick score or assessment of the overall safety/security risk (e.g. "Safe", "Needs Attention", "Unsafe/Quarantined").
4. **Key Recommendations**:
   - Bulleted list of 2-3 critical things the human reviewer should verify manually before approving the merge.
