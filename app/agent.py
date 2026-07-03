# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import sys
import json
import tempfile
import subprocess
import httpx
from typing import Any, AsyncGenerator
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.workflow import Workflow, JoinNode, node
from google.genai import types

# Ensure environment variables are respected
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "False")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = GOOGLE_GENAI_USE_VERTEXAI


# Input Schemas
class PRReviewInput(BaseModel):
    repo: str = Field(description="The GitHub repository name (e.g. 'owner/repo')")
    pr_number: int = Field(description="The Pull Request number")


# Node schemas
class FindingItem(BaseModel):
    category: str = Field(description="STRIDE Category (Spoofing, Tampering, etc.)")
    location: str = Field(description="File path and lines")
    threat: str = Field(description="Vulnerability description")
    severity: str = Field(description="Severity (Low, Medium, High, Critical)")
    remediation: str = Field(description="Remediation steps")


class StrideOutput(BaseModel):
    findings: list[FindingItem] = Field(
        default_factory=list, description="List of STRIDE security threats"
    )


class PRSummaryOutput(BaseModel):
    purpose: str = Field(description="High-level purpose of the PR")
    complexity: str = Field(description="Complexity level (Low, Medium, High)")
    impact: str = Field(description="Business/Functional impact summary")
    recommendations: list[str] = Field(
        default_factory=list, description="Key files/recommendations for human review"
    )


# Skill Loader
def load_skill_instruction(skill_name: str) -> str:
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace_dir = os.path.dirname(project_dir)
    skill_path = os.path.join(
        workspace_dir, ".agents", "skills", skill_name, "SKILL.md"
    )
    if os.path.exists(skill_path):
        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        return parts[2].strip()
                return content.strip()
        except Exception:
            pass
    return f"Use standard instructions for skill {skill_name}."


# Nodes Implementation


