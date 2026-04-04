/* ═══════════════════════════════════════════════════════════════════════
   CALL Analytics — Frontend Logic
   HCL x Guvi Hackathon 2026
   ═══════════════════════════════════════════════════════════════════════ */

// ── DOM Elements ────────────────────────────────────────────────────
const dropzone = document.getElementById('dropzone');
const audioFileInput = document.getElementById('audioFileInput');
const fileNameDisplay = document.getElementById('fileNameDisplay');
const languageSelect = document.getElementById('languageSelect');
const analyzeBtn = document.getElementById('analyzeBtn');
const processingState = document.getElementById('processingState');
const processingText = document.getElementById('processingText');
const processingStep = document.getElementById('processingStep');
const progressFill = document.getElementById('progressFill');
const resultsDashboard = document.getElementById('resultsDashboard');
const auditSection = document.getElementById('auditSection');
const navResults = document.getElementById('navResults');
const navAudit = document.getElementById('navAudit');
const refreshAudit = document.getElementById('refreshAudit');

// ── API Configuration ───────────────────────────────────────────────
const API_BASE = "";
const API_URL = `${API_BASE}/api/call-analytics`;
const API_KEY = "hcl-guvi-hackathon-2026";

// ── State ───────────────────────────────────────────────────────────
let currentBase64 = null;
let requestStartTime = null;

// ═══════════════════════════════════════════════════════════════════════
//  File Upload (Drag & Drop + Click)
// ═══════════════════════════════════════════════════════════════════════

dropzone.addEventListener('click', () => audioFileInput.click());

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
});
audioFileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleFileSelect(e.target.files[0]);
});

function handleFileSelect(file) {
    if (!file.type.match('audio.*') && !file.name.endsWith('.mp3')) {
        alert('Please select a valid audio file (MP3).');
        return;
    }
    const sizeMB = (file.size / 1024 / 1024).toFixed(2);
    fileNameDisplay.textContent = `✓ ${file.name} (${sizeMB} MB)`;

    const reader = new FileReader();
    reader.onload = (e) => {
        currentBase64 = e.target.result.split(',')[1];
        analyzeBtn.disabled = false;
    };
    reader.readAsDataURL(file);
}

// ═══════════════════════════════════════════════════════════════════════
//  Processing Animation
// ═══════════════════════════════════════════════════════════════════════

const processingStages = [
    { text: "Decoding Audio...", sub: "Converting Base64 to MP3 format", progress: 10 },
    { text: "Transcribing Audio...", sub: "Sarvam AI processing Hinglish/Tanglish speech", progress: 30 },
    { text: "Running AI Analysis...", sub: "Gemini 2.5 Flash extracting SOP compliance", progress: 60 },
    { text: "Storing Audit Trail...", sub: "ChromaDB semantic vector indexing", progress: 80 },
    { text: "Generating Report...", sub: "Building structured JSON response", progress: 95 },
];

let stageInterval = null;

function startProcessingAnimation() {
    let stage = 0;
    updateStage(processingStages[0]);

    stageInterval = setInterval(() => {
        stage++;
        if (stage < processingStages.length) {
            updateStage(processingStages[stage]);
        }
    }, 3000);
}

function updateStage(s) {
    processingText.textContent = s.text;
    processingStep.textContent = s.sub;
    progressFill.style.width = s.progress + '%';
}

function stopProcessingAnimation() {
    if (stageInterval) clearInterval(stageInterval);
    progressFill.style.width = '100%';
}

// ═══════════════════════════════════════════════════════════════════════
//  API Request
// ═══════════════════════════════════════════════════════════════════════

