/**
 * AuditTrailPanel — registro modifiche per un NoiseAssessmentContext.
 *
 * Mostra audit log con filtri source/action, dettagli espandibili
 * (before/after JSON), export CSV.
 *
 * Backend dependency (Wave 25 audit_logs + Wave 26 MARS context):
 *   GET /api/v1/noise/audit/by-context/{context_id}?source=...&action=...
 *   GET /api/v1/noise/audit/by-context/{context_id}/export.csv
 * Quando il backend non è ancora live → 404 → mostriamo stato vuoto
 * con messaggio "Registro non ancora disponibile".
 */
(function () {
    'use strict';

    const SOURCE_LABELS = {
        user: 'Utente',
        ai_autopilot: 'AI Autopilot',
        ai_agent: 'AI Agent',
        system: 'Sistema',
        scheduler: 'Scheduler',
        mars_webhook: 'MARS Webhook',
    };

    const ACTION_LABELS = {
        create: 'Creazione',
        update: 'Modifica',
        delete: 'Eliminazione',
        approve: 'Approvazione',
        reject: 'Rifiuto',
        ai_run: 'Esecuzione AI',
        sync: 'Sincronizzazione',
        export: 'Export',
    };

    function escapeHtml(s) {
        return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    class AuditTrailPanel {
        constructor(container, contextId) {
            this.container = container;
            this.contextId = contextId;
            this.filter = { source: '', action: '' };
            this.backendAvailable = true;
        }

        async render() {
            this.container.innerHTML = `
                <div class="audit-panel">
                    <header class="audit-header">
                        <h2>Registro modifiche</h2>
                        <p class="audit-subhead">Ogni modifica al DVR — da utente, AI o sistema — viene registrata qui.</p>
                        <div class="audit-filters">
                            <label>Fonte
                                <select id="filter-audit-source">
                                    <option value="">Tutte</option>
                                    ${Object.entries(SOURCE_LABELS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}
                                </select>
                            </label>
                            <label>Azione
                                <select id="filter-audit-action">
                                    <option value="">Tutte</option>
                                    ${Object.entries(ACTION_LABELS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}
                                </select>
                            </label>
                            <button class="btn btn-sm" id="btn-audit-refresh" type="button">Aggiorna</button>
                            <button class="btn btn-sm btn-ghost" id="btn-audit-export" type="button">Scarica CSV</button>
                        </div>
                    </header>
                    <ul class="audit-list" id="audit-list" aria-live="polite"></ul>
                </div>
            `;

            this.container.querySelector('#filter-audit-source').addEventListener('change', (e) => {
                this.filter.source = e.target.value;
                this.load();
            });
            this.container.querySelector('#filter-audit-action').addEventListener('change', (e) => {
                this.filter.action = e.target.value;
                this.load();
            });
            this.container.querySelector('#btn-audit-refresh').addEventListener('click', () => this.load());
            this.container.querySelector('#btn-audit-export').addEventListener('click', () => this.exportCsv());

            await this.load();
        }

        async load() {
            const list = this.container.querySelector('#audit-list');
            list.innerHTML = '<li class="loader-inline">Caricamento…</li>';

            const filters = {};
            if (this.filter.source) filters.source = this.filter.source;
            if (this.filter.action) filters.action = this.filter.action;
            filters.limit = 200;

            try {
                const entries = await window.apiClient.listAuditByContext(this.contextId, filters);
                this.backendAvailable = true;
                this._renderEntries(entries);
            } catch (err) {
                if (err.status === 404) {
                    this.backendAvailable = false;
                    list.innerHTML = `
                        <li class="audit-empty">
                            <p>Registro non ancora disponibile.</p>
                            <p class="hint">Il backend audit verrà attivato con la prossima release. Le modifiche effettuate ora saranno visibili retroattivamente.</p>
                        </li>`;
                    return;
                }
                list.innerHTML = `<li class="error-inline">Errore: ${escapeHtml(err.message)}</li>`;
            }
        }

        _renderEntries(entries) {
            const list = this.container.querySelector('#audit-list');
            list.innerHTML = '';
            if (!entries || !entries.length) {
                list.innerHTML = '<li class="audit-empty">Nessuna voce per i filtri selezionati.</li>';
                return;
            }

            for (const e of entries) {
                const li = document.createElement('li');
                li.className = `audit-entry source-${escapeHtml(e.source || 'system')}`;
                const ts = e.created_at ? new Date(e.created_at).toLocaleString('it-IT') : '—';
                const sourceLabel = SOURCE_LABELS[e.source] || e.source || '—';
                const actionLabel = ACTION_LABELS[e.action] || e.action || '—';

                li.innerHTML = `
                    <div class="entry-ts">${escapeHtml(ts)}</div>
                    <div class="entry-main">
                        <span class="entry-badge badge-${escapeHtml(e.source || 'system')}">${escapeHtml(sourceLabel)}</span>
                        <span class="entry-action">${escapeHtml(actionLabel)}</span>
                        ${e.entity_type ? `<span class="entry-entity">${escapeHtml(e.entity_type)}</span>` : ''}
                        ${e.user_id ? `<span class="entry-user" title="User ID">${escapeHtml(e.user_id.substring(0, 8))}…</span>` : ''}
                    </div>
                    <details class="entry-details">
                        <summary>Dettagli</summary>
                        <div class="entry-diff">
                            ${e.before ? `<div><b>Prima:</b><pre>${escapeHtml(JSON.stringify(e.before, null, 2))}</pre></div>` : ''}
                            ${e.after ? `<div><b>Dopo:</b><pre>${escapeHtml(JSON.stringify(e.after, null, 2))}</pre></div>` : ''}
                        </div>
                    </details>
                `;
                list.appendChild(li);
            }
        }

        async exportCsv() {
            if (!this.backendAvailable) {
                window.app?.showToast?.('Export non disponibile (backend audit non attivo)', 'warning');
                return;
            }
            const token = window.authService?.getToken() || sessionStorage.getItem('mars_access_token') || '';
            const url = window.apiClient.auditExportCsvUrl(this.contextId);
            try {
                const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const blob = await response.blob();
                const dlUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = dlUrl;
                link.download = `audit_${this.contextId}.csv`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(dlUrl);
                window.app?.showToast?.('CSV scaricato', 'success');
            } catch (err) {
                window.app?.showToast?.(`Errore export: ${err.message}`, 'error');
            }
        }

        unmount() {
            this.container.innerHTML = '';
        }
    }

    window.AuditTrailPanel = AuditTrailPanel;
})();
