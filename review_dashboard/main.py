import os
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google.adk.sessions import VertexAiSessionService, Session
from google.adk.events import Event
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

app = FastAPI(title="Code Review Crew — Manager Dashboard")

# Read environment variables
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "project-c2b2c72a-4fa3-45ab-b72")
AGENT_RUNTIME_ID = os.getenv(
    "AGENT_RUNTIME_ID",
    "projects/514276508634/locations/us-central1/reasoningEngines/5049571471991504896"
)
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Mock database to allow local testing and fallbacks
MOCK_SESSIONS = [
    {
        "session_id": "mock-session-1",
        "repo": "google/adk",
        "pr_url": "https://github.com/google/adk/pull/12",
        "pr_number": 12,
        "technical_review": "### STRIDE Security Findings\n\n- **[HIGH] Tampering** in `usb_handler.cc:42-58`:\n  *Threat:* Potential buffer overflow in USB connection packet parsing.\n  *Remediation:* Enforce size verification.\n\nRecommended Action: BLOCK",
        "executive_summary": "This pull request refactors the JNI state lifecycle listener bindings and improves hardware connection recovery timeouts for Android 13+ devices.",
        "timestamp": "09:15"
    },
    {
        "session_id": "mock-session-2",
        "repo": "firebase/auth",
        "pr_url": "https://github.com/firebase/auth/pull/15",
        "pr_number": 15,
        "technical_review": "### STRIDE Security Findings\n\n- **[MEDIUM] Information Disclosure** in configuration:\n  *Threat:* Hardcoded testing PSK config detected.\n  *Remediation:* Load from environment dynamically.\n\nRecommended Action: APPROVE WITH CHANGES",
        "executive_summary": "Integrates Firebase authentication flow, adds OAuth2 configuration endpoints, and migrates session storage to Redis.",
        "timestamp": "11:42"
    },
    {
        "session_id": "mock-session-3",
        "repo": "chippymary/code-review-crew",
        "pr_url": "https://github.com/chippymary/code-review-crew/pull/3",
        "pr_number": 3,
        "technical_review": "### STRIDE Security Findings\n\nNo security vulnerabilities or leaks identified in this change. Code complies with CONTEXT.md guidelines.\n\nRecommended Action: APPROVE",
        "executive_summary": "Initial pipeline setup for OIDC and Cloud Run dashboard.",
        "timestamp": "12:05"
    }
]

class ActionRequest(BaseModel):
    decision: str  # "APPROVE" or "REJECT"

# Session Service initialization
session_service = None
try:
    if GOOGLE_CLOUD_PROJECT and AGENT_RUNTIME_ID:
        session_service = VertexAiSessionService(
            project=GOOGLE_CLOUD_PROJECT,
            location=LOCATION,
            app_name=AGENT_RUNTIME_ID
        )
        logger.info(f"Initialized VertexAiSessionService for project={GOOGLE_CLOUD_PROJECT}, app={AGENT_RUNTIME_ID}")
except Exception as e:
    logger.warning(f"Could not initialize VertexAiSessionService: {e}. Falling back to mock sessions.")

def parse_severity(tech_review: str) -> str:
    lines = [line.strip() for line in tech_review.split("\n") if line.strip()]
    if not lines:
        return "APPROVE"
    last_line = lines[-1].upper()
    if "BLOCK" in last_line:
        return "BLOCK"
    elif "APPROVE WITH CHANGES" in last_line:
        return "APPROVE WITH CHANGES"
    return "APPROVE"

