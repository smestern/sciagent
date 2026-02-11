/**
 * wizard.js — Client-side logic for the self-assembly wizard.
 *
 * Manages the multi-step form and transitions into the WebSocket
 * chat for conversational refinement.
 */

// ── State ──────────────────────────────────────────────────────────────

const wizardState = {
    step: 1,
    domainDescription: '',
    goals: [],
    fileTypes: [],
    knownPackages: [],
    uploadedFiles: [],       // File objects
    uploadedFilePaths: [],   // Server-side paths
    sessionId: null,
};

// ── Quick-start templates ──────────────────────────────────────────────

const quickstarts = {
    electrophysiology: {
        description: 'I study patch-clamp electrophysiology. I record voltage and current traces from neurons to analyze ion channel properties, action potential firing patterns, and synaptic responses. I need to extract features like amplitude, rise time, decay time, and fit exponential curves to the data.',
        goals: ['Extract action potential features', 'Fit exponential decay curves', 'Analyze synaptic events', 'Plot IV curves'],
        fileTypes: ['.abf', '.csv', '.nwb'],
        packages: ['pyabf', 'neo', 'elephant'],
    },
    genomics: {
        description: 'I work in genomics and transcriptomics. I process sequencing data, perform quality control, align reads, and do differential expression analysis. I need to handle large datasets and produce publication-quality visualizations.',
        goals: ['Quality control on FASTQ files', 'Differential expression analysis', 'Gene set enrichment analysis', 'Variant calling'],
        fileTypes: ['.fastq', '.bam', '.vcf', '.csv', '.tsv'],
        packages: ['biopython', 'pysam', 'scanpy'],
    },
    imaging: {
        description: 'I do calcium imaging experiments on neurons. I acquire TIFF stacks, extract fluorescence intensity traces from ROIs, detect calcium transient events, and correlate activity across cells.',
        goals: ['Extract fluorescence traces from ROIs', 'Detect calcium events', 'Correlate neural activity', 'Motion correction'],
        fileTypes: ['.tif', '.tiff', '.csv', '.npy'],
        packages: ['suite2p', 'caiman', 'scikit-image'],
    },
    chemistry: {
        description: 'I am a chemist working with spectroscopy data (UV-Vis, NMR, IR). I need to load spectra, perform baseline correction, fit peaks (Gaussian/Lorentzian), calculate concentrations from calibration curves, and compare samples.',
        goals: ['Baseline correction', 'Peak fitting', 'Build calibration curves', 'Compare sample spectra'],
        fileTypes: ['.csv', '.txt', '.json', '.xlsx'],
        packages: ['lmfit', 'nmrglue', 'rampy'],
    },
};

// ── Quick-start ────────────────────────────────────────────────────────

function useQuickstart(key) {
    const qs = quickstarts[key];
    if (!qs) return;

    document.getElementById('domain-desc').value = qs.description;

    // Populate goals
    wizardState.goals = [...qs.goals];
    renderTags('goals-container', 'goals-input', wizardState.goals);

    // Populate file types
    wizardState.fileTypes = [...qs.fileTypes];
    renderTags('filetypes-container', 'filetypes-input', wizardState.fileTypes);

    // Populate packages
    wizardState.knownPackages = [...qs.packages];
    renderTags('packages-container', 'packages-input', wizardState.knownPackages);
}

// ── Step navigation ────────────────────────────────────────────────────

function goToStep(step) {
    // Save current step data
    wizardState.domainDescription = document.getElementById('domain-desc').value;

    // Update step indicators
    document.querySelectorAll('.wizard-step').forEach(el => {
        const s = parseInt(el.dataset.step);
        el.classList.remove('active', 'completed');
        if (s < step) el.classList.add('completed');
        if (s === step) el.classList.add('active');
    });

    // Show/hide panels
    document.querySelectorAll('.wizard-panel').forEach(el => {
        el.classList.remove('active');
    });
    document.getElementById(`step-${step}`).classList.add('active');

    wizardState.step = step;
}

// ── Tag input helpers ──────────────────────────────────────────────────

