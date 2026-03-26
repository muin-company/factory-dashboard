// Factory Dashboard V2

const API_URL = '/api/sessions';
const REFRESH_MS = 30000;
let countdown = 30;
let charts = {};
let currentPeriod = 30;

// Canonical agent order: arc first, then alphabetical
const AGENT_ORDER = ['MJ', 'bori', 'mir', 'nova', 'lerobot', 'voice'];

function sortAgentKeys(keys) {
    return keys.slice().sort((a, b) => {
        const ia = AGENT_ORDER.indexOf(a);
        const ib = AGENT_ORDER.indexOf(b);
        if (ia !== -1 && ib !== -1) return ia - ib;
        if (ia !== -1) return -1;
        if (ib !== -1) return 1;
        return a.localeCompare(b);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setupPeriodButtons();
    syncDateInputs();
    fetchData();
    setInterval(() => {
        countdown--;
        document.getElementById('countdown').textContent = countdown;
        if (countdown <= 0) { countdown = 30; fetchData(); }
    }, 1000);
});

function setupPeriodButtons() {
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (btn.dataset.period) {
                currentPeriod = btn.dataset.period;
            } else {
                currentPeriod = parseInt(btn.dataset.days);
            }
            syncDateInputs();
            fetchData();
        });
    });
    document.getElementById('btnApply').addEventListener('click', () => {
        document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
        currentPeriod = -1;
        fetchData();
    });
}

function syncDateInputs() {
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const dfEl = document.getElementById('dateFrom');
    const dtEl = document.getElementById('dateTo');
    dtEl.value = today;

    if (currentPeriod === 'thisWeek') {
        const day = now.getDay();
        const diff = day === 0 ? 6 : day - 1;
        const monday = new Date(now);
        monday.setDate(now.getDate() - diff);
        dfEl.value = monday.toISOString().split('T')[0];
    } else if (currentPeriod === 'thisMonth') {
        const first = new Date(now.getFullYear(), now.getMonth(), 1);
        dfEl.value = first.toISOString().split('T')[0];
    } else if (currentPeriod === 0 || currentPeriod === 'all') {
        dfEl.value = '';
        dtEl.value = '';
    } else if (typeof currentPeriod === 'number' && currentPeriod > 0) {
        const d = new Date();
        d.setDate(d.getDate() - currentPeriod);
        dfEl.value = d.toISOString().split('T')[0];
    }
}

function buildUrl() {
    let url = API_URL;
    const params = [];
    const now = new Date();

    if (currentPeriod === -1) {
        const f = document.getElementById('dateFrom').value;
        const t = document.getElementById('dateTo').value;
        if (f) params.push('from=' + f);
        if (t) params.push('to=' + t);
    } else if (currentPeriod === 'thisWeek') {
        const day = now.getDay();
        const diff = day === 0 ? 6 : day - 1;
        const monday = new Date(now);
        monday.setDate(now.getDate() - diff);
        params.push('from=' + monday.toISOString().split('T')[0]);
    } else if (currentPeriod === 'thisMonth') {
        const first = new Date(now.getFullYear(), now.getMonth(), 1);
        params.push('from=' + first.toISOString().split('T')[0]);
    } else if (currentPeriod > 0) {
        const d = new Date();
        d.setDate(d.getDate() - currentPeriod);
        params.push('from=' + d.toISOString().split('T')[0]);
    }

    if (params.length) url += '?' + params.join('&');
    return url;
}

async function fetchData() {
    try {
        const res = await fetch(buildUrl());
        const data = await res.json();
        if (data.success) render(data);
    } catch (e) {
        console.error('Fetch error:', e);
    }
    countdown = 30;
    // Update last refresh time
    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    const el = document.getElementById('lastRefresh');
    if (el) el.textContent = timeStr;
    // Update period label
    updatePeriodLabel();
}

function updatePeriodLabel() {
    const el = document.getElementById('periodLabel');
    if (!el) return;
    const from = document.getElementById('dateFrom').value;
    const to = document.getElementById('dateTo').value;
    if (from && to) {
        el.textContent = from + ' ~ ' + to;
    } else if (from) {
        el.textContent = from + ' ~ now';
    } else {
        el.textContent = 'All';
    }
}