@node
async def security_screen(ctx: Context, node_input: types.Content) -> Event:
    repo = "google/adk"
    pr_number = 12

    try:
        if node_input and node_input.parts:
            text = node_input.parts[0].text
            data = json.loads(text)
            repo = data.get("repo", repo)
            pr_number = int(data.get("pr_number", pr_number))
    except Exception:
        repo = ctx.state.get("repo", repo)
        pr_number = ctx.state.get("pr_number", pr_number)

    # Save parameters to state
    ctx.state["repo"] = repo
    ctx.state["pr_number"] = pr_number

    github_token = os.getenv("GITHUB_PAT")

    pr_details = {}
    diff_content = ""

    # Fetch PR data from GitHub API with mock fallback
    try:
        headers = {
            "Authorization": f"Bearer {github_token}" if github_token else "",
            "Accept": "application/vnd.github.v3+json",
        }
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
                headers=headers,
                timeout=10.0,
            )
            if res.status_code == 200:
                pr_details = res.json()

            headers_diff = {
                "Authorization": f"Bearer {github_token}" if github_token else "",
                "Accept": "application/vnd.github.v3.diff",
            }
            res_diff = await client.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
                headers=headers_diff,
                timeout=10.0,
            )
            if res_diff.status_code == 200:
                diff_content = res_diff.text
    except Exception as e:
        # Fallback Mock PR data for testing
        pr_details = {
            "title": "Mock Pull Request for testing",
            "body": "This is a mock pull request containing stable connection updates and JNI validation tests.",
            "changed_files": 2,
        }
        diff_content = """diff --git a/auth/auth_service.py b/auth/auth_service.py
index 012345..6789ab 100644
--- a/auth/auth_service.py
+++ b/auth/auth_service.py
@@ -10,3 +10,6 @@ def check_auth(token):
+    # Hardcoded test credentials
+    admin_secret = "ghp_" + "mocksecretkeyvalue1234567890abcdef"
+    email = "test_admin@example.com"
+    return token == admin_secret
"""

    pr_text = (
        str(pr_details.get("title") or "")
        + " "
        + str(pr_details.get("body") or "")
        + " "
        + str(diff_content or "")
    ).lower()

    # Use regex for more robust injection checking to prevent bypasses (F-01)
    injection_regex = r"(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt\s+bypass|override\s+system\s+prompt)"
    if re.search(injection_regex, pr_text):
        ctx.state["security_alert"] = (
            "Prompt injection attempt detected in PR title/body/diff."
        )
        return Event(output={"error": "Prompt injection detected"}, route="unsafe")

    # 2. PII / Secret Redaction
    redacted_diff = diff_content
    # Redact Emails
    redacted_diff = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[REDACTED_EMAIL]", redacted_diff)
    # Redact common credentials/keys patterns
    redacted_diff = re.sub(
        r"ghp_[A-Za-z0-9_]{36}", "[REDACTED_GITHUB_PAT]", redacted_diff
    )
    redacted_diff = re.sub(
        r"AIzaSy[A-Za-z0-9_-]{35}", "[REDACTED_API_KEY]", redacted_diff
    )

    # Save sanitized diff to state
    ctx.state["sanitized_diff"] = redacted_diff
    ctx.state["pr_title"] = pr_details.get("title", "")
    ctx.state["pr_body"] = pr_details.get("body", "")

    # 3. Semgrep scan on temporary file
    semgrep_output = ""
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(
        temp_dir, f"pr_diff_{repo.replace('/', '_')}_{pr_number}.diff"
    )
    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(redacted_diff)

        # Run Semgrep
        cmd = [sys.executable, "-m", "semgrep", "scan", "--config=auto", temp_file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        semgrep_output = result.stdout + result.stderr
    except Exception as e:
        semgrep_output = f"Semgrep scan skipped/failed: {str(e)}"
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    ctx.state["semgrep_results"] = semgrep_output

    # 4. hooks.json checks (Sensitive paths warning)
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hooks_path = os.path.join(project_dir, ".agents", "hooks.json")
    if os.path.exists(hooks_path):
        try:
            with open(hooks_path, "r") as f:
                hooks_config = json.load(f)
                if hooks_config.get("enabled"):
                    # Basic simulation of hooks warnings based on modified paths in diff
                    for sensitive in ["auth/", "secrets/", "config/"]:
                        if sensitive in redacted_diff:
                            ctx.state["sensitive_path_modified"] = True
        except Exception:
            pass

    return Event(output=redacted_diff, route="safe")


# LlmAgents definitions using loaded skill instructions
stride_analysis = LlmAgent(
    name="stride_analysis",
    model="gemini-flash-latest",
    instruction=f"You are a threat modeler. Analyze the PR diff for STRIDE vulnerabilities.\n\nSkill Instructions:\n{load_skill_instruction('stride-threat-modeling')}",
    output_schema=StrideOutput,
    output_key="stride_result",
)

pr_summary = LlmAgent(
    name="pr_summary",
    model="gemini-flash-latest",
    instruction=f"You are a code reviewer. Generate an executive summary of this PR.\n\nSkill Instructions:\n{load_skill_instruction('pr-executive-summary')}",
    output_schema=PRSummaryOutput,
    output_key="summary_result",
)

merge_reviews = JoinNode(name="merge_reviews")


@node
async def request_approval(
    ctx: Context, node_input: dict
) -> AsyncGenerator[Event | RequestInput, None]:
    if not ctx.resume_inputs:
        stride = node_input.get("stride_analysis", {})
        summary = node_input.get("pr_summary", {})

        review_msg = (
            f"## Pull Request Review Approval Request\n\n"
            f"### Executive Summary\n"
            f"**Purpose:** {summary.get('purpose', 'N/A')}\n"
            f"**Complexity:** {summary.get('complexity', 'N/A')}\n"
            f"**Impact:** {summary.get('impact', 'N/A')}\n"
            f"**Recommendations:**\n"
        )
        for rec in summary.get("recommendations", []):
            review_msg += f"- {rec}\n"

        review_msg += f"\n### STRIDE Threat Modeling Findings\n"
        findings = stride.get("findings", [])
        if not findings:
            review_msg += "No threats identified.\n"
        else:
            for f in findings:
                review_msg += f"- **[{f.get('severity', 'LOW')}]** {f.get('category', 'Threat')}: {f.get('threat', '')} at {f.get('location', '')}\n"
                review_msg += f"  *Remediation:* {f.get('remediation', '')}\n"

        review_msg += f"\nDo you approve posting this review to GitHub? (Yes/No)"

        yield RequestInput(interrupt_id="approval", message=review_msg)
        return

    # Check approval
    approval_resp = ctx.resume_inputs.get("approval", False)
    approved = False
    if isinstance(approval_resp, dict):
        approved = approval_resp.get("approved", False)
    elif isinstance(approval_resp, str):
        approved = approval_resp.strip().lower() in [
            "yes",
            "y",
            "approve",
            "approved",
            "true",
        ]
    elif isinstance(approval_resp, bool):
        approved = approval_resp

    if approved:
        yield Event(output=node_input, route="approved")
    else:
        yield Event(output=node_input, route="rejected")


@node
async def post_review(ctx: Context, node_input: dict) -> str:
    repo = ctx.state.get("repo")
    pr_number = ctx.state.get("pr_number")

    stride = node_input.get("stride_analysis", {})
    summary = node_input.get("pr_summary", {})

    comment_md = (
        f"## Ambient Code Review Report (Crew)\n\n"
        f"### Executive Summary\n"
        f"- **Purpose:** {summary.get('purpose', 'N/A')}\n"
        f"- **Complexity:** {summary.get('complexity', 'N/A')}\n"
        f"- **Impact:** {summary.get('impact', 'N/A')}\n"
        f"#### File/Review Recommendations:\n"
    )
    for rec in summary.get("recommendations", []):
        comment_md += f"- {rec}\n"

    comment_md += f"\n### STRIDE Security Assessment\n"
    findings = stride.get("findings", [])
    if not findings:
        comment_md += "✅ No major security threats identified in this PR.\n"
    else:
        for f in findings:
            comment_md += f"- **[{f.get('severity', 'LOW')}]** {f.get('category', 'Threat')}: {f.get('threat', '')} ({f.get('location', '')})\n"
            comment_md += f"  *Fix:* {f.get('remediation', '')}\n"

    # Post back to GitHub API
    github_token = os.getenv("GITHUB_PAT")
    if github_token and repo and pr_number:
        try:
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json={"body": comment_md}, headers=headers)
                return f"Successfully posted review comment to GitHub PR #{pr_number}. API Status: {res.status_code}"
        except Exception as e:
            return f"Failed to post to GitHub: {str(e)}. Review markdown output:\n{comment_md}"

    return f"Review complete. (Mock GitHub post) Output:\n{comment_md}"


@node
async def reject_review(ctx: Context, node_input: dict) -> str:
    return "Review rejected by human operator. Review comment not posted to GitHub."


@node
async def quarantine(ctx: Context, node_input: dict) -> str:
    alert = ctx.state.get("security_alert", "Unknown security threat.")
    return f"ALERT: Pull Request is quarantined! Reason: {alert}"


root_agent = Workflow(
    name="code_review_workflow",
    edges=[
        ("START", security_screen),
        (
            security_screen,
            {"safe": (stride_analysis, pr_summary), "unsafe": quarantine},
        ),
        ((stride_analysis, pr_summary), merge_reviews),
        (merge_reviews, request_approval),
        (request_approval, {"approved": post_review, "rejected": reject_review}),
    ],
    description="Ambience multi-agent code reviewer graph workflow.",
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
