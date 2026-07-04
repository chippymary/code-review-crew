---
name: stride-threat-model
description: Analyzes the agent codebase itself for security threats and vulnerabilities using the STRIDE threat modeling framework.
---

# STRIDE Threat Modeling for Agent Codebase

Use this skill to model security threats against our own agent codebase (e.g. `fast_api_app.py`, `agent.py`, dependencies, and hooks). Analyze the agent's architecture, integrations, and tools:

1. **Spoofing**:
   - Check how GitHub webhooks and API calls are authenticated. Ensure webhook secret verification is in place so malicious parties cannot spoof PR notifications.
   - Verify that any external agent connections (A2A) validate identity.
2. **Tampering**:
   - Check if agent instructions or tools can be manipulated by malicious inputs (Prompt Injection).
   - Ensure the `hooks.json` pre-tool validation script cannot be bypassed or modified by the agent itself.
3. **Repudiation**:
   - Verify that all agent tool executions, user requests, and security screens are logged securely (e.g. using Cloud Logging) and cannot be deleted by the agent.
4. **Information Disclosure**:
   - Verify that the agent never leaks the `GEMINI_API_KEY`, `GITHUB_PAT`, or other secrets in logs, error messages, or PR comments.
   - Ensure pre-LLM PII and secret redaction is active before LLM invocation.
5. **Denial of Service**:
   - Assess risks of the agent entering infinite loops (e.g., in graph routing or retry handlers).
   - Ensure the server has rate limits and timeouts configured for API requests.
6. **Elevation of Privilege**:
   - Analyze the tools exposed to the agent. Ensure the agent cannot execute arbitrary bash commands or modify its own environment/codebase unless explicitly allowed and approved by a human.
   - Verify that the FastAPI app runs with the minimum necessary permissions.
