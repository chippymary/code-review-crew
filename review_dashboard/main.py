import os
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google.adk.sessions import VertexAiSessionService, Session
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

app = FastAPI(title="Code Review Crew — Manager Dashboard")

# Read environment variables
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0223097535")
AGENT_RUNTIME_ID = os.getenv("AGENT_RUNTIME_ID", "code-review-agent")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Mock database to allow local testing and fallbacks
MOCK_SESSIONS = [
    {
        "session_id": "mock-session-1",
        "pr_url": "https://github.com/google/adk/pull/12",
        "pr_number": 12,
        "technical_review": "### STRIDE Security Findings\n\n- **[HIGH] Tampering** in `usb_handler.cc:42-58`:\n  *Threat:* Potential buffer overflow in USB connection packet parsing.\n  *Remediation:* Enforce strict size verification on the payload header length.\n\n- **[MEDIUM] Information Disclosure** in `adk_config.json:14`:\n  *Threat:* Hardcoded default pre-shared key (PSK) found in configuration template.\n  *Remediation:* Load configurations from environmental variables dynamically.",
        "executive_summary": "This pull request refactors the JNI state lifecycle listener bindings and improves hardware connection recovery timeouts for Android 13+ devices.",
    },
    {
        "session_id": "mock-session-2",
        "pr_url": "https://github.com/google/adk/pull/15",
        "pr_number": 15,
        "technical_review": "### STRIDE Security Findings\n\nNo security vulnerabilities or leaks identified in this change. Code complies with CONTEXT.md guidelines.",
        "executive_summary": "Integrates Firebase authentication flow, adds OAuth2 configuration endpoints, and migrates session storage to Redis.",
    },
]


class ActionRequest(BaseModel):
    decision: str  # "APPROVE" or "REJECT"


# Session Service initialization
session_service = None
try:
    if GOOGLE_CLOUD_PROJECT and AGENT_RUNTIME_ID:
        session_service = VertexAiSessionService(
            project=GOOGLE_CLOUD_PROJECT, location=LOCATION, app_name=AGENT_RUNTIME_ID
        )
        logger.info(
            f"Initialized VertexAiSessionService for project={GOOGLE_CLOUD_PROJECT}, app={AGENT_RUNTIME_ID}"
        )
except Exception as e:
    logger.warning(
        f"Could not initialize VertexAiSessionService: {e}. Falling back to mock sessions."
    )


@app.get("/api/pending")
async def get_pending_sessions():
    pending = []

    # Try querying Vertex AI Session Service if initialized
    if session_service:
        try:
            # list_sessions returns a ListSessionsResponse containing list of Session objects
            response = session_service.list_sessions(app_name=AGENT_RUNTIME_ID)
            sessions: List[Session] = getattr(response, "sessions", [])
            for s in sessions:
                # Check if session has unresolved adk_request_input/interrupted state
                is_pending = False
                if s.events:
                    latest_event: Event = s.events[-1]
                    if getattr(latest_event, "interrupted", False):
                        is_pending = True

                if is_pending:
                    state = s.state or {}
                    # Extract variables from workflow state
                    pr_summary = state.get("pr_summary", {})
                    tech_review = state.get("technical_review", "")

                    pending.append(
                        {
                            "session_id": s.id,
                            "pr_url": f"https://github.com/{state.get('repo', 'unknown')}/pull/{state.get('pr_number', 0)}",
                            "pr_number": state.get("pr_number", 0),
                            "technical_review": tech_review
                            or "No technical review available.",
                            "executive_summary": pr_summary.get(
                                "purpose", "No summary available."
                            ),
                        }
                    )
        except Exception as e:
            logger.warning(
                f"Error querying Vertex AI Session Service: {e}. Using mock fallback."
            )

    # If no real sessions found, fallback to mock list for demo / offline playground testing
    if not pending:
        pending = MOCK_SESSIONS

    return pending


@app.post("/api/action/{session_id}")
async def handle_action(session_id: str, payload: ActionRequest):
    logger.info(f"Received decision '{payload.decision}' for session '{session_id}'")

    # If it's a mock session, remove it from the mock database list and return
    global MOCK_SESSIONS
    mock_found = False
    for i, s in enumerate(MOCK_SESSIONS):
        if s["session_id"] == session_id:
            MOCK_SESSIONS.pop(i)
            mock_found = True
            break

    if mock_found:
        return {
            "status": "success",
            "message": f"Mock session {session_id} updated with {payload.decision}.",
        }

    # If it is a real session, resume it using the ADK agent engine interface
    if session_service:
        try:
            # Map frontend APPROVE/REJECT to the exact match string expected by request_approval node
            decision_text = "Yes" if payload.decision.upper() == "APPROVE" else "No"

            # Since the service is deployed to reasoning engines, we resume using the Vertex AI client or Runner:
            # For this exercise, we simulation-resume by appending the user message event
            session = session_service.get_session(session_id=session_id)
            user_event = Event(
                content=types.Content(
                    role="user", parts=[types.Part.from_text(text=decision_text)]
                )
            )
            session_service.append_event(session=session, event=user_event)
            session_service.flush()
            return {
                "status": "success",
                "message": f"Session {session_id} resumed with '{decision_text}'",
            }
        except Exception as e:
            logger.error(f"Failed to resume session {session_id} via API: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to resume session: {e}"
            )

    raise HTTPException(
        status_code=404, detail="Session not found or service unavailable."
    )


