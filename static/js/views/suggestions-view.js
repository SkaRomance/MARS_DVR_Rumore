/**
 * SuggestionsView — lista suggerimenti AI con filter + bulk actions.
 *
 * Usage:
 *   const view = new SuggestionsView(container, contextId);
 *   await view.render();
 */
(function () {
    'use strict';

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
                <div class="suggestions-view">
                    <header class="suggestions-header">
                        <h1>Suggerimenti AI</h1>
                        <p class="suggestions-subhead">Revisiona, modifica o rifiuta i suggerimenti generati dall'autopilot. Solo i suggerimenti approvati vengono applicati al DVR.</p>
                        <div class="filter-bar" role="tablist">
                            <label class="filter-pill"><input type="radio" name="sugg-filter" value="pending" checked> Pendenti</label>
                            <label class="filter-pill"><input type="radio" name="sugg-filter" value="approved"> Approvati</label>
                            <label class="filter-pill"><input type="radio" name="sugg-filter" value="rejected"> Rifiutati</label>
                            <label class="filter-pill"><input type="radio" name="sugg-filter" value="all"> Tutti</label>
                        </div>
                        <div class="bulk-bar hidden" id="bulk-bar" role="toolbar" aria-label="Azioni multiple">
                            <span id="bulk-count">0 selezionati</span>
                            <button class="btn btn-sm btn-primary" id="btn-bulk-approve" type="button">Approva selezionati</button>
                            <button class="btn btn-sm btn-ghost" id="btn-bulk-reject" type="button">Rifiuta selezionati</button>
                            <button class="btn btn-sm btn-ghost" id="btn-select-none" type="button">Deseleziona tutto</button>
                        </div>
                        <div class="select-all-bar hidden" id="select-all-bar">
                            <button class="btn btn-sm btn-ghost" id="btn-select-all" type="button">Seleziona tutti</button>
                        </div>
                    </header>
                    <section class="suggestions-list" id="suggestions-list" aria-live="polite"></section>
                </div>
            `;

            this.container.querySelectorAll('input[name="sugg-filter"]').forEach((rb) => {
                rb.addEventListener('change', (e) => {
                    this.filter = e.target.value;
                    this.selected.clear();
                    this._updateBulkBar();
                    this.loadAndRender();
                });
            });

            this.container.querySelector('#btn-bulk-approve').addEventListener('click', () => this._bulk('approve'));
            this.container.querySelector('#btn-bulk-reject').addEventListener('click', () => this._bulk('reject'));
            this.container.querySelector('#btn-select-none').addEventListener('click', () => this._clearSelection());
            this.container.querySelector('#btn-select-all').addEventListener('click', () => this._selectAll());

            await this.loadAndRender();
        }

        async loadAndRender() {
            const list = this.container.querySelector('#suggestions-list');
            list.innerHTML = '<div class="loader">Caricamento…</div>';

            const statusFilter = this.filter === 'all' ? null : this.filter;
            try {
                this.suggestions = await window.apiClient.listSuggestionsByContext(this.contextId, statusFilter);
            } catch (err) {
                list.innerHTML = `<div class="error-inline">Errore: ${this._escapeHtml(err.message)}</div>`;
                return;
            }

            list.innerHTML = '';
            this.container.querySelector('#select-all-bar').classList.toggle('hidden', this.filter !== 'pending' || !this.suggestions.length);

            if (!this.suggestions.length) {
                list.innerHTML = `<div class="empty">Nessun suggerimento ${this._filterLabel()}</div>`;
                return;
            }

            const selectable = this.filter === 'pending';
            for (const s of this.suggestions) {
                const card = new SuggestionCard(s, {
                    selectable,
                    onAction: (action, detail) => this._onCardAction(action, detail),
                });
                list.appendChild(card.render());
            }
        }

        _filterLabel() {
            return { pending: 'pendente', approved: 'approvato', rejected: 'rifiutato', all: '' }[this.filter] || '';
        }

        _onCardAction(action, detail) {
            if (action === 'select') {
                if (detail.selected) this.selected.add(detail.suggestion.id);
                else this.selected.delete(detail.suggestion.id);
                this._updateBulkBar();
                return;
            }
            if (action === 'approved' || action === 'rejected') {
                // Refresh if current filter excludes the new status
                if (this.filter === 'pending') {
                    this.selected.delete(detail.suggestion.id);
                    this._updateBulkBar();
                    this.loadAndRender();
                }
            }
        }

        _selectAll() {
            if (this.filter !== 'pending') return;
            this.container.querySelectorAll('.js-select').forEach((chk) => {
                if (!chk.checked) {
                    chk.checked = true;
                    chk.dispatchEvent(new Event('change'));
                }
            });
        }

        _clearSelection() {
            this.selected.clear();
            this.container.querySelectorAll('.js-select').forEach((chk) => { chk.checked = false; });
            this._updateBulkBar();
        }

        _updateBulkBar() {
            const bar = this.container.querySelector('#bulk-bar');
            const count = this.selected.size;
            if (count > 0) {
                bar.classList.remove('hidden');
                this.container.querySelector('#bulk-count').textContent = `${count} selezionat${count === 1 ? 'o' : 'i'}`;
            } else {
                bar.classList.add('hidden');
            }
        }

        async _bulk(action) {
            const ids = Array.from(this.selected);
            if (!ids.length) return;

            const verb = action === 'approve' ? 'approvare' : 'rifiutare';
            if (!confirm(`${action === 'approve' ? 'Approvare' : 'Rifiutare'} ${ids.length} suggeriment${ids.length === 1 ? 'o' : 'i'}?`)) return;

            try {
                const result = await window.apiClient.bulkSuggestionAction(ids, action);
                window.app?.showToast?.(`Elaborati ${result.processed}/${result.total_requested}`, 'success');
                this.selected.clear();
                this._updateBulkBar();
                await this.loadAndRender();
            } catch (err) {
                window.app?.showToast?.(`Errore bulk ${verb}: ${err.message}`, 'error');
            }
        }

        _escapeHtml(s) {
            return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
        }

        unmount() {
            this.container.innerHTML = '';
        }
    }

    window.SuggestionsView = SuggestionsView;
})();