analyzeBtn.addEventListener('click', async () => {
    if (!currentBase64) return;

    analyzeBtn.disabled = true;
    processingState.classList.remove('hidden');
    resultsDashboard.classList.add('hidden');
    requestStartTime = performance.now();
    startProcessingAnimation();

    const payload = {
        language: languageSelect.value,
        audioFormat: "mp3",
        audioBase64: currentBase64
    };

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        stopProcessingAnimation();

        if (response.ok) {
            const elapsed = ((performance.now() - requestStartTime) / 1000).toFixed(1);
            populateDashboard(data, elapsed);
            resultsDashboard.classList.remove('hidden');
            navResults.classList.add('active');
            setTimeout(() => {
                resultsDashboard.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
        } else {
            alert(`API Error (${response.status}): ${data.message || 'Unknown'}`);
        }
    } catch (error) {
        stopProcessingAnimation();
        console.error("Fetch Error:", error);
        alert('Connection failed. Check if the Hugging Face Space is running.');
    } finally {
        processingState.classList.add('hidden');
        analyzeBtn.disabled = false;
    }
});

// ═══════════════════════════════════════════════════════════════════════
//  Dashboard Population
// ═══════════════════════════════════════════════════════════════════════

function populateDashboard(data, elapsed) {
    // Timing
    document.getElementById('totalTimeOut').textContent = `${elapsed}s`;
    document.getElementById('statusOut').textContent = 'Success';
    document.getElementById('langOut').textContent = data.language || '-';

    // Transcript & Summary
    document.getElementById('transcriptOut').textContent = data.transcript || "No transcript.";
    document.getElementById('summaryOut').textContent = data.summary || "No summary.";

    // Compliance Score
    const sop = data.sop_validation || {};
    const analytics = data.analytics || {};
    const scorePercent = Math.round((sop.complianceScore || 0) * 100);
    const circle = document.getElementById('complianceProgress');

    circle.style.setProperty('--val', `${scorePercent * 3.6}deg`);
    circle.style.setProperty('--color', scorePercent >= 80 ? 'var(--success)' : scorePercent >= 40 ? 'var(--warning)' : 'var(--danger)');
    document.getElementById('complianceText').textContent = `${scorePercent}%`;

    // Adherence Badge
    const badge = document.getElementById('adherenceBadge');
    badge.textContent = sop.adherenceStatus || "NOT_FOLLOWED";
    badge.className = `status-badge ${sop.adherenceStatus === 'FOLLOWED' ? 'status-followed' : 'status-not-followed'}`;

    // Analytics
    document.getElementById('sentimentOut').textContent = analytics.sentiment || '-';
    document.getElementById('paymentOut').textContent = analytics.paymentPreference || '-';
    document.getElementById('rejectionOut').textContent = analytics.rejectionReason || '-';

    // SOP Checklist
    const sopMap = {
        greeting: 'sop-greeting',
        identification: 'sop-identification',
        problemStatement: 'sop-problem',
        solutionOffering: 'sop-solution',
        closing: 'sop-closing'
    };

    Object.entries(sopMap).forEach(([field, elId]) => {
        const el = document.getElementById(elId);
        const icon = el.querySelector('.sop-icon i');
        const status = el.querySelector('.sop-status');
        const passed = !!sop[field];

        icon.className = passed ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark';
        status.textContent = passed ? 'Passed' : 'Failed';
        status.className = `sop-status ${passed ? 'passed' : 'failed'}`;
    });

    // SOP Explanation
    const explanation = document.getElementById('sopExplanation');
    if (sop.explanation) {
        explanation.textContent = sop.explanation;
        explanation.style.display = 'block';
    } else {
        explanation.style.display = 'none';
    }

    // Keywords
    const keywordsContainer = document.getElementById('keywordsOut');
    keywordsContainer.innerHTML = '';
    const keywords = data.keywords || [];

    if (keywords.length === 0) {
        keywordsContainer.innerHTML = '<span style="color: var(--text-muted)">No keywords extracted.</span>';
    } else {
        keywords.forEach((kw, i) => {
            const span = document.createElement('span');
            span.className = 'keyword-pill';
            span.textContent = kw;
            span.style.animationDelay = `${i * 0.05}s`;
            keywordsContainer.appendChild(span);
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════
//  Navigation
// ═══════════════════════════════════════════════════════════════════════

document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        const target = link.getAttribute('href');
        if (target === '#audit') {
            auditSection.classList.remove('hidden');
            auditSection.scrollIntoView({ behavior: 'smooth' });
        } else if (target === '#results' && !resultsDashboard.classList.contains('hidden')) {
            resultsDashboard.scrollIntoView({ behavior: 'smooth' });
        } else if (target === '#upload') {
            document.getElementById('inputCard').scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// ═══════════════════════════════════════════════════════════════════════
//  Audit Log
// ═══════════════════════════════════════════════════════════════════════

refreshAudit.addEventListener('click', async () => {
    const statsEl = document.getElementById('auditStats');
    statsEl.innerHTML = '<p style="color: var(--accent-primary)"><i class="fa-solid fa-spinner fa-spin"></i> Loading...</p>';

    try {
        const res = await fetch(`${API_BASE}/audit/stats`);
        const data = await res.json();
        statsEl.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                <div class="analytics-item" style="padding:1rem;background:rgba(0,0,0,0.2);border-radius:10px;border:1px solid var(--glass-border)">
                    <div class="analytics-icon sentiment-icon"><i class="fa-solid fa-phone"></i></div>
                    <div class="analytics-info">
                        <span class="analytics-label">Total Calls</span>
                        <span class="analytics-value">${data.total_calls ?? '-'}</span>
                    </div>
                </div>
                <div class="analytics-item" style="padding:1rem;background:rgba(0,0,0,0.2);border-radius:10px;border:1px solid var(--glass-border)">
                    <div class="analytics-icon payment-icon"><i class="fa-solid fa-chart-line"></i></div>
                    <div class="analytics-info">
                        <span class="analytics-label">Avg Compliance</span>
                        <span class="analytics-value">${data.avg_compliance ?? '-'}</span>
                    </div>
                </div>
                <div class="analytics-item" style="padding:1rem;background:rgba(0,0,0,0.2);border-radius:10px;border:1px solid var(--glass-border)">
                    <div class="analytics-icon rejection-icon"><i class="fa-solid fa-database"></i></div>
                    <div class="analytics-info">
                        <span class="analytics-label">Vector Store</span>
                        <span class="analytics-value">ChromaDB</span>
                    </div>
                </div>
            </div>
        `;
    } catch {
        statsEl.innerHTML = '<p style="color:var(--danger)">Failed to fetch audit stats. Is the API running?</p>';
    }
});

const auditSearchBtn = document.getElementById('auditSearchBtn');
const auditSearchInput = document.getElementById('auditSearchInput');
const auditSearchResults = document.getElementById('auditSearchResults');

if (auditSearchBtn) {
    auditSearchBtn.addEventListener('click', async () => {
        const query = auditSearchInput.value.trim();
        if (!query) return;

        auditSearchBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        auditSearchResults.innerHTML = '';

        try {
            const res = await fetch(`${API_BASE}/audit/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            
            auditSearchBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Search';
            
            if (data.results && data.results.length > 0) {
                let html = `<h4><i class="fa-solid fa-layer-group"></i> Semantic Search Results (${data.results_count})</h4>`;
                data.results.forEach((transcript, i) => {
                    html += `
                    <div style="padding: 1rem; background: rgba(0,0,0,0.3); border-left: 3px solid var(--accent-primary); border-radius: 4px;">
                        <span style="font-size: 0.8rem; color: var(--text-muted); display: block; margin-bottom: 0.5rem">Match #${i+1}</span>
                        <p style="font-size: 0.9rem; line-height: 1.4; margin: 0;">${transcript.substring(0, 300)}${transcript.length > 300 ? '...' : ''}</p>
                    </div>`;
                });
                auditSearchResults.innerHTML = html;
            } else {
                auditSearchResults.innerHTML = '<p style="color: var(--text-muted)">No matching records found in ChromaDB vector store.</p>';
            }
        } catch {
            auditSearchBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Search';
            auditSearchResults.innerHTML = '<p style="color:var(--danger)">Failed to perform semantic search.</p>';
        }
    });
}


// ── Health Check on page load ───────────────────────────────────────
(async function checkHealth() {
    const dot = document.querySelector('.status-dot');
    try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
        if (res.ok) { dot.classList.add('online'); dot.classList.remove('offline'); }
        else { dot.classList.add('offline'); dot.classList.remove('online'); }
    } catch {
        dot.classList.add('offline'); dot.classList.remove('online');
        dot.style.background = 'var(--danger)';
        dot.style.boxShadow = '0 0 8px var(--danger)';
    }
})();