@app.get("/api/pending")
async def get_pending_sessions():
    pending = []

    # Try querying Vertex AI Session Service if initialized
    if session_service:
        try:
            response = session_service.list_sessions(app_name=AGENT_RUNTIME_ID)
            sessions: List[Session] = getattr(response, "sessions", [])
            for s in sessions:
                is_pending = False
                if s.events:
                    latest_event: Event = s.events[-1]
                    if getattr(latest_event, "interrupted", False):
                        is_pending = True

                if is_pending:
                    state = s.state or {}
                    pr_summary = state.get("pr_summary", {})
                    tech_review = state.get("technical_review", "")

                    time_str = "10:00"
                    try:
                        if getattr(s, "last_update_time", None):
                            time_str = s.last_update_time.strftime("%H:%M")
                    except Exception:
                        pass

                    pending.append({
                        "session_id": s.id,
                        "repo": state.get("repo", "unknown/repo"),
                        "pr_url": f"https://github.com/{state.get('repo', 'unknown')}/pull/{state.get('pr_number', 0)}",
                        "pr_number": state.get("pr_number", 0),
                        "technical_review": tech_review or "No technical review available.",
                        "executive_summary": pr_summary.get("purpose", "No summary available."),
                        "timestamp": time_str
                    })
        except Exception as e:
            logger.warning(f"Error querying Vertex AI Session Service: {e}. Using mock fallback.")

    # If no real sessions found, fallback to mock list for demo
    if not pending:
        global MOCK_SESSIONS
        if not MOCK_SESSIONS:
            MOCK_SESSIONS = [
                {
                    "session_id": "mock-session-1",
                    "repo": "google/adk",
                    "pr_url": "https://github.com/google/adk/pull/12",
                    "pr_number": 12,
                    "technical_review": "### STRIDE Security Findings\n\n- **[HIGH] Tampering** in `usb_handler.cc:42-58`:\n  *Threat:* Potential buffer overflow in USB connection packet parsing.\n  *Remediation:* Enforce size verification.\n\nRecommended Action: BLOCK",
                    "executive_summary": "This pull request refactors the JNI state lifecycle listener bindings and improves hardware connection recovery timeouts for Android 13+ devices.",
                    "timestamp": "09:15"
                },
                {
                    "session_id": "mock-session-2",
                    "repo": "firebase/auth",
                    "pr_url": "https://github.com/firebase/auth/pull/15",
                    "pr_number": 15,
                    "technical_review": "### STRIDE Security Findings\n\n- **[MEDIUM] Information Disclosure** in configuration:\n  *Threat:* Hardcoded testing PSK config detected.\n  *Remediation:* Load from environment dynamically.\n\nRecommended Action: APPROVE WITH CHANGES",
                    "executive_summary": "Integrates Firebase authentication flow, adds OAuth2 configuration endpoints, and migrates session storage to Redis.",
                    "timestamp": "11:42"
                },
                {
                    "session_id": "mock-session-3",
                    "repo": "chippymary/code-review-crew",
                    "pr_url": "https://github.com/chippymary/code-review-crew/pull/3",
                    "pr_number": 3,
                    "technical_review": "### STRIDE Security Findings\n\nNo security vulnerabilities or leaks identified in this change. Code complies with CONTEXT.md guidelines.\n\nRecommended Action: APPROVE",
                    "executive_summary": "Initial pipeline setup for OIDC and Cloud Run dashboard.",
                    "timestamp": "12:05"
                }
            ]
        pending = MOCK_SESSIONS

    # Append severity badge value to each response dict
    for p in pending:
        p["severity"] = parse_severity(p["technical_review"])

    return pending

