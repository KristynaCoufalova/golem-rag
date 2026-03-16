"""
HTML templates for the FemCAD Assistant Web UI.
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FemCAD Assistant</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --bg: #edf0ff;
      --card: #ffffff;
      --border: #dfe4ff;
      --ink: #0f172a;
      --muted: #5f6fb5;
      --accent: #6c63ff;
      --accent-strong: #4f46e5;
      --surface: rgba(255, 255, 255, 0.7);
      --success: #10b981;
      --warning: #f59e0b;
      --error: #ef4444;
      --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.04);
      --shadow-md: 0 8px 24px rgba(15, 23, 42, 0.08);
      --shadow-lg: 0 20px 50px rgba(15, 23, 42, 0.12);
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      padding: 2rem;
      background: radial-gradient(circle at top, rgba(111, 84, 255, 0.25), transparent 55%),
                  radial-gradient(circle at 20% 20%, rgba(255, 255, 255, 0.65), transparent 45%),
                  linear-gradient(120deg, #e6e9ff 0%, #f8f9ff 35%, #fefefe 100%);
      color: var(--ink);
      animation: fadeIn 0.5s ease-in;
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .shell {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .hero {
      display: flex;
      justify-content: space-between;
      gap: 2rem;
      padding: 2.5rem;
      border-radius: 24px;
      background: var(--surface);
      backdrop-filter: blur(22px);
      border: 1px solid rgba(255, 255, 255, 0.6);
      box-shadow: var(--shadow-lg);
      animation: slideUp 0.6s ease-out;
    }
    .hero h1 {
      margin: 0.2rem 0 0.6rem;
      font-size: clamp(2rem, 4vw, 2.7rem);
      color: #100d3e;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .eyebrow {
      letter-spacing: 0.2em;
      text-transform: uppercase;
      font-size: 0.75rem;
      color: var(--muted);
      margin: 0;
      font-weight: 600;
    }
    .tagline {
      margin: 0;
      color: #5a5f7a;
      max-width: 32rem;
      line-height: 1.6;
      font-size: 1.05rem;
    }
    .status-cluster {
      min-width: 220px;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      align-items: flex-start;
    }
    .status-cluster button {
      border-radius: 12px;
      padding: 0.5rem 1rem;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      border: 1px solid #e5e7eb;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    .status-cluster button:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .status-pill {
      padding: 0.4rem 1rem;
      border-radius: 999px;
      font-weight: 600;
      font-size: 0.9rem;
      color: #fff;
      background: var(--muted);
      transition: all 0.3s ease;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .status-pill[data-tone="ready"] {
      background: linear-gradient(120deg, #34d399, #059669);
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    .status-pill[data-tone="warning"] {
      background: linear-gradient(120deg, #fbbf24, #f59e0b);
      box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
    }
    .status-pill[data-tone="error"] {
      background: linear-gradient(120deg, #f87171, #ef4444);
      box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
    }
    .status-pill[data-tone="thinking"] {
      background: linear-gradient(120deg, #8b5cf6, #6d28d9);
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
      animation: pulse 2s ease-in-out infinite;
    }
    .status-pill[data-tone="thinking"]::before {
      content: "";
      width: 12px;
      height: 12px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    #status-text {
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.4;
      transition: color 0.3s ease;
    }
    .panel {
      background: var(--card);
      border-radius: 22px;
      padding: 1.75rem;
      border: 1px solid var(--border);
      box-shadow: var(--shadow-md);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      animation: slideUp 0.5s ease-out backwards;
    }
    .panel:nth-child(2) { animation-delay: 0.1s; }
    .panel:nth-child(3) { animation-delay: 0.2s; }
    .panel:hover {
      box-shadow: var(--shadow-lg);
    }
    .query-panel {
      position: relative;
    }
    .query-panel textarea {
      width: 100%;
      resize: vertical;
      min-height: 140px;
      max-height: 300px;
      padding: 1.25rem;
      border-radius: 18px;
      border: 2px solid var(--border);
      font: inherit;
      line-height: 1.6;
      background: #f7f8ff;
      color: var(--ink);
      transition: all 0.3s ease;
      font-size: 1rem;
    }
    .query-panel textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 4px rgba(108, 99, 255, 0.1), 0 12px 36px rgba(108, 99, 255, 0.15);
      background: #fff;
    }
    .query-panel textarea::placeholder {
      color: #9ca3b8;
    }
    label {
      font-weight: 600;
      color: #252b57;
      margin-bottom: 0.6rem;
      display: block;
      font-size: 1.05rem;
    }
    .actions {
      margin-top: 1rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }
    small {
      color: #7b82a8;
      font-size: 0.875rem;
    }
    button {
      border: none;
      border-radius: 16px;
      padding: 0.95rem 2.4rem;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      background: linear-gradient(120deg, var(--accent), var(--accent-strong));
      color: #fff;
      box-shadow: 0 8px 24px rgba(83, 75, 200, 0.35);
      transition: all 0.2s ease;
      position: relative;
      overflow: hidden;
    }
    button::before {
      content: "";
      position: absolute;
      top: 50%;
      left: 50%;
      width: 0;
      height: 0;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.3);
      transform: translate(-50%, -50%);
      transition: width 0.6s, height 0.6s;
    }
    button:active::before {
      width: 300px;
      height: 300px;
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      box-shadow: none;
      transform: none;
    }
    button:not(:disabled):hover {
      transform: translateY(-2px) scale(1.02);
      box-shadow: 0 12px 32px rgba(83, 75, 200, 0.4);
    }
    button:not(:disabled):active {
      transform: translateY(0) scale(0.98);
    }
    #reset-btn {
      background: linear-gradient(120deg, #e5e7eb, #d1d5db);
      color: #111827;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    #reset-btn:hover {
      background: linear-gradient(120deg, #d1d5db, #9ca3af);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
    }
    .button-loading {
      position: relative;
      color: transparent !important;
    }
    .button-loading::after {
      content: "";
      position: absolute;
      top: 50%;
      left: 50%;
      width: 20px;
      height: 20px;
      margin: -10px 0 0 -10px;
      border: 3px solid rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.5rem;
      animation: slideUp 0.6s ease-out;
    }
    .answer-panel {
      grid-column: 1 / -1;
    }
    .context-panel {
      grid-column: 1 / -1;
    }
    .panel-heading {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
      margin-bottom: 1.25rem;
    }
    .panel-heading h2,
    .panel-heading h3 {
      margin: 0;
      color: #101344;
      font-weight: 700;
    }
    .panel-heading h2 {
      font-size: 1.5rem;
    }
    .panel-heading h3 {
      font-size: 1.25rem;
    }
    #answer {
      margin: 0;
      line-height: 1.8;
      font-size: 1.05rem;
      color: #14172f;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    #answer code {
      background: #f1f5f9;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      font-size: 0.9em;
      color: #4338ca;
      font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
    }
    #answer pre {
      background: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 8px;
      padding: 1rem;
      margin: 1rem 0;
      overflow-x: auto;
      font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
      font-size: 0.9em;
      line-height: 1.6;
    }
    #answer pre code.code-block {
      background: transparent;
      padding: 0;
      border-radius: 0;
      color: #212529;
      font-size: inherit;
      display: block;
      white-space: pre;
      word-wrap: normal;
    }
    .code-block-wrapper {
      position: relative;
      margin: 1rem 0;
    }
    .code-block-wrapper pre {
      margin: 0;
      position: relative;
    }
    .code-copy-btn {
      position: absolute;
      top: 0.75rem;
      right: 0.75rem;
      padding: 0.4rem 0.8rem;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid rgba(0, 0, 0, 0.1);
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #374151;
      cursor: pointer;
      transition: all 0.2s ease;
      z-index: 10;
      opacity: 0;
      backdrop-filter: blur(8px);
    }
    .code-block-wrapper:hover .code-copy-btn {
      opacity: 1;
    }
    .code-copy-btn:hover {
      background: rgba(255, 255, 255, 1);
      border-color: rgba(0, 0, 0, 0.2);
      transform: translateY(-1px);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    .code-copy-btn:active {
      transform: translateY(0);
    }
    .code-copy-btn.copied {
      background: rgba(16, 185, 129, 0.9);
      color: white;
      border-color: rgba(16, 185, 129, 1);
    }
    .code-copy-btn.copied::after {
      content: " ✓";
    }
    .chat-bubble.user .code-block-wrapper pre {
      background: rgba(0, 0, 0, 0.2);
    }
    .chat-bubble.user .code-copy-btn {
      background: rgba(255, 255, 255, 0.15);
      color: rgba(255, 255, 255, 0.9);
      border-color: rgba(255, 255, 255, 0.2);
    }
    .chat-bubble.user .code-copy-btn:hover {
      background: rgba(255, 255, 255, 0.25);
      border-color: rgba(255, 255, 255, 0.3);
    }
    .chat-bubble.user .code-copy-btn.copied {
      background: rgba(16, 185, 129, 0.8);
      color: white;
      border-color: rgba(16, 185, 129, 1);
    }
    #answer .code-block-wrapper {
      margin: 1rem 0;
    }
    #answer .code-copy-btn {
      opacity: 0.7;
    }
    #answer .code-block-wrapper:hover .code-copy-btn {
      opacity: 1;
    }
    #latency {
      font-size: 0.9rem;
      color: #6972a4;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .mode-badge {
      padding: 0.3rem 0.85rem;
      border-radius: 999px;
      background: rgba(108, 99, 255, 0.12);
      color: var(--accent-strong);
      font-size: 0.85rem;
      font-weight: 600;
      display: inline-block;
      margin-left: 0.75rem;
      transition: all 0.2s ease;
    }
    .mode-badge[data-mode="fallback"] {
      background: rgba(248, 191, 64, 0.18);
      color: #b45309;
    }
    .context-panel {
      position: relative;
    }
    .context-panel pre {
      background: #0f172a;
      color: #e0e7ff;
      margin: 0;
      border-radius: 18px;
      padding: 1.5rem;
      max-height: 500px;
      overflow: auto;
      font-size: 0.9rem;
      line-height: 1.7;
      font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
      scrollbar-width: thin;
      scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
    }
    .context-panel pre::-webkit-scrollbar {
      width: 8px;
    }
    .context-panel pre::-webkit-scrollbar-track {
      background: transparent;
    }
    .context-panel pre::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.2);
      border-radius: 4px;
    }
    .context-panel pre::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.3);
    }
    .copy-btn {
      position: absolute;
      top: 1.75rem;
      right: 1.75rem;
      padding: 0.5rem 1rem;
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 8px;
      color: #e0e7ff;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.2s ease;
      backdrop-filter: blur(10px);
    }
    .copy-btn:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }
    .copy-btn.copied {
      background: rgba(16, 185, 129, 0.3);
      border-color: rgba(16, 185, 129, 0.5);
    }
    .sources {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .source-card {
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.25rem;
      background: linear-gradient(135deg, #f8f9ff 0%, #ffffff 100%);
      transition: all 0.3s ease;
      cursor: pointer;
    }
    .source-card:hover {
      border-color: var(--accent);
      transform: translateY(-3px);
      box-shadow: 0 8px 20px rgba(108, 99, 255, 0.15);
    }
    .source-card h3 {
      margin: 0 0 0.5rem;
      font-size: 1.05rem;
      color: #272a6c;
      font-weight: 600;
    }
    .source-card h3 small {
      font-size: 0.75rem;
      color: var(--muted);
      font-weight: 500;
      margin-left: 0.5rem;
    }
    .source-card code {
      background: #e8ecff;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      font-size: 0.85rem;
      color: #4338ca;
      font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
      display: inline-block;
      margin: 0.5rem 0;
    }
    .source-card p {
      margin: 0.5rem 0 0;
      color: #4c5270;
      line-height: 1.6;
      font-size: 0.95rem;
    }
    #chat-panel {
      max-height: 500px;
      overflow-y: auto;
      scrollbar-width: thin;
      scrollbar-color: var(--border) transparent;
    }
    #chat-panel::-webkit-scrollbar {
      width: 8px;
    }
    #chat-panel::-webkit-scrollbar-track {
      background: transparent;
    }
    #chat-panel::-webkit-scrollbar-thumb {
      background: var(--border);
      border-radius: 4px;
    }
    #chat-panel::-webkit-scrollbar-thumb:hover {
      background: var(--muted);
    }
    #chat-messages {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .chat-bubble {
      max-width: 75%;
      padding: 1rem 1.25rem;
      border-radius: 18px;
      font-size: 0.95rem;
      line-height: 1.6;
      box-shadow: var(--shadow-sm);
      animation: slideUp 0.3s ease-out;
      word-wrap: break-word;
    }
    .chat-bubble.user {
      margin-left: auto;
      background: linear-gradient(135deg, #4f46e5, #6366f1);
      color: #fff;
      border-bottom-right-radius: 6px;
    }
    .chat-bubble.assistant {
      margin-right: auto;
      background: linear-gradient(135deg, #f4f5ff, #ffffff);
      color: #111827;
      border-bottom-left-radius: 6px;
      border: 1px solid var(--border);
    }
    .chat-bubble code {
      background: #e8ecff;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      font-size: 0.85em;
      color: #4338ca;
      font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
    }
    .chat-bubble pre {
      background: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 6px;
      padding: 0.75rem;
      margin: 0.5rem 0;
      overflow-x: auto;
      font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
      font-size: 0.85em;
      line-height: 1.5;
    }
    .chat-bubble pre code.code-block {
      background: transparent;
      padding: 0;
      border-radius: 0;
      color: #212529;
      font-size: inherit;
      display: block;
      white-space: pre;
      word-wrap: normal;
    }
    .chat-meta {
      font-size: 0.75rem;
      opacity: 0.8;
      margin-bottom: 0.5rem;
      font-weight: 600;
    }
    .chat-time {
      font-size: 0.7rem;
      opacity: 0.6;
      margin-top: 0.25rem;
    }
    .empty-state {
      text-align: center;
      padding: 3rem 2rem;
      color: var(--muted);
    }
    .empty-state svg {
      width: 64px;
      height: 64px;
      margin: 0 auto 1rem;
      opacity: 0.5;
    }
    @media (max-width: 900px) {
      body {
        padding: 1.25rem;
      }
      .hero {
        flex-direction: column;
        padding: 2rem;
      }
      .answer-panel {
        grid-column: span 1;
      }
      .panel {
        padding: 1.5rem;
      }
      .chat-bubble {
        max-width: 85%;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div>
        <h1>Golem</h1>
        <p class="tagline">Ask about FemCAD code, syntax, or documentation.</p>
      </div>
      <div class="status-cluster">
        <div class="status-pill" id="status-pill" data-tone="info">Checking</div>
        <p id="status-text">Checking backend health…</p>
        <button type="button" id="reset-btn" style="margin-top: 0.5rem; background: #f3f4f6; color: #6b7280;">New chat</button>
      </div>
    </header>

    <section class="panel query-panel">
      <label for="question">What should Golem explain?</label>
      <textarea id="question" placeholder="Describe the workflow, command, or design challenge you want to explore."></textarea>
      <div class="actions">
        <small>Press <kbd>Enter</kbd> to submit, <kbd>Shift + Enter</kbd> for new line</small>
        <button type="button" id="submit-btn">Ask Golem</button>
      </div>
    </section>

    <!-- Chat history panel -->
    <section id="chat-panel" class="panel" style="display:none;">
      <div class="panel-heading">
        <h2 style="margin:0;">Conversation</h2>
        <button type="button" id="clear-chat-btn" style="padding: 0.5rem 1rem; font-size: 0.875rem; background: #f3f4f6; color: #6b7280; box-shadow: none;">Clear</button>
      </div>
      <div id="chat-messages"></div>
    </section>

    <section id="results" class="results-grid" style="display:none;">
      <div class="panel answer-panel">
        <div class="panel-heading">
          <div>
            <h2>Answer</h2>
            <span class="mode-badge" id="mode-pill" data-mode="enhanced">Enhanced</span>
          </div>
          <div style="display: flex; align-items: center; gap: 1rem;">
            <span id="latency">Latency: —</span>
            <button type="button" id="copy-answer-btn" class="copy-btn" style="position: static; padding: 0.5rem 1rem; font-size: 0.875rem; background: #f3f4f6; color: #6b7280; border: 1px solid #e5e7eb; box-shadow: none;">Copy</button>
          </div>
        </div>
        <div id="answer"></div>
      </div>

      <div class="panel context-panel">
        <div class="panel-heading">
          <h3>Full Context</h3>
          <button type="button" id="copy-context-btn" class="copy-btn">Copy</button>
        </div>
        <pre id="context"></pre>
      </div>

      <div class="panel sources-panel">
        <div class="panel-heading">
          <h3>Sources</h3>
          <p style="margin:0;color:#7d84b1;font-size:0.9rem;">Document and code snippets that backed the answer.</p>
        </div>
        <div class="sources" id="sources"></div>
      </div>
    </section>
  </div>

  <script>
    const questionInput = document.getElementById("question");
    const submitBtn = document.getElementById("submit-btn");
    const resetBtn = document.getElementById("reset-btn");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const results = document.getElementById("results");
    const answerEl = document.getElementById("answer");
    const contextEl = document.getElementById("context");
    const sourcesEl = document.getElementById("sources");
    const latencyEl = document.getElementById("latency");
    const modePill = document.getElementById("mode-pill");
    const statusText = document.getElementById("status-text");
    const statusPill = document.getElementById("status-pill");
    const chatPanel = document.getElementById("chat-panel");
    const chatMessagesEl = document.getElementById("chat-messages");
    const copyAnswerBtn = document.getElementById("copy-answer-btn");
    const copyContextBtn = document.getElementById("copy-context-btn");
    let backendMode = "unknown";
    
    // Conversation memory: get or create session ID
    let sessionId = localStorage.getItem("femcad_session_id");
    if (!sessionId) {
      sessionId = null; // Will be created by backend
    }

    // In-memory chat for the UI (backend memory is separate)
    let chatMessages = [];

    // Auto-resize textarea
    questionInput.addEventListener("input", function() {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 300) + "px";
    });

    function setStatus(message, tone = "info") {
      statusText.textContent = message;
      statusPill.dataset.tone = tone;
      statusPill.textContent =
        tone === "ready"
          ? "Ready"
          : tone === "warning"
          ? "Heads up"
          : tone === "error"
          ? "Needs attention"
          : tone === "thinking"
          ? "Working…"
          : "Status";
    }

    function formatTime(date) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function renderChat() {
      if (chatMessages.length === 0) {
        chatPanel.style.display = "none";
        return;
      }
      chatPanel.style.display = "block";
      chatMessagesEl.innerHTML = "";

      chatMessages.forEach((msg, index) => {
        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${msg.role}`;
        bubble.style.animationDelay = `${index * 0.1}s`;

        const meta = document.createElement("div");
        meta.className = "chat-meta";
        meta.textContent = msg.role === "user" ? "You" : "Golem";

        const text = document.createElement("div");
        text.innerHTML = formatAnswerWithCode(msg.content);

        const time = document.createElement("div");
        time.className = "chat-time";
        time.textContent = formatTime(new Date(msg.timestamp || Date.now()));

        bubble.appendChild(meta);
        bubble.appendChild(text);
        bubble.appendChild(time);
        chatMessagesEl.appendChild(bubble);
      });

      // Scroll to bottom on every update
      setTimeout(() => {
        chatPanel.scrollTop = chatPanel.scrollHeight;
        setupCodeCopyButtons(); // Setup copy buttons for chat messages
      }, 100);
    }

    function formatAnswerWithCode(text) {
      if (!text) return '';
      
      // Escape HTML to prevent XSS
      function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
      }
      
      // Normalize newlines - handle both \n and \\n (from JSON strings)
      // Also handle \r\n (Windows) and \r (old Mac)
      const newlineChar = String.fromCharCode(10);
      const crChar = String.fromCharCode(13);
      let normalized = text;
      // First replace escaped newlines (from JSON strings)
      normalized = normalized.replace(/\\\\n/g, newlineChar);
      normalized = normalized.replace(/\\\\r\\\\n/g, newlineChar);
      normalized = normalized.replace(/\\\\r/g, newlineChar);
      // Then normalize any remaining \r\n or \r
      normalized = normalized.replace(new RegExp(crChar + newlineChar, "g"), newlineChar);
      normalized = normalized.replace(new RegExp(crChar, "g"), newlineChar);
      
      // First, handle markdown-style code blocks (```...```)
      let formatted = normalized;
      const codeBlockPlaceholders = [];
      let placeholderIndex = 0;
      
      // Use String.fromCharCode to avoid issues with backticks in Python string
      const backtick = String.fromCharCode(96);
      const codeBlockStart = backtick + backtick + backtick;
      
      let searchIndex = 0;
      while (true) {
        const startIdx = formatted.indexOf(codeBlockStart, searchIndex);
        if (startIdx === -1) break;
        
        const endIdx = formatted.indexOf(codeBlockStart, startIdx + 3);
        if (endIdx === -1) break;
        
        const match = formatted.substring(startIdx, endIdx + 3);
        const matchContent = match.slice(3, -3);
        const firstNewline = matchContent.indexOf(newlineChar);
        const lang = firstNewline > 0 ? matchContent.slice(0, firstNewline).trim() : "";
        const code = firstNewline > 0 ? matchContent.slice(firstNewline + 1) : matchContent;
        const trimmedCode = code.trim();
        const escapedCode = escapeHtml(trimmedCode);
        const placeholder = "__CODE_BLOCK_" + placeholderIndex + "__";
        // Encode code for data attribute using base64
        const encodedCode = btoa(unescape(encodeURIComponent(trimmedCode)));
        const codeId = "code-block-" + placeholderIndex + "-" + Date.now();
        codeBlockPlaceholders.push("<div class=\"code-block-wrapper\"><button class=\"code-copy-btn\" data-code-id=\"" + codeId + "\" data-code-encoded=\"" + encodedCode + "\" aria-label=\"Copy code\">Copy code</button><pre><code class=\"code-block\">" + escapedCode + "</code></pre></div>");
        
        formatted = formatted.substring(0, startIdx) + placeholder + formatted.substring(endIdx + 3);
        placeholderIndex++;
        searchIndex = startIdx + placeholder.length;
      }
      
      // Split into lines for processing
      const lines = formatted.split(newlineChar);
      const result = [];
      let inCodeBlock = false;
      let codeBlockLines = [];
      let consecutiveCodeLines = 0;
      let consecutiveTextLines = 0;
      
      function isCodeLine(line, prevWasCode = false) {
        const trimmed = line.trim();
        if (!trimmed) {
          // Empty lines: if we're in a code block, continue it
          return prevWasCode;
        }
        
        // Skip if it's a placeholder
        if (trimmed.includes('__CODE_BLOCK_')) return false;
        
        // Strong code indicators (always code):
        // 1. Variable assignment: x := value, x = value (FemCAD uses :=)
        if (/^[a-zA-Z_$][a-zA-Z0-9_$]*\s*[:=]=\s*/.test(trimmed)) return true;
        
        // 2. File header: File: something.fcs or File: something.fcc
        if (/^File:\s*[\w\.]+(fcs|fcc)?/i.test(trimmed)) return true;
        
        // 3. FemCAD-specific patterns:
        //    - res := Resources{}
        //    - css := res.cssLib.
        //    - cross_section {cs1} geometry_class
        if (/^\w+\s*[:=]=\s*\w+\./.test(trimmed)) return true;
        if (/\{\s*\w+\s*\}\s*\w+/.test(trimmed)) return true;
        if (/\.\w+\s*\(/.test(trimmed)) return true;
        
        // 4. Function/method calls: func( or method.
        if (/^[a-zA-Z_$][a-zA-Z0-9_$]*\s*[\.\(]/.test(trimmed)) return true;
        
        // 5. Arrow functions: => or ⇒
        if (trimmed.includes('=>') || trimmed.includes('⇒')) return true;
        
        // 6. Method chaining: .Select(, .Where(, etc.
        if (/^\s*\.\s*[A-Z][a-zA-Z]*\s*\(/.test(trimmed)) return true;
        
        // 7. Comments - if we're already in a code block, treat as code
        //    Also treat standalone comments as code if they look like code file comments
        if (trimmed.startsWith('#')) {
          if (prevWasCode || inCodeBlock) return true;
          // Standalone comments that look like code file headers/sections
          if (/^#\s*(Parameters|Cross-section|Geometry|Class|Function|a simple|built as)/i.test(trimmed)) return true;
          // Comments followed by code-like content on same line
          if (/^#.*[:=]/.test(trimmed)) return true;
        }
        
        // 8. Indented lines (continuation of code blocks)
        if (line.startsWith('  ') || line.startsWith('\t')) return true;
        
        // 9. Code-like patterns: curly braces, semicolons, etc.
        if (/[{};]/.test(trimmed) && prevWasCode) return true;
        
        // 10. Section headers that are part of code files
        if (/^#\s*(Parameters|Cross-section|Geometry|Class|Function)/i.test(trimmed) && prevWasCode) return true;
        
        // 11. FemCAD unit syntax: * Unit.m, * Unit.cm, etc.
        if (/\*\s*Unit\.(m|cm|mm|kg|N)/i.test(trimmed)) return true;
        
        // 12. If previous line was code and this looks code-like (continuation)
        if (prevWasCode && (
          /^[a-zA-Z_$]/.test(trimmed) || 
          trimmed.startsWith('.') || 
          trimmed.startsWith('{') ||
          trimmed.startsWith('}')
        )) return true;
        
        return false;
      }
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        const prevWasCode = i > 0 && (inCodeBlock || isCodeLine(lines[i-1], false));
        
        // Handle placeholders
        if (trimmed.includes('__CODE_BLOCK_')) {
          // End any current code block first
          if (inCodeBlock && codeBlockLines.length > 0) {
            const codeContent = codeBlockLines.map(l => escapeHtml(l)).join(newlineChar);
            result.push('<pre><code class="code-block">' + codeContent + '</code></pre>');
            inCodeBlock = false;
            codeBlockLines = [];
            consecutiveCodeLines = 0;
          }
          // Insert placeholder (will be replaced later)
          const placeholderMatch = trimmed.match(/__CODE_BLOCK_(\d+)__/);
          if (placeholderMatch) {
            const idx = parseInt(placeholderMatch[1]);
            result.push(codeBlockPlaceholders[idx]);
          }
          consecutiveTextLines = 0;
          continue;
        }
        
        const isCode = isCodeLine(line, prevWasCode);
        
        if (isCode) {
          consecutiveCodeLines++;
          consecutiveTextLines = 0;
          if (!inCodeBlock) {
            // Start new code block if:
            // 1. We have 2+ consecutive code lines, OR
            // 2. It's a strong indicator (file header, assignment, etc.), OR
            // 3. It's a comment that looks like a code file header
            const isStrongIndicator = /^File:|^[a-zA-Z_$][a-zA-Z0-9_$]*\s*[:=]=\s*/.test(trimmed);
            const isCodeFileComment = /^#\s*(a simple|built as|Parameters|Cross-section|File:)/i.test(trimmed);
            
            if (consecutiveCodeLines >= 2 || isStrongIndicator || isCodeFileComment) {
              inCodeBlock = true;
              codeBlockLines = [line];
            } else {
              // Single code line - treat as inline code later
              result.push(escapeHtml(line));
            }
          } else {
            // Continue code block
            codeBlockLines.push(line);
          }
        } else {
          consecutiveTextLines++;
          consecutiveCodeLines = 0;
          if (inCodeBlock) {
            // End code block if we have 2+ consecutive text lines
            // OR if the text line looks like a paragraph (not just a blank line or short separator)
            const isParagraph = trimmed && trimmed.length > 60 && !trimmed.match(/^[#\-*=]/);
            const isSeparator = /^[-=]{3,}$/.test(trimmed);
            
            if (consecutiveTextLines >= 2 || isParagraph) {
              if (codeBlockLines.length > 0) {
                const codeContent = codeBlockLines.map(l => escapeHtml(l)).join(newlineChar);
                const rawCode = codeBlockLines.join(newlineChar);
                const encodedCode = btoa(unescape(encodeURIComponent(rawCode)));
                const codeId = "code-block-pattern-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
                result.push('<div class="code-block-wrapper"><button class="code-copy-btn" data-code-id="' + codeId + '" data-code-encoded="' + encodedCode + '" aria-label="Copy code">Copy code</button><pre><code class="code-block">' + codeContent + '</code></pre></div>');
              }
              inCodeBlock = false;
              codeBlockLines = [];
            } else if (trimmed) {
              // Single text line within code block - might be a comment, separator, or short description
              // Keep it in the code block if it looks code-related
              if (trimmed.startsWith('#') || isSeparator || (trimmed.length < 100 && /^[A-Z]/.test(trimmed))) {
                codeBlockLines.push(line);
                continue;
              } else {
                // End code block - this looks like real text
                if (codeBlockLines.length > 0) {
                  const codeContent = codeBlockLines.map(l => escapeHtml(l)).join(newlineChar);
                  const rawCode = codeBlockLines.join(newlineChar);
                  const encodedCode = btoa(unescape(encodeURIComponent(rawCode)));
                  const codeId = "code-block-pattern-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
                  result.push('<div class="code-block-wrapper"><button class="code-copy-btn" data-code-id="' + codeId + '" data-code-encoded="' + encodedCode + '" aria-label="Copy code">Copy code</button><pre><code class="code-block">' + codeContent + '</code></pre></div>');
                }
                inCodeBlock = false;
                codeBlockLines = [];
              }
            } else {
              // Empty line - keep in code block (code files often have blank lines)
              codeBlockLines.push(line);
              continue;
            }
          }
          // Add regular text line
          result.push(escapeHtml(line));
        }
      }
      
      // Handle remaining code block at end
      if (inCodeBlock && codeBlockLines.length > 0) {
        const codeContent = codeBlockLines.map(l => escapeHtml(l)).join(newlineChar);
        const rawCode = codeBlockLines.join(newlineChar);
        const encodedCode = btoa(unescape(encodeURIComponent(rawCode)));
        const codeId = "code-block-pattern-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
        result.push('<div class="code-block-wrapper"><button class="code-copy-btn" data-code-id="' + codeId + '" data-code-encoded="' + encodedCode + '" aria-label="Copy code">Copy code</button><pre><code class="code-block">' + codeContent + '</code></pre></div>');
      }
      
      // Process inline code before joining
      // Replace inline code: `code` in text parts (not in code blocks)
      const processedResult = result.map(line => {
        // Skip if it's already a code block
        if (line.startsWith('<pre>')) return line;
        
        // Replace backticks with inline code tags
        const parts = line.split('`');
        for (let i = 1; i < parts.length; i += 2) {
          // Odd indices are code
          if (parts[i]) {
            parts[i] = '<code>' + escapeHtml(parts[i]) + '</code>';
          }
        }
        return parts.join('');
      });
      
      // Join with <br> for line breaks (code blocks already have their own formatting)
      formatted = processedResult.join('<br>');
      
      return formatted;
    }

    function copyToClipboard(text, button) {
      navigator.clipboard.writeText(text).then(() => {
        const originalText = button.textContent;
        button.textContent = "Copied!";
        button.classList.add("copied");
        setTimeout(() => {
          button.textContent = originalText;
          button.classList.remove("copied");
        }, 2000);
      }).catch(err => {
        console.error("Failed to copy:", err);
        button.textContent = "Failed";
        setTimeout(() => {
          button.textContent = "Copy";
        }, 2000);
      });
    }

    async function checkHealth() {
      try {
        // Add timeout to prevent hanging
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 120 second timeout
        
        const res = await fetch("/api/health", { 
          signal: controller.signal,
          cache: 'no-cache'
        });
        
        clearTimeout(timeoutId);
        
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const data = await res.json();
        backendMode = data.mode || "unknown";
        if (!data.ready) {
          setStatus(data.error || "Initializing FemCAD RAG…", "warning");
        } else if (data.warning) {
          setStatus(data.warning, "warning");
        } else if (backendMode === "fallback") {
          setStatus("Ready (local fallback mode).", "ready");
        } else {
          setStatus("Ready for FemCAD questions.", "ready");
        }
      } catch (err) {
        if (err.name === 'AbortError') {
          setStatus("Backend health check timed out.", "error");
        } else {
          console.error("Health check error:", err);
          setStatus("Unable to reach backend.", "error");
        }
      }
    }

    checkHealth();
    setInterval(checkHealth, 30000); // Check every 30 seconds

    async function submitQuestion() {
      const question = questionInput.value.trim();
      if (!question) {
        setStatus("Please enter a question first.", "warning");
        questionInput.focus();
        return;
      }

      // Add user message to chat
      chatMessages.push({ 
        role: "user", 
        content: question,
        timestamp: Date.now()
      });
      renderChat();

      submitBtn.disabled = true;
      submitBtn.classList.add("button-loading");
      setStatus("Composing an answer…", "thinking");
      questionInput.value = "";
      questionInput.style.height = "auto";

      try {
        const response = await fetch("/api/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            question: question,
            session_id: sessionId 
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "Request failed.");
        }

        const data = await response.json();
        
        // Update session ID from response and store it
        if (data.session_id) {
          sessionId = data.session_id;
          localStorage.setItem("femcad_session_id", sessionId);
        }

        // Add assistant message to chat
        chatMessages.push({ 
          role: "assistant", 
          content: data.answer,
          timestamp: Date.now()
        });
        renderChat();
        
        results.style.display = "grid";
        answerEl.innerHTML = formatAnswerWithCode(data.answer);
        setupCodeCopyButtons(); // Setup copy buttons for answer
        contextEl.textContent = data.context;
        latencyEl.textContent = `⚡ ${data.latency_ms.toFixed(0)} ms`;
        modePill.textContent = data.mode === "fallback" ? "Fallback" : "Enhanced";
        modePill.dataset.mode = data.mode === "fallback" ? "fallback" : "enhanced";

        sourcesEl.innerHTML = "";
        if (data.sources && data.sources.length > 0) {
          data.sources.forEach((source, index) => {
            const card = document.createElement("div");
            card.className = "source-card";
            card.innerHTML = `
              <h3>${index + 1}. ${source.title} <small>(${source.source_type})</small></h3>
              ${source.path ? `<code>${source.path}</code>` : ""}
              <p>${source.preview}</p>
            `;
            sourcesEl.appendChild(card);
          });
        } else {
          sourcesEl.innerHTML = '<div class="empty-state"><p>No sources available</p></div>';
        }

        backendMode = data.mode || backendMode;
        setStatus(
          backendMode === "fallback" ? "Answer ready (local fallback)." : "Answer ready.",
          "ready"
        );
      } catch (error) {
        setStatus(error.message || "Something went wrong.", "error");
        chatMessages.push({ 
          role: "assistant", 
          content: `Error: ${error.message}`,
          timestamp: Date.now()
        });
        renderChat();
      } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove("button-loading");
        questionInput.focus();
      }
    }

    async function resetChat() {
      if (!sessionId) {
        // Just clear local UI
        chatMessages = [];
        renderChat();
        results.style.display = "none";
        questionInput.value = "";
        questionInput.style.height = "auto";
        return;
      }

      try {
        await fetch("/api/memory/clear", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        });
      } catch (err) {
        // If it fails, we still reset local view
        console.warn("Failed to clear backend session", err);
      }

      // Clear local state
      chatMessages = [];
      renderChat();
      results.style.display = "none";
      questionInput.value = "";
      questionInput.style.height = "auto";
      localStorage.removeItem("femcad_session_id");
      sessionId = null;
      setStatus("Conversation cleared. Start a new question.", "ready");
    }

    submitBtn.addEventListener("click", submitQuestion);
    resetBtn.addEventListener("click", resetChat);
    clearChatBtn.addEventListener("click", resetChat);
    
    copyAnswerBtn.addEventListener("click", () => {
      // Get plain text version for copying (strip HTML tags)
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = answerEl.innerHTML;
      const plainText = tempDiv.textContent || tempDiv.innerText || '';
      copyToClipboard(plainText, copyAnswerBtn);
    });
    
    copyContextBtn.addEventListener("click", () => {
      copyToClipboard(contextEl.textContent, copyContextBtn);
    });

    // Handle code block copy buttons
    function setupCodeCopyButtons() {
      const copyButtons = document.querySelectorAll(".code-copy-btn");
      copyButtons.forEach((button) => {
        // Remove existing listeners by cloning
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        
        newButton.addEventListener("click", async function() {
          const encodedCode = this.getAttribute("data-code-encoded");
          if (!encodedCode) return;
          
          try {
            // Decode from base64
            const decodedCode = decodeURIComponent(escape(atob(encodedCode)));
            await navigator.clipboard.writeText(decodedCode);
            
            // Update button state
            const originalText = this.textContent;
            this.textContent = "Copied!";
            this.classList.add("copied");
            
            setTimeout(() => {
              this.textContent = originalText;
              this.classList.remove("copied");
            }, 2000);
          } catch (err) {
            console.error("Failed to copy code:", err);
            const originalText = this.textContent;
            this.textContent = "Failed";
            setTimeout(() => {
              this.textContent = originalText;
            }, 2000);
          }
        });
      });
    }

    // Setup copy buttons when answer is rendered
    const originalFormatAnswer = formatAnswerWithCode;
    const answerObserver = new MutationObserver(() => {
      setupCodeCopyButtons();
    });
    
    if (answerEl) {
      answerObserver.observe(answerEl, { childList: true, subtree: true });
    }
    
    // Also setup for chat messages
    const chatObserver = new MutationObserver(() => {
      setupCodeCopyButtons();
    });
    
    if (chatMessagesEl) {
      chatObserver.observe(chatMessagesEl, { childList: true, subtree: true });
    }

    questionInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitQuestion();
      }
    });

    // Focus textarea on load
    questionInput.focus();
  </script>
</body>
</html>
"""