function setupTagInput(containerId, inputId, stateArray) {
    const input = document.getElementById(inputId);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && input.value.trim()) {
            e.preventDefault();
            const val = input.value.trim();
            if (!stateArray.includes(val)) {
                stateArray.push(val);
                renderTags(containerId, inputId, stateArray);
            }
            input.value = '';
        }
    });

    // Click container to focus input
    document.getElementById(containerId).addEventListener('click', () => {
        input.focus();
    });
}

function renderTags(containerId, inputId, arr) {
    const container = document.getElementById(containerId);
    const input = document.getElementById(inputId);

    // Remove existing tags (keep input)
    container.querySelectorAll('.tag').forEach(t => t.remove());

    arr.forEach((val, idx) => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.innerHTML = `${escHtml(val)} <button onclick="removeTag('${containerId}', '${inputId}', ${idx})">&times;</button>`;
        container.insertBefore(tag, input);
    });
}

function removeTag(containerId, inputId, idx) {
    // Determine which array
    if (containerId === 'goals-container') wizardState.goals.splice(idx, 1);
    else if (containerId === 'filetypes-container') wizardState.fileTypes.splice(idx, 1);
    else if (containerId === 'packages-container') wizardState.knownPackages.splice(idx, 1);

    renderTags(containerId, inputId,
        containerId === 'goals-container' ? wizardState.goals :
        containerId === 'filetypes-container' ? wizardState.fileTypes :
        wizardState.knownPackages
    );
}

// ── File upload ────────────────────────────────────────────────────────

function setupFileUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
        fileInput.value = '';
    });
}

function handleFiles(fileList) {
    for (const file of fileList) {
        if (!wizardState.uploadedFiles.find(f => f.name === file.name)) {
            wizardState.uploadedFiles.push(file);
        }
    }
    renderFileList();
}

function removeFile(idx) {
    wizardState.uploadedFiles.splice(idx, 1);
    renderFileList();
}

function renderFileList() {
    const list = document.getElementById('file-list');
    list.innerHTML = wizardState.uploadedFiles.map((f, i) => `
        <div class="file-item">
            <span>📄 ${escHtml(f.name)} <span style="color: var(--text-secondary)">(${(f.size/1024).toFixed(1)} KB)</span></span>
            <button onclick="removeFile(${i})">&times;</button>
        </div>
    `).join('');
}

// ── Start wizard (transition to chat) ──────────────────────────────────

async function startWizard() {
    wizardState.domainDescription = document.getElementById('domain-desc').value;

    // Upload files first (if any)
    if (wizardState.uploadedFiles.length > 0) {
        await uploadFiles();
    }

    // Send initial data to backend
    try {
        const resp = await fetch('/wizard/api/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                domain_description: wizardState.domainDescription,
                research_goals: wizardState.goals,
                file_types: wizardState.fileTypes,
                known_packages: wizardState.knownPackages,
            }),
        });
        const data = await resp.json();
        wizardState.sessionId = data.session_id;

        // Transition to chat
        goToStep(4);
        initChat(data.kickoff_prompt);
    } catch (err) {
        console.error('Failed to start wizard:', err);
        alert('Failed to start the wizard. Check your connection.');
    }
}

async function uploadFiles() {
    for (const file of wizardState.uploadedFiles) {
        try {
            const form = new FormData();
            form.append('file', file);
            form.append('session_id', wizardState.sessionId || 'wizard-upload');
            const resp = await fetch('/upload', {method: 'POST', body: form});
            const data = await resp.json();
            if (data.path) {
                wizardState.uploadedFilePaths.push(data.path);
            }
        } catch (err) {
            console.error(`Upload failed for ${file.name}:`, err);
        }
    }
}

// ── Chat interface (reuses base sciagent chat protocol) ────────────────

let ws = null;

