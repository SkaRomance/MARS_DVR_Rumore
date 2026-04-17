# Wave 29 — Frontend P0 Completion

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. Vanilla JS, no framework. Dipende da Wave 27 (SSE endpoint + suggestion API).

**Goal:** Completare il frontend Rumore con: ModuleBootstrap iframe handshake, AutopilotView con progress streaming SSE, SuggestionCard con approve/reject, SafeEditor con undo/redo + paste sanitization, AuditTrailPanel con filtri + export CSV, design tokens condivisi con MARS.

**Architecture:** File statici in `static/`. Nuovo layer `views/` per pagine logiche, `components/` per componenti riutilizzabili, `lib/` per utility. Refactor minimo di `app.js` per supportare lifecycle `onMount`/`onUnmount` e prevenire memory leak.

**Tech Stack:** Vanilla JS (ES2020+), HTML5, CSS3, DOMPurify (CDN or bundled), EventSource API nativa.

**Stima:** 4h.

---

## Pre-requisiti

- Wave 26+27 done (backend endpoints live)
- Branch work: `noise-thin-plugin-refactor`

---

## Task 1: ModuleBootstrap — iframe handshake JWT

**Files:**
- Create: `static/js/module-bootstrap.js`
- Modify: `static/index.html` (aggiungi script load)
- Test: manual in browser con parent postMessage mock

- [ ] **Step 1.1: Implementa module bootstrap**

File: `static/js/module-bootstrap.js`

```javascript
/**
 * Module Bootstrap — handshake con parent MARS web via postMessage.
 *
 * Flow:
 *   1. Iframe si carica, signal "ready" al parent
 *   2. Parent risponde con {type: "ready", payload: {moduleKey, dvrDocumentId, revisionId, accessToken, marsApiBaseUrl}}
 *   3. Iframe salva token, setup ApiClient, carica view iniziale
 *
 * Fallback standalone (no iframe parent):
 *   Se nessun postMessage entro 3s, usa query string ?dev=1 con token in URL.
 */
(function () {
    'use strict';

    const READY_TIMEOUT_MS = 3000;
    const EXPECTED_PARENT_ORIGIN = new URL(document.referrer || 'http://localhost:5173').origin;

    window.ModuleBootstrap = {
        context: null,  // populated on handshake
        ready: false,
        _listeners: [],

        onReady(cb) {
            if (this.ready) {
                cb(this.context);
            } else {
                this._listeners.push(cb);
            }
        },

        _signalReady() {
            if (window.parent !== window) {
                window.parent.postMessage({ type: 'ready' }, EXPECTED_PARENT_ORIGIN);
            }
        },

        _handleParentMessage(ev) {
            if (ev.origin !== EXPECTED_PARENT_ORIGIN) return;
            if (!ev.data || typeof ev.data !== 'object') return;
            if (ev.data.type !== 'ready' || !ev.data.payload) return;

            const { moduleKey, dvrDocumentId, revisionId, accessToken, marsApiBaseUrl } = ev.data.payload;
            this.context = {
                moduleKey,
                dvrDocumentId,
                revisionId,
                accessToken,
                marsApiBaseUrl,
                parentOrigin: ev.origin,
            };

            // Store token in sessionStorage (not localStorage) for iframe isolation
            sessionStorage.setItem('mars_access_token', accessToken);
            sessionStorage.setItem('mars_dvr_doc_id', dvrDocumentId);
            sessionStorage.setItem('mars_revision_id', revisionId);

            this.ready = true;
            this._listeners.forEach((cb) => cb(this.context));
            this._listeners = [];
        },

        _fallbackFromQueryString() {
            const params = new URLSearchParams(window.location.search);
            const devToken = params.get('token');
            const docId = params.get('dvr_doc_id');
            const revId = params.get('revision_id');

            if (devToken && docId && revId) {
                this.context = {
                    moduleKey: 'noise',
                    dvrDocumentId: docId,
                    revisionId: revId,
                    accessToken: devToken,
                    marsApiBaseUrl: params.get('mars_api') || 'http://localhost:5000',
                    parentOrigin: null,
                };
                sessionStorage.setItem('mars_access_token', devToken);
                this.ready = true;
                this._listeners.forEach((cb) => cb(this.context));
                this._listeners = [];
                return true;
            }
            return false;
        },

        close() {
            if (this.context?.parentOrigin) {
                window.parent.postMessage({ type: 'close' }, this.context.parentOrigin);
            } else {
                window.close();
            }
        },

        refresh() {
            if (this.context?.parentOrigin) {
                window.parent.postMessage({ type: 'refresh' }, this.context.parentOrigin);
            }
        },

        error(message) {
            if (this.context?.parentOrigin) {
                window.parent.postMessage({ type: 'error', payload: { message } }, this.context.parentOrigin);
            }
        },

        init() {
            window.addEventListener('message', (ev) => this._handleParentMessage(ev));

            // Signal ready to parent
            this._signalReady();

            // Fallback: if no parent response within timeout, use query params
            setTimeout(() => {
                if (!this.ready) {
                    if (!this._fallbackFromQueryString()) {
                        console.warn('ModuleBootstrap: no parent handshake and no query string fallback');
                        // Last-ditch: show a login/debug panel
                        document.body.innerHTML = '<div style="padding:40px;font-family:sans-serif;"><h1>Modulo Rumore</h1><p>Accesso non autorizzato. Apri questo modulo da MARS web.</p></div>';
                    }
                }
            }, READY_TIMEOUT_MS);
        },
    };

    document.addEventListener('DOMContentLoaded', () => window.ModuleBootstrap.init());
})();
```

- [ ] **Step 1.2: Update index.html**

File: `static/index.html`

Aggiungi prima di `app.js`:

```html
<script src="js/module-bootstrap.js"></script>
<script src="js/api-client.js"></script>
<script src="js/app.js"></script>
```

- [ ] **Step 1.3: Commit**

