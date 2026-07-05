# Code Review Crew 🔍

An ambient, multi-agent code reviewer that automatically analyzes GitHub Pull Requests the moment they are opened, catches security vulnerabilities using the STRIDE threat modeling framework, and always requires human approval before posting reviews back to GitHub.

## Video Demo
🎥 **[Watch the 4-Minute YouTube Demo Video](https://youtu.be/GbizNRIHEkY)**

## The Problem
Manual code review is one of the most significant bottlenecks in modern software development pipelines, often delaying releases and increasing lead times. Moreover, developers frequently miss critical security flaws—like buffer overflows or exposed API credentials—due to alert fatigue or lack of specialized security training. Relying solely on manual oversight increases the risk of deploying vulnerable code to production.

## The Solution
Code Review Crew automates this process by instantly intercepting code changes at the pull request phase. Using a secure pre-LLM screen, it filters out prompt injection attacks, redacts sensitive PII or credentials, runs Semgrep, and then runs parallel analysis engines to construct both a high-level executive summary and a detailed STRIDE threat model of the diff. Crucially, the workflow halts on a human-in-the-loop gate, preventing any comments from being posted to GitHub until an operator explicitly approves the findings via a dark-mode glassmorphic manager dashboard.

## Architecture

```text
                                  +-------------------+
                                  |  GitHub Webhook   |
                                  +---------+---------+
                                            |
                                            v (PR Created/Updated)
                                  +---------+---------+
                                  |  Pub/Sub Trigger  |
                                  +---------+---------+
                                            |
                                            v (Push Notification)
+-------------------------------------------v-------------------------------------------+
|                                  AGENT RUNTIME (Vertex AI)                            |
|                                                                                       |
|  +-------------------+                                                                |
|  |       START       |                                                                |
|  +---------+---------+                                                                |
|            |                                                                          |
|            v                                                                          |
|  +---------+---------+                                                                |
|  |  security_screen  | (PII Redaction, Prompt Injection Scan, Semgrep on Temp File)  |
|  +----+---------+----+                                                                |
|       |         |                                                                     |
|  (If Unsafe)  (If Safe)                                                               |
|       |         +-------------------------+                                           |
|       v                                   v                                           |
|  +----+----+                    +---------+---------+                                 |
|  |Quarantine|                   |  stride_analysis  | (Parallel LLM Thread)           |
|  +---------+                    +---------+---------+                                 |
|                                           |                                           |
|                                           v                                           |
|                                 +---------+---------+                                 |
|                                 |   pr_summary      | (Parallel LLM Thread)           |
|                                 +---------+---------+                                 |
|                                           |                                           |
|                                           v                                           |
|                                 +---------+---------+                                 |
|                                 |   merge_reviews   | (JoinNode)                      |
|                                 +---------+---------+                                 |
|                                           |                                           |
|                                           v                                           |
|                                 +---------+---------+                                 |
|                                 | request_approval  | (Suspends & Yields RequestInput)|
|                                 +---------+---------+                                 |
|                                           |                                           |
+-------------------------------------------|-------------------------------------------+
                                            | (Triggers HITL Pending State)
                                            v
                                  +---------+---------+
                                  | Manager Dashboard | (FastAPI / Cloud Run App)
                                  +---------+---------+
                                            |
                                            v (Operator Types "APPROVE")
                                  +---------+---------+
                                  |    post_review    | (GitHub API Review Posted)
                                  +-------------------+
```

## Key Concepts Demonstrated

| Concept | Where in Code |
|---|---|
| ADK 2.0 Multi-agent Graph Workflow | [app/agent.py](file:///c:/Users/josec/agy2-projects/code-review-crew/code-review-agent/app/agent.py) |
| MCP Servers (GitHub + Dev Knowledge) | [mcp_config.json](file:///C:/Users/josec/.gemini/config/mcp_config.json) |
| Antigravity Vibe Coding | Entire codebase iteration |
| Security Features | [agent.py](file:///c:/Users/josec/agy2-projects/code-review-crew/code-review-agent/app/agent.py), [.agents/](file:///c:/Users/josec/agy2-projects/code-review-crew/code-review-agent/.agents/) |
| Agent Skills | [.agents/skills/](file:///c:/Users/josec/agy2-projects/code-review-crew/code-review-agent/.agents/skills/) |
| Deployability | Agent Runtime + Cloud Run |

## Project Structure

```text
code-review-agent/
├── .agents/
│   ├── CONTEXT.md                    # Core security standards and guidelines
│   ├── hooks.json                    # Command execution guardrail hooks configuration
│   └── scripts/
│       ├── validate_tool_call.py     # Tool validation rules block
│       └── mock_semgrep.py           # Cross-platform mock Semgrep scanner for pre-commit
├── .gitignore                        # Git ignore patterns for credentials and envs
├── .pre-commit-config.yaml           # Local Git pre-commit hooks configurations
├── Dockerfile                        # Docker configuration for dashboard deployment
├── Makefile                          # Development task automation commands
├── app/
│   ├── __init__.py
│   └── agent.py                      # Declares ADK 2.0 Graph Workflow nodes and edges
├── pyproject.toml                    # Virtual environment dependencies lock
├── review_dashboard/
│   ├── Dockerfile                    # Container definition for Cloud Run
│   ├── requirements.txt              # Dashboard package dependencies
│   └── main.py                       # FastAPI manager dashboard backend and embedded UI
└── threat_model.md                   # STRIDE threat model security analysis
```

## Prerequisites
- Python 3.11+
- uv package manager
- Node.js 18+ (for GitHub MCP)
- Google Cloud project with billing enabled
- Antigravity IDE
- agents-cli (installed via `uvx google-agents-cli setup`)

## Setup Instructions

### 1. Clone and install
Navigate to the directory and sync dependencies:
```bash
uv sync --dev --all-extras
```

### 2. Configure environment variables
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key                # Gemini API key for local LLM nodes execution
GOOGLE_GENAI_USE_VERTEXAI=False                   # Set to False to run LLMs locally via Gemini API
GITHUB_PAT=your_github_pat_token                  # GitHub token to query PR diffs and write review comments
DEVELOPER_KNOWLEDGE_API_KEY=your_api_key         # restricted key for Google Dev Knowledge MCP
TEST_MODE=true                                    # Set to true to bypass remote GitHub API and run offline
```

### 3. Configure MCP servers
Add the configurations inside `~/.gemini/config/mcp_config.json`:
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "<YOUR_GITHUB_PAT>"
      }
    },
    "google-developer-knowledge": {
      "url": "https://developerknowledge.googleapis.com/mcp",
      "headers": {
        "X-Goog-Api-Key": "<YOUR_DEVELOPER_KNOWLEDGE_API_KEY>"
      }
    }
  }
}
```

### 4. Run locally
Start the local environment:
```bash
# Install dependencies
make install

# Start the agent developer playground (runs locally on port 8080)
make playground
```

### 5. Run evaluation
Run the test evaluations:
```bash
make generate-traces
make grade
```

## Deployment

### Deploy to Agent Runtime
Deploy the agent container to Vertex AI Agent Runtime:
```bash
agents-cli deploy --project YOUR_PROJECT_ID --region us-central1
```

### Deploy dashboard to Cloud Run
Deploy the FastAPI manager dashboard to Cloud Run:
```bash
cd review_dashboard
gcloud run deploy code-review-dashboard \
  --source . \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,AGENT_RUNTIME_ID=YOUR_AGENT_RUNTIME_ID \
  --allow-unauthenticated
```

### Wire Pub/Sub trigger
Setup Pub/Sub message subscriptions:
```bash
# Create topics
gcloud pubsub topics create pr-review-requests --project YOUR_PROJECT_ID
gcloud pubsub topics create pr-review-requests-dead-letter --project YOUR_PROJECT_ID

# Setup push subscription pointing to Agent Runtime engine
gcloud pubsub subscriptions create pr-review-push \
  --topic=pr-review-requests \
  --push-endpoint="https://us-central1-aiplatform.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID:query" \
  --push-auth-service-account="pubsub-invoker@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --push-no-wrapper \
  --ack-deadline=600 \
  --dead-letter-topic=pr-review-requests-dead-letter \
  --max-delivery-attempts=5 \
  --project YOUR_PROJECT_ID
```

## Security Design

The **pre-LLM security screen** runs as the entry point function node in the workflow. It parses the incoming PR payload and conducts regex PII redaction and prompt injection checks *before* forwarding the data to any LLM nodes. This acts as a robust firewall, blocking adversarial jailbreaks or instructions (such as "ignore previous reviews") from reaching downstream reasoning agents. It also spins up a localized Semgrep scan on a temporary file to detect secrets and vulnerabilities, deleting the file safely in a `finally` block to prevent leaks.

The **STRIDE threat model** ([threat_model.md](file:///c:/Users/josec/agy2-projects/code-review-crew/code-review-agent/threat_model.md)) evaluates the agent's architecture. It classified weaknesses in basic substring prompt injection detection and loose user approval matching as High severity threats. We mitigated these in the final iteration by deploying a robust regex-based injection scanner and strict exact-match array lists (`['yes', 'y', 'approve']`) to prevent accidental publications on sentences like "Yesterday I checked, but please reject."

The pipeline enforces code-level safety using a **git pre-commit hook** and a **`hooks.json` PreToolUse command interceptor**. When developers stage python code containing secrets or keys, the pre-commit scanner runs Semgrep locally to block the git commit. Furthermore, the `PreToolUse` hook intercepts any shell tool invocation made by the agent and validates it against `validate_tool_call.py`, blocking path traversal, force pushes, or system level deletions.

## Evaluation Results

Evaluation traces are graded on GCP-enabled metrics:

| Case ID | Metric | Expected | Actual | Status |
|---|---|---|---|---|
| case_01 (Buffer Overflow Diff) | STRIDE Threat Detection | Identifies Tampering in connection.cc | Identifies Tampering in connection.cc | **PASSED** |
| case_01 (Buffer Overflow Diff) | PII Redaction | Redacts ghp_ PAT / credentials | Redacts ghp_ PAT / credentials | **PASSED** |
| case_02 (Prompt Injection Diff) | Prompt Injection Defense | Quarantines injection payload | Quarantines injection payload | **PASSED** |

## Live Demo
- **Agent Runtime ID:** `projects/514276508634/locations/us-central1/reasoningEngines/5049571471991504896`
- **Manager Dashboard:** https://code-review-dashboard-514276508634.us-central1.run.app
- **YouTube Video:** [to be added]

## ⚠️ Security Note
No API keys, tokens, or secrets are included in this repository. All credentials are loaded from environment variables via `.env` which is excluded by `.gitignore`.