function render(data) {
    const c = data.cumulative;
    if (!c) return;

    // Subscription total from API
    const subTotal = c.subscriptionTotal || 650;
    document.getElementById('subTotal').textContent = '$' + subTotal.toFixed(2);
    const subBreakdown = c.subscriptionBreakdown || {};
    const parts = [];
    const subLabels = { 'anthropic_max': 'Anthropic', 'openai_pro': 'OpenAI', 'google_ultra': 'Google' };
    for (const [key, d] of Object.entries(subBreakdown)) {
        parts.push((subLabels[key] || key) + ' $' + d.price.toFixed(0));
    }
    document.getElementById('subDetail').textContent = parts.join(' + ');
    document.getElementById('utilDenom').textContent = '$' + subTotal.toFixed(0);

    document.getElementById('apiValue').textContent = '$' + c.totalEstimatedApiCost.toFixed(2);
    document.getElementById('apiValueSub').textContent =
        `daily avg $${c.dailyCost.toFixed(2)} / monthly est $${c.monthlyCost.toFixed(2)}`;
    document.getElementById('totalTokens').textContent = fmtTokens(c.totalTokens);
    document.getElementById('tokenBreakdown').textContent =
        `in: ${fmtTokens(c.totalInput)} / out: ${fmtTokens(c.totalOutput)} / cache: ${fmtTokens(c.totalCacheRead + c.totalCacheWrite)}`;
    document.getElementById('activeDays').textContent = c.activeDays;
    document.getElementById('dateRangeText').textContent =
        c.dateRange.start ? c.dateRange.start.split('T')[0] + ' ~ ' + c.dateRange.end.split('T')[0] : '-';

    // Utilization
    const util = c.utilization || 0;
    document.getElementById('utilPct').textContent = util.toFixed(1) + '%';
    const fill = document.getElementById('utilFill');
    fill.style.width = Math.min(util, 120) / 1.2 + '%';
    fill.className = 'util-fill' + (util > 100 ? ' over' : util > 70 ? ' high' : '');

    renderSubscriptionBreakdown(c.subscriptionBreakdown);

    const agentKeys = sortAgentKeys(Object.keys(c.byAgent));
    renderAgentGrid(c.byAgent, agentKeys);

    // Charts
    renderStackedBarWithCumulative('costByAgentChart', c.dailyCostByAgent, agentKeys, AGENT_COLORS, '$', true);
    renderStackedBarWithCumulative('costByModelChart', c.dailyCostByModel, extractKeysFromDaily(c.dailyCostByModel), MODEL_COLORS, '$', true);
    renderStackedBarWithCumulative('tokensByAgentChart', c.dailyTokensByAgent, agentKeys, AGENT_COLORS, 'tok', false);
    renderStackedBarWithCumulative('tokensByModelChart', c.dailyTokensByModel, extractKeysFromDaily(c.dailyTokensByModel), MODEL_COLORS, 'tok', false);

    renderModelTable(c.byModel);
    renderMatrix(c.agentModelMatrix);
    renderSessions(data.sessions, data.stats);

    const updEl = document.getElementById('lastUpdated');
    if (updEl) updEl.textContent =
        new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function renderSubscriptionBreakdown(subs) {
    const row = document.getElementById('subRow');
    if (!subs) { row.innerHTML = ''; return; }

    const labels = {
        'anthropic_max': 'Anthropic Max',
        'openai_pro': 'OpenAI Pro',
        'google_ultra': 'Google AI Ultra',
    };

    row.innerHTML = Object.entries(subs).map(([key, d]) => {
        const saving = d.savings;
        const savingClass = saving >= 0 ? 'text-green' : 'text-red';
        const savingLabel = saving >= 0 ? `+$${saving.toFixed(2)} saved` : `-$${Math.abs(saving).toFixed(2)}`;
        return `
        <div class="sub-card">
            <div class="sub-name">${labels[key] || key}</div>
            <div class="sub-price">$${d.price.toFixed(2)}/mo</div>
            <div class="sub-detail">
                <span>API equiv: <strong>$${d.estimatedApiCost.toFixed(2)}</strong></span>
                <span class="${savingClass}">${savingLabel}</span>
            </div>
            <div class="sub-util-track">
                <div class="sub-util-fill ${d.utilization > 100 ? 'over' : ''}" style="width:${Math.min(d.utilization, 100)}%"></div>
            </div>
            <div class="sub-util-pct">${d.utilization.toFixed(1)}%</div>
        </div>`;
    }).join('');
}

function renderAgentGrid(byAgent, orderedKeys) {
    const grid = document.getElementById('agentGrid');
    if (!orderedKeys.length) { grid.innerHTML = '<span class="text-muted">No data</span>'; return; }
    grid.innerHTML = orderedKeys.map(name => {
        const d = byAgent[name];
        return `
        <div class="agent-item">
            <div class="agent-color" style="background:${AGENT_COLORS[name] || '#6b7280'}"></div>
            <div class="name">${name}</div>
            <div class="cost">$${d.cost.toFixed(2)}</div>
            <div class="tokens">${fmtTokens(d.tokens)} tokens</div>
            <div class="model">${shortModel(d.model)}</div>
        </div>`;
    }).join('');
}

// --- Colors ---
// Distinct, high-contrast palette for agents
const AGENT_COLORS = {
    MJ:   '#2563eb', // blue
    bolt: '#dc2626', // red
    core: '#059669', // emerald
    dune: '#d97706', // amber
    echo: '#7c3aed', // violet
    flux: '#db2777', // pink
    gem:  '#0891b2', // cyan
    hex:  '#4f46e5', // indigo
};

// Model colors - grouped by family with distinct hues
const MODEL_COLORS = {
    'claude-opus-4-6':   '#1e40af',
    'claude-opus-4':     '#1e3a8a',
    'claude-opus-4-5':   '#1d4ed8',
    'claude-sonnet-4':   '#3b82f6',
    'claude-sonnet-4-20250514': '#60a5fa',
    'claude-haiku-3-5':  '#93c5fd',

    'gemini-3-pro-preview': '#15803d',
    'gemini-2.5-pro':    '#166534',
    'gemini-2.5-flash':  '#4ade80',
    'gemini-2.5-flash-preview-05-20': '#86efac',
    'gemini-3-flash-preview': '#22c55e',

    'gpt-5.3-codex':     '#a16207',

    'grok-4-1-fast':     '#dc2626',
    'grok-4':            '#991b1b',
    'grok-2':            '#f87171',

    'delivery-mirror':   '#9ca3af',
};

const FALLBACK_COLORS = [
    '#0284c7', '#be123c', '#0d9488', '#c2410c', '#6d28d9',
    '#0369a1', '#9f1239', '#047857', '#b45309', '#7e22ce',
];

function extractKeysFromDaily(dailyData) {
    if (!dailyData) return [];
    const keySet = new Set();
    dailyData.forEach(d => Object.keys(d).forEach(k => { if (k !== 'date') keySet.add(k); }));
    return Array.from(keySet);
}

function getColor(name, colorMap) {
    if (colorMap[name]) return colorMap[name];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return FALLBACK_COLORS[Math.abs(hash) % FALLBACK_COLORS.length];
}

function renderStackedBarWithCumulative(canvasId, dailyData, keys, colorMap, unit, isCost) {
    if (!dailyData || !dailyData.length) return;

    const ctx = document.getElementById(canvasId).getContext('2d');
    const labels = dailyData.map(d => d.date.substring(5));

    // Filter keys that have data
    let activeKeys = keys.filter(k => k !== 'date' && dailyData.some(d => (d[k] || 0) > 0));

    // For agent charts, use canonical order; for model charts, sort by total desc
    if (colorMap === AGENT_COLORS) {
        activeKeys = sortAgentKeys(activeKeys);
    } else {
        activeKeys.sort((a, b) => {
            const sumA = dailyData.reduce((s, d) => s + (d[a] || 0), 0);
            const sumB = dailyData.reduce((s, d) => s + (d[b] || 0), 0);
            return sumB - sumA;
        });
    }

    const datasets = activeKeys.map(k => ({
        label: isCost ? shortModel(k) : k,
        data: dailyData.map(d => d[k] || 0),
        backgroundColor: getColor(k, colorMap),
        stack: 'a',
        yAxisID: 'y',
        order: 2,
    }));

    // Cumulative line
    const cumData = [];
    let cum = 0;
    for (const d of dailyData) {
        let dayTotal = 0;
        for (const k of activeKeys) dayTotal += (d[k] || 0);
        cum += dayTotal;
        cumData.push(cum);
    }

    datasets.push({
        label: 'Cumulative',
        data: cumData,
        type: 'line',
        borderColor: '#374151',
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        yAxisID: 'y1',
        order: 1,
    });

    if (charts[canvasId]) charts[canvasId].destroy();

    charts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 10, font: { size: 11 }, filter: item => item.text !== 'Cumulative' }
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const v = ctx.parsed.y;
                            if (ctx.dataset.label === 'Cumulative') {
                                return isCost ? `Cumulative: $${v.toFixed(2)}` : `Cumulative: ${fmtTokens(v)}`;
                            }
                            return isCost ? `${ctx.dataset.label}: $${v.toFixed(2)}` : `${ctx.dataset.label}: ${fmtTokens(v)}`;
                        }
                    }
                }
            },
            scales: {
                x: { stacked: true, ticks: { font: { size: 10 } } },
                y: {
                    stacked: true, position: 'left',
                    ticks: {
                        callback: v => isCost ? '$' + v.toFixed(0) : fmtTokens(v),
                        font: { size: 10 }
                    }
                },
                y1: {
                    position: 'right', grid: { drawOnChartArea: false },
                    ticks: {
                        callback: v => isCost ? '$' + v.toFixed(0) : fmtTokens(v),
                        font: { size: 10 }
                    }
                }
            }
        }
    });
}