```bash
git add static/js/module-bootstrap.js static/index.html
git commit -m "Wave 29.1: Add ModuleBootstrap for iframe handshake

postMessage-based handshake with MARS parent web.
Fallback to query string in dev (?token=...&dvr_doc_id=...&revision_id=...).
Exposes close/refresh/error methods for parent communication.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Refactor ApiClient per MARS context

**Scope:** Il client attuale usa localStorage per JWT e endpoint `/api/v1/noise/auth`. Va refactorizzato per usare `ModuleBootstrap.context.accessToken`, timeout 30s, retry esponenziale.

**Files:**
- Modify: `static/js/api-client.js`
- Test: manual browser

- [ ] **Step 2.1: Refactor**

File: `static/js/api-client.js` — sostituisci logica auth:

```javascript
class APIClient {
    constructor() {
        this.baseUrl = '';  // same-origin for FastAPI static mount
        this.defaultTimeout = 30000;
        this.maxRetries = 2;
    }

    _getToken() {
        if (window.ModuleBootstrap?.context?.accessToken) {
            return window.ModuleBootstrap.context.accessToken;
        }
        return sessionStorage.getItem('mars_access_token') || '';
    }

    async request(path, { method = 'GET', body, headers = {}, timeout, signal } = {}) {
        const url = this.baseUrl + path;
        const token = this._getToken();

        const reqHeaders = {
            'Accept': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...headers,
        };

        const isFormData = body instanceof FormData;
        if (body && !isFormData && !reqHeaders['Content-Type']) {
            reqHeaders['Content-Type'] = 'application/json';
        }

        const ctrl = new AbortController();
        const timeoutMs = timeout ?? this.defaultTimeout;
        const timer = setTimeout(() => ctrl.abort(), timeoutMs);

        if (signal) {
            signal.addEventListener('abort', () => ctrl.abort());
        }

        let lastError = null;
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                const response = await fetch(url, {
                    method,
                    headers: reqHeaders,
                    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
                    signal: ctrl.signal,
                });

                clearTimeout(timer);

                if (response.status === 401) {
                    window.ModuleBootstrap?.refresh?.();
                    throw new APIError('Session expired', 401, null);
                }
                if (response.status === 402) {
                    throw new APIError('Module not purchased', 402, await response.json().catch(() => null));
                }
                if (response.status >= 500 && attempt < this.maxRetries) {
                    await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt));
                    continue;
                }
                if (!response.ok) {
                    const detail = await response.json().catch(() => ({ detail: response.statusText }));
                    throw new APIError(detail.detail || response.statusText, response.status, detail);
                }

                const ct = response.headers.get('Content-Type') || '';
                if (ct.includes('application/json')) return await response.json();
                if (ct.startsWith('text/')) return await response.text();
                return await response.blob();
            } catch (err) {
                lastError = err;
                if (err.name === 'AbortError') {
                    throw new APIError('Request timeout', 408, null);
                }
                if (attempt >= this.maxRetries) throw err;
            }
        }
        throw lastError;
    }

    // Noise-specific methods
    bootstrapContext(dvrDocumentId, revisionId) {
        return this.request('/api/v1/noise/contexts/bootstrap', {
            method: 'POST',
            body: { mars_dvr_document_id: dvrDocumentId, mars_revision_id: revisionId },
        });
    }

    runAutopilot(contextId, eventCallback) {
        // SSE endpoint — returns EventSource-like iterator
        const url = `${this.baseUrl}/api/v1/noise/autopilot/${contextId}/run`;
        return this._sseRequest(url, eventCallback);
    }

    async _sseRequest(url, eventCallback) {
        const token = this._getToken();
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'text/event-stream' },
        });

        if (!response.ok) throw new APIError('SSE request failed', response.status, null);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();  // last partial line

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        eventCallback(data);
                        if (data.kind === 'completed' || data.kind === 'failed') {
                            return data;
                        }
                    } catch (e) {
                        console.warn('SSE parse error:', e);
                    }
                }
            }
        }
    }

    getAutopilotStatus(contextId) {
        return this.request(`/api/v1/noise/autopilot/${contextId}/status`);
    }

    listSuggestions(contextId, statusFilter) {
        let path = `/api/v1/noise/suggestions/by-context/${contextId}`;
        if (statusFilter) path += `?status_filter=${encodeURIComponent(statusFilter)}`;
        return this.request(path);
    }

    approveSuggestion(suggestionId, editedPayload = null) {
        return this.request(`/api/v1/noise/suggestions/${suggestionId}/approve`, {
            method: 'POST',
            body: editedPayload ? { edited_payload: editedPayload } : {},
        });
    }

    rejectSuggestion(suggestionId, reason = null) {
        return this.request(`/api/v1/noise/suggestions/${suggestionId}/reject`, {
            method: 'POST',
            body: { reason },
        });
    }

    bulkSuggestionAction(suggestionIds, action, options = {}) {
        return this.request('/api/v1/noise/suggestions/bulk', {
            method: 'POST',
            body: { suggestion_ids: suggestionIds, action, ...options },
        });
    }

    // ... other methods existing (assessments, companies, etc.)
}

class APIError extends Error {
    constructor(message, status, detail) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.detail = detail;
    }
}

window.apiClient = new APIClient();
window.APIError = APIError;
```

- [ ] **Step 2.2: Commit**

```bash
git add static/js/api-client.js
git commit -m "Wave 29.2: Refactor APIClient — MARS context, timeout, retry, SSE

- Bearer token from ModuleBootstrap.context (fallback sessionStorage)
- 30s default timeout with AbortController
- Exponential backoff retry on 5xx (max 2)
- 401 triggers ModuleBootstrap.refresh()
- New methods: bootstrapContext, runAutopilot (SSE), suggestion ops

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: AutopilotView — progress streaming + result dashboard

**Files:**
- Create: `static/js/views/autopilot.js`
- Create: `static/css/autopilot.css`

