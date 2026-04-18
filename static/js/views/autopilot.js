/**
 * AutopilotView — landing page per valutazione AI rumore.
 *
 * State machine:
 *   idle -> running (SSE progress) -> completed (result card) | failed (error)
 *
 * Usage:
 *   const view = new AutopilotView(containerEl, contextId);
 *   view.render();
 *
 * Events emitted (on window via CustomEvent):
 *   - navigate:suggestions {contextId}
 *   - navigate:manual {contextId}
 *   - navigate:document {contextId}
 */
(function () {
    'use strict';

    const STEP_LABELS = {
        initialize: 'Inizializzazione',
        parse_dvr: 'Importazione DVR',
        source_detection: 'Identificazione sorgenti (PAF)',
        exposure_estimation: 'Stima esposizione per mansione',
        iso_9612_calc: 'Calcolo ISO 9612 (LEX,8h)',
        review: 'Validazione incrociata',
        mitigation: 'Misure di mitigazione',
        narrative: 'Generazione narrativa DVR',
        persist: 'Salvataggio',
        done: 'Completato',
    };

    const STEP_ICONS = {
        started: '▶',
        step_started: '⟳',
        step_completed: '✓',
        step_failed: '✕',
        completed: '✓',
        failed: '✕',
        progress: '·',
    };

    class AutopilotView {
        constructor(container, contextId) {
            this.container = container;
            this.contextId = contextId;
            this.state = 'idle';
            this.events = [];
            this.finalPayload = null;
            this._abortController = null;
        }

        render() {
            this.container.innerHTML = `
                <div class="autopilot-view">
                    <header class="autopilot-header">
                        <h1>Valutazione AI Rischio Rumore</h1>
                        <p class="autopilot-subhead" id="autopilot-subhead">L'AI analizza il DVR base, identifica le sorgenti, stima l'esposizione per mansione e propone misure di mitigazione.</p>
                    </header>

                    <section class="autopilot-actions" id="autopilot-actions">
                        <button class="btn btn-primary btn-lg" id="btn-autopilot-start" type="button">
                            Avvia valutazione AI
                        </button>
                        <button class="btn btn-ghost" id="btn-autopilot-manual" type="button">
                            Modalità manuale
                        </button>
                    </section>

                    <section class="autopilot-progress hidden" id="autopilot-progress" aria-live="polite">
                        <div class="progress-header">
                            <span class="progress-label">Autopilot AI in corso</span>
                            <span class="progress-percent" id="progress-percent">0%</span>
                        </div>
                        <div class="progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                            <div class="progress-fill" id="progress-fill"></div>
                        </div>
                        <ul class="progress-steps" id="progress-steps"></ul>
                        <button class="btn btn-sm btn-ghost" id="btn-autopilot-cancel" type="button">Annulla</button>
                    </section>

                    <section class="autopilot-result hidden" id="autopilot-result" aria-live="polite"></section>
                    <section class="autopilot-error hidden" id="autopilot-error" role="alert"></section>
                </div>
            `;
            this._bindInitialEvents();
        }

        _bindInitialEvents() {
            this.container.querySelector('#btn-autopilot-start').addEventListener('click', () => this.startAutopilot());
            this.container.querySelector('#btn-autopilot-manual').addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('navigate:manual', { detail: { contextId: this.contextId } }));
            });
        }

        async startAutopilot() {
            if (this.state === 'running') return;
            this.state = 'running';
            this.events = [];
            this._showProgress();

            try {
                const final = await window.apiClient.runAutopilot(this.contextId, (ev) => this._onEvent(ev));
                this.finalPayload = final;
                if (final && final.kind === 'completed') {
                    this.state = 'completed';
                    this._showResult(final);
                } else {
                    this.state = 'failed';
                    this._showError(final?.message || final?.payload?.error || 'Valutazione fallita', final?.payload);
                }
            } catch (err) {
                this.state = 'failed';
                this._showError(err?.message || String(err), null);
            }
        }

        _onEvent(ev) {
            this.events.push(ev);

            if (ev.progress_percent != null) {
                const pct = Math.max(0, Math.min(100, Math.round(ev.progress_percent)));
                const fill = this.container.querySelector('#progress-fill');
                const pctEl = this.container.querySelector('#progress-percent');
                if (fill) fill.style.width = `${pct}%`;
                const bar = this.container.querySelector('.progress-bar');
                if (bar) bar.setAttribute('aria-valuenow', String(pct));
                if (pctEl) pctEl.textContent = `${pct}%`;
            }

            if (ev.kind === 'step_started' || ev.kind === 'step_completed' || ev.kind === 'step_failed') {
                this._appendStep(ev);
            }
        }

        _appendStep(ev) {
            const list = this.container.querySelector('#progress-steps');
            if (!list) return;

            const existing = list.querySelector(`[data-step="${ev.step}"]`);
            if (existing) {
                existing.className = `step step-${ev.kind}`;
                existing.querySelector('.step-icon').textContent = STEP_ICONS[ev.kind] || '·';
                const extra = this._extraForPayload(ev.payload);
                if (extra) existing.querySelector('.step-extra').textContent = extra;
                return;
            }

            const li = document.createElement('li');
            li.className = `step step-${ev.kind}`;
            li.setAttribute('data-step', ev.step);
            li.innerHTML = `
                <span class="step-icon">${STEP_ICONS[ev.kind] || '·'}</span>
                <span class="step-label">${this._escapeHtml(STEP_LABELS[ev.step] || ev.step)}</span>
                <span class="step-extra">${this._escapeHtml(this._extraForPayload(ev.payload))}</span>
            `;
            list.appendChild(li);
        }

        _extraForPayload(payload) {
            if (!payload) return '';
            if (payload.candidates_count != null) return `${payload.candidates_count} candidati`;
            if (payload.matched_count != null && payload.total != null) return `${payload.matched_count}/${payload.total} match`;
            if (payload.estimates_count != null) return `${payload.estimates_count} stime`;
            if (payload.lex_8h_db != null) return `LEX=${Number(payload.lex_8h_db).toFixed(1)}dB (${payload.risk_band || '?'})`;
            if (payload.measures_count != null) return `${payload.measures_count} misure`;
            if (payload.sections_count != null) return `${payload.sections_count} sezioni`;
            if (payload.duration_ms != null) return `${Math.round(payload.duration_ms)} ms`;
            return '';
        }

        _showProgress() {
            this.container.querySelector('#autopilot-actions').classList.add('hidden');
            this.container.querySelector('#autopilot-progress').classList.remove('hidden');
            this.container.querySelector('#autopilot-error').classList.add('hidden');
            const cancelBtn = this.container.querySelector('#btn-autopilot-cancel');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => this._cancel(), { once: true });
            }
        }

        async _cancel() {
            try {
                await window.apiClient.cancelAutopilot(this.contextId);
                window.showToast?.('Autopilot annullato', 'info');
            } catch (err) {
                window.showToast?.(`Errore annullamento: ${err.message}`, 'error');
            }
        }

        _showResult(ev) {
            const p = ev.payload || {};
            const lex = p.lex_8h_db != null ? Number(p.lex_8h_db).toFixed(1) : '—';
            const band = (p.risk_band || 'unknown').toLowerCase();
            const confidence = p.confidence != null ? Math.round(p.confidence * 100) : null;
            const duration = p.duration_s != null ? Math.round(p.duration_s) : null;

            this.container.querySelector('#autopilot-progress').classList.add('hidden');
            const el = this.container.querySelector('#autopilot-result');
            el.classList.remove('hidden');
            el.innerHTML = `
                <div class="result-card risk-${this._escapeAttr(band)}">
                    <div class="result-icon" aria-hidden="true">✓</div>
                    <h2>Valutazione completata${duration != null ? ` in ${duration}s` : ''}</h2>
                    ${confidence != null ? `<p class="result-confidence">Confidence complessiva: <strong>${confidence}%</strong></p>` : ''}
                    <div class="result-stats">
                        <div class="stat">
                            <div class="stat-label">LEX,8h medio</div>
                            <div class="stat-value">${this._escapeHtml(lex)}<small> dB(A)</small></div>
                        </div>
                        <div class="stat stat-risk-${this._escapeAttr(band)}">
                            <div class="stat-label">Banda di rischio</div>
                            <div class="stat-value">${this._escapeHtml(band.toUpperCase())}</div>
                        </div>
                        ${p.suggestions_count != null ? `
                        <div class="stat">
                            <div class="stat-label">Suggerimenti generati</div>
                            <div class="stat-value">${p.suggestions_count}</div>
                        </div>` : ''}
                    </div>
                    <div class="result-actions">
                        <button class="btn btn-primary" id="btn-review-suggestions" type="button">Rivedi suggerimenti</button>
                        <button class="btn" id="btn-approve-high-conf" type="button">Approva tutti (conf ≥ 80%)</button>
                        <button class="btn btn-ghost" id="btn-edit-manual" type="button">Modifica manualmente</button>
                    </div>
                </div>
            `;

            el.querySelector('#btn-review-suggestions').addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('navigate:suggestions', { detail: { contextId: this.contextId } }));
            });
            el.querySelector('#btn-approve-high-conf').addEventListener('click', () => this._approveHighConf());
            el.querySelector('#btn-edit-manual').addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('navigate:manual', { detail: { contextId: this.contextId } }));
            });
        }

        async _approveHighConf() {
            try {
                const suggestions = await window.apiClient.listSuggestionsByContext(this.contextId, 'pending');
                if (!suggestions.length) {
                    window.showToast?.('Nessun suggerimento pendente', 'info');
                    return;
                }
                const ids = suggestions.map((s) => s.id);
                const result = await window.apiClient.bulkSuggestionAction(ids, 'approve', { min_confidence: 0.8 });
                window.showToast?.(`Approvati ${result.processed}/${result.total_requested}`, 'success');
                window.dispatchEvent(new CustomEvent('navigate:suggestions', { detail: { contextId: this.contextId } }));
            } catch (err) {
                window.showToast?.(`Errore: ${err.message}`, 'error');
            }
        }

        _showError(message, payload) {
            this.container.querySelector('#autopilot-progress').classList.add('hidden');
            const el = this.container.querySelector('#autopilot-error');
            el.classList.remove('hidden');
            el.innerHTML = `
                <div class="error-card">
                    <h2>Autopilot fallito</h2>
                    <p>${this._escapeHtml(message)}</p>
                    ${payload?.failed_step ? `<p class="error-step">Step fallito: <code>${this._escapeHtml(payload.failed_step)}</code></p>` : ''}
                    <div class="error-actions">
                        <button class="btn btn-primary" id="btn-retry-autopilot" type="button">Riprova</button>
                        <button class="btn btn-ghost" id="btn-fallback-manual" type="button">Modalità manuale</button>
                    </div>
                </div>
            `;
            el.querySelector('#btn-retry-autopilot').addEventListener('click', () => {
                this.state = 'idle';
                this.events = [];
                this.container.querySelector('#progress-steps').innerHTML = '';
                this.container.querySelector('#progress-fill').style.width = '0%';
                this.container.querySelector('#progress-percent').textContent = '0%';
                el.classList.add('hidden');
                this.startAutopilot();
            });
            el.querySelector('#btn-fallback-manual').addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('navigate:manual', { detail: { contextId: this.contextId } }));
            });
        }

        _escapeHtml(s) {
            return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
        }

        _escapeAttr(s) {
            return String(s ?? '').replace(/[^a-z0-9_-]/gi, '');
        }

        unmount() {
            this.container.innerHTML = '';
        }
    }

    window.AutopilotView = AutopilotView;
})();