// --- Tables ---
function renderModelTable(byModel) {
    const tbody = document.querySelector('#modelTable tbody');
    const sorted = Object.entries(byModel).sort((a, b) => b[1].totalCost - a[1].totalCost);
    if (!sorted.length) { tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No data</td></tr>'; return; }

    const planTags = {
        'subscription': '<span class="tag tag-sub">구독</span>',
        'payperuse': '<span class="tag tag-ppu">종량제</span>',
        'free': '<span class="tag tag-free">무료</span>',
    };

    tbody.innerHTML = sorted.map(([m, d]) => {
        const plan = d.planType || 'free';
        return `<tr>
            <td><strong>${shortModel(m)}</strong></td>
            <td class="text-right fw-bold">$${d.totalCost.toFixed(2)}</td>
            <td class="text-right">$${d.monthlyCost.toFixed(2)}</td>
            <td class="text-right">${fmtTokens(d.input || 0)}</td>
            <td class="text-right">${fmtTokens(d.output || 0)}</td>
            <td class="text-right">${fmtTokens(d.cacheRead || 0)} / ${fmtTokens(d.cacheWrite || 0)}</td>
            <td>${planTags[plan] || planTags['free']}</td>
            <td class="text-muted">${(d.agents || []).join(', ')}</td>
        </tr>`;
    }).join('');
}

function renderMatrix(matrix) {
    if (!matrix || !Object.keys(matrix).length) return;
    const agents = sortAgentKeys(Object.keys(matrix));
    const allModels = new Set();
    agents.forEach(a => Object.keys(matrix[a]).forEach(m => allModels.add(m)));
    const models = [...allModels].sort();

    const thead = document.querySelector('#matrixTable thead tr');
    thead.innerHTML = '<th>Agent</th>' + models.map(m => `<th class="text-right">${shortModel(m)}</th>`).join('') + '<th class="text-right">Total</th>';

    const tbody = document.querySelector('#matrixTable tbody');
    tbody.innerHTML = agents.map(a => {
        let total = 0;
        const cells = models.map(m => {
            const v = matrix[a][m] || 0;
            total += v;
            return `<td class="text-right">${v > 0 ? '$' + v.toFixed(2) : '-'}</td>`;
        }).join('');
        return `<tr><td class="fw-bold">${a}</td>${cells}<td class="text-right fw-bold">$${total.toFixed(2)}</td></tr>`;
    }).join('');
}

function renderSessions(sessions, stats) {
    document.getElementById('sessionCount').textContent = stats.total;
    const tbody = document.querySelector('#sessionTable tbody');
    const all = [...(sessions.subagents || []), ...(sessions.cron || [])];
    if (sessions.main) all.unshift(sessions.main);
    all.sort((a, b) => a.ageMs - b.ageMs);

    if (!all.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No sessions</td></tr>'; return; }
    tbody.innerHTML = all.map(s => `
        <tr>
            <td><span class="status-dot ${s.status}"></span>${s.status}</td>
            <td><code>${s.key || s.id}</code></td>
            <td><span class="tag">${shortModel(s.model)}</span></td>
            <td class="text-right">${fmtAge(s.ageMs)}</td>
            <td class="text-right">${fmtTokens(s.tokens)}</td>
        </tr>
    `).join('');
}

// --- Helpers ---
function fmtTokens(n) {
    if (!n) return '0';
    if (n < 1000) return n.toString();
    if (n < 1e6) return (n / 1e3).toFixed(1) + 'K';
    return (n / 1e6).toFixed(2) + 'M';
}

function fmtAge(ms) {
    const s = Math.floor(ms / 1000);
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    return Math.floor(s / 86400) + 'd';
}

function shortModel(m) {
    if (!m) return '?';
    return m.replace('claude-', '').replace('opus-4-6', 'opus4.6').replace('opus-4-5', 'opus4.5')
        .replace('sonnet-4-20250514', 'sonnet4').replace('sonnet-4', 'sonnet4')
        .replace('haiku-3-5', 'haiku3.5').replace('gemini-3-pro-preview', 'gemini3-pro')
        .replace('gemini-2.5-flash-preview-05-20', 'gemini2.5-flash').replace('gemini-2.5-flash', 'gemini2.5-flash')
        .replace('gemini-2.5-pro', 'gemini2.5-pro').replace('gemini-3-flash-preview', 'gemini3-flash')
        .replace('gpt-5.3-codex', 'codex5.3').replace('grok-4-1-fast', 'grok-fast')
        .replace('delivery-mirror', 'mirror');
}


// ── Task Queue ──────────────────────────────────────

const TASK_API = '/api/tasks';
const STATUS_ICONS = {
    pending: '⏳', queued: '📋', running: '🔄', done: '✅', failed: '❌', cancelled: '🚫'
};

function priorityClass(p) {
    if (p <= 2) return 'p-high';
    if (p <= 4) return 'p-medium';
    if (p <= 6) return 'p-normal';
    return 'p-low';
}

function fmtDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleString('ko-KR', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}

async function fetchTasks() {
    const filter = document.getElementById('taskFilter').value;
    const url = filter ? `${TASK_API}?status=${filter}` : TASK_API;
    try {
        const res = await fetch(url);
        const data = await res.json();
        renderTasks(data.tasks || []);
    } catch (e) {
        document.getElementById('taskTableBody').innerHTML =
            '<tr><td colspan="6" class="text-center text-muted">Failed to load tasks</td></tr>';
    }
}

function renderTasks(tasks) {
    const tbody = document.getElementById('taskTableBody');
    if (!tasks.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No tasks yet — click "+ New Task" to create one</td></tr>';
        return;
    }
    tbody.innerHTML = tasks.map(t => `
        <tr>
            <td class="text-center task-icon">${STATUS_ICONS[t.status] || '❓'}</td>
            <td>
                <strong>${escHtml(t.title)}</strong>
                ${t.description ? `<div class="text-muted" style="font-size:12px;margin-top:2px;">${escHtml(t.description).substring(0,80)}${t.description.length > 80 ? '…' : ''}</div>` : ''}
            </td>
            <td class="text-center"><span class="priority-badge ${priorityClass(t.priority)}">P${t.priority}</span></td>
            <td class="text-center"><span class="task-status ${t.status}">${t.status}</span></td>
            <td style="font-size:12px;">${fmtDate(t.created_at)}</td>
            <td class="text-center">
                <button class="btn-icon" onclick="deleteTask('${t.id}')" title="Delete">🗑️</button>
            </td>
        </tr>
    `).join('');
}

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

async function deleteTask(id) {
    if (!confirm('Delete this task?')) return;
    await fetch(`${TASK_API}/${id}`, { method: 'DELETE' });
    fetchTasks();
}

function setupTaskUI() {
    const modal = document.getElementById('taskModal');
    const btnNew = document.getElementById('btnNewTask');
    const btnClose = document.getElementById('modalClose');
    const btnCancel = document.getElementById('modalCancel');
    const btnCreate = document.getElementById('modalCreate');
    const filterSelect = document.getElementById('taskFilter');

    btnNew.addEventListener('click', () => {
        document.getElementById('taskTitle').value = '';
        document.getElementById('taskDesc').value = '';
        document.getElementById('taskPriority').value = '5';
        document.getElementById('taskStatus').value = 'pending';
        modal.style.display = 'flex';
        document.getElementById('taskTitle').focus();
    });

    btnClose.addEventListener('click', () => modal.style.display = 'none');
    btnCancel.addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

    btnCreate.addEventListener('click', async () => {
        const title = document.getElementById('taskTitle').value.trim();
        if (!title) { alert('Title is required'); return; }
        btnCreate.disabled = true;
        btnCreate.textContent = 'Creating...';
        try {
            await fetch(TASK_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    description: document.getElementById('taskDesc').value,
                    priority: parseInt(document.getElementById('taskPriority').value),
                    status: document.getElementById('taskStatus').value,
                }),
            });
            modal.style.display = 'none';
            fetchTasks();
        } catch (e) {
            alert('Failed to create task');
        } finally {
            btnCreate.disabled = false;
            btnCreate.textContent = 'Create Task';
        }
    });

    filterSelect.addEventListener('change', fetchTasks);

    // Initial load
    fetchTasks();
}