- [ ] **Step 3.1: Implementa view**

File: `static/js/views/autopilot.js`

```javascript
/**
 * AutopilotView — landing page del valutazione rumore.
 * Stati: idle -> running (progress) -> completed (dashboard) | failed (error UI).
 */
class AutopilotView {
    constructor(container, contextId) {
        this.container = container;
        this.contextId = contextId;
        this.state = 'idle';  // idle | running | completed | failed
        this.events = [];
        this.finalPayload = null;
    }

    render() {
        this.container.innerHTML = `
            <div class="autopilot-view" id="autopilot-view">
                <header class="autopilot-header">
                    <h1>Valutazione AI Rischio Rumore</h1>
                    <div class="autopilot-subhead" id="autopilot-subhead">Pronto per iniziare</div>
                </header>

                <section class="autopilot-actions" id="autopilot-actions">
                    <button class="btn btn-primary btn-lg" id="btn-start">
                        🤖 Avvia Valutazione AI
                    </button>
                    <button class="btn btn-ghost" id="btn-manual">
                        Modalità manuale
                    </button>
                </section>

                <section class="autopilot-progress hidden" id="autopilot-progress">
                    <div class="progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                        <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
                    </div>
                    <div class="progress-percent" id="progress-percent">0%</div>
                    <ul class="progress-steps" id="progress-steps"></ul>
                </section>

                <section class="autopilot-result hidden" id="autopilot-result"></section>

                <section class="autopilot-error hidden" id="autopilot-error"></section>
            </div>
        `;

        this._bindEvents();
    }

    _bindEvents() {
        document.getElementById('btn-start').addEventListener('click', () => this.startAutopilot());
        document.getElementById('btn-manual').addEventListener('click', () => {
            window.dispatchEvent(new CustomEvent('navigate:manual', { detail: { contextId: this.contextId } }));
        });
    }

    async startAutopilot() {
        this.state = 'running';
        this._showProgress();

        try {
            const result = await window.apiClient.runAutopilot(this.contextId, (event) => {
                this._handleEvent(event);
            });

            this.finalPayload = result;
            if (result.kind === 'completed') {
                this.state = 'completed';
                this._showResult(result);
            } else {
                this.state = 'failed';
                this._showError(result.message || 'Autopilot fallito');
            }
        } catch (err) {
            this.state = 'failed';
            this._showError(err.message || String(err));
        }
    }

    _handleEvent(event) {
        this.events.push(event);

        const percent = event.progress_percent;
        if (percent != null) {
            const fill = document.getElementById('progress-fill');
            const pct = document.getElementById('progress-percent');
            fill.style.width = `${percent}%`;
            fill.parentElement.setAttribute('aria-valuenow', String(percent));
            pct.textContent = `${percent}%`;
        }

        const stepsList = document.getElementById('progress-steps');
        const li = document.createElement('li');
        li.className = `step step-${event.kind}`;
        const icon = this._iconForKind(event.kind);
        li.innerHTML = `<span class="step-icon">${icon}</span><span class="step-label">${this._labelForStep(event.step)}</span><span class="step-extra">${this._extraForPayload(event.payload)}</span>`;
        stepsList.appendChild(li);
    }

    _iconForKind(kind) {
        const map = {
            started: '▶️',
            step_started: '⏳',
            step_completed: '✅',
            step_failed: '❌',
            completed: '🎉',
            failed: '💥',
            progress: '•',
        };
        return map[kind] || '•';
    }

    _labelForStep(step) {
        const map = {
            initialize: 'Inizializzazione',
            parse_dvr: 'Importazione DVR',
            source_detection: 'Identificazione sorgenti (PAF)',
            exposure_estimation: 'Stima esposizione',
            iso_9612_calc: 'Calcolo LEX,8h',
            review: 'Validazione incrociata',
            mitigation: 'Misure di mitigazione',
            narrative: 'Generazione narrativa DVR',
            persist: 'Salvataggio dati',
            done: 'Completato',
        };
        return map[step] || step;
    }

    _extraForPayload(payload) {
        if (!payload) return '';
        if (payload.candidates_count != null) return `${payload.candidates_count} candidati`;
        if (payload.matched_count != null) return `${payload.matched_count}/${payload.total} match`;
        if (payload.estimates_count != null) return `${payload.estimates_count} stime`;
        if (payload.lex_8h_db != null) return `LEX=${payload.lex_8h_db.toFixed(1)}dB (${payload.risk_band})`;
        if (payload.measures_count != null) return `${payload.measures_count} misure`;
        if (payload.sections_count != null) return `${payload.sections_count} sezioni`;
        return '';
    }

    _showProgress() {
        document.getElementById('autopilot-actions').classList.add('hidden');
        document.getElementById('autopilot-progress').classList.remove('hidden');
        document.getElementById('autopilot-subhead').textContent = 'Autopilot AI in corso...';
    }

    _showResult(result) {
        const { lex_8h_db, risk_band, confidence, duration_s } = result.payload || {};
        document.getElementById('autopilot-progress').classList.add('hidden');
        const resultEl = document.getElementById('autopilot-result');
        resultEl.classList.remove('hidden');

        const riskClass = `risk-${risk_band}`;
        resultEl.innerHTML = `
            <div class="result-card ${riskClass}">
                <div class="result-icon">✨</div>
                <h2>Valutazione AI completata in ${Math.round(duration_s)}s</h2>
                <p>Confidence complessiva: <strong>${(confidence * 100).toFixed(0)}%</strong></p>
                <div class="result-stats">
                    <div class="stat">
                        <div class="stat-label">LEX,8h medio</div>
                        <div class="stat-value">${lex_8h_db.toFixed(1)} <small>dB(A)</small></div>
                    </div>
                    <div class="stat stat-risk">
                        <div class="stat-label">Banda di rischio</div>
                        <div class="stat-value">${risk_band.toUpperCase()}</div>
                    </div>
                </div>
                <div class="result-actions">
                    <button class="btn btn-primary" id="btn-review">Rivedi suggerimenti</button>
                    <button class="btn" id="btn-approve-all">Approva tutto</button>
                    <button class="btn btn-ghost" id="btn-edit-manual">Modifica manualmente</button>
                </div>
            </div>
        `;

        document.getElementById('btn-review').addEventListener('click', () =>
            window.dispatchEvent(new CustomEvent('navigate:suggestions', { detail: { contextId: this.contextId } }))
        );

        document.getElementById('btn-approve-all').addEventListener('click', () => this._approveAll());

        document.getElementById('btn-edit-manual').addEventListener('click', () =>
            window.dispatchEvent(new CustomEvent('navigate:manual', { detail: { contextId: this.contextId } }))
        );
    }

    async _approveAll() {
        const suggestions = await window.apiClient.listSuggestions(this.contextId, 'pending');
        const ids = suggestions.map((s) => s.id);
        if (!ids.length) {
            window.showToast?.('Nessun suggerimento pendente', 'info');
            return;
        }
        const result = await window.apiClient.bulkSuggestionAction(ids, 'approve', { min_confidence: 0.6 });
        window.showToast?.(`Approvati ${result.processed}/${result.total_requested}`, 'success');
    }

    _showError(message) {
        document.getElementById('autopilot-progress').classList.add('hidden');
        const errEl = document.getElementById('autopilot-error');
        errEl.classList.remove('hidden');
        errEl.innerHTML = `
            <div class="error-card">
                <h2>❌ Autopilot fallito</h2>
                <p>${this._escapeHtml(message)}</p>
                <button class="btn" id="btn-retry">Riprova</button>
                <button class="btn btn-ghost" id="btn-manual-fallback">Modalità manuale</button>
            </div>
        `;
        document.getElementById('btn-retry').addEventListener('click', () => {
            this.events = [];
            document.getElementById('progress-steps').innerHTML = '';
            document.getElementById('autopilot-error').classList.add('hidden');
            this.startAutopilot();
        });
    }

    _escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    unmount() {
        // Cleanup event listeners (already released when DOM replaced)
    }
}

window.AutopilotView = AutopilotView;
```