@app.post("/api/action/{session_id}")
async def handle_action(session_id: str, payload: ActionRequest):
    logger.info(f"Received decision '{payload.decision}' for session '{session_id}'")

    global MOCK_SESSIONS
    mock_found = False
    for i, s in enumerate(MOCK_SESSIONS):
        if s["session_id"] == session_id:
            MOCK_SESSIONS.pop(i)
            mock_found = True
            break

    if mock_found:
        return {"status": "success", "message": f"Mock session {session_id} updated with {payload.decision}."}

    if session_service:
        try:
            decision_text = "Yes" if payload.decision.upper() == "APPROVE" else "No"
            session = session_service.get_session(session_id=session_id)
            user_event = Event(
                content=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=decision_text)]
                )
            )
            session_service.append_event(session=session, event=user_event)
            session_service.flush()
            return {"status": "success", "message": f"Session {session_id} resumed with '{decision_text}'"}
        except Exception as e:
            logger.error(f"Failed to resume session {session_id} via API: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to resume session: {e}")

    raise HTTPException(status_code=404, detail="Session not found or service unavailable.")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = r"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Code Review Crew — Manager Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #020617 100%);
                --glass-bg: rgba(30, 41, 59, 0.45);
                --glass-border: rgba(255, 255, 255, 0.08);
                --glass-glow: rgba(99, 102, 241, 0.15);
                --text-primary: #f8fafc;
                --text-secondary: #94a3b8;
                --accent-primary: #6366f1;
                --accent-hover: #4f46e5;
                --success: #10b981;
                --danger: #ef4444;
                --warning: #f59e0b;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Inter', sans-serif;
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 2.5rem 1.5rem;
            }

            header {
                max-width: 1200px;
                margin: 0 auto 1.5rem auto;
                width: 100%;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .header-divider {
                max-width: 1200px;
                margin: 0 auto 2.5rem auto;
                width: 100%;
                height: 1px;
                background: rgba(255, 255, 255, 0.08);
            }

            h1 {
                font-size: 2rem;
                font-weight: 700;
                letter-spacing: -0.025em;
                background: linear-gradient(to right, #818cf8, #c084fc);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            /* Live status indicator */
            .status-indicator {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.875rem;
                font-weight: 500;
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.1);
                border: 1px solid rgba(56, 189, 248, 0.2);
                padding: 0.5rem 1rem;
                border-radius: 9999px;
            }

            .pulse-dot {
                width: 8px;
                height: 8px;
                background-color: var(--success);
                border-radius: 50%;
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
                animation: pulse 1.6s infinite;
            }

            @keyframes pulse {
                0% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
                }
                70% {
                    transform: scale(1);
                    box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
                }
                100% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
                }
            }

            .badge {
                background: rgba(99, 102, 241, 0.15);
                border: 1px solid rgba(99, 102, 241, 0.3);
                padding: 0.5rem 1rem;
                border-radius: 9999px;
                font-size: 0.875rem;
                font-weight: 500;
                color: #a5b4fc;
            }

            main {
                max-width: 1200px;
                margin: 0 auto;
                width: 100%;
                flex-grow: 1;
            }

            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
                gap: 2rem;
            }

            .card {
                background: var(--glass-bg);
                backdrop-filter: blur(16px);
                border: 1px solid var(--glass-border);
                border-radius: 16px;
                padding: 1.75rem;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
                transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
                position: relative;
            }

            .card:hover {
                transform: translateY(-4px);
                border-color: rgba(99, 102, 241, 0.35);
                box-shadow: 0 12px 40px 0 var(--glass-glow);
            }

            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 0.75rem;
            }

            .pr-link {
                color: #818cf8;
                text-decoration: none;
                font-weight: 600;
                font-size: 1.05rem;
                display: block;
                max-width: 70%;
                white-space: normal;
                word-break: break-word;
                transition: color 0.2s;
            }

            .pr-link:hover {
                color: #a5b4fc;
            }

            .severity-badge {
                padding: 0.25rem 0.6rem;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            .severity-block {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.4);
                color: #fca5a5;
            }

            .severity-changes {
                background: rgba(245, 158, 11, 0.15);
                border: 1px solid rgba(245, 158, 11, 0.4);
                color: #fcd34d;
            }

            .severity-approve {
                background: rgba(16, 185, 129, 0.15);
                border: 1px solid rgba(16, 185, 129, 0.4);
                color: #6ee7b7;
            }

            .summary {
                font-size: 0.95rem;
                color: var(--text-secondary);
                line-height: 1.6;
                margin-bottom: 1rem;
            }

            /* Expandable Review block */
            .expand-link {
                color: #a5b4fc;
                font-size: 0.85rem;
                font-weight: 600;
                text-decoration: none;
                cursor: pointer;
                display: inline-block;
                margin-bottom: 1.25rem;
                transition: color 0.2s;
            }

            .expand-link:hover {
                color: #c084fc;
            }

            .expandable-content {
                display: none;
                background: rgba(15, 23, 42, 0.6);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1.25rem;
                font-size: 0.875rem;
                color: var(--text-secondary);
                max-height: 220px;
                overflow-y: auto;
                border: 1px solid rgba(255, 255, 255, 0.04);
            }

            .expandable-content.active {
                display: block;
            }

            .card-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: auto;
                padding-top: 1rem;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
            }

            .timestamp {
                font-size: 0.775rem;
                color: var(--text-secondary);
                font-weight: 500;
            }

            .actions {
                display: flex;
                gap: 1rem;
                flex: 1;
                margin-left: 1rem;
            }

            button {
                flex: 1;
                padding: 0.7rem;
                border: none;
                border-radius: 10px;
                font-weight: 600;
                font-size: 0.9rem;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
                transition: all 0.2s ease;
            }

            .btn-approve {
                background: var(--accent-primary);
                color: var(--text-primary);
            }

            .btn-approve:hover {
                background: var(--accent-hover);
            }

            .btn-reject {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.3);
                color: #fca5a5;
            }

            .btn-reject:hover {
                background: var(--danger);
                color: var(--text-primary);
            }

            .spinner {
                width: 14px;
                height: 14px;
                border: 2px solid currentColor;
                border-bottom-color: transparent;
                border-radius: 50%;
                display: inline-block;
                animation: rotation 1s linear infinite;
            }

            @keyframes rotation {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* Modal */
            .modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
                z-index: 1000;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s ease, visibility 0.3s ease;
            }

            .modal-overlay.active {
                opacity: 1;
                visibility: visible;
            }

            .modal {
                position: fixed;
                top: 0;
                right: -600px;
                width: 100%;
                max-width: 580px;
                height: 100vh;
                background: #0b0f19;
                border-left: 1px solid var(--glass-border);
                box-shadow: -8px 0 32px rgba(0, 0, 0, 0.5);
                z-index: 1001;
                padding: 2.5rem;
                overflow-y: auto;
                transition: right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            }

            .modal.active {
                right: 0;
            }

            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2rem;
                border-bottom: 1px solid var(--glass-border);
                padding-bottom: 1rem;
            }

            .modal-title {
                font-size: 1.5rem;
                font-weight: 700;
            }

            .modal-close {
                background: none;
                border: none;
                color: var(--text-secondary);
                cursor: pointer;
                font-size: 1.5rem;
            }

            .modal-body {
                font-size: 0.975rem;
                color: var(--text-secondary);
                line-height: 1.7;
            }

            /* Toasts */
            .toast-container {
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                z-index: 2000;
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }

            .toast {
                background: rgba(16, 185, 129, 0.95);
                color: #ffffff;
                padding: 1rem 1.5rem;
                border-radius: 10px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
                font-weight: 500;
                transform: translateY(100px);
                opacity: 0;
                animation: slideIn 0.3s forwards, fadeOut 0.3s 4s forwards;
            }

            @keyframes slideIn {
                to { transform: translateY(0); opacity: 1; }
            }

            @keyframes fadeOut {
                to { transform: translateY(-50px); opacity: 0; }
            }

            /* Empty Clear State with Pulse Animation */
            .empty-state {
                text-align: center;
                padding: 5rem 2rem;
                background: var(--glass-bg);
                border: 1px dashed var(--glass-border);
                border-radius: 16px;
                grid-column: 1 / -1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }

            .checkmark-icon {
                font-size: 3.5rem;
                color: var(--success);
                margin-bottom: 1rem;
                animation: pulse-green 2s infinite;
            }

            @keyframes pulse-green {
                0% {
                    transform: scale(0.95);
                    text-shadow: 0 0 0 rgba(16, 185, 129, 0.4);
                }
                70% {
                    transform: scale(1.05);
                    text-shadow: 0 0 15px rgba(16, 185, 129, 0.6);
                }
                100% {
                    transform: scale(0.95);
                    text-shadow: 0 0 0 rgba(16, 185, 129, 0);
                }
            }

            .empty-state h3 {
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                color: var(--text-primary);
            }

            .empty-state p {
                color: var(--text-secondary);
                font-size: 0.95rem;
            }

            /* Footer */
            footer {
                width: 100%;
                text-align: center;
                padding-top: 3rem;
                margin-top: 3rem;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                font-size: 0.85rem;
                color: var(--text-secondary);
                line-height: 1.6;
            }

            footer a {
                color: #818cf8;
                text-decoration: none;
                font-weight: 600;
                transition: color 0.2s;
            }

            footer a:hover {
                color: #a5b4fc;
            }
        </style>
    </head>
    <body>
        <header>
            <div>
                <h1>Code Review Crew</h1>
                <p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;">Ambient Pull Request Review Approvals Manager</p>
            </div>

            <div class="status-indicator">
                <div class="pulse-dot"></div>
                <span>Agent Runtime: Live</span>
            </div>

            <div class="badge" id="pending-count">0 pending reviews</div>
        </header>

        <div class="header-divider"></div>

        <main>
            <div class="grid" id="cards-grid">
                <!-- Cards will render here -->
            </div>
        </main>

        <!-- Technical Review Drawer -->
        <div class="modal-overlay" id="modal-overlay" onclick="closeModal()"></div>
        <div class="modal" id="modal">
            <div class="modal-header">
                <div class="modal-title" id="modal-pr-title">Technical Review Summary</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-content">
                <!-- Review content will render here -->
            </div>
            <div style="margin-top: 2rem; display: flex; gap: 1rem;">
                <button class="btn-approve" id="modal-approve-btn">Approve & Publish to GitHub</button>
            </div>
        </div>

        <div class="toast-container" id="toast-container"></div>

        <footer>
            <p>Built with Google ADK 2.0 &middot; Antigravity &middot; Agent Runtime</p>
            <p>Code Repository: <a href="https://github.com/chippymary/code-review-crew" target="_blank">chippymary/code-review-crew</a></p>
            <p style="margin-top: 0.25rem; font-size: 0.775rem; opacity: 0.8;">Kaggle 5-Day AI Agents Capstone 2026</p>
        </footer>

        <script>
            let currentSessionId = null;

            async function fetchPending() {
                try {
                    const response = await fetch('/api/pending');
                    const data = await response.json();
                    renderCards(data);
                } catch (error) {
                    console.error("Error fetching pending requests:", error);
                }
            }

            function getSeverityClass(severity) {
                if (severity === 'BLOCK') return 'severity-block';
                if (severity === 'APPROVE WITH CHANGES') return 'severity-changes';
                return 'severity-approve';
            }

            function toggleExpand(sessionId, event) {
                if (event) event.preventDefault();
                const contentDiv = document.getElementById(`expand-${sessionId}`);
                const link = document.getElementById(`link-${sessionId}`);
                if (contentDiv.classList.contains('active')) {
                    contentDiv.classList.remove('active');
                    link.innerText = "View Full Technical Review ▼";
                } else {
                    contentDiv.classList.add('active');
                    link.innerText = "Hide Technical Review ▲";
                }
            }

            function renderCards(sessions) {
                const grid = document.getElementById('cards-grid');
                const badge = document.getElementById('pending-count');
                badge.innerText = `${sessions.length} pending review${sessions.length !== 1 ? 's' : ''}`;

                if (sessions.length === 0) {
                    grid.innerHTML = `
                        <div class="empty-state">
                            <div class="checkmark-icon">✓</div>
                            <h3>All Clear</h3>
                            <p>No pull requests awaiting approval. The agent is actively monitoring.</p>
                        </div>
                    `;
                    return;
                }

                grid.innerHTML = sessions.map(session => `
                    <div class="card" id="card-${session.session_id}">
                        <div>
                            <div class="card-header">
                                <a href="${session.pr_url}" target="_blank" class="pr-link" title="${session.repo} — PR #${session.pr_number}">
                                    ${session.repo} — PR #${session.pr_number}
                                </a>
                                <span class="severity-badge ${getSeverityClass(session.severity)}">${session.severity}</span>
                            </div>
                            <div class="summary">
                                <strong>Executive Summary:</strong><br>
                                ${session.executive_summary}
                            </div>

                            <!-- Inline Expandable Review -->
                            <a class="expand-link" id="link-${session.session_id}" onclick="toggleExpand('${session.session_id}', event)">
                                View Full Technical Review ▼
                            </a>
                            <div class="expandable-content" id="expand-${session.session_id}">
                                ${parseMarkdown(session.technical_review)}
                            </div>
                        </div>

                        <div class="card-meta">
                            <span class="timestamp">Waiting since ${session.timestamp}</span>
                            <div class="actions">
                                <button class="btn-approve" onclick="openApproveModal('${session.session_id}', '${session.pr_number}', \`${encodeURIComponent(session.technical_review)}\`)">
                                    Approve
                                </button>
                                <button class="btn-reject" onclick="takeAction('${session.session_id}', 'REJECT', this)">
                                    Reject
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            function openApproveModal(sessionId, prNumber, encodedReview) {
                currentSessionId = sessionId;
                document.getElementById('modal-pr-title').innerText = `Technical Review for PR #${prNumber}`;

                const markdown = decodeURIComponent(encodedReview);
                document.getElementById('modal-content').innerHTML = parseMarkdown(markdown);

                const approveBtn = document.getElementById('modal-approve-btn');
                approveBtn.onclick = () => {
                    takeAction(sessionId, 'APPROVE', approveBtn);
                    closeModal();
                };

                document.getElementById('modal-overlay').classList.add('active');
                document.getElementById('modal').classList.add('active');
            }

            function closeModal() {
                document.getElementById('modal-overlay').classList.remove('active');
                document.getElementById('modal').classList.remove('active');
                currentSessionId = null;
            }

            async function takeAction(sessionId, decision, element) {
                const originalText = element.innerHTML;
                element.disabled = true;
                element.innerHTML = `<span class="spinner"></span>`;

                try {
                    const response = await fetch(`/api/action/${sessionId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ decision })
                    });

                    if (response.ok) {
                        showToast(`Review ${decision === 'APPROVE' ? 'Approved' : 'Rejected'} Successfully!`);
                        const card = document.getElementById(`card-${sessionId}`);
                        if (card) {
                            card.style.transform = "scale(0.9)";
                            card.style.opacity = "0";
                            setTimeout(() => {
                                fetchPending();
                            }, 300);
                        } else {
                            fetchPending();
                        }
                    } else {
                        showToast("Action failed. Please try again.", true);
                        element.disabled = false;
                        element.innerHTML = originalText;
                    }
                } catch (error) {
                    console.error("Error running decision action:", error);
                    showToast("Network error. Action aborted.", true);
                    element.disabled = false;
                    element.innerHTML = originalText;
                }
            }

            function showToast(message, isError = false) {
                const container = document.getElementById('toast-container');
                const toast = document.createElement('div');
                toast.className = 'toast';
                if (isError) {
                    toast.style.background = 'var(--danger)';
                }
                toast.innerText = message;
                container.appendChild(toast);
                setTimeout(() => toast.remove(), 4500);
            }

            function parseMarkdown(md) {
                return md
                    .replace(/### (.*)/g, '<h3>$1</h3>')
                    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                    .replace(/- (.*)/g, '<li>$1</li>')
                    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
                    .replace(/\n/g, '<br>');
            }

            // Initial Load
            fetchPending();

            // Poll for changes every 5 seconds
            setInterval(fetchPending, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