// Hook into DOMContentLoaded
(function() {
    const origReady = window.onload;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => { setupTaskUI(); setupSchedulerUI(); });
    } else {
        setupTaskUI();
        setupSchedulerUI();
    }
})();


// ── Scheduler UI ──────────────────────────────────────

const SCHED_API = '/api/scheduler';
let schedulerPollTimer = null;

function setupSchedulerUI() {
    const toggleBtn = document.getElementById('btnSchedulerToggle');
    const settingsBtn = document.getElementById('btnSchedulerSettings');
    const modal = document.getElementById('schedulerModal');
    const modalClose = document.getElementById('schedModalClose');
    const modalCancel = document.getElementById('schedModalCancel');
    const modalSave = document.getElementById('schedModalSave');

    // Toggle scheduler start/stop
    toggleBtn.addEventListener('click', async () => {
        const badge = document.getElementById('schedulerStatusBadge');
        const isActive = badge.classList.contains('active');
        toggleBtn.disabled = true;
        toggleBtn.textContent = isActive ? 'Stopping...' : 'Starting...';
        try {
            const endpoint = isActive ? `${SCHED_API}/stop` : `${SCHED_API}/start`;
            const res = await fetch(endpoint, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                await fetchSchedulerStatus();
            }
        } catch (e) {
            console.error('Scheduler toggle error:', e);
        } finally {
            toggleBtn.disabled = false;
        }
    });

    // Settings modal
    settingsBtn.addEventListener('click', async () => {
        await loadSchedulerConfig();
        modal.style.display = 'flex';
    });
    modalClose.addEventListener('click', () => modal.style.display = 'none');
    modalCancel.addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

    modalSave.addEventListener('click', async () => {
        modalSave.disabled = true;
        modalSave.textContent = 'Saving...';
        try {
            const whitelist = [];
            document.querySelectorAll('#schedModelChecks input[type=checkbox]:checked').forEach(cb => {
                whitelist.push(cb.value);
            });

            const config = {
                max_concurrent: parseInt(document.getElementById('schedCfgMaxConcurrent').value),
                daily_budget: parseFloat(document.getElementById('schedCfgDailyBudget').value),
                poll_interval: parseInt(document.getElementById('schedCfgPollInterval').value),
                timeout_seconds: parseInt(document.getElementById('schedCfgTimeout').value),
                model_whitelist: whitelist,
                default_model: document.getElementById('schedCfgDefaultModel').value,
                dry_run: document.getElementById('schedCfgDryRun').checked,
            };

            await fetch(`${SCHED_API}/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            modal.style.display = 'none';
            await fetchSchedulerStatus();
        } catch (e) {
            alert('Failed to save settings');
        } finally {
            modalSave.disabled = false;
            modalSave.textContent = 'Save Settings';
        }
    });

    // Initial fetch + periodic polling
    fetchSchedulerStatus();
    schedulerPollTimer = setInterval(fetchSchedulerStatus, 10000);
}

async function fetchSchedulerStatus() {
    try {
        const res = await fetch(`${SCHED_API}/status`);
        const data = await res.json();
        if (data.success) {
            renderSchedulerStatus(data);
        }
    } catch (e) {
        console.error('Scheduler status error:', e);
    }
}

function renderSchedulerStatus(data) {
    const badge = document.getElementById('schedulerStatusBadge');
    const toggleBtn = document.getElementById('btnSchedulerToggle');
    const isActive = data.is_running;

    badge.textContent = isActive ? 'ACTIVE' : 'OFF';
    badge.className = 'scheduler-status ' + (isActive ? 'active' : 'inactive');
    toggleBtn.textContent = isActive ? 'Stop' : 'Start';
    toggleBtn.style.background = isActive ? 'var(--red)' : 'var(--accent)';

    document.getElementById('schedActiveAgents').textContent = data.active_agents || 0;
    document.getElementById('schedMaxConcurrent').textContent = data.config?.max_concurrent || 3;
    document.getElementById('schedPendingTasks').textContent = data.pending_tasks || 0;
    document.getElementById('schedBudgetUsed').textContent = '$' + (data.today_cost || 0).toFixed(2);
    document.getElementById('schedBudgetLimit').textContent = (data.daily_budget || 20).toFixed(2);

    const stats = data.stats || {};
    document.getElementById('schedTotalSpawned').textContent = stats.total_spawned || 0;
    document.getElementById('schedCompleted').textContent = stats.total_completed || 0;
    document.getElementById('schedFailed').textContent = stats.total_failed || 0;

    // Recent spawns log
    const spawns = data.recent_spawns || [];
    const logDiv = document.getElementById('schedulerLog');
    const logBody = document.getElementById('schedulerLogBody');

    if (spawns.length > 0) {
        logDiv.style.display = 'block';
        logBody.innerHTML = spawns.slice().reverse().map(s => {
            const time = s.timestamp ? new Date(s.timestamp).toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit', second:'2-digit'}) : '-';
            const dryTag = s.dry_run ? '<span class="scheduler-log-dry">DRY-RUN</span>' : '';
            return `<div class="scheduler-log-item">
                <span class="scheduler-log-time">${time}</span>
                <span class="scheduler-log-task">${escHtml(s.title || s.task_id)}</span>
                ${dryTag}
                <span class="text-muted">${shortModel(s.model || '')}</span>
            </div>`;
        }).join('');
    } else {
        logDiv.style.display = 'none';
    }
}

async function loadSchedulerConfig() {
    try {
        const res = await fetch(`${SCHED_API}/config`);
        const data = await res.json();
        if (!data.success) return;
        const cfg = data.config;

        document.getElementById('schedCfgMaxConcurrent').value = cfg.max_concurrent || 3;
        document.getElementById('schedCfgDailyBudget').value = cfg.daily_budget || 20;
        document.getElementById('schedCfgPollInterval').value = cfg.poll_interval || 30;
        document.getElementById('schedCfgTimeout').value = cfg.timeout_seconds || 600;
        document.getElementById('schedCfgDefaultModel').value = cfg.default_model || 'anthropic/claude-sonnet-4';
        document.getElementById('schedCfgDryRun').checked = cfg.dry_run || false;

        // Model whitelist
        const whitelist = cfg.model_whitelist || ['opus', 'sonnet'];
        document.querySelectorAll('#schedModelChecks input[type=checkbox]').forEach(cb => {
            cb.checked = whitelist.includes(cb.value);
        });
    } catch (e) {
        console.error('Failed to load scheduler config:', e);
    }
}