- [ ] **Step 3.2: CSS**

File: `static/css/autopilot.css`

```css
.autopilot-view { max-width: 860px; margin: 40px auto; padding: 0 20px; }
.autopilot-header h1 { font-size: 28px; margin: 0 0 8px; }
.autopilot-subhead { color: var(--text-muted, #6b7280); margin-bottom: 32px; }
.autopilot-actions { display: flex; gap: 12px; margin: 24px 0; }
.btn-lg { padding: 14px 28px; font-size: 16px; }
.progress-bar { height: 8px; background: #e5e7eb; border-radius: 999px; overflow: hidden; margin: 16px 0 8px; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }
.progress-percent { font-weight: 600; text-align: right; margin-bottom: 24px; }
.progress-steps { list-style: none; padding: 0; }
.progress-steps .step { display: flex; align-items: center; gap: 12px; padding: 8px 0; font-size: 14px; }
.step-icon { width: 24px; }
.step-label { flex: 1; }
.step-extra { color: var(--text-muted, #6b7280); font-size: 13px; }
.step-step_failed { color: #dc2626; }
.result-card { padding: 24px; border-radius: 12px; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }
.result-card.risk-red { border-top: 4px solid #dc2626; }
.result-card.risk-orange { border-top: 4px solid #ea580c; }
.result-card.risk-yellow { border-top: 4px solid #ca8a04; }
.result-card.risk-green { border-top: 4px solid #16a34a; }
.result-icon { font-size: 48px; }
.result-stats { display: flex; justify-content: center; gap: 40px; margin: 24px 0; }
.stat-value { font-size: 32px; font-weight: 700; }
.stat-value small { font-size: 16px; font-weight: 400; color: var(--text-muted, #6b7280); }
.result-actions { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
.error-card { padding: 24px; border-radius: 12px; border: 2px solid #fecaca; background: #fef2f2; text-align: center; }
.hidden { display: none !important; }
```

Link nel `<head>` di index.html:
```html
<link rel="stylesheet" href="css/autopilot.css">
```

- [ ] **Step 3.3: Commit**

```bash
git add static/js/views/autopilot.js static/css/autopilot.css static/index.html
git commit -m "Wave 29.3: Add AutopilotView with SSE progress + result dashboard

Landing UI: start button -> SSE streaming progress with step list
-> result card with LEX/risk band stats + action buttons.
Fallback to error UI with retry button on failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: SuggestionCard + approve/reject UI

**Files:**
- Create: `static/js/components/suggestion-card.js`
- Create: `static/js/views/suggestions-view.js`
- Create: `static/css/suggestions.css`

- [ ] **Step 4.1: SuggestionCard component**

File: `static/js/components/suggestion-card.js`

```javascript
/**
 * SuggestionCard — renders a single AISuggestion with approve/reject actions.
 */
class SuggestionCard {
    constructor(suggestion, options = {}) {
        this.suggestion = suggestion;
        this.onAction = options.onAction || (() => {});
        this.selectable = options.selectable ?? false;
        this.selected = false;
        this.el = null;
    }

