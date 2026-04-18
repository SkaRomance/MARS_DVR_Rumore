/**
 * SuggestionCard — rende un singolo AISuggestion con azioni approve/reject/edit.
 *
 * Tipologie suggerimento supportate:
 *   - phase_laeq        : stima LAeq + durata per fase/mansione
 *   - phase_duration    : correzione durata esposizione
 *   - mitigation        : misura di mitigazione
 *   - training          : formazione obbligatoria
 *   - narrative_section : sezione DVR generata
 *   - k_correction      : correzione K (tonale/impulsiva)
 *
 * Editable flow: structured form per phase_laeq / mitigation; JSON fallback altrimenti.
 */
(function () {
    'use strict';

    const TYPE_LABELS = {
        phase_laeq: 'Stima esposizione fase',
        phase_duration: 'Durata esposizione',
        mitigation: 'Misura di mitigazione',
        training: 'Formazione richiesta',
        narrative_section: 'Sezione DVR',
        k_correction: 'Correzione K',
    };

    function escapeHtml(s) {
        return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function confBadge(confidence) {
        if (confidence == null) return '';
        const pct = Math.round(confidence * 100);
        const tier = pct >= 80 ? 'high' : pct >= 50 ? 'mid' : 'low';
        return `<span class="conf-badge conf-${tier}" title="Confidence AI">${pct}%</span>`;
    }

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
            card.className = `suggestion-card status-${escapeHtml(s.status)}`;
            card.setAttribute('data-suggestion-id', s.id);

            const actionsVisible = s.status === 'pending';

            card.innerHTML = `
                ${this.selectable && actionsVisible ? `
                <label class="suggestion-select">
                    <input type="checkbox" class="js-select" aria-label="Seleziona suggerimento">
                </label>` : ''}
                <div class="suggestion-header">
                    <span class="suggestion-type">${escapeHtml(TYPE_LABELS[s.suggestion_type] || s.suggestion_type)}</span>
                    ${confBadge(s.confidence)}
                    <span class="suggestion-status status-${escapeHtml(s.status)}">${escapeHtml(s.status)}</span>
                </div>
                <div class="suggestion-body">
                    ${this._renderPayload(s)}
                </div>
                ${actionsVisible ? `
                <div class="suggestion-actions">
                    <button class="btn btn-sm btn-primary js-approve" type="button">Approva</button>
                    <button class="btn btn-sm js-approve-edit" type="button">Approva con modifiche</button>
                    <button class="btn btn-sm btn-ghost js-reject" type="button">Rifiuta</button>
                </div>` : `
                <div class="suggestion-meta">
                    ${s.reviewed_at ? `<span>Revisionato: ${escapeHtml(new Date(s.reviewed_at).toLocaleString('it-IT'))}</span>` : ''}
                    ${s.reviewer_notes ? `<span>Note: ${escapeHtml(s.reviewer_notes)}</span>` : ''}
                </div>`}
            `;

            this.el = card;
            this._bindEvents();
            return card;
        }

        _renderPayload(s) {
            const p = s.payload_json || {};
            switch (s.suggestion_type) {
                case 'phase_laeq':
                    return this._renderPhaseLaeq(p);
                case 'phase_duration':
                    return this._renderPhaseDuration(p);
                case 'mitigation':
                    return this._renderMitigation(p);
                case 'training':
                    return this._renderTraining(p);
                case 'narrative_section':
                    return this._renderNarrative(p);
                case 'k_correction':
                    return this._renderKCorrection(p);
                default:
                    return `<pre class="payload-json">${escapeHtml(JSON.stringify(p, null, 2))}</pre>`;
            }
        }

        _renderPhaseLaeq(p) {
            const fields = [];
            if (p.phase_name) fields.push(`<div><b>Fase:</b> ${escapeHtml(p.phase_name)}</div>`);
            if (p.job_role) fields.push(`<div><b>Mansione:</b> ${escapeHtml(p.job_role)}</div>`);
            if (p.laeq_db != null) fields.push(`<div><b>LAeq:</b> ${Number(p.laeq_db).toFixed(1)} dB(A)</div>`);
            if (p.duration_hours != null) fields.push(`<div><b>Durata:</b> ${Number(p.duration_hours).toFixed(2)} h/g</div>`);
            if (p.lcpeak_db != null) fields.push(`<div><b>LCpeak:</b> ${Number(p.lcpeak_db).toFixed(0)} dB(C)</div>`);
            if (p.k_corrections) {
                const kc = p.k_corrections;
                const parts = [];
                if (kc.k_tone) parts.push(`K_T=+${kc.k_tone}`);
                if (kc.k_imp) parts.push(`K_I=+${kc.k_imp}`);
                if (parts.length) fields.push(`<div><b>Correzioni K:</b> ${parts.join(', ')} dB</div>`);
            }
            const reasoning = p.reasoning ? `<div class="payload-reasoning"><b>Motivazione AI:</b> ${escapeHtml(p.reasoning)}</div>` : '';
            const gaps = (p.data_gaps && p.data_gaps.length) ? `
                <div class="payload-gaps">
                    <b>Dati mancanti:</b>
                    <ul>${p.data_gaps.map((g) => `<li>${escapeHtml(g)}</li>`).join('')}</ul>
                </div>` : '';
            return `<div class="payload-grid">${fields.join('')}</div>${reasoning}${gaps}`;
        }

        _renderPhaseDuration(p) {
            return `
                ${p.phase_name ? `<div><b>Fase:</b> ${escapeHtml(p.phase_name)}</div>` : ''}
                <div><b>Durata suggerita:</b> ${Number(p.duration_hours ?? 0).toFixed(2)} h/g</div>
                ${p.reasoning ? `<div class="payload-reasoning">${escapeHtml(p.reasoning)}</div>` : ''}
            `;
        }

        _renderMitigation(p) {
            return `
                <div><b>Tipo:</b> ${escapeHtml(p.type || 'tecnica')}</div>
                <div><b>Titolo:</b> ${escapeHtml(p.title || '')}</div>
                ${p.description ? `<div class="payload-reasoning">${escapeHtml(p.description)}</div>` : ''}
                ${p.estimated_reduction_db != null ? `<div><b>Riduzione stimata:</b> −${Number(p.estimated_reduction_db).toFixed(1)} dB</div>` : ''}
                ${p.priority ? `<div><b>Priorità:</b> <span class="priority-${escapeHtml(p.priority)}">${escapeHtml(p.priority)}</span></div>` : ''}
                ${p.legal_reference ? `<div><b>Riferimento:</b> ${escapeHtml(p.legal_reference)}</div>` : ''}
            `;
        }

        _renderTraining(p) {
            return `
                <div><b>Corso:</b> ${escapeHtml(p.course_title || '')}</div>
                ${p.duration_hours ? `<div><b>Durata:</b> ${p.duration_hours} h</div>` : ''}
                ${p.frequency ? `<div><b>Frequenza:</b> ${escapeHtml(p.frequency)}</div>` : ''}
                ${p.target_roles?.length ? `<div><b>Mansioni:</b> ${p.target_roles.map(escapeHtml).join(', ')}</div>` : ''}
            `;
        }

        _renderNarrative(p) {
            const excerpt = (p.content_html || p.content || '').toString();
            const truncated = excerpt.length > 400 ? excerpt.substring(0, 400) + '…' : excerpt;
            return `
                <div><b>Sezione:</b> <code>${escapeHtml(p.section_key || '—')}</code></div>
                <div class="payload-narrative">${truncated}</div>
            `;
        }

        _renderKCorrection(p) {
            const list = [];
            if (p.k_tone != null) list.push(`K_T = +${p.k_tone} dB (tonale)`);
            if (p.k_imp != null) list.push(`K_I = +${p.k_imp} dB (impulsivo)`);
            return `
                ${p.phase_name ? `<div><b>Fase:</b> ${escapeHtml(p.phase_name)}</div>` : ''}
                <div><b>Correzione:</b> ${list.join(', ') || '—'}</div>
                ${p.reasoning ? `<div class="payload-reasoning">${escapeHtml(p.reasoning)}</div>` : ''}
            `;
        }

        _bindEvents() {
            const $ = (sel) => this.el.querySelector(sel);
            $('.js-approve')?.addEventListener('click', () => this._doApprove());
            $('.js-approve-edit')?.addEventListener('click', () => this._openEditModal());
            $('.js-reject')?.addEventListener('click', () => this._doReject());

            const chk = $('.js-select');
            if (chk) {
                chk.addEventListener('change', (e) => {
                    this.selected = e.target.checked;
                    this.onAction('select', { suggestion: this.suggestion, selected: this.selected });
                });
            }
        }

        async _doApprove() {
            try {
                const updated = await window.apiClient.approveSuggestionV2(this.suggestion.id);
                this.suggestion = updated;
                window.app?.showToast?.('Suggerimento approvato', 'success');
                this.onAction('approved', { suggestion: updated });
            } catch (err) {
                window.app?.showToast?.(`Errore: ${err.message}`, 'error');
            }
        }

        async _doReject() {
            const reason = prompt('Motivo del rifiuto (opzionale):');
            if (reason === null) return; // user cancelled
            try {
                const updated = await window.apiClient.rejectSuggestionV2(this.suggestion.id, reason || null);
                this.suggestion = updated;
                window.app?.showToast?.('Suggerimento rifiutato', 'info');
                this.onAction('rejected', { suggestion: updated });
            } catch (err) {
                window.app?.showToast?.(`Errore: ${err.message}`, 'error');
            }
        }

        _openEditModal() {
            const editorHtml = this._buildEditorForm();
            if (!window.app?.showModal) {
                // Fallback: native prompt with JSON
                const raw = prompt('Modifica JSON:', JSON.stringify(this.suggestion.payload_json, null, 2));
                if (!raw) return;
                try {
                    const edited = JSON.parse(raw);
                    this._submitEdit(edited);
                } catch (e) {
                    alert(`JSON non valido: ${e.message}`);
                }
                return;
            }

            window.app.showModal('Modifica prima di approvare', editorHtml, async () => {
                const edited = this._readEditorForm();
                if (edited === null) return false; // invalid
                try {
                    await this._submitEdit(edited);
                    return true;
                } catch (err) {
                    window.app?.showToast?.(`Errore: ${err.message}`, 'error');
                    return false;
                }
            });
        }

        _buildEditorForm() {
            const type = this.suggestion.suggestion_type;
            const p = this.suggestion.payload_json || {};

            if (type === 'phase_laeq') {
                return `
                    <div class="edit-form">
                        <div class="form-group"><label>Fase</label>
                            <input type="text" class="js-edit-phase_name" value="${escapeHtml(p.phase_name || '')}"></div>
                        <div class="form-group"><label>LAeq dB(A)</label>
                            <input type="number" step="0.1" min="0" max="140" class="js-edit-laeq_db" value="${p.laeq_db ?? ''}"></div>
                        <div class="form-group"><label>Durata (h/g)</label>
                            <input type="number" step="0.1" min="0" max="24" class="js-edit-duration_hours" value="${p.duration_hours ?? ''}"></div>
                        <div class="form-group"><label>LCpeak dB(C) (opzionale)</label>
                            <input type="number" step="1" min="0" max="200" class="js-edit-lcpeak_db" value="${p.lcpeak_db ?? ''}"></div>
                        <div class="form-group"><label>Motivazione</label>
                            <textarea rows="3" class="js-edit-reasoning">${escapeHtml(p.reasoning || '')}</textarea></div>
                    </div>
                `;
            }
            if (type === 'mitigation') {
                return `
                    <div class="edit-form">
                        <div class="form-group"><label>Titolo</label>
                            <input type="text" class="js-edit-title" value="${escapeHtml(p.title || '')}"></div>
                        <div class="form-group"><label>Descrizione</label>
                            <textarea rows="4" class="js-edit-description">${escapeHtml(p.description || '')}</textarea></div>
                        <div class="form-group"><label>Riduzione stimata dB</label>
                            <input type="number" step="0.5" min="0" max="40" class="js-edit-estimated_reduction_db" value="${p.estimated_reduction_db ?? ''}"></div>
                        <div class="form-group"><label>Priorità</label>
                            <select class="js-edit-priority">
                                <option value="low"${p.priority === 'low' ? ' selected' : ''}>Bassa</option>
                                <option value="medium"${p.priority === 'medium' || !p.priority ? ' selected' : ''}>Media</option>
                                <option value="high"${p.priority === 'high' ? ' selected' : ''}>Alta</option>
                            </select>
                        </div>
                    </div>
                `;
            }
            // Fallback: raw JSON textarea
            return `
                <div class="edit-form">
                    <label>Payload JSON</label>
                    <textarea rows="12" class="js-edit-json" style="font-family:monospace;width:100%">${escapeHtml(JSON.stringify(p, null, 2))}</textarea>
                </div>
            `;
        }

        _readEditorForm() {
            const type = this.suggestion.suggestion_type;
            const base = { ...(this.suggestion.payload_json || {}) };

            const num = (sel) => {
                const v = document.querySelector(sel)?.value?.trim();
                return v === '' || v == null ? null : Number(v);
            };
            const str = (sel) => document.querySelector(sel)?.value?.trim() || '';

            if (type === 'phase_laeq') {
                return {
                    ...base,
                    phase_name: str('.js-edit-phase_name'),
                    laeq_db: num('.js-edit-laeq_db'),
                    duration_hours: num('.js-edit-duration_hours'),
                    lcpeak_db: num('.js-edit-lcpeak_db'),
                    reasoning: str('.js-edit-reasoning'),
                };
            }
            if (type === 'mitigation') {
                return {
                    ...base,
                    title: str('.js-edit-title'),
                    description: str('.js-edit-description'),
                    estimated_reduction_db: num('.js-edit-estimated_reduction_db'),
                    priority: str('.js-edit-priority'),
                };
            }
            const raw = document.querySelector('.js-edit-json')?.value;
            if (!raw) return null;
            try {
                return JSON.parse(raw);
            } catch (e) {
                window.app?.showToast?.(`JSON non valido: ${e.message}`, 'error');
                return null;
            }
        }

        async _submitEdit(editedPayload) {
            const updated = await window.apiClient.approveSuggestionV2(this.suggestion.id, editedPayload);
            this.suggestion = updated;
            window.app?.showToast?.('Approvato con modifiche', 'success');
            this.onAction('approved', { suggestion: updated });
        }
    }

    window.SuggestionCard = SuggestionCard;
})();
