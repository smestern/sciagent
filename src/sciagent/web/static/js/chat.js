/**
 * sciagent — WebSocket Chat Client
 *
 * Generic chat UI that loads its configuration (branding, suggestion chips,
 * accepted file types) from /api/config at startup.
 */

const WS_PATH = "/ws/chat";

const chatMessages  = document.getElementById("chatMessages");
const inputForm     = document.getElementById("inputForm");
const userInput     = document.getElementById("userInput");
const sendBtn       = document.getElementById("sendBtn");
const statusBar     = document.getElementById("statusBar");
const statusText    = document.getElementById("statusText");
const statusDot     = document.getElementById("statusDot");
const sampleList    = document.getElementById("sampleList");
const fileInput     = document.getElementById("fileInput");
const uploadArea    = document.getElementById("uploadArea");
const uploadStatus  = document.getElementById("uploadStatus");
const themeToggle   = document.getElementById("themeToggle");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebar       = document.getElementById("sidebar");

let ws = null;
let sessionId = null;
let activeFileId = null;
let currentAssistantEl = null;
let currentTextBuffer = "";
let thinkingEl = null;
let toolContainer = null;
let afterTool = false;
let isConnected = false;
let appConfig = {};

// ── Markdown ───────────────────────────────────────────────────────────
marked.setOptions({
    highlight: function (code, lang) {
        if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true,
});

// ── Init: load config then connect ─────────────────────────────────────
(async function init() {
    try {
        const resp = await fetch("/api/config");
        appConfig = await resp.json();
        applyConfig(appConfig);
    } catch (e) {
        console.warn("Could not load /api/config, using defaults", e);
    }
    loadSamples();
    connect();
})();

function applyConfig(cfg) {
    document.getElementById("pageTitle").textContent = cfg.display_name || "SciAgent";
    document.getElementById("logoEmoji").textContent = cfg.logo_emoji || "🔬";
    document.getElementById("logoName").textContent = cfg.display_name || "SciAgent";
    document.getElementById("tagline").textContent = cfg.description || "AI-powered scientific analysis";
    document.getElementById("welcomeTitle").textContent = "Welcome to " + (cfg.display_name || "SciAgent");
    document.getElementById("welcomeDesc").textContent =
        "I'm an AI assistant for scientific data analysis. Load a sample file or upload your own, then ask me to analyze it.";

    if (cfg.github_url) {
        const link = document.getElementById("githubLink");
        link.href = cfg.github_url;
        link.style.display = "";
    }

    if (cfg.accepted_file_types && cfg.accepted_file_types.length) {
        fileInput.accept = cfg.accepted_file_types.join(",");
        const exts = cfg.accepted_file_types.join(" or ");
        document.querySelector(".upload-text").innerHTML = `Drop ${exts} here<br>or click to browse`;
    }

    const container = document.getElementById("suggestionsContainer");
    container.innerHTML = "";
    (cfg.suggestion_chips || []).forEach(chip => {
        const btn = document.createElement("button");
        btn.className = "suggestion-chip";
        btn.dataset.prompt = chip.prompt;
        btn.textContent = chip.label;
        btn.addEventListener("click", () => {
            userInput.value = chip.prompt;
            inputForm.dispatchEvent(new Event("submit"));
        });
        container.appendChild(btn);
    });

    if (cfg.accent_color) {
        document.documentElement.style.setProperty("--accent", cfg.accent_color);
    }
}

// ── WebSocket ──────────────────────────────────────────────────────────
function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}${WS_PATH}`);
    ws.onopen = () => console.log("[ws] connected");
    ws.onmessage = (evt) => {
        let msg;
        try { msg = JSON.parse(evt.data); } catch { return; }
        handleServerMessage(msg);
    };
    ws.onerror = () => setStatus("error", "Connection error");
    ws.onclose = () => {
        isConnected = false;
        statusDot.className = "status-dot error";
        setStatus("show", "Disconnected — refresh to reconnect");
        sendBtn.disabled = true;
    };
}

function sendMessage(text) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const payload = { text };
    if (activeFileId) payload.file_id = activeFileId;
    ws.send(JSON.stringify(payload));
}

// ── Message handling ───────────────────────────────────────────────────
function handleServerMessage(msg) {
    switch (msg.type) {
        case "connected":
            sessionId = msg.session_id;
            isConnected = true;
            statusDot.className = "status-dot connected";
            sendBtn.disabled = false;
            setStatus("hide");
            break;
        case "status":
            setStatus("show", msg.text);
            break;
        case "thinking":
            ensureAssistantMessage();
            appendThinking(msg.text);
            break;
        case "tool_start":
            ensureAssistantMessage();
            addToolPill(msg.name, "running");
            setStatus("show", `Running ${msg.name}…`);
            break;
        case "tool_complete":
            updateToolPill(msg.name, "done");
            afterTool = true;
            setStatus("hide");
            break;
        case "text_delta":
            ensureAssistantMessage();
            closeThinking();
            if (afterTool && currentTextBuffer.length > 0) {
                currentTextBuffer += "\n\n";
            }
            afterTool = false;
            currentTextBuffer += msg.text;
            renderMarkdown();
            scrollToBottom();
            break;
        case "figure":
            ensureAssistantMessage();
            appendFigure(msg.data, msg.figure_number, msg.filename);
            scrollToBottom();
            break;
        case "error":
            ensureAssistantMessage();
            appendError(msg.text);
            finalizeAssistant();
            break;
        case "done":
            finalizeAssistant();
            break;
    }
}

// ── Rendering helpers ──────────────────────────────────────────────────
function addUserMessage(text) {
    const welcome = chatMessages.querySelector(".welcome-message");
    if (welcome) welcome.remove();
    const div = document.createElement("div");
    div.className = "message user";
    div.innerHTML = `<div class="message-avatar">🧑</div><div class="message-body">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
}