    render() {
        const s = this.suggestion;
        const card = document.createElement('article');
        card.className = `suggestion-card status-${s.status}`;
        card.setAttribute('data-suggestion-id', s.id);

        const confidence = s.confidence != null ? Math.round(s.confidence * 100) : null;
        const conflPct = confidence != null ? `<span class="conf-badge conf-${confidence >= 80 ? 'high' : confidence >= 50 ? 'mid' : 'low'}">${confidence}%</span>` : '';

        card.innerHTML = `
            ${this.selectable ? `<label class="suggestion-select"><input type="checkbox" class="js-select"></label>` : ''}
            <div class="suggestion-header">
                <span class="suggestion-type">${this._labelType(s.suggestion_type)}</span>
                ${conflPct}
                <span class="suggestion-status">${s.status}</span>
            </div>
            <div class="suggestion-body">
                ${this._renderPayload(s)}
            </div>
            <div class="suggestion-actions" ${s.status !== 'pending' ? 'style="display:none"' : ''}>
                <button class="btn btn-sm btn-primary js-approve">✓ Approva</button>
                <button class="btn btn-sm js-approve-edit">✏️ Approva con modifiche</button>
                <button class="btn btn-sm btn-ghost js-reject">✗ Rifiuta</button>
            </div>
        `;

        this.el = card;
        this._bindEvents();
        return card;
    }

    _labelType(type) {
        const map = {
            phase_laeq: 'Stima esposizione fase',
            phase_duration: 'Durata esposizione',
            mitigation: 'Misura di mitigazione',
            training: 'Formazione richiesta',
            narrative_section: 'Sezione DVR',
            k_correction: 'Correzione K',
        };
        return map[type] || type;
    }

    _renderPayload(s) {
        const p = s.payload_json;
        switch (s.suggestion_type) {
            case 'phase_laeq':
                return `
                    <div class="payload-field"><b>LAeq:</b> ${p.laeq_db?.toFixed(1)} dB(A)</div>
                    <div class="payload-field"><b>Durata:</b> ${p.duration_hours?.toFixed(1)} h/g</div>
                    ${p.lcpeak_db ? `<div class="payload-field"><b>LCpeak:</b> ${p.lcpeak_db} dB(C)</div>` : ''}
                    ${p.k_corrections?.k_tone ? `<div class="payload-field"><b>K_T:</b> +${p.k_corrections.k_tone} dB (${p.k_corrections.reasoning || 'tonale'})</div>` : ''}
                    <div class="payload-reasoning">${this._escapeHtml(p.reasoning || '')}</div>
                    ${p.data_gaps?.length ? `<div class="payload-gaps"><b>Dati mancanti:</b><ul>${p.data_gaps.map((g) => `<li>${this._escapeHtml(g)}</li>`).join('')}</ul></div>` : ''}
                `;
            case 'mitigation':
                return `
                    <div class="payload-field"><b>Tipo:</b> ${p.type || 'tecnica'}</div>
                    <div class="payload-field"><b>Titolo:</b> ${this._escapeHtml(p.title || '')}</div>
                    <div class="payload-reasoning">${this._escapeHtml(p.description || '')}</div>
                    ${p.estimated_reduction_db ? `<div class="payload-field"><b>Riduzione stimata:</b> -${p.estimated_reduction_db} dB</div>` : ''}
                `;
            case 'narrative_section':
                return `
                    <div class="payload-field"><b>Sezione:</b> ${p.section_key}</div>
                    <div class="payload-narrative">${p.content_html?.substring(0, 400) || ''}${(p.content_html?.length || 0) > 400 ? '…' : ''}</div>
                `;
            default:
                return `<pre>${this._escapeHtml(JSON.stringify(p, null, 2))}</pre>`;
        }
    }

    _bindEvents() {
        const $ = (sel) => this.el.querySelector(sel);
        $('.js-approve')?.addEventListener('click', () => this._doAction('approve'));
        $('.js-approve-edit')?.addEventListener('click', () => this._doAction('approve-edit'));
        $('.js-reject')?.addEventListener('click', () => this._doAction('reject'));

        const chk = $('.js-select');
        if (chk) {
            chk.addEventListener('change', (e) => {
                this.selected = e.target.checked;
                this.onAction('select', { suggestion: this.suggestion, selected: this.selected });
            });
        }
    }

    async _doAction(action) {
        if (action === 'approve') {
            try {
                const updated = await window.apiClient.approveSuggestion(this.suggestion.id);
                this.suggestion = updated;
                this._refresh();
                window.showToast?.('Approvato', 'success');
                this.onAction('approved', { suggestion: updated });
            } catch (err) {
                window.showToast?.(`Errore: ${err.message}`, 'error');
            }
        } else if (action === 'approve-edit') {
            this._openEditModal();
        } else if (action === 'reject') {
            const reason = prompt('Motivo del rifiuto (opzionale):');
            try {
                const updated = await window.apiClient.rejectSuggestion(this.suggestion.id, reason);
                this.suggestion = updated;
                this._refresh();
                this.onAction('rejected', { suggestion: updated });
            } catch (err) {
                window.showToast?.(`Errore: ${err.message}`, 'error');
            }
        }
    }

    _openEditModal() {
        const textarea = `<textarea class="js-edit-json" rows="10" style="width:100%;font-family:monospace;">${this._escapeHtml(JSON.stringify(this.suggestion.payload_json, null, 2))}</textarea>`;
        window.showModal?.('Modifica prima di approvare', textarea, async () => {
            const raw = document.querySelector('.js-edit-json').value;
            try {
                const edited = JSON.parse(raw);
                const updated = await window.apiClient.approveSuggestion(this.suggestion.id, edited);
                this.suggestion = updated;
                this._refresh();
                this.onAction('approved', { suggestion: updated });
                return true;
            } catch (err) {
                window.showToast?.(`JSON non valido o errore: ${err.message}`, 'error');
                return false;
            }
        });
    }

    _refresh() {
        const newEl = this.render();
        this.el.replaceWith(newEl);
    }

    _escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }
}

window.SuggestionCard = SuggestionCard;
```

- [ ] **Step 4.2: SuggestionsView (list + bulk)**

File: `static/js/views/suggestions-view.js`

```javascript
class SuggestionsView {
    constructor(container, contextId) {
        this.container = container;
        this.contextId = contextId;
        this.suggestions = [];
        this.filter = 'pending';
        this.selected = new Set();
    }

