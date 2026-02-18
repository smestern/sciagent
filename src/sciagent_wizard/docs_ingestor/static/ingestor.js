/**
 * SciAgent Docs Ingestor — Frontend logic
 *
 * Handles:
 *  1. Form submission → POST /ingestor/api/start
 *  2. WebSocket connection → /ingestor/ws/ingest
 *  3. Progress rendering (crawl, LLM sections, finalize)
 *  4. Result display + download
 */

let ws = null;
let sessionId = null;
let resultMarkdown = '';

// ── Form submission ────────────────────────────────────────────────

async function startIngestion() {
    const packageName = document.getElementById('packageName').value.trim();
    if (!packageName) {
        alert('Please enter a package name.');
        return;
    }

    const githubUrl = document.getElementById('githubUrl').value.trim();
    const startBtn = document.getElementById('startBtn');

    // Disable form
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="spinner"></span> Starting...';

    try {
        // Check auth status before calling API
        try {
            const authCheck = await fetch('/auth/status');
            if (authCheck.ok) {
                const authData = await authCheck.json();
                if (authData.authenticated === false) {
                    window.location.href = '/auth/login?return_to=/ingestor/';
                    return;
                }
            }
        } catch (_) { /* auth endpoint not available — OAuth not configured */ }

        // Get session ID
        const resp = await fetch('/ingestor/api/start', {
            method: 'POST',
            redirect: 'manual',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify({
                package_name: packageName,
                github_url: githubUrl || null,
            }),
        });

        // Handle auth redirect (opaque redirect or 401)
        if (resp.type === 'opaqueredirect' || resp.status === 0) {
            window.location.href = '/auth/login?return_to=/ingestor/';
            return;
        }

        if (resp.status === 401) {
            try {
                const authData = await resp.json();
                if (authData.auth_required && authData.login_url) {
                    window.location.href = authData.login_url;
                    return;
                }
            } catch (_) {}
            window.location.href = '/auth/login?return_to=/ingestor/';
            return;
        }

        const data = await resp.json();

        if (data.error) {
            alert(data.error);
            resetButton();
            return;
        }

        sessionId = data.session_id;

        // Show progress panel
        document.getElementById('progressPanel').classList.add('visible');
        document.getElementById('resultPanel').classList.remove('visible');

        // Open WebSocket
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${location.host}/ingestor/ws/ingest`);

        ws.onopen = () => {
            // Send package info to start the process
            const selectedModel = document.getElementById('modelSelect').value;
            ws.send(JSON.stringify({
                package_name: packageName,
                github_url: githubUrl || null,
                session_id: sessionId,
                model: selectedModel,
            }));
            addLog('Connected — starting ingestion...', 'status');
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        };

        ws.onerror = () => {
            addLog('WebSocket error', 'error');
            resetButton();
        };

        ws.onclose = () => {
            addLog('Connection closed', 'status');
            resetButton();
        };

    } catch (err) {
        alert('Failed to start: ' + err.message);
        resetButton();
    }
}


// ── Message handling ───────────────────────────────────────────────

function handleMessage(msg) {
    switch (msg.type) {
        case 'status':
            addLog(msg.text, 'status');
            break;

        case 'crawl_complete':
            setStepDone('stepCrawl');
            addLog(
                `Crawled ${msg.pages} pages (${(msg.total_chars / 1000).toFixed(1)}k chars)`,
                'success'
            );
            if (msg.page_titles) {
                msg.page_titles.forEach(t => addLog(`  📄 ${t}`, 'status'));
            }
            break;

        case 'tool_start':
            addLog(`🔧 ${msg.name}...`, 'tool');
            break;

        case 'tool_complete':
            addLog(`✅ ${msg.name} complete`, 'tool');
            updateSectionSteps(msg.sections_filled || []);
            if (msg.name === 'finalize') {
                setStepDone('stepFinalize');
            }
            break;

        case 'text_delta':
            // LLM thinking — show in log as a running line
            appendLog(msg.text);
            break;

        case 'error':
            addLog(`❌ ${msg.text}`, 'error');
            break;

        case 'result':
            resultMarkdown = msg.markdown;
            showResult(msg.markdown, msg.download_url);
            break;

        case 'done':
            addLog('Processing complete.', 'success');
            break;
    }
}


// ── Progress helpers ───────────────────────────────────────────────

function setStepDone(stepId) {
    const el = document.getElementById(stepId);
    if (el) {
        el.classList.remove('active');
        el.classList.add('done');
    }
}

function setStepActive(stepId) {
    const el = document.getElementById(stepId);
    if (el) {
        el.classList.add('active');
    }
}

function updateSectionSteps(filled) {
    const map = {
        'core_classes': 'stepClasses',
        'key_functions': 'stepFunctions',
        'common_pitfalls': 'stepPitfalls',
        'recipes': 'stepRecipes',
    };
    for (const [section, stepId] of Object.entries(map)) {
        if (filled.includes(section)) {
            setStepDone(stepId);
        }
    }
}

let currentLogLine = null;

function addLog(text, cls = '') {
    currentLogLine = null;
    const container = document.getElementById('logContainer');
    const entry = document.createElement('div');
    entry.className = 'log-entry' + (cls ? ' ' + cls : '');
    entry.textContent = text;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function appendLog(text) {
    // Append text to the last log entry (for streaming LLM text)
    if (!currentLogLine) {
        const container = document.getElementById('logContainer');
        currentLogLine = document.createElement('div');
        currentLogLine.className = 'log-entry';
        container.appendChild(currentLogLine);
    }
    currentLogLine.textContent += text;
    const container = document.getElementById('logContainer');
    container.scrollTop = container.scrollHeight;
}


// ── Result display ─────────────────────────────────────────────────

function showResult(markdown, downloadUrl) {
    document.getElementById('resultPanel').classList.add('visible');
    document.getElementById('markdownPreview').textContent = markdown;

    if (downloadUrl) {
        const btn = document.getElementById('downloadBtn');
        btn.href = downloadUrl;
    }
}

async function copyToClipboard() {
    if (!resultMarkdown) return;
    try {
        await navigator.clipboard.writeText(resultMarkdown);
        alert('Copied to clipboard!');
    } catch {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = resultMarkdown;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
        alert('Copied to clipboard!');
    }
}


// ── Reset ──────────────────────────────────────────────────────────

function resetButton() {
    const btn = document.getElementById('startBtn');
    btn.disabled = false;
    btn.innerHTML = '🔍 Generate API Reference';
}

function resetForm() {
    document.getElementById('progressPanel').classList.remove('visible');
    document.getElementById('resultPanel').classList.remove('visible');
    document.getElementById('logContainer').innerHTML = '';
    document.getElementById('packageName').value = '';
    document.getElementById('githubUrl').value = '';
    resultMarkdown = '';
    currentLogLine = null;

    // Reset steps
    ['stepCrawl', 'stepClasses', 'stepFunctions', 'stepPitfalls', 'stepRecipes', 'stepFinalize']
        .forEach(id => {
            const el = document.getElementById(id);
            el.classList.remove('done', 'active');
        });
    document.getElementById('stepCrawl').classList.add('active');

    resetButton();
    document.getElementById('packageName').focus();
}


// ── Enter key support ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('packageName').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startIngestion();
    });
    document.getElementById('githubUrl').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startIngestion();
    });
});