function ensureAssistantMessage() {
    if (currentAssistantEl) return;
    const div = document.createElement("div");
    div.className = "message assistant";
    div.innerHTML = `<div class="message-avatar">🤖</div><div class="message-body"></div>`;
    chatMessages.appendChild(div);
    currentAssistantEl = div.querySelector(".message-body");
    currentTextBuffer = "";
    thinkingEl = null;
    toolContainer = null;
}

function appendThinking(text) {
    if (!thinkingEl) {
        const details = document.createElement("details");
        details.className = "thinking-block";
        details.innerHTML = `<summary>💭 Thinking…</summary><span class="thinking-text"></span>`;
        currentAssistantEl.appendChild(details);
        thinkingEl = details.querySelector(".thinking-text");
    }
    thinkingEl.textContent += text;
}

function closeThinking() {
    if (thinkingEl) {
        thinkingEl.parentElement.open = false;
        thinkingEl = null;
    }
}

function addToolPill(name, state) {
    if (!toolContainer) {
        toolContainer = document.createElement("div");
        toolContainer.className = "tool-pills";
        currentAssistantEl.appendChild(toolContainer);
    }
    const pill = document.createElement("span");
    pill.className = `tool-pill ${state}`;
    pill.dataset.tool = name;
    pill.textContent = `⚙ ${name}`;
    toolContainer.appendChild(pill);
}

function updateToolPill(name, state) {
    if (!toolContainer) return;
    const pill = toolContainer.querySelector(`[data-tool="${name}"]`);
    if (pill) { pill.className = `tool-pill ${state}`; pill.textContent = `✓ ${name}`; }
}

function renderMarkdown() {
    if (!currentAssistantEl) return;
    let mdContainer = currentAssistantEl.querySelector(".md-content");
    if (!mdContainer) {
        mdContainer = document.createElement("div");
        mdContainer.className = "md-content";
        currentAssistantEl.appendChild(mdContainer);
    }
    mdContainer.innerHTML = marked.parse(currentTextBuffer);
    mdContainer.querySelectorAll("pre code").forEach(el => hljs.highlightElement(el));
}

function appendFigure(base64, figNum, filename) {
    const wrapper = document.createElement("div");
    wrapper.className = "figure-wrapper";
    const img = document.createElement("img");
    img.src = `data:image/png;base64,${base64}`;
    img.alt = filename ? filename : `Figure ${figNum}`;
    img.className = "chat-figure";
    wrapper.appendChild(img);
    const label = document.createElement("span");
    label.className = "figure-label";
    label.textContent = filename ? filename : `Figure ${figNum}`;
    wrapper.appendChild(label);
    currentAssistantEl.appendChild(wrapper);
}

function appendError(text) {
    const div = document.createElement("div");
    div.className = "error-block";
    div.textContent = `⚠ ${text}`;
    if (currentAssistantEl) currentAssistantEl.appendChild(div);
}

function finalizeAssistant() {
    currentAssistantEl = null;
    currentTextBuffer = "";
    thinkingEl = null;
    toolContainer = null;
    afterTool = false;
    setStatus("hide");
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setStatus(mode, text) {
    if (mode === "hide") { statusBar.hidden = true; return; }
    statusBar.hidden = false;
    statusText.textContent = text || "";
}

function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
}