    async render() {
        this.container.innerHTML = `
            <header class="suggestions-header">
                <h1>Suggerimenti AI</h1>
                <div class="filter-bar">
                    <label><input type="radio" name="filter" value="pending" checked> Pendenti</label>
                    <label><input type="radio" name="filter" value="approved"> Approvati</label>
                    <label><input type="radio" name="filter" value="rejected"> Rifiutati</label>
                </div>
                <div class="bulk-bar hidden" id="bulk-bar">
                    <span id="bulk-count">0 selezionati</span>
                    <button class="btn btn-sm btn-primary" id="btn-bulk-approve">Approva selezionati</button>
                    <button class="btn btn-sm btn-ghost" id="btn-bulk-reject">Rifiuta selezionati</button>
                </div>
            </header>
            <section class="suggestions-list" id="suggestions-list"></section>
        `;

        this.container.querySelectorAll('input[name="filter"]').forEach((rb) => {
            rb.addEventListener('change', (e) => {
                this.filter = e.target.value;
                this.selected.clear();
                this._updateBulkBar();
                this.loadAndRender();
            });
        });

        document.getElementById('btn-bulk-approve').addEventListener('click', () => this._bulk('approve'));
        document.getElementById('btn-bulk-reject').addEventListener('click', () => this._bulk('reject'));

        await this.loadAndRender();
    }

    async loadAndRender() {
        const list = document.getElementById('suggestions-list');
        list.innerHTML = '<div class="loader">Caricamento...</div>';

        try {
            this.suggestions = await window.apiClient.listSuggestions(this.contextId, this.filter);
        } catch (err) {
            list.innerHTML = `<div class="error">Errore: ${err.message}</div>`;
            return;
        }

        list.innerHTML = '';
        if (!this.suggestions.length) {
            list.innerHTML = `<div class="empty">Nessun suggerimento ${this.filter}</div>`;
            return;
        }

        for (const s of this.suggestions) {
            const card = new SuggestionCard(s, {
                selectable: this.filter === 'pending',
                onAction: (action, detail) => this._onCardAction(action, detail),
            });
            list.appendChild(card.render());
        }
    }

    _onCardAction(action, detail) {
        if (action === 'select') {
            if (detail.selected) this.selected.add(detail.suggestion.id);
            else this.selected.delete(detail.suggestion.id);
            this._updateBulkBar();
        } else if (action === 'approved' || action === 'rejected') {
            // Remove from pending list if filter is pending
            if (this.filter === 'pending') this.loadAndRender();
        }
    }

    _updateBulkBar() {
        const bar = document.getElementById('bulk-bar');
        const count = this.selected.size;
        if (count > 0) {
            bar.classList.remove('hidden');
            document.getElementById('bulk-count').textContent = `${count} selezionati`;
        } else {
            bar.classList.add('hidden');
        }
    }

    async _bulk(action) {
        const ids = Array.from(this.selected);
        try {
            const result = await window.apiClient.bulkSuggestionAction(ids, action);
            window.showToast?.(`Elaborati ${result.processed}/${result.total_requested}`, 'success');
            this.selected.clear();
            this._updateBulkBar();
            this.loadAndRender();
        } catch (err) {
            window.showToast?.(`Errore: ${err.message}`, 'error');
        }
    }
}

window.SuggestionsView = SuggestionsView;
```

- [ ] **Step 4.3: Commit**

```bash
git add static/js/components/suggestion-card.js static/js/views/suggestions-view.js static/css/suggestions.css
git commit -m "Wave 29.4: Add SuggestionCard + SuggestionsView with bulk actions

Individual approve/reject/approve-edit per suggestion.
Bulk toolbar for batch actions on pending suggestions.
Filter by status (pending/approved/rejected).
Payload rendering per suggestion type (phase_laeq, mitigation, narrative).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: SafeEditor — undo/redo + paste sanitize

**Files:**
- Create: `static/js/components/safe-editor.js`
- Create: `static/js/lib/undo-stack.js`

- [ ] **Step 5.1: Undo stack**

File: `static/js/lib/undo-stack.js`

```javascript
/**
 * Simple undo/redo stack with debouncing.
 */
class UndoStack {
    constructor(maxSize = 50) {
        this.maxSize = maxSize;
        this.stack = [];
        this.cursor = -1;
        this._debounceTimer = null;
    }

    push(state) {
        clearTimeout(this._debounceTimer);
        this._debounceTimer = setTimeout(() => {
            // Truncate redo history when pushing new state
            if (this.cursor < this.stack.length - 1) {
                this.stack = this.stack.slice(0, this.cursor + 1);
            }
            this.stack.push(state);
            if (this.stack.length > this.maxSize) {
                this.stack.shift();
            } else {
                this.cursor++;
            }
        }, 250);
    }

    undo() {
        if (this.cursor <= 0) return null;
        this.cursor--;
        return this.stack[this.cursor];
    }

    redo() {
        if (this.cursor >= this.stack.length - 1) return null;
        this.cursor++;
        return this.stack[this.cursor];
    }

    clear() {
        this.stack = [];
        this.cursor = -1;
    }
}

window.UndoStack = UndoStack;
```

- [ ] **Step 5.2: SafeEditor**

File: `static/js/components/safe-editor.js`