function initChat(kickoffPrompt) {
    const chatEmbed = document.getElementById('chat-embed');
    chatEmbed.innerHTML = `
        <div id="wizard-chat" style="height: 60vh; display: flex; flex-direction: column;">
            <div id="chat-messages" style="flex: 1; overflow-y: auto; padding: 1rem;
                background: var(--bg-primary); border-radius: 8px; margin-bottom: 1rem;
                font-size: 0.95rem; line-height: 1.6;"></div>
            <div style="display: flex; gap: 0.5rem;">
                <input type="text" id="chat-input"
                    placeholder="Type a message..."
                    style="flex: 1; padding: 0.75rem; border: 1px solid var(--border-color);
                    border-radius: 8px; background: var(--bg-primary);
                    color: var(--text-primary); font-size: 0.95rem;">
                <button class="btn btn-primary" onclick="sendChat()" id="send-btn">Send</button>
            </div>
        </div>
    `;

    // Set up Enter key
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChat();
        }
    });

    // Connect WebSocket
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/chat`);

    ws.onopen = () => {
        appendMessage('system', '🧙 Connected! Searching for domain tools…');
        // Send the kickoff prompt
        setTimeout(() => {
            ws.send(JSON.stringify({text: kickoffPrompt}));
        }, 500);
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWsMessage(msg);
        } catch (e) {
            console.error('WS parse error:', e);
        }
    };

    ws.onerror = () => appendMessage('system', '❌ Connection error');
    ws.onclose = () => appendMessage('system', '🔌 Disconnected');
}

let currentAssistantEl = null;
let assistantBuffer = '';

function handleWsMessage(msg) {
    switch (msg.type) {
        case 'connected':
            // Already shown via onopen
            break;
        case 'text_delta':
            if (!currentAssistantEl) {
                currentAssistantEl = appendMessage('assistant', '');
                assistantBuffer = '';
            }
            assistantBuffer += msg.text;
            currentAssistantEl.innerHTML = renderMarkdown(assistantBuffer);
            scrollChat();
            break;
        case 'thinking':
            // Show thinking indicator
            break;
        case 'tool_start':
            appendMessage('system', `⚙️ Running ${msg.name}…`);
            break;
        case 'tool_complete':
            appendMessage('system', `✅ ${msg.name} done`);
            break;
        case 'done':
            currentAssistantEl = null;
            assistantBuffer = '';
            break;
        case 'error':
            appendMessage('system', `❌ ${msg.text}`);
            break;
    }
}

function sendChat() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    appendMessage('user', text);
    ws.send(JSON.stringify({text}));
    input.value = '';
}

function appendMessage(role, content) {
    const messages = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.style.marginBottom = '1rem';

    if (role === 'user') {
        div.style.textAlign = 'right';
        div.innerHTML = `<span style="background: #a855f7; color: white; padding: 0.5rem 1rem;
            border-radius: 1rem; display: inline-block; max-width: 80%;">${escHtml(content)}</span>`;
    } else if (role === 'assistant') {
        div.innerHTML = `<div style="background: var(--bg-secondary); padding: 0.75rem 1rem;
            border-radius: 8px; max-width: 90%;">${renderMarkdown(content)}</div>`;
    } else {
        div.innerHTML = `<div style="color: var(--text-secondary); font-size: 0.85rem;
            text-align: center;">${content}</div>`;
    }

    messages.appendChild(div);
    scrollChat();
    return div.querySelector('div') || div;
}

function scrollChat() {
    const messages = document.getElementById('chat-messages');
    if (messages) messages.scrollTop = messages.scrollHeight;
}

function renderMarkdown(text) {
    // Basic markdown rendering (bold, code, lists)
    return text
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code style="background: var(--bg-primary); padding: 2px 4px; border-radius: 3px;">$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/^- (.+)$/gm, '• $1<br>')
        .replace(/^(\d+)\. (.+)$/gm, '$1. $2<br>')
        .replace(/\n/g, '<br>');
}

function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Init ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    setupTagInput('goals-container', 'goals-input', wizardState.goals);
    setupTagInput('filetypes-container', 'filetypes-input', wizardState.fileTypes);
    setupTagInput('packages-container', 'packages-input', wizardState.knownPackages);
    setupFileUpload();
});