// ── Input handling ─────────────────────────────────────────────────────
inputForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text || !isConnected) return;
    addUserMessage(text);
    sendMessage(text);
    userInput.value = "";
    userInput.style.height = "auto";
});

userInput.addEventListener("input", () => {
    sendBtn.disabled = !userInput.value.trim() || !isConnected;
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 160) + "px";
});

userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        inputForm.dispatchEvent(new Event("submit"));
    }
});

// ── Theme toggle ───────────────────────────────────────────────────────
themeToggle.addEventListener("click", () => {
    const html = document.documentElement;
    const next = html.dataset.theme === "dark" ? "light" : "dark";
    html.dataset.theme = next;
    themeToggle.textContent = next === "dark" ? "🌙" : "☀️";
});

// ── Sidebar toggle ─────────────────────────────────────────────────────
sidebarToggle.addEventListener("click", () => sidebar.classList.toggle("collapsed"));

// ── Samples ────────────────────────────────────────────────────────────
async function loadSamples() {
    try {
        const resp = await fetch("/api/samples");
        const data = await resp.json();
        if (!data.samples || data.samples.length === 0) {
            sampleList.innerHTML = '<p class="muted">No sample files found</p>';
            return;
        }
        sampleList.innerHTML = "";
        data.samples.forEach(s => {
            const item = document.createElement("div");
            item.className = "sample-item";
            item.innerHTML = `<span>${s.name}</span><span class="muted">${s.size_kb} KB</span>`;
            item.addEventListener("click", () => loadSample(s.name));
            sampleList.appendChild(item);
        });
    } catch { sampleList.innerHTML = '<p class="muted">Could not load samples</p>'; }
}

async function loadSample(name) {
    if (!sessionId) return;
    try {
        const resp = await fetch("/api/load-sample", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, session_id: sessionId }),
        });
        const data = await resp.json();
        if (data.error) { uploadStatus.textContent = data.error; return; }
        activeFileId = data.file_id;
        uploadStatus.textContent = `✓ Loaded ${name}`;
    } catch (e) { uploadStatus.textContent = "Failed to load sample"; }
}

// ── File upload ────────────────────────────────────────────────────────
uploadArea.addEventListener("click", () => fileInput.click());
uploadArea.addEventListener("dragover", (e) => { e.preventDefault(); uploadArea.classList.add("dragover"); });
uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => { if (fileInput.files.length) uploadFile(fileInput.files[0]); });

async function uploadFile(file) {
    uploadStatus.textContent = `Uploading ${file.name}…`;
    const form = new FormData();
    form.append("file", file);
    if (sessionId) form.append("session_id", sessionId);
    try {
        const resp = await fetch("/upload", { method: "POST", body: form });
        const data = await resp.json();
        if (data.error) { uploadStatus.textContent = `⚠ ${data.error}`; return; }
        activeFileId = data.file_id;
        if (data.session_id) sessionId = data.session_id;
        uploadStatus.textContent = `✓ ${file.name} uploaded`;
    } catch { uploadStatus.textContent = "Upload failed"; }
}

// ── Export script ──────────────────────────────────────────────────────
const exportScriptBtn = document.getElementById("exportScriptBtn");
const exportHint = document.getElementById("exportHint");

exportScriptBtn.addEventListener("click", async () => {
    if (!sessionId) {
        exportHint.textContent = "No active session.";
        return;
    }
    // First ask the agent to produce the script via chat
    const exportPrompt = "Please review the session log with get_session_log and produce a clean, standalone reproducible Python script for the analysis we just performed. Include argparse with --input-file and --output-dir, all necessary imports, and only the working analysis steps. Save it using save_reproducible_script.";
    addUserMessage("Export reproducible script");
    sendMessage(exportPrompt);
    exportHint.textContent = "Asking agent to compose script…";

    // After a short delay, try downloading
    setTimeout(async () => {
        try {
            const resp = await fetch(`/api/export-script?session_id=${sessionId}`);
            if (resp.ok) {
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "reproducible_analysis.py";
                a.click();
                URL.revokeObjectURL(url);
                exportHint.textContent = "✓ Script downloaded!";
            } else {
                exportHint.textContent = "Script will be ready when the agent finishes.";
            }
        } catch {
            exportHint.textContent = "Download will be available after the agent finishes.";
        }
    }, 15000);  // Wait 15s for agent to compose and save
});