```javascript
/**
 * SafeEditor — contenteditable wrapper with undo/redo + paste sanitize.
 *
 * Uses DOMPurify (loaded from CDN) for paste sanitization.
 * Keyboard: Ctrl+Z/Y, Tab indent, Ctrl+B/I/U formatting.
 */
class SafeEditor {
    constructor(element, options = {}) {
        this.el = element;
        this.el.contentEditable = 'true';
        this.el.setAttribute('role', 'textbox');
        this.el.setAttribute('aria-multiline', 'true');
        this.undoStack = new UndoStack(options.maxUndoSteps || 50);
        this.onChange = options.onChange || (() => {});
        this.sanitizer = options.sanitizer || this._defaultSanitizer;

        this._bindEvents();
        this.undoStack.push(this.el.innerHTML);
    }

    _bindEvents() {
        this.el.addEventListener('input', () => {
            this.undoStack.push(this.el.innerHTML);
            this.onChange(this.el.innerHTML);
        });

        this.el.addEventListener('paste', (ev) => this._onPaste(ev));
        this.el.addEventListener('keydown', (ev) => this._onKeyDown(ev));
    }

    _onPaste(ev) {
        ev.preventDefault();
        const text = ev.clipboardData.getData('text/html') || ev.clipboardData.getData('text/plain');
        const sanitized = this.sanitizer(text);

        // Insert at caret
        const selection = window.getSelection();
        if (!selection.rangeCount) {
            this.el.innerHTML += sanitized;
        } else {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            const fragment = range.createContextualFragment(sanitized);
            range.insertNode(fragment);
            range.collapse(false);
        }

        this.undoStack.push(this.el.innerHTML);
        this.onChange(this.el.innerHTML);
    }

    _onKeyDown(ev) {
        if ((ev.ctrlKey || ev.metaKey) && ev.key === 'z' && !ev.shiftKey) {
            ev.preventDefault();
            const prev = this.undoStack.undo();
            if (prev != null) {
                this.el.innerHTML = prev;
                this.onChange(prev);
            }
        } else if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'y' || (ev.key === 'z' && ev.shiftKey))) {
            ev.preventDefault();
            const next = this.undoStack.redo();
            if (next != null) {
                this.el.innerHTML = next;
                this.onChange(next);
            }
        } else if (ev.key === 'Tab') {
            ev.preventDefault();
            document.execCommand('insertText', false, '    ');
        }
    }

    _defaultSanitizer(html) {
        if (window.DOMPurify) {
            return window.DOMPurify.sanitize(html, {
                ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'a', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'td', 'th'],
                ALLOWED_ATTR: ['href', 'title'],
            });
        }
        // Fallback: strip all tags
        const tmp = document.createElement('div');
        tmp.textContent = html;
        return tmp.innerHTML;
    }

    getValue() {
        return this.el.innerHTML;
    }

    setValue(html) {
        this.el.innerHTML = this.sanitizer(html);
        this.undoStack.push(this.el.innerHTML);
    }

    destroy() {
        this.undoStack.clear();
    }
}

window.SafeEditor = SafeEditor;
```

Load DOMPurify in index.html:
```html
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.9/dist/purify.min.js"></script>
```

- [ ] **Step 5.3: Commit**