@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = """
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
                overflow-x: hidden;
                padding: 2.5rem 1.5rem;
            }

            header {
                max-width: 1200px;
                margin: 0 auto 3rem auto;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            h1 {
                font-size: 2rem;
                font-weight: 700;
                letter-spacing: -0.025em;
                background: linear-gradient(to right, #818cf8, #c084fc);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
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
                margin-bottom: 1rem;
            }

            .pr-link {
                color: #818cf8;
                text-decoration: none;
                font-weight: 600;
                font-size: 1.1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
                transition: color 0.2s;
            }

            .pr-link:hover {
                color: #a5b4fc;
            }

            .pr-num {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid var(--glass-border);
                padding: 0.25rem 0.6rem;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 600;
                color: var(--text-secondary);
            }

            .summary {
                font-size: 0.95rem;
                color: var(--text-secondary);
                line-height: 1.6;
                margin-bottom: 1.75rem;
                flex-grow: 1;
            }

            .actions {
                display: flex;
                gap: 1rem;
            }

            button {
                flex: 1;
                padding: 0.8rem;
                border: none;
                border-radius: 10px;
                font-weight: 600;
                font-size: 0.95rem;
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

            /* Loader Spinner */
            .spinner {
                width: 16px;
                height: 16px;
                border: 2px solid currentColor;
                border-bottom-color: transparent;
                border-radius: 50%;
                display: inline-block;
                box-sizing: border-box;
                animation: rotation 1s linear infinite;
            }

            @keyframes rotation {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* Side Sheet Panel Modal */
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

            .modal-body h3 {
                color: var(--text-primary);
                margin: 1.5rem 0 0.8rem 0;
                font-size: 1.15rem;
            }

            .modal-body ul {
                padding-left: 1.25rem;
                margin-bottom: 1.5rem;
            }

            .modal-body li {
                margin-bottom: 0.5rem;
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

            .empty-state {
                text-align: center;
                padding: 5rem 2rem;
                background: var(--glass-bg);
                border: 1px dashed var(--glass-border);
                border-radius: 16px;
                grid-column: 1 / -1;
            }

            .empty-state p {
                color: var(--text-secondary);
                font-size: 1.1rem;
            }
        </style>
    </head>
    <body>
        <header>
            <div>
                <h1>Code Review Crew</h1>
                <p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;">Ambient Pull Request Review Approvals Manager</p>
            </div>
            <div class="badge" id="pending-count">0 pending reviews</div>
        </header>

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

            function renderCards(sessions) {
                const grid = document.getElementById('cards-grid');
                const badge = document.getElementById('pending-count');
                badge.innerText = `${sessions.length} pending review${sessions.length !== 1 ? 's' : ''}`;

                if (sessions.length === 0) {
                    grid.innerHTML = `
                        <div class="empty-state">
                            <p>All reviews are up to date! Waiting for new Pull Requests...</p>
                        </div>
                    `;
                    return;
                }

                grid.innerHTML = sessions.map(session => `
                    <div class="card" id="card-${session.session_id}">
                        <div>
                            <div class="card-header">
                                <a href="${session.pr_url}" target="_blank" class="pr-link">
                                    PR: #${session.pr_number} ↗
                                </a>
                                <span class="pr-num">ID: ${session.session_id.substring(0, 8)}</span>
                            </div>
                            <div class="summary">
                                <strong>Executive Summary:</strong><br>
                                ${session.executive_summary}
                            </div>
                        </div>
                        <div class="actions">
                            <button class="btn-approve" onclick="openApproveModal('${session.session_id}', '${session.pr_number}', \`${encodeURIComponent(session.technical_review)}\`)">
                                Approve
                            </button>
                            <button class="btn-reject" onclick="takeAction('${session.session_id}', 'REJECT', this)">
                                Reject
                            </button>
                        </div>
                    </div>
                `).join('');
            }

            function openApproveModal(sessionId, prNumber, encodedReview) {
                currentSessionId = sessionId;
                document.getElementById('modal-pr-title').innerText = `Technical Review for PR #${prNumber}`;

                // Decode and render simple markdown (paragraphs/headers/lists)
                const markdown = decodeURIComponent(encodedReview);
                document.getElementById('modal-content').innerHTML = parseMarkdown(markdown);

                // Attach submit handler to action button
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
                element.innerHTML = `<span class="spinner"></span> Processing...`;

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