```bash
git add static/js/components/safe-editor.js static/js/lib/undo-stack.js static/index.html
git commit -m "Wave 29.5: Add SafeEditor with undo/redo + paste sanitize

UndoStack with debounce 250ms + max 50 states.
Keyboard: Ctrl+Z/Y, Tab indent.
Paste sanitized via DOMPurify with allowlist (headings, lists, tables, links).
Fallback to textContent if DOMPurify missing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: AuditTrailPanel

**Files:**
- Create: `static/js/views/audit-trail.js`
- Create: `src/api/routes/audit_routes.py` (endpoint list + CSV export)

- [ ] **Step 6.1: Backend endpoint**

File: `src/api/routes/audit_routes.py`

```python
"""Audit log list + CSV export."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.mars import require_mars_context
from src.bootstrap.database import get_session
from src.infrastructure.database.models.audit_log import AuditLog
from src.infrastructure.mars.tenant_resolver import MarsContext

router = APIRouter(prefix="/api/v1/noise/audit", tags=["audit"])


@router.get("/by-context/{context_id}")
async def list_audit(
    context_id: uuid.UUID,
    mars_ctx: MarsContext = Depends(require_mars_context),
    session: AsyncSession = Depends(get_session),
    source: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100, le=1000),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == mars_ctx.tenant_id)
        .where(AuditLog.entity_uuid == context_id)
    )
    if source:
        stmt = stmt.where(AuditLog.source == source)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)

    results = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "source": r.source.value,
            "action": r.action.value,
            "entity_type": r.entity_type,
            "entity_uuid": str(r.entity_uuid) if r.entity_uuid else None,
            "user_id": str(r.user_id) if r.user_id else None,
            "before": r.before_json,
            "after": r.after_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]


@router.get("/by-context/{context_id}/export.csv")
async def export_audit_csv(
    context_id: uuid.UUID,
    mars_ctx: MarsContext = Depends(require_mars_context),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == mars_ctx.tenant_id)
        .where(AuditLog.entity_uuid == context_id)
        .order_by(AuditLog.created_at.asc())
    )
    results = (await session.execute(stmt)).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["timestamp", "source", "action", "entity_type", "entity_id", "user_id", "summary"])
    for r in results:
        summary = (str(r.after_json) if r.after_json else "")[:200]
        writer.writerow([
            r.created_at.isoformat(),
            r.source.value,
            r.action.value,
            r.entity_type or "",
            str(r.entity_uuid) if r.entity_uuid else "",
            str(r.user_id) if r.user_id else "",
            summary,
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit_{context_id}.csv"'},
    )
```

- [ ] **Step 6.2: Frontend view**

File: `static/js/views/audit-trail.js`

```javascript
class AuditTrailPanel {
    constructor(container, contextId) {
        this.container = container;
        this.contextId = contextId;
        this.filter = { source: null, action: null };
    }

    async render() {
        this.container.innerHTML = `
            <header class="audit-header">
                <h2>Registro modifiche</h2>
                <div class="audit-filters">
                    <select id="filter-source">
                        <option value="">Tutte le fonti</option>
                        <option value="user">Utente</option>
                        <option value="ai_autopilot">AI Autopilot</option>
                        <option value="ai_agent">AI Agent</option>
                        <option value="system">Sistema</option>
                        <option value="scheduler">Scheduler</option>
                    </select>
                    <select id="filter-action">
                        <option value="">Tutte le azioni</option>
                        <option value="create">Create</option>
                        <option value="update">Update</option>
                        <option value="approve">Approve</option>
                        <option value="reject">Reject</option>
                        <option value="ai_run">AI Run</option>
                    </select>
                    <a class="btn btn-sm" id="btn-export-csv" href="#">📥 Export CSV</a>
                </div>
            </header>
            <ul class="audit-list" id="audit-list"></ul>
        `;

        document.getElementById('filter-source').addEventListener('change', (e) => {
            this.filter.source = e.target.value || null;
            this.load();
        });
        document.getElementById('filter-action').addEventListener('change', (e) => {
            this.filter.action = e.target.value || null;
            this.load();
        });
        document.getElementById('btn-export-csv').addEventListener('click', (e) => {
            e.preventDefault();
            this.exportCsv();
        });

        await this.load();
    }

    async load() {
        const list = document.getElementById('audit-list');
        list.innerHTML = '<li>Caricamento...</li>';

        const params = new URLSearchParams();
        if (this.filter.source) params.set('source', this.filter.source);
        if (this.filter.action) params.set('action', this.filter.action);
        const q = params.toString() ? `?${params}` : '';

        try {
            const entries = await window.apiClient.request(`/api/v1/noise/audit/by-context/${this.contextId}${q}`);
            list.innerHTML = '';
            if (!entries.length) {
                list.innerHTML = '<li class="empty">Nessuna voce</li>';
                return;
            }
            for (const e of entries) {
                const li = document.createElement('li');
                li.className = `audit-entry source-${e.source}`;
                li.innerHTML = `
                    <div class="entry-ts">${new Date(e.created_at).toLocaleString('it-IT')}</div>
                    <div class="entry-main">
                        <span class="entry-badge badge-${e.source}">${e.source}</span>
                        <span class="entry-action">${e.action}</span>
                        <span class="entry-entity">${e.entity_type || '–'}</span>
                    </div>
                    <details class="entry-details">
                        <summary>Dettagli</summary>
                        <pre>${this._escapeHtml(JSON.stringify({ before: e.before, after: e.after }, null, 2))}</pre>
                    </details>
                `;
                list.appendChild(li);
            }
        } catch (err) {
            list.innerHTML = `<li class="error">Errore: ${err.message}</li>`;
        }
    }

    async exportCsv() {
        const token = window.ModuleBootstrap?.context?.accessToken || sessionStorage.getItem('mars_access_token');
        const url = `/api/v1/noise/audit/by-context/${this.contextId}/export.csv`;
        const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!response.ok) {
            window.showToast?.('Errore export', 'error');
            return;
        }
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `audit_${this.contextId}.csv`;
        link.click();
    }

    _escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }
}

window.AuditTrailPanel = AuditTrailPanel;
```

- [ ] **Step 6.3: Commit**

```bash
git add src/api/routes/audit_routes.py static/js/views/audit-trail.js src/bootstrap/main.py
git commit -m "Wave 29.6: Add AuditTrailPanel + GET /audit endpoints

Backend: list + CSV export filtered by source/action/context_id.
Frontend: filtrable list with badge per source, details expandable,
CSV export button downloads file with native browser API.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Design tokens condivisi MARS

**Files:**
- Create: `static/css/design-tokens.css`

File: `static/css/design-tokens.css`

```css
/**
 * Design tokens shared with MARS apps/web.
 * Source of truth: MARS. Rumore copies values.
 */
:root {
    --color-primary: #2563eb;
    --color-primary-hover: #1d4ed8;
    --color-success: #16a34a;
    --color-warning: #d97706;
    --color-danger: #dc2626;
    --color-info: #0284c7;

    --color-bg: #ffffff;
    --color-bg-muted: #f9fafb;
    --color-border: #e5e7eb;
    --color-border-strong: #d1d5db;
    --color-text: #111827;
    --color-text-muted: #6b7280;

    --color-risk-green: #16a34a;
    --color-risk-yellow: #ca8a04;
    --color-risk-orange: #ea580c;
    --color-risk-red: #dc2626;

    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', 'Cascadia Code', ui-monospace, monospace;

    --spacing-1: 4px;
    --spacing-2: 8px;
    --spacing-3: 12px;
    --spacing-4: 16px;
    --spacing-6: 24px;
    --spacing-8: 32px;

    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;

    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
    --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.15);
}
```

Link nel `<head>` di index.html come primo stylesheet.

Commit:
```bash
git add static/css/design-tokens.css static/index.html
git commit -m "Wave 29.7: Add design tokens shared with MARS"
```

---

## Task 8: Lint + smoke + STATUS

- [ ] **Step 8.1: Avvia server dev**

```bash
make dev
```

Apri browser a `http://localhost:8085/static/index.html?token=<fake-jwt>&dvr_doc_id=<uuid>&revision_id=<uuid>` per smoke test.

Verifica console browser: zero errori caricamento JS/CSS.

- [ ] **Step 8.2: STATUS + commit + push**

```bash
# Update STATUS.md
git add docs/superpowers/plans/STATUS.md
git commit -m "Wave 29: Mark complete in STATUS"
git push
```

---

## Acceptance criteria Wave 29

1. ✅ ModuleBootstrap con postMessage handshake + fallback query string
2. ✅ APIClient refactored (timeout, retry, SSE, MARS context)
3. ✅ AutopilotView: progress streaming + result dashboard + error state
4. ✅ SuggestionCard + SuggestionsView con bulk actions
5. ✅ SafeEditor con undo/redo + paste sanitize
6. ✅ AuditTrailPanel + endpoint /api/v1/noise/audit/* + CSV export
7. ✅ Design tokens condivisi
8. ✅ Smoke test browser senza errori console

---

## Rollback Wave 29

Feature flags in index.html via URL param `?feature_autopilot=false` → UI skip AutopilotView.

---

## Next Wave

**Wave 30 — Hardening** (`2026-04-17-wave-30-hardening.md`)
