(function () {
    'use strict';

    const RISK_BAND_COLORS = {
        negligible: '#276749',
        low: '#d4870e',
        medium: '#dd6b20',
        high: '#c53030',
        critical: '#9b2c2c'
    };
    const RISK_BAND_LABELS = {
        negligible: 'Trascurabile',
        low: 'Basso',
        medium: 'Medio',
        high: 'Alto',
        critical: 'Critico'
    };
    const RISK_BAND_THRESHOLDS = [
        { max: 80, band: 'negligible', label: '< 80 dB(A)', color: RISK_BAND_COLORS.negligible },
        { max: 85, band: 'low', label: '80-85 dB(A)', color: RISK_BAND_COLORS.low },
        { max: 87, band: 'medium', label: '85-87 dB(A)', color: RISK_BAND_COLORS.medium },
        { max: 999, band: 'high', label: '\u2265 87 dB(A)', color: RISK_BAND_COLORS.high }
    ];
    const ORIGIN_LABELS = {
        measured: 'Misurata',
        calculated: 'Calcolata',
        estimated: 'Stimata',
        imported: 'Importata',
        ai_suggested: 'AI',
        validated: 'Validata',
        default_value: 'Default'
    };
    const MITIGATION_TYPE_LABELS = {
        engineering: 'Tecnica',
        administrative: 'Amministrativa',
        ppe: 'DPI',
        technical: 'Tecnica',
        medical: 'Medica',
        training: 'Formazione'
    };
    const SECTION_ORDER = ['identificazione', 'processi', 'valutazione', 'misure_prevenzione', 'sorveglianza', 'formazione'];
    const SECTION_LABELS = {
        identificazione: '1. Identificazione',
        processi: '2. Processi e Attivit\u00e0',
        valutazione: '3. Valutazione Rischio',
        misure_prevenzione: '4. Misure Prevenzione',
        sorveglianza: '6. Sorveglianza Sanitaria',
        formazione: '7. Formazione'
    };

    class App {
        constructor() {
            this.currentView = 'dashboard';
            this.allAssessments = [];
            this.allCompanies = [];
            this.searchFilter = '';
            this.statusFilter = '';
            this.phases = [];
            this.calculationResult = null;
            this.toastContainer = document.getElementById('toast-container');
            window.apiClient = new window.APIClient();
            this.setupRouting();
            this.setupNavigation();
            this.loadInitialView();
        }

        setupRouting() {
            window.addEventListener('hashchange', () => this.handleRoute());
        }

        setupNavigation() {
            document.querySelectorAll('.nav-link').forEach(link => {
                link.addEventListener('click', e => {
                    e.preventDefault();
                    window.location.hash = link.getAttribute('href');
                });
            });
        }

        setActiveNav(view) {
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            const active = document.querySelector(`.nav-link[data-view="${view}"]`);
            if (active) active.classList.add('active');
        }

        handleRoute() {
            const hash = window.location.hash || '#dashboard';
            const route = hash.substring(1);
            if (route.startsWith('assessment/')) {
                this.showAssessmentDetail(route.split('/')[1]);
                return;
            }
            const valid = ['dashboard', 'assessments', 'companies', 'catalog', 'templates', 'settings'];
            this.navigateTo(valid.includes(route) ? route : 'dashboard');
        }

        navigateTo(view) {
            this.currentView = view;
            this.setActiveNav(view);
            this.loadView(view);
        }

        loadInitialView() {
            this.handleRoute();
        }

        loadView(view) {
            const mc = document.getElementById('main-content');
            if (!mc) return;
            mc.style.animation = 'none';
            mc.offsetHeight;
            mc.style.animation = 'fadeIn 0.3s var(--ease) both';

            switch (view) {
                case 'dashboard': this.renderDashboard(mc); break;
                case 'assessments': this.renderAssessments(mc); break;
                case 'companies': this.renderCompanies(mc); break;
                case 'catalog': this.renderCatalog(mc); break;
                case 'templates': this.renderTemplates(mc); break;
                case 'settings': this.renderSettings(mc); break;
                default: this.renderDashboard(mc);
            }
        }

        // ── Dashboard ──
        renderDashboard(c) {
            c.innerHTML = `
                <div class="dashboard-header">
                    <h1>Dashboard</h1>
                    <p>Panoramica delle valutazioni rischio rumore</p>
                </div>
                <div class="dashboard-grid">
                    <div class="stat-card"><p class="stat-label">Valutazioni Totali</p><p class="stat-value" id="stat-total">-</p></div>
                    <div class="stat-card accent"><p class="stat-label">In Corso</p><p class="stat-value" id="stat-active">-</p></div>
                    <div class="stat-card success"><p class="stat-label">Completate</p><p class="stat-value" id="stat-archived">-</p></div>
                    <div class="stat-card"><p class="stat-label">Aziende</p><p class="stat-value" id="stat-companies">-</p></div>
                </div>
                <h2 class="section-title">Attivit\u00e0 Recente</h2>
                <div id="recent-activity" class="activity-list">
                    <div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento...</p></div>
                </div>`;
            this.loadDashboardData();
        }

        async loadDashboardData() {
            try {
                const [assessments, companies] = await Promise.all([
                    window.apiClient.listAssessments().catch(() => []),
                    window.apiClient.listCompanies().catch(() => [])
                ]);
                this.allAssessments = Array.isArray(assessments) ? assessments : [];
                const t = document.getElementById('stat-total');
                const a = document.getElementById('stat-active');
                const ar = document.getElementById('stat-archived');
                const co = document.getElementById('stat-companies');
                if (t) t.textContent = this.allAssessments.length;
                if (a) a.textContent = this.allAssessments.filter(x => x.status === 'active').length;
                if (ar) ar.textContent = this.allAssessments.filter(x => x.status === 'archived').length;
                if (co) co.textContent = Array.isArray(companies) ? companies.length : 0;

                const el = document.getElementById('recent-activity');
                if (!this.allAssessments.length) {
                    el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna valutazione</p><p class="empty-state-desc">Crea la prima valutazione dalla sezione Valutazioni</p></div>';
                    return;
                }
                el.innerHTML = this.allAssessments.slice(0, 8).map(a => `
                    <div class="activity-item" style="cursor:pointer" onclick="window.app.viewAssessment('${a.id}')">
                        <span class="activity-date">${a.assessment_date ? new Date(a.assessment_date).toLocaleDateString('it-IT') : '-'}</span>
                        <span class="activity-desc">${a.description || 'Valutazione Rischio Rumore'}</span>
                        <span class="status-badge badge-${a.status}">${{ active: 'Attiva', archived: 'Archiviata', inactive: 'Inattiva' }[a.status] || a.status}</span>
                    </div>`).join('');
            } catch (e) {
                console.warn('Dashboard load error:', e);
            }
        }

        // ── Assessments List ──
        renderAssessments(c) {
            c.innerHTML = `
                <div class="view-header">
                    <h1>Valutazioni</h1>
                    <button class="btn btn-accent" id="new-assessment-btn">+ Nuova Valutazione</button>
                </div>
                <div class="assessments-filters">
                    <input type="text" id="search-assessments" class="search-input" placeholder="Cerca valutazioni...">
                    <select id="filter-status" class="filter-select">
                        <option value="">Tutti gli stati</option>
                        <option value="active">Attiva</option>
                        <option value="archived">Archiviata</option>
                    </select>
                </div>
                <div id="assessments-list">
                    <div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento valutazioni...</p></div>
                </div>`;
            this.loadAssessments();
            this.bindAssessmentEvents();
        }

        async loadAssessments() {
            try {
                const data = await window.apiClient.listAssessments();
                this.allAssessments = Array.isArray(data) ? data : [];
                this.searchFilter = '';
                this.statusFilter = '';
                this.renderAssessmentsList(this.allAssessments);
            } catch (e) {
                const el = document.getElementById('assessments-list');
                if (el) el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u26a0\ufe0f</div><p class="empty-state-title">Errore di caricamento</p><p class="empty-state-desc">Impossibile caricare le valutazioni</p></div>';
            }
        }

        renderAssessmentsList(list) {
            const el = document.getElementById('assessments-list');
            if (!list.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna valutazione</p><p class="empty-state-desc">Crea una nuova valutazione per iniziare</p></div>';
                return;
            }
            el.innerHTML = list.map(a => {
                const label = { active: 'Attiva', archived: 'Archiviata', inactive: 'Inattiva' }[a.status] || a.status;
                const date = a.assessment_date ? new Date(a.assessment_date).toLocaleDateString('it-IT') : '-';
                return `<div class="assessment-card" onclick="window.app.viewAssessment('${a.id}')">
                    <div class="assessment-info">
                        <h3>${a.description || 'Valutazione Rischio Rumore'}</h3>
                        <p class="assessment-meta">${date} &mdash; ${label}</p>
                    </div>
                    <div class="assessment-actions">
                        <button class="btn btn-secondary btn-small" onclick="event.stopPropagation(); window.app.exportAssessment('${a.id}')">Esporta</button>
                    </div>
                </div>`;
            }).join('');
        }

        bindAssessmentEvents() {
            const nb = document.getElementById('new-assessment-btn');
            if (nb) nb.addEventListener('click', () => this.showNewAssessmentModal());
            const si = document.getElementById('search-assessments');
            if (si) si.addEventListener('input', e => { this.searchFilter = e.target.value.toLowerCase(); this.applyFilters(); });
            const sf = document.getElementById('filter-status');
            if (sf) sf.addEventListener('change', e => { this.statusFilter = e.target.value; this.applyFilters(); });
        }

        applyFilters() {
            let f = this.allAssessments;
            if (this.searchFilter) f = f.filter(a => (a.description || '').toLowerCase().includes(this.searchFilter) || (a.status || '').toLowerCase().includes(this.searchFilter));
            if (this.statusFilter) f = f.filter(a => a.status === this.statusFilter);
            this.renderAssessmentsList(f);
        }

        viewAssessment(id) { window.location.hash = '#assessment/' + id; }

        // ── Assessment Detail with Tabs ──
        showAssessmentDetail(id) {
            this.setActiveNav('');
            this.currentAssessmentId = id;
            const mc = document.getElementById('main-content');
            mc.innerHTML = `
                <div class="view-header">
                    <h1>Dettaglio Valutazione</h1>
                    <button class="btn btn-secondary" onclick="window.location.hash='#assessments'">&larr; Torna alle valutazioni</button>
                </div>
                <div class="detail-tabs" id="detail-tabs">
                    <button class="detail-tab active" data-tab="general" onclick="window.app.switchTab('general','${id}')">Dati Generali</button>
                    <button class="detail-tab" data-tab="exposure" onclick="window.app.switchTab('exposure','${id}')">Fasi Esposizione</button>
                    <button class="detail-tab" data-tab="mitigations" onclick="window.app.switchTab('mitigations','${id}')">Misure Prevenzione</button>
                    <button class="detail-tab" data-tab="machines" onclick="window.app.switchTab('machines','${id}')">Macchinari</button>
                    <button class="detail-tab" data-tab="document" onclick="window.app.switchTab('document','${id}')">Documento DVR</button>
                    <button class="detail-tab" data-tab="ai" onclick="window.app.switchTab('ai','${id}')">AI Assistant</button>
                </div>
                <div id="tab-content" class="tab-content">
                    <div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento...</p></div>
                </div>
                <div class="form-actions" style="margin-top:1.5rem" id="detail-actions"></div>`;
            this.loadAssessmentAndTab(id, 'general');
        }

        async loadAssessmentAndTab(id, tab) {
            try {
                this._assessment = await window.apiClient.getAssessment(id);
            } catch (e) {
                this._assessment = null;
            }
            this.switchTab(tab, id);
        }

        switchTab(tab, id) {
            document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
            const activeTab = document.querySelector(`.detail-tab[data-tab="${tab}"]`);
            if (activeTab) activeTab.classList.add('active');
            const tc = document.getElementById('tab-content');
            const da = document.getElementById('detail-actions');
            if (da) da.innerHTML = '';
            switch (tab) {
                case 'general': this.renderTabGeneral(tc, id); break;
                case 'exposure': this.renderTabExposure(tc, id); break;
                case 'mitigations': this.renderTabMitigations(tc, id); break;
                case 'machines': this.renderTabMachines(tc, id); break;
                case 'document': this.renderTabDocument(tc, id); break;
                case 'ai': this.renderTabAI(tc, id); break;
            }
        }

        // ── Tab: Dati Generali ──
        renderTabGeneral(tc, id) {
            const a = this._assessment;
            if (!a) { tc.innerHTML = '<div class="empty-state"><p>Errore caricamento valutazione</p></div>'; return; }
            const da = document.getElementById('detail-actions');
            da.innerHTML = `
                <button class="btn btn-danger btn-small" onclick="window.app.deleteAssessment('${id}')">Elimina</button>
                <button class="btn btn-accent" onclick="window.app.exportAssessment('${id}')">Esporta DOCX</button>`;

            tc.innerHTML = `
                <div class="detail-grid">
                    <div class="form-group">
                        <label>Descrizione</label>
                        <input type="text" id="f-description" class="form-control" value="${a.description || ''}">
                    </div>
                    <div class="form-group">
                        <label>Stato</label>
                        <select id="f-status" class="form-control">
                            <option value="active" ${a.status === 'active' ? 'selected' : ''}>Attiva</option>
                            <option value="inactive" ${a.status === 'inactive' ? 'selected' : ''}>Inattiva</option>
                            <option value="archived" ${a.status === 'archived' ? 'selected' : ''}>Archiviata</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Data Valutazione</label>
                        <input type="date" id="f-date" class="form-control" value="${a.assessment_date ? a.assessment_date.substring(0, 10) : ''}">
                    </div>
                    <div class="form-group">
                        <label>Prossima Revisione</label>
                        <input type="date" id="f-next-review" class="form-control" value="${a.next_review_date ? a.next_review_date.substring(0, 10) : ''}">
                    </div>
                    <div class="form-group">
                        <label>Protocollo Misura</label>
                        <input type="text" id="f-protocol" class="form-control" value="${a.measurement_protocol || ''}" placeholder="es. ISO 9612">
                    </div>
                    <div class="form-group">
                        <label>Classe Strumento</label>
                        <select id="f-instrument" class="form-control">
                            <option value="">-- Seleziona --</option>
                            <option value="1" ${a.instrument_class === '1' ? 'selected' : ''}>Classe 1</option>
                            <option value="2" ${a.instrument_class === '2' ? 'selected' : ''}>Classe 2</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Lavoratori Esposti</label>
                        <input type="number" id="f-workers" class="form-control" min="0" value="${a.workers_count_exposed || 0}">
                    </div>
                    <div class="form-group">
                        <label>Versione</label>
                        <input type="text" class="form-control" value="${a.version || 1}" disabled>
                    </div>
                </div>
                <div class="form-actions" style="margin-top:1rem">
                    <button class="btn btn-primary" id="save-general-btn">Salva Modifiche</button>
                </div>`;

            document.getElementById('save-general-btn').addEventListener('click', async () => {
                try {
                    await window.apiClient.updateAssessment(id, {
                        description: document.getElementById('f-description').value || undefined,
                        status: document.getElementById('f-status').value,
                        measurement_protocol: document.getElementById('f-protocol').value || undefined,
                        instrument_class: document.getElementById('f-instrument').value || undefined,
                        workers_count_exposed: parseInt(document.getElementById('f-workers').value) || 0
                    });
                    this.showToast('Valutazione aggiornata', 'success');
                } catch (e) {
                    this.showToast('Errore: ' + e.message, 'error');
                }
            });
        }

        // ── Tab: Fasi Esposizione + Calcolo ──
        renderTabExposure(tc, id) {
            this.phases = [];
            this.calculationResult = null;
            tc.innerHTML = `
                <div class="exposure-layout">
                    <div class="exposure-form-panel">
                        <h3 style="margin-bottom:1rem">Aggiungi Fase di Esposizione</h3>
                        <div class="form-group">
                            <label>LAeq dB(A) <span style="color:var(--c-slate-400)">(0-140)</span></label>
                            <div class="input-with-unit">
                                <input type="number" id="f-laeq" class="form-control" min="0" max="140" step="0.1" value="80">
                                <span class="input-unit">dB(A)</span>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Durata <span style="color:var(--c-slate-400)">(ore, max 24)</span></label>
                            <div class="input-with-unit">
                                <input type="number" id="f-duration" class="form-control" min="0.25" max="24" step="0.25" value="8">
                                <span class="input-unit">h</span>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Origine Dato</label>
                            <select id="f-origin" class="form-control">
                                <option value="measured">Misurata</option>
                                <option value="calculated">Calcolata</option>
                                <option value="estimated">Stimata</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>LCPicco dB(C) <span style="color:var(--c-slate-400)">(opzionale)</span></label>
                            <div class="input-with-unit">
                                <input type="number" id="f-lcpeak" class="form-control" min="0" max="200" step="0.1" value="">
                                <span class="input-unit">dB(C)</span>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Rumore di Fondo dB(A) <span style="color:var(--c-slate-400)">(opzionale)</span></label>
                            <div class="input-with-unit">
                                <input type="number" id="f-background" class="form-control" min="0" max="140" step="0.1" value="">
                                <span class="input-unit">dB(A)</span>
                            </div>
                        </div>
                        <button class="btn btn-primary btn-block" id="add-phase-btn">+ Aggiungi Fase</button>
                    </div>
                    <div class="exposure-phases-panel">
                        <h3 style="margin-bottom:1rem">Fasi Inserite</h3>
                        <div id="phases-table-container">
                            <div class="empty-state"><p class="empty-state-desc">Nessuna fase inserita</p></div>
                        </div>
                        <div style="margin-top:1.25rem">
                            <button class="btn btn-accent" id="calculate-btn" disabled>Calcola LEX,8h</button>
                        </div>
                    </div>
                </div>
                <div id="calculation-result" style="margin-top:1.5rem"></div>`;

            document.getElementById('add-phase-btn').addEventListener('click', () => this.addPhase());
            document.getElementById('calculate-btn').addEventListener('click', () => this.calculateExposure(id));
        }

        addPhase() {
            const laeq = parseFloat(document.getElementById('f-laeq').value);
            const duration = parseFloat(document.getElementById('f-duration').value);
            const origin = document.getElementById('f-origin').value;
            const lcpeak = document.getElementById('f-lcpeak').value ? parseFloat(document.getElementById('f-lcpeak').value) : null;
            const background = document.getElementById('f-background').value ? parseFloat(document.getElementById('f-background').value) : null;

            if (isNaN(laeq) || laeq < 0 || laeq > 140) {
                this.showToast('LAeq deve essere tra 0 e 140 dB(A)', 'error');
                return;
            }
            if (isNaN(duration) || duration <= 0 || duration > 24) {
                this.showToast('Durata deve essere tra 0.25 e 24 ore', 'error');
                return;
            }

            this.phases.push({ laeq_db_a: laeq, duration_hours: duration, origin, lcpeak_db_c: lcpeak, background_noise_db_a: background });
            this.renderPhasesTable();
            document.getElementById('calculate-btn').disabled = false;
            document.getElementById('f-laeq').value = '';
            document.getElementById('f-duration').value = '8';
            document.getElementById('f-lcpeak').value = '';
            document.getElementById('f-background').value = '';
            this.showToast('Fase aggiunta', 'success');
        }

        removePhase(index) {
            this.phases.splice(index, 1);
            this.renderPhasesTable();
            if (!this.phases.length) document.getElementById('calculate-btn').disabled = true;
        }

        renderPhasesTable() {
            const container = document.getElementById('phases-table-container');
            if (!this.phases.length) {
                container.innerHTML = '<div class="empty-state"><p class="empty-state-desc">Nessuna fase inserita</p></div>';
                return;
            }
            container.innerHTML = `
                <table class="phases-table">
                    <thead>
                        <tr><th>#</th><th>LAeq</th><th>Durata</th><th>Origine</th><th>LCPicco</th><th>Fondo</th><th></th></tr>
                    </thead>
                    <tbody>
                        ${this.phases.map((p, i) => `<tr>
                            <td>${i + 1}</td>
                            <td><strong>${p.laeq_db_a.toFixed(1)}</strong> dB(A)</td>
                            <td>${p.duration_hours} h</td>
                            <td><span class="status-badge badge-origin-${p.origin}">${ORIGIN_LABELS[p.origin] || p.origin}</span></td>
                            <td>${p.lcpeak_db_c != null ? p.lcpeak_db_c.toFixed(1) + ' dB(C)' : '-'}</td>
                            <td>${p.background_noise_db_a != null ? p.background_noise_db_a.toFixed(1) + ' dB(A)' : '-'}</td>
                            <td><button class="btn btn-danger btn-small" onclick="window.app.removePhase(${i})">&times;</button></td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        }

        async calculateExposure(assessmentId) {
            if (!this.phases.length) { this.showToast('Inserisci almeno una fase', 'error'); return; }
            this.showToast('Calcolo in corso...', 'info');
            try {
                const result = await window.apiClient.calculateNoise({
                    assessment_id: assessmentId,
                    exposures: this.phases,
                    apply_k_corrections: true
                });
                this.calculationResult = result;
                this.renderCalculationResult(result);
                this.showToast('Calcolo completato', 'success');
            } catch (e) {
                this.showToast('Errore calcolo: ' + e.message, 'error');
            }
        }

        renderCalculationResult(result) {
            const el = document.getElementById('calculation-result');
            const band = result.risk_band || 'negligible';
            const color = RISK_BAND_COLORS[band] || RISK_BAND_COLORS.negligible;
            const label = RISK_BAND_LABELS[band] || band;
            const lex = result.lex_8h != null ? result.lex_8h.toFixed(1) : '-';

            el.innerHTML = `
                <div class="calc-result-card">
                    <div class="calc-main">
                        <div class="calc-lex" style="border-color:${color}">
                            <span class="calc-lex-label">LEX,8h</span>
                            <span class="calc-lex-value" style="color:${color}">${lex}</span>
                            <span class="calc-lex-unit">dB(A)</span>
                        </div>
                        <div class="calc-risk-band">
                            <span class="risk-pill" style="background:${color};color:white">${label}</span>
                            <div class="risk-bar">
                                ${RISK_BAND_THRESHOLDS.map(t => `<div class="risk-bar-segment" style="background:${t.color};flex:${t.max === 999 ? 13 : t.max - (t.max === 85 ? 80 : t.max === 87 ? 85 : t.max === 80 ? 0 : 87)}" title="${t.label}"></div>`).join('')}
                                <div class="risk-bar-marker" style="left:${Math.min(Math.max((result.lex_8h - 60) / 40 * 100, 0), 100)}%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="calc-details">
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">LEX,weekly</span>
                            <span class="calc-detail-value">${result.lex_weekly != null ? result.lex_weekly.toFixed(1) + ' dB(A)' : '-'}</span>
                        </div>
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">LCPicco aggregato</span>
                            <span class="calc-detail-value">${result.lcpeak_aggregated != null ? result.lcpeak_aggregated.toFixed(1) + ' dB(C)' : '-'}</span>
                        </div>
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">Incertezza (k=2)</span>
                            <span class="calc-detail-value">\u00b1 ${result.uncertainty_db != null ? result.uncertainty_db.toFixed(1) : '-'} dB</span>
                        </div>
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">Confidenza</span>
                            <span class="calc-detail-value">${result.confidence_score != null ? (result.confidence_score * 100).toFixed(0) + '%' : '-'}</span>
                        </div>
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">K impulso</span>
                            <span class="calc-detail-value">${result.k_impulse != null ? '+' + result.k_impulse.toFixed(0) : '0'} dB</span>
                        </div>
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">K tono</span>
                            <span class="calc-detail-value">${result.k_tone != null ? '+' + result.k_tone.toFixed(0) : '0'} dB</span>
                        </div>
                        <div class="calc-detail-item">
                            <span class="calc-detail-label">K fondo</span>
                            <span class="calc-detail-value">${result.k_background != null ? result.k_background.toFixed(0) : '0'} dB</span>
                        </div>
                    </div>
                </div>`;
        }

        // ── Tab: Misure di Prevenzione ──
        async renderTabMitigations(tc, id) {
            tc.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento misure...</p></div>';
            try {
                const mitigations = await window.apiClient.listMitigations(id);
                this._mitigations = Array.isArray(mitigations) ? mitigations : [];
            } catch (e) {
                this._mitigations = [];
            }
            this.renderMitigationsList(tc, id);
        }

        renderMitigationsList(tc, id) {
            const addBtn = `<button class="btn btn-accent btn-small" id="add-mitigation-btn" style="margin-bottom:1rem">+ Aggiungi Misura</button>`;
            if (!this._mitigations.length) {
                tc.innerHTML = `${addBtn}<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna misura di prevenzione</p><p class="empty-state-desc">Aggiungi misure tecniche, amministrative o DPI</p></div>`;
            } else {
                tc.innerHTML = `${addBtn}<table class="phases-table">
                    <thead><tr><th>Tipo</th><th>Titolo</th><th>Priorit\u00e0</th><th>Stato</th><th>Costo</th><th></th></tr></thead>
                    <tbody>${this._mitigations.map(m => `<tr>
                        <td><span class="status-badge badge-mitigation-${m.type}">${MITIGATION_TYPE_LABELS[m.type] || m.type}</span></td>
                        <td><strong>${m.title}</strong><br><small style="color:var(--c-slate-500)">${m.description || ''}</small></td>
                        <td>${m.priority || '-'}</td>
                        <td><span class="status-badge badge-mitigation-status-${m.status}">${m.status || 'pending'}</span></td>
                        <td>${m.cost_euro != null ? '\u20ac ' + parseFloat(m.cost_euro).toLocaleString('it-IT') : '-'}</td>
                        <td><button class="btn btn-danger btn-small" onclick="window.app.deleteMitigation('${m.id}','${id}')">&times;</button></td>
                    </tr>`).join('')}</tbody></table>`;
            }
            const ab = document.getElementById('add-mitigation-btn');
            if (ab) ab.addEventListener('click', () => this.showMitigationModal(id));
        }

        showMitigationModal(assessmentId) {
            this.showModal('Nuova Misura di Prevenzione', `
                <div class="form-group"><label>Tipo</label>
                    <select id="m-type" class="form-control">
                        <option value="engineering">Tecnica (ingegneristica)</option>
                        <option value="administrative">Amministrativa</option>
                        <option value="ppe">DPI (protezione individuale)</option>
                    </select>
                </div>
                <div class="form-group"><label>Titolo *</label><input type="text" id="m-title" class="form-control" placeholder="es. Cabina insonorizzata"></div>
                <div class="form-group"><label>Descrizione</label><textarea id="m-desc" class="form-control" rows="3"></textarea></div>
                <div class="form-group"><label>Priorit\u00e0 (1=massima)</label><input type="number" id="m-priority" class="form-control" min="1" max="5" value="3"></div>
                <div class="form-group"><label>Costo stimato (\u20ac)</label><input type="number" id="m-cost" class="form-control" min="0" step="100" value=""></div>
            `, async () => {
                const title = document.getElementById('m-title').value.trim();
                if (!title) { this.showToast('Titolo obbligatorio', 'error'); return false; }
                const data = {
                    assessment_id: assessmentId,
                    type: document.getElementById('m-type').value,
                    title,
                    description: document.getElementById('m-desc').value.trim() || undefined,
                    priority: parseInt(document.getElementById('m-priority').value) || 3,
                    cost_euro: document.getElementById('m-cost').value ? parseFloat(document.getElementById('m-cost').value) : undefined
                };
                await window.apiClient.createMitigation(data);
                this.showToast('Misura aggiunta', 'success');
                this.closeModal();
                const tc = document.getElementById('tab-content');
                this.renderTabMitigations(tc, assessmentId);
                return true;
            });
        }

        async deleteMitigation(mitigationId, assessmentId) {
            if (!confirm('Eliminare questa misura?')) return;
            try {
                await window.apiClient.deleteMitigation(mitigationId);
                this.showToast('Misura eliminata', 'success');
                const tc = document.getElementById('tab-content');
                this.renderTabMitigations(tc, assessmentId);
            } catch (e) {
                this.showToast('Errore: ' + e.message, 'error');
            }
        }

        // ── Tab: Macchinari ──
        async renderTabMachines(tc, id) {
            tc.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento macchinari...</p></div>';
            try {
                const a = this._assessment;
                if (a && a.company_id) {
                    const machines = await window.apiClient.listMachineAssets(a.company_id);
                    this._machines = Array.isArray(machines) ? machines : [];
                } else {
                    this._machines = [];
                }
            } catch (e) {
                this._machines = [];
            }
            this.renderMachinesList(tc, id);
        }

        renderMachinesList(tc, assessmentId) {
            const companyId = this._assessment ? this._assessment.company_id : '';
            const addBtn = `<button class="btn btn-accent btn-small" id="add-machine-btn" style="margin-bottom:1rem">+ Aggiungi Macchinario</button>`;
            if (!this._machines.length) {
                tc.innerHTML = `${addBtn}<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessun macchinario</p><p class="empty-state-desc">Aggiungi i macchinari dell'azienda</p></div>`;
            } else {
                tc.innerHTML = `${addBtn}<table class="phases-table">
                    <thead><tr><th>Marca</th><th>Modello</th><th>Matricola</th><th>Data Acquisizione</th><th></th></tr></thead>
                    <tbody>${this._machines.map(m => `<tr>
                        <td>${m.marca}</td>
                        <td>${m.modello}</td>
                        <td>${m.matricola || '-'}</td>
                        <td>${m.acquisition_date || '-'}</td>
                        <td><button class="btn btn-danger btn-small" onclick="window.app.deleteMachine('${m.id}','${assessmentId}')">&times;</button></td>
                    </tr>`).join('')}</tbody></table>`;
            }
            const ab = document.getElementById('add-machine-btn');
            if (ab) ab.addEventListener('click', () => this.showMachineModal(companyId, assessmentId));
        }

        showMachineModal(companyId, assessmentId) {
            this.showModal('Nuovo Macchinario', `
                <div class="form-group"><label>Marca *</label><input type="text" id="mc-marca" class="form-control" placeholder="es. Hilti"></div>
                <div class="form-group"><label>Modello *</label><input type="text" id="mc-modello" class="form-control" placeholder="es. TE 70-ATC"></div>
                <div class="form-group"><label>Matricola</label><input type="text" id="mc-matricola" class="form-control"></div>
                <div class="form-group"><label>Data Acquisizione</label><input type="date" id="mc-date" class="form-control"></div>
            `, async () => {
                const marca = document.getElementById('mc-marca').value.trim();
                const modello = document.getElementById('mc-modello').value.trim();
                if (!marca || !modello) { this.showToast('Marca e Modello obbligatori', 'error'); return false; }
                const data = {
                    company_id: companyId,
                    marca,
                    modello,
                    matricola: document.getElementById('mc-matricola').value.trim() || undefined,
                    acquisition_date: document.getElementById('mc-date').value || undefined
                };
                await window.apiClient.createMachineAsset(data);
                this.showToast('Macchinario aggiunto', 'success');
                this.closeModal();
                const tc = document.getElementById('tab-content');
                this.renderTabMachines(tc, assessmentId);
                return true;
            });
        }

        async deleteMachine(machineId, assessmentId) {
            if (!confirm('Eliminare questo macchinario?')) return;
            try {
                await window.apiClient.deleteMachineAsset(machineId);
                this.showToast('Macchinario eliminato', 'success');
                const tc = document.getElementById('tab-content');
                this.renderTabMachines(tc, assessmentId);
            } catch (e) {
                this.showToast('Errore: ' + e.message, 'error');
            }
        }

        // ── Tab: Documento DVR ──
        async renderTabDocument(tc, id) {
            tc.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento sezioni documento...</p></div>';
            try {
                const sections = await window.apiClient.getAssessmentSections(id);
                this._sections = Array.isArray(sections) ? sections : [];
            } catch (e) {
                this._sections = [];
            }
            this.renderDocumentSections(tc, id);
        }

        renderDocumentSections(tc, assessmentId) {
            const da = document.getElementById('detail-actions');
            if (da) {
                da.innerHTML = `
                    <button class="btn btn-secondary" onclick="window.app.exportAssessment('${assessmentId}')">Esporta DOCX</button>
                    <button class="btn btn-secondary" onclick="window.app.exportJSON('${assessmentId}')">Esporta JSON</button>`;
            }

            if (!this._sections.length) {
                tc.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna sezione</p><p class="empty-state-desc">Genera il documento con AI o esporta</p></div>';
                return;
            }

            const sectionTabs = this._sections.map((s, i) => {
                const key = s.id || Object.keys(SECTION_LABELS)[i] || `s${i}`;
                return `<button class="section-tab ${i === 0 ? 'active' : ''}" data-sec="${key}" onclick="window.app.switchSectionTab('${key}','${assessmentId}')">${SECTION_LABELS[key] || s.title || key}</button>`;
            }).join('');

            tc.innerHTML = `
                <div class="section-tabs">${sectionTabs}</div>
                <div id="section-editor-container"></div>`;

            this.switchSectionTab(this._sections[0].id || Object.keys(SECTION_LABELS)[0], assessmentId);
        }

        switchSectionTab(sectionKey, assessmentId) {
            document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
            const activeTab = document.querySelector(`.section-tab[data-sec="${sectionKey}"]`);
            if (activeTab) activeTab.classList.add('active');

            const section = this._sections.find(s => s.id === sectionKey);
            const container = document.getElementById('section-editor-container');
            const content = section ? (section.content_html || section.content || '') : '';

            container.innerHTML = `
                <div class="editor-toolbar">
                    <button class="btn btn-small" onclick="document.execCommand('bold')" title="Grassetto"><strong>B</strong></button>
                    <button class="btn btn-small" onclick="document.execCommand('italic')" title="Corsivo"><em>I</em></button>
                    <button class="btn btn-small" onclick="document.execCommand('underline')" title="Sottolinea"><u>U</u></button>
                    <button class="btn btn-small" onclick="document.execCommand('insertUnorderedList')" title="Lista">&bull; Lista</button>
                    <button class="btn btn-small" onclick="document.execCommand('insertOrderedList')" title="Lista numerata">1. Lista</button>
                </div>
                <div id="section-editor" contenteditable="true" class="rich-editor">${content}</div>
                <div class="form-actions" style="margin-top:0.75rem">
                    <button class="btn btn-primary btn-small" id="save-section-btn">Salva Sezione</button>
                    <span id="save-indicator" style="color:var(--c-green);font-weight:600;display:none;margin-left:0.5rem">Salvato</span>
                </div>`;

            document.getElementById('save-section-btn').addEventListener('click', async () => {
                const ed = document.getElementById('section-editor');
                if (!ed) return;
                try {
                    await window.apiClient.updateSection(assessmentId, sectionKey, ed.innerHTML);
                    this.showToast('Sezione salvata', 'success');
                    const ind = document.getElementById('save-indicator');
                    if (ind) { ind.style.display = 'inline'; setTimeout(() => ind.style.display = 'none', 3000); }
                } catch (e) {
                    this.showToast('Errore salvataggio: ' + e.message, 'error');
                }
            });
        }

        async exportAssessment(id) {
            this.showToast('Preparazione documento...', 'info');
            try {
                const blob = await window.apiClient.exportDOCX(id, { language: 'it' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `DVR_RUMORE_${id}.docx`; a.click();
                URL.revokeObjectURL(url);
                this.showToast('Documento scaricato!', 'success');
            } catch (e) {
                this.showToast('Esportazione fallita: ' + e.message, 'error');
            }
        }

        async exportJSON(id) {
            try {
                const data = await window.apiClient.exportJSON(id, 'it');
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `DVR_RUMORE_${id}.json`; a.click();
                URL.revokeObjectURL(url);
                this.showToast('JSON esportato', 'success');
            } catch (e) {
                this.showToast('Esportazione fallita: ' + e.message, 'error');
            }
        }

        async deleteAssessment(id) {
            if (!confirm('Eliminare questa valutazione? L\'operazione \u00e8 irreversibile.')) return;
            try {
                await window.apiClient.deleteAssessment(id);
                this.showToast('Valutazione eliminata', 'success');
                window.location.hash = '#assessments';
            } catch (e) {
                this.showToast('Errore: ' + e.message, 'error');
            }
        }

        // ── Tab: AI Assistant ──
        renderTabAI(tc, id) {
            const a = this._assessment;
            tc.innerHTML = `
                <div class="ai-panel">
                    <div class="ai-actions-grid">
                        <div class="ai-action-card" id="ai-bootstrap-card">
                            <div class="ai-action-icon">\u{1F680}</div>
                            <h3>Bootstrap</h3>
                            <p>Imposta la valutazione con suggerimenti AI basati su codice ATECO</p>
                        </div>
                        <div class="ai-action-card" id="ai-sources-card">
                            <div class="ai-action-icon">\U0001F50D</div>
                            <h3>Rileva Sorgenti</h3>
                            <p>Identifica sorgenti di rumore da una descrizione testuale</p>
                        </div>
                        <div class="ai-action-card" id="ai-review-card">
                            <div class="ai-action-icon">\u2705</div>
                            <h3>Revisione</h3>
                            <p>Valida completezza, coerenza e correttezza della valutazione</p>
                        </div>
                        <div class="ai-action-card" id="ai-mitigations-card">
                            <div class="ai-action-icon">\u{1F6E1}\uFE0F</div>
                            <h3>Misure Prevenzione</h3>
                            <p>Suggerisci misure tecnich, amministrative e DPI</p>
                        </div>
                        <div class="ai-action-card" id="ai-narrative-card">
                            <div class="ai-action-icon">\u{1F4DD}</div>
                            <h3>Narrativa DVR</h3>
                            <p>Genera testo narrativo formale per il documento DVR</p>
                        </div>
                        <div class="ai-action-card" id="ai-explain-card">
                            <div class="ai-action-icon">\u{1F4A1}</div>
                            <h3>Spiega</h3>
                            <p>Spiegazione tecnica su calcoli, rischi e normativa</p>
                        </div>
                    </div>
                    <div id="ai-form-container"></div>
                    <div id="ai-result-container" style="margin-top:1.5rem"></div>
                </div>`;

            document.getElementById('ai-bootstrap-card').addEventListener('click', () => this.showAIBootstrapForm(id));
            document.getElementById('ai-sources-card').addEventListener('click', () => this.showAISourcesForm(id));
            document.getElementById('ai-review-card').addEventListener('click', () => this.runAIReview(id));
            document.getElementById('ai-mitigations-card').addEventListener('click', () => this.showAIMitigationsForm(id));
            document.getElementById('ai-narrative-card').addEventListener('click', () => this.showAINarrativeForm(id));
            document.getElementById('ai-explain-card').addEventListener('click', () => this.showAIExplainForm(id));
        }

        showAIBootstrapForm(assessmentId) {
            const a = this._assessment;
            document.getElementById('ai-form-container').innerHTML = `
                <div class="ai-form">
                    <h4>Bootstrap Valutazione AI</h4>
                    <div class="form-group">
                        <label>Codici ATECO <span style="color:var(--c-slate-400)">(separati da virgola)</span></label>
                        <input type="text" id="ai-ateco-codes" class="form-control" value="${a && a.ateco_code ? a.ateco_code : ''}" placeholder="25.11.00">
                    </div>
                    <div class="form-group">
                        <label>Descrizione Azienda</label>
                        <textarea id="ai-company-desc" class="form-control" rows="4" placeholder="Descrivi le attivit\u00e0 dell'azienda...">${a && a.description ? a.description : ''}</textarea>
                    </div>
                    <button class="btn btn-accent" id="ai-bootstrap-run">Avvia Bootstrap</button>
                </div>`;
            document.getElementById('ai-bootstrap-run').addEventListener('click', async () => {
                const codes = document.getElementById('ai-ateco-codes').value.split(',').map(s => s.trim()).filter(Boolean);
                const desc = document.getElementById('ai-company-desc').value.trim();
                if (!codes.length || !desc) { this.showToast('Codici ATECO e descrizione obbligatori', 'error'); return; }
                this.setAILoading();
                try {
                    const result = await window.apiClient.aiBootstrap(assessmentId, { ateco_codes: codes, company_description: desc });
                    this.renderAIResult(this.formatBootstrapResult(result));
                } catch (e) {
                    this.renderAIError(e.message);
                }
            });
        }

        showAISourcesForm(assessmentId) {
            document.getElementById('ai-form-container').innerHTML = `
                <div class="ai-form">
                    <h4>Rilevamento Sorgenti di Rumore</h4>
                    <div class="form-group">
                        <label>Descrizione attivit\u00e0 / processo</label>
                        <textarea id="ai-source-desc" class="form-control" rows="4" placeholder="es. Lavorazione metalli con trapano a colonna e smerigliatrice angolare..."></textarea>
                    </div>
                    <button class="btn btn-accent" id="ai-sources-run">Rileva Sorgenti</button>
                </div>`;
            document.getElementById('ai-sources-run').addEventListener('click', async () => {
                const desc = document.getElementById('ai-source-desc').value.trim();
                if (!desc || desc.length < 5) { this.showToast('Descrizione troppo breve (min 5 caratteri)', 'error'); return; }
                this.setAILoading();
                try {
                    const result = await window.apiClient.aiDetectSources(assessmentId, { description: desc });
                    this.renderAIResult(this.formatSourceDetectionResult(result));
                } catch (e) {
                    this.renderAIError(e.message);
                }
            });
        }

        async runAIReview(assessmentId) {
            const a = this._assessment;
            if (!a) { this.showToast('Carica prima la valutazione', 'error'); return; }
            this.setAILoading();
            try {
                const result = await window.apiClient.aiReview(assessmentId, {
                    assessment_id: assessmentId,
                    assessment_data: a
                });
                this.renderAIResult(this.formatReviewResult(result));
            } catch (e) {
                this.renderAIError(e.message);
            }
        }

        showAIMitigationsForm(assessmentId) {
            document.getElementById('ai-form-container').innerHTML = `
                <div class="ai-form">
                    <h4>Suggerimento Misure di Prevenzione AI</h4>
                    <div class="form-group">
                        <label>Includi DPI</label>
                        <select id="ai-include-ppe" class="form-control"><option value="true">S\u00ec</option><option value="false">No</option></select>
                    </div>
                    <div class="form-group">
                        <label>Includi misure ingegneristiche</label>
                        <select id="ai-include-eng" class="form-control"><option value="true">S\u00ec</option><option value="false">No</option></select>
                    </div>
                    <div class="form-group">
                        <label>Includi misure amministrative</label>
                        <select id="ai-include-admin" class="form-control"><option value="true">S\u00ec</option><option value="false">No</option></select>
                    </div>
                    <button class="btn btn-accent" id="ai-mitigations-run">Suggerisci Misure</button>
                </div>`;
            document.getElementById('ai-mitigations-run').addEventListener('click', async () => {
                this.setAILoading();
                try {
                    const result = await window.apiClient.aiSuggestMitigations(assessmentId, {
                        include_ppe: document.getElementById('ai-include-ppe').value === 'true',
                        include_engineering: document.getElementById('ai-include-eng').value === 'true',
                        include_administrative: document.getElementById('ai-include-admin').value === 'true'
                    });
                    this.renderAIResult(this.formatMitigationResult(result));
                } catch (e) {
                    this.renderAIError(e.message);
                }
            });
        }

        showAINarrativeForm(assessmentId) {
            const a = this._assessment;
            document.getElementById('ai-form-container').innerHTML = `
                <div class="ai-form">
                    <h4>Generazione Narrativa DVR</h4>
                    <div class="form-group">
                        <label>Nome Responsabile</label>
                        <input type="text" id="ai-resp-name" class="form-control" placeholder="Nome del datore di lavoro / RSPP">
                    </div>
                    <div class="form-group">
                        <label>Sezione specifica <span style="color:var(--c-slate-400)">(opzionale, vuoto=tutte)</span></label>
                        <select id="ai-section" class="form-control">
                            <option value="">Tutte le sezioni</option>
                            ${SECTION_ORDER.map(s => `<option value="${s}">${SECTION_LABELS[s]}</option>`).join('')}
                        </select>
                    </div>
                    <button class="btn btn-accent" id="ai-narrative-run">Genera Narrativa</button>
                </div>`;
            document.getElementById('ai-narrative-run').addEventListener('click', async () => {
                const respName = document.getElementById('ai-resp-name').value.trim();
                if (!respName) { this.showToast('Nome responsabile obbligatorio', 'error'); return; }
                this.setAILoading();
                try {
                    const data = {
                        assessment_id: assessmentId,
                        company_name: a && a.company_id ? '' : '',
                        ateco_code: a && a.ateco_code ? a.ateco_code : '',
                        assessment_date: a && a.assessment_date ? a.assessment_date.substring(0, 10) : new Date().toISOString().substring(0, 10),
                        responsible_name: respName
                    };
                    const section = document.getElementById('ai-section').value;
                    if (section) data.section = section;
                    const result = await window.apiClient.aiNarrative(assessmentId, data);
                    this.renderAIResult(this.formatNarrativeResult(result));
                } catch (e) {
                    this.renderAIError(e.message);
                }
            });
        }

        showAIExplainForm(assessmentId) {
            document.getElementById('ai-form-container').innerHTML = `
                <div class="ai-form">
                    <h4>Spiegazione Tecnica AI</h4>
                    <div class="form-group">
                        <label>Argomento</label>
                        <select id="ai-explain-subject" class="form-control">
                            <option value="lex_calculation">Calcolo LEX,8h</option>
                            <option value="risk_band">Classificazione Risk Band</option>
                            <option value="threshold">Significato Soglie (80/85/87 dB)</option>
                            <option value="mitigation">Misure di Prevenzione</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Livello Dettaglio</label>
                        <select id="ai-explain-level" class="form-control">
                            <option value="beginner">Principiante</option>
                            <option value="technical">Tecnico</option>
                            <option value="expert">Esperto</option>
                        </select>
                    </div>
                    <button class="btn btn-accent" id="ai-explain-run">Spiega</button>
                </div>`;
            document.getElementById('ai-explain-run').addEventListener('click', async () => {
                this.setAILoading();
                try {
                    const result = await window.apiClient.aiExplain(assessmentId, {
                        subject: document.getElementById('ai-explain-subject').value,
                        level: document.getElementById('ai-explain-level').value,
                        target_id: assessmentId
                    });
                    this.renderAIResult(this.formatExplainResult(result));
                } catch (e) {
                    this.renderAIError(e.message);
                }
            });
        }

        setAILoading() {
            document.getElementById('ai-result-container').innerHTML = '<div class="ai-loading"><div class="ai-spinner"></div><p>AI in elaborazione...</p></div>';
        }

        renderAIResult(html) {
            document.getElementById('ai-result-container').innerHTML = `<div class="ai-result-card">${html}</div>`;
        }

        renderAIError(msg) {
            document.getElementById('ai-result-container').innerHTML = `<div class="ai-result-card ai-error"><p style="color:var(--c-red)">Errore: ${msg}</p></div>`;
        }

        formatBootstrapResult(r) {
            let html = '<h4>Risultato Bootstrap</h4>';
            if (r.confidence_overall != null) html += `<p>Confidence: ${(r.confidence_overall * 100).toFixed(0)}%</p>`;
            if (r.processes && r.processes.length) {
                html += '<h5>Processi Suggeriti</h5><ul>' + r.processes.map(p => `<li><strong>${p.name}</strong> (conf: ${(p.confidence * 100).toFixed(0)}%)<br><small>${p.description || ''}</small></li>`).join('') + '</ul>';
            }
            if (r.roles && r.roles.length) {
                html += '<h5>Mansioni Suggerite</h5><ul>' + r.roles.map(r => `<li><strong>${r.name}</strong> &mdash; ${r.typical_exposure_hours}h/giorno</li>`).join('') + '</ul>';
            }
            if (r.noise_sources && r.noise_sources.length) {
                html += '<h5>Sorgenti Rumore</h5><ul>' + r.noise_sources.map(s => `<li>${s.type}: ~${s.typical_noise_level} dB(A)</li>`).join('') + '</ul>';
            }
            if (r.missing_data && r.missing_data.length) {
                html += '<h5>Dati Mancanti</h5><ul>' + r.missing_data.map(d => `<li>${d}</li>`).join('') + '</ul>';
            }
            if (r.next_actions && r.next_actions.length) {
                html += '<h5>Prossimi Passi</h5><ol>' + r.next_actions.map(a => `<li>${a}</li>`).join('') + '</ol>';
            }
            return html;
        }

        formatSourceDetectionResult(r) {
            let html = '<h4>Sorgenti Rilevate</h4>';
            if (r.confidence_overall != null) html += `<p>Confidence: ${(r.confidence_overall * 100).toFixed(0)}%</p>`;
            if (r.detected_sources && r.detected_sources.length) {
                html += '<table class="phases-table"><thead><tr><th>Tipo</th><th>Descrizione</th><th>Livello Tipico</th><th>Confidence</th></tr></thead><tbody>' +
                    r.detected_sources.map(s => `<tr><td>${s.type || '-'}</td><td>${s.description || '-'}</td><td>${s.typical_noise_level || '-'} dB(A)</td><td>${s.confidence != null ? (s.confidence * 100).toFixed(0) + '%' : '-'}</td></tr>`).join('') +
                    '</tbody></table>';
            }
            return html;
        }

        formatReviewResult(r) {
            let html = '<h4>Esito Revisione</h4>';
            if (r.validation_passed != null) html += `<p style="font-size:1.25rem;font-weight:700;color:${r.validation_passed ? 'var(--c-green)' : 'var(--c-red)'}">${r.validation_passed ? 'VALIDAZIONE SUPERATA' : 'VALIDAZIONE NON SUPERATA'}</p>`;
            if (r.overall_score != null) html += `<p>Score: ${(r.overall_score * 100).toFixed(0)}%</p>`;
            if (r.issues && r.issues.length) {
                html += '<h5>Problemi</h5><ul>' + r.issues.map(i => {
                    const colors = { critical: 'var(--c-red)', warning: 'var(--c-amber)', info: 'var(--c-navy)' };
                    return `<li><span style="color:${colors[i.severity] || 'inherit'};font-weight:700">[${i.severity || ''}]</span> ${i.description} ${i.suggestion ? '<br><small>Suggerimento: ' + i.suggestion + '</small>' : ''}</li>`;
                }).join('') + '</ul>';
            }
            if (r.warnings && r.warnings.length) {
                html += '<h5>Avvisi</h5><ul>' + r.warnings.map(w => `<li>${w.description || w}</li>`).join('') + '</ul>';
            }
            if (r.missing_data && r.missing_data.length) {
                html += '<h5>Dati Mancanti</h5><ul>' + r.missing_data.map(d => `<li>${d}</li>`).join('') + '</ul>';
            }
            return html;
        }

        formatMitigationResult(r) {
            let html = '<h4>Misure Suggerite</h4>';
            if (r.overall_risk_reduction) html += `<p>Riduzione stimata: <strong>${r.overall_risk_reduction}</strong></p>`;
            if (r.engineer_controls && r.engineer_controls.length) {
                html += '<h5>Misure Tecniche</h5><ul>' + r.engineer_controls.map(c => `<li><strong>${c.type}</strong>: ${c.description} (efficacia: ${c.estimated_effectiveness || '-'}, priorit\u00e0: ${c.priority || '-'})</li>`).join('') + '</ul>';
            }
            if (r.administrative_controls && r.administrative_controls.length) {
                html += '<h5>Misure Amministrative</h5><ul>' + r.administrative_controls.map(c => `<li><strong>${c.type}</strong>: ${c.description} (priorit\u00e0: ${c.priority || '-'})</li>`).join('') + '</ul>';
            }
            if (r.ppe_recommendations && r.ppe_recommendations.length) {
                html += '<h5>DPI</h5><ul>' + r.ppe_recommendations.map(p => `<li><strong>${p.type}</strong> (NRR: ${p.nrr || '-'}) : ${p.description}</li>`).join('') + '</ul>';
            }
            return html;
        }

        formatNarrativeResult(r) {
            let html = '<h4>Narrativa Generata</h4>';
            if (r.confidence != null) html += `<p>Confidence: ${(r.confidence * 100).toFixed(0)}%</p>`;
            if (r.sections && r.sections.length) {
                html += r.sections.map(s => `<div class="narrative-section"><h5>${s.title}</h5><div class="narrative-content">${s.content || ''}</div><small style="color:var(--c-slate-400)">Origine dati: ${s.data_origin || 'AI'}</small></div>`).join('');
            } else if (r.full_text) {
                html += `<div class="narrative-content">${r.full_text.replace(/\n/g, '<br>')}</div>`;
            }
            return html;
        }

        formatExplainResult(r) {
            let html = '<h4>Spiegazione</h4>';
            if (r.explanation) html += `<div class="narrative-content">${r.explanation.replace(/\n/g, '<br>')}</div>`;
            if (r.technical_details) {
                html += '<div class="calc-details"><h5>Dettagli Tecnici</h5>';
                if (r.technical_details.formulas) html += `<p><strong>Formule:</strong> ${Array.isArray(r.technical_details.formulas) ? r.technical_details.formulas.join(', ') : r.technical_details.formulas}</p>`;
                if (r.technical_details.references) html += `<p><strong>Riferimenti:</strong> ${Array.isArray(r.technical_details.references) ? r.technical_details.references.join(', ') : r.technical_details.references}</p>`;
                html += '</div>';
            }
            if (r.related_regulations && r.related_regulations.length) {
                html += '<h5>Normativa Correlata</h5><ul>' + r.related_regulations.map(reg => `<li>${typeof reg === 'string' ? reg : (reg.title || reg.reference || JSON.stringify(reg))}</li>`).join('') + '</ul>';
            }
            return html;
        }

        // ── Companies View ──
        async renderCompanies(c) {
            c.innerHTML = `
                <div class="view-header">
                    <h1>Aziende</h1>
                    <button class="btn btn-accent" id="new-company-btn">+ Nuova Azienda</button>
                </div>
                <div id="companies-list"><div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento...</p></div></div>`;
            try {
                const companies = await window.apiClient.listCompanies();
                this.allCompanies = Array.isArray(companies) ? companies : [];
                this.renderCompaniesList();
            } catch (e) {
                document.getElementById('companies-list').innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u26a0\ufe0f</div><p>Errore caricamento aziende</p></div>';
            }
            document.getElementById('new-company-btn').addEventListener('click', () => this.showNewCompanyModal());
        }

        renderCompaniesList() {
            const el = document.getElementById('companies-list');
            if (!this.allCompanies.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna azienda</p><p class="empty-state-desc">Crea la prima azienda</p></div>';
                return;
            }
            el.innerHTML = this.allCompanies.map(c => `
                <div class="assessment-card">
                    <div class="assessment-info">
                        <h3>${c.name}</h3>
                        <p class="assessment-meta">ATECO: ${c.ateco_primary_code || '-'} &mdash; CF: ${c.fiscal_code || '-'}</p>
                    </div>
                    <div class="assessment-actions">
                        <button class="btn btn-danger btn-small" onclick="window.app.deleteCompanyAction('${c.id}')">Elimina</button>
                    </div>
                </div>`).join('');
        }

        showNewCompanyModal() {
            this.showModal('Nuova Azienda', `
                <div class="form-group"><label>Nome Azienda *</label><input type="text" id="nc-name" class="form-control" placeholder="Es. ACME S.r.l."></div>
                <div class="form-group"><label>Codice ATECO</label><input type="text" id="nc-ateco" class="form-control" placeholder="25.11.00"></div>
                <div class="form-group"><label>Codice Fiscale</label><input type="text" id="nc-fiscal" class="form-control" maxlength="16"></div>
            `, async () => {
                const name = document.getElementById('nc-name').value.trim();
                if (!name) { this.showToast('Nome obbligatorio', 'error'); return false; }
                const data = { name };
                const ateco = document.getElementById('nc-ateco').value.trim();
                const fiscal = document.getElementById('nc-fiscal').value.trim();
                if (ateco) data.ateco_primary_code = ateco;
                if (fiscal) data.fiscal_code = fiscal;
                await window.apiClient.createCompany(data);
                this.showToast('Azienda creata', 'success');
                this.closeModal();
                const c = document.getElementById('main-content');
                this.renderCompanies(c);
                return true;
            });
        }

        async deleteCompanyAction(id) {
            if (!confirm('Eliminare questa azienda?')) return;
            try {
                await window.apiClient.deleteCompany(id);
                this.showToast('Azienda eliminata', 'success');
                const c = document.getElementById('main-content');
                this.renderCompanies(c);
            } catch (e) { this.showToast('Errore: ' + e.message, 'error'); }
        }

        // ── Catalog View ──
        async renderCatalog(c) {
            c.innerHTML = `
                <div class="view-header"><h1>Catalogo Sorgenti Rumore</h1></div>
                <div class="assessments-filters">
                    <input type="text" id="catalog-search" class="search-input" placeholder="Cerca marca o modello...">
                    <select id="catalog-type" class="filter-select"><option value="">Tutte le tipologie</option></select>
                    <button class="btn btn-secondary btn-small" id="catalog-stats-btn">Statistiche</button>
                </div>
                <div id="catalog-stats" style="display:none;margin-bottom:1rem"></div>
                <div id="catalog-list"><div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento catalogo...</p></div></div>`;
            try {
                const [entries, stats] = await Promise.all([
                    window.apiClient.listCatalog({ limit: 100 }),
                    window.apiClient.getCatalogStats()
                ]);
                this._catalogEntries = Array.isArray(entries) ? entries : [];
                this._catalogStats = stats;
                this.renderCatalogList();
                if (stats && stats.count_by_tipologia) {
                    const sel = document.getElementById('catalog-type');
                    Object.keys(stats.count_by_tipologia).forEach(t => {
                        const o = document.createElement('option');
                        o.value = t; o.textContent = `${t} (${stats.count_by_tipologia[t]})`;
                        sel.appendChild(o);
                    });
                }
            } catch (e) {
                document.getElementById('catalog-list').innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u26a0\ufe0f</div><p>Errore caricamento catalogo</p></div>';
            }
            document.getElementById('catalog-search').addEventListener('input', () => this.filterCatalog());
            document.getElementById('catalog-type').addEventListener('change', () => this.filterCatalog());
            document.getElementById('catalog-stats-btn').addEventListener('click', () => {
                const el = document.getElementById('catalog-stats');
                el.style.display = el.style.display === 'none' ? 'block' : 'none';
                if (this._catalogStats) {
                    el.innerHTML = `<div class="stat-card"><p class="stat-label">Totale Sorgenti</p><p class="stat-value">${this._catalogStats.total_count || 0}</p></div>`;
                }
            });
        }

        filterCatalog() {
            const search = (document.getElementById('catalog-search').value || '').toLowerCase();
            const type = document.getElementById('catalog-type').value;
            let f = this._catalogEntries || [];
            if (search) f = f.filter(e => (e.marca + ' ' + e.modello).toLowerCase().includes(search));
            if (type) f = f.filter(e => e.tipologia === type);
            this.renderCatalogList(f);
        }

        renderCatalogList(list) {
            list = list || this._catalogEntries || [];
            const el = document.getElementById('catalog-list');
            if (!list.length) {
                el.innerHTML = '<div class="empty-state"><p class="empty-state-desc">Nessuna sorgente trovata</p></div>';
                return;
            }
            el.innerHTML = `<table class="phases-table"><thead><tr><th>Marca</th><th>Modello</th><th>Tipologia</th><th>LAeq min</th><th>LAeq max</th><th>LAeq tipico</th></tr></thead><tbody>
                ${list.slice(0, 50).map(e => `<tr>
                    <td>${e.marca}</td>
                    <td>${e.modello}</td>
                    <td><span class="status-badge badge-origin-measured">${e.tipologia}</span></td>
                    <td>${e.laeq_min_db_a || '-'}</td>
                    <td>${e.laeq_max_db_a || '-'}</td>
                    <td><strong>${e.laeq_typical_db_a || '-'}</strong></td>
                </tr>`).join('')}
            </tbody></table>
            ${list.length > 50 ? '<p style="color:var(--c-slate-500);font-size:0.8125rem;margin-top:0.5rem">Mostrati 50 di ' + list.length + ' risultati</p>' : ''}`;
        }

        // ── Templates View ──
        async renderTemplates(c) {
            c.innerHTML = `
                <div class="view-header"><h1>Template Documentali</h1></div>
                <div id="templates-grid" class="templates-grid">
                    <div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento template...</p></div>
                </div>`;
            try {
                const templates = await window.apiClient.getTemplates();
                const grid = document.getElementById('templates-grid');
                if (!templates || !templates.length) {
                    grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessun template</p><p class="empty-state-desc">I template saranno disponibili dopo la prima valutazione</p></div>';
                    return;
                }
                grid.innerHTML = templates.map(t => `
                    <div class="template-card">
                        <div class="template-icon">\u{1F4C4}</div>
                        <h3>${t.name || t.template_key || 'Template'}</h3>
                        <p>${t.description || ''}</p>
                        <small style="color:var(--c-slate-400)">${t.language || 'it'} &middot; ${t.template_type || ''}</small>
                    </div>`).join('');
            } catch (e) {
                this.showToast('Errore caricamento template', 'error');
            }
        }

        // ── Settings View ──
        async renderSettings(c) {
            c.innerHTML = `
                <div class="settings-view">
                    <h1 style="margin-bottom:1.5rem">Impostazioni</h1>
                    <div class="settings-section">
                        <h2>Profilo Utente</h2>
                        <div class="form-group"><label>Nome Completo</label><input type="text" id="s-fullname" class="form-control"></div>
                        <div class="form-group"><label>Email</label><input type="email" id="s-email" class="form-control" disabled></div>
                        <div class="form-group"><label>Ruolo</label><input type="text" id="s-role" class="form-control" disabled></div>
                        <button class="btn btn-primary" id="save-profile-btn">Salva Profilo</button>
                    </div>
                    <div class="settings-section">
                        <h2>Configurazione Stampa</h2>
                        <div class="config-form">
                            <div class="form-group"><label>Testo Intestazione</label><input type="text" id="s-header" class="form-control" value="MARS - Valutazione Agenti di Rischio"></div>
                            <div class="form-group"><label>Testo Pi\u00e8 di Pagina</label><input type="text" id="s-footer" class="form-control" value="Documento generato automaticamente"></div>
                            <div class="form-group"><label>Colore Principale</label><input type="color" id="s-primary-color" value="#0c2340"></div>
                            <div class="form-group"><label>Colore Secondario</label><input type="color" id="s-secondary-color" value="#d4870e"></div>
                            <div class="form-group"><label>Formato Carta</label>
                                <select id="s-paper-size" class="form-control">
                                    <option value="A4" selected>A4</option>
                                    <option value="A3">A3</option>
                                    <option value="Letter">Letter</option>
                                </select>
                            </div>
                            <div class="form-group"><label>Logo Aziendale</label>
                                <div class="logo-upload">
                                    <input type="file" id="logo-input" accept="image/*">
                                    <div id="logo-preview" class="logo-preview">Nessun logo caricato</div>
                                </div>
                            </div>
                            <div class="form-actions">
                                <button class="btn btn-secondary" id="reset-settings">Reimposta</button>
                                <button class="btn btn-primary" id="save-settings">Salva</button>
                            </div>
                        </div>
                    </div>
                    <div class="settings-section" id="license-section">
                        <h2>Licenza</h2>
                        <div id="license-info"><p style="color:var(--c-slate-500)">Caricamento...</p></div>
                    </div>
                </div>`;

            try {
                const user = authService.currentUser;
                if (user) {
                    document.getElementById('s-fullname').value = user.full_name || '';
                    document.getElementById('s-email').value = user.email || '';
                    document.getElementById('s-role').value = user.role || '';
                }

                const printSettings = await window.apiClient.getPrintSettings();
                if (printSettings) {
                    if (printSettings.header_text) document.getElementById('s-header').value = printSettings.header_text;
                    if (printSettings.footer_text) document.getElementById('s-footer').value = printSettings.footer_text;
                    if (printSettings.primary_color) document.getElementById('s-primary-color').value = printSettings.primary_color;
                    if (printSettings.secondary_color) document.getElementById('s-secondary-color').value = printSettings.secondary_color;
                    if (printSettings.paper_size) document.getElementById('s-paper-size').value = printSettings.paper_size;
                }

                try {
                    const licenseStatus = await window.apiClient.getLicenseStatus();
                    const licenseEl = document.getElementById('license-info');
                    if (licenseStatus) {
                        licenseEl.innerHTML = `
                            <div class="detail-grid" style="grid-template-columns:1fr 1fr">
                                <div><strong>Stato:</strong> <span class="status-badge badge-${licenseStatus.license_status === 'active' ? 'active' : 'inactive'}">${licenseStatus.license_status === 'active' ? 'Attiva' : 'Inattiva'}</span></div>
                                <div><strong>Piano:</strong> ${licenseStatus.plan || 'free'}</div>
                                <div><strong>Attivata:</strong> ${licenseStatus.activated_at ? new Date(licenseStatus.activated_at).toLocaleDateString('it-IT') : '-'}</div>
                                <div><strong>Scadenza:</strong> ${licenseStatus.expires_at ? new Date(licenseStatus.expires_at).toLocaleDateString('it-IT') : '-'}</div>
                            </div>`;
                    }
                } catch (e) { /* license optional */ }
            } catch (e) { /* non-critical */ }

            const logoInput = document.getElementById('logo-input');
            if (logoInput) {
                logoInput.addEventListener('change', async e => {
                    const file = e.target.files[0];
                    if (!file) return;
                    try {
                        await window.apiClient.uploadLogo(file);
                        const reader = new FileReader();
                        reader.onload = ev => { document.getElementById('logo-preview').innerHTML = `<img src="${ev.target.result}" alt="Logo">`; };
                        reader.readAsDataURL(file);
                        this.showToast('Logo caricato', 'success');
                    } catch (err) {
                        this.showToast('Errore upload logo: ' + err.message, 'error');
                    }
                });
            }

            document.getElementById('save-profile-btn').addEventListener('click', async () => {
                try {
                    await window.apiClient.updateProfile({ full_name: document.getElementById('s-fullname').value.trim() });
                    this.showToast('Profilo aggiornato', 'success');
                } catch (e) { this.showToast('Errore: ' + e.message, 'error'); }
            });

            document.getElementById('save-settings').addEventListener('click', async () => {
                try {
                    await window.apiClient.savePrintSettings({
                        header_text: document.getElementById('s-header').value,
                        footer_text: document.getElementById('s-footer').value,
                        primary_color: document.getElementById('s-primary-color').value,
                        secondary_color: document.getElementById('s-secondary-color').value,
                        paper_size: document.getElementById('s-paper-size').value
                    });
                    this.showToast('Impostazioni salvate', 'success');
                } catch (e) { this.showToast('Errore: ' + e.message, 'error'); }
            });

            document.getElementById('reset-settings').addEventListener('click', () => {
                document.getElementById('s-header').value = 'MARS - Valutazione Agenti di Rischio';
                document.getElementById('s-footer').value = 'Documento generato automaticamente';
                document.getElementById('s-primary-color').value = '#0c2340';
                document.getElementById('s-secondary-color').value = '#d4870e';
                document.getElementById('s-paper-size').value = 'A4';
                this.showToast('Impostazioni ripristinate', 'info');
            });
        }

        // ── New Assessment Modal ──
        showNewAssessmentModal() {
            const modal = document.getElementById('modal-container');
            modal.innerHTML = `
                <div class="modal-overlay" id="modal-overlay">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2>Nuova Valutazione</h2>
                            <button class="modal-close" id="modal-close">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div class="form-group">
                                <label for="modal-company-select">Azienda</label>
                                <select id="modal-company-select" class="form-control">
                                    <option value="">Caricamento aziende...</option>
                                </select>
                                <button type="button" class="btn btn-link" id="toggle-new-company" style="margin-top:0.25rem">+ Crea nuova azienda</button>
                            </div>
                            <div id="new-company-form" style="display:none; margin-top:1rem; padding:1rem; background:var(--c-slate-50); border-radius:var(--radius-md)">
                                <div class="form-group"><label for="new-company-name">Nome Azienda *</label><input type="text" id="new-company-name" class="form-control" placeholder="Es. ACME S.r.l."></div>
                                <div class="form-group"><label for="new-company-ateco">Codice ATECO</label><input type="text" id="new-company-ateco" class="form-control" placeholder="25.11.00"></div>
                                <div class="form-group"><label for="new-company-fiscal">Codice Fiscale</label><input type="text" id="new-company-fiscal" class="form-control" placeholder="Codice fiscale"></div>
                            </div>
                            <div class="form-group"><label for="modal-ateco-code">Codice ATECO Valutazione *</label><input type="text" id="modal-ateco-code" class="form-control" placeholder="25.11.00" required></div>
                            <div class="form-group"><label for="modal-description">Descrizione</label><textarea id="modal-description" class="form-control" rows="3" placeholder="Descrizione della valutazione..."></textarea></div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" id="modal-cancel">Annulla</button>
                            <button class="btn btn-primary" id="modal-submit">Crea Valutazione</button>
                        </div>
                    </div>
                </div>`;

            modal.style.display = 'block';
            document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
            document.getElementById('modal-cancel').addEventListener('click', () => this.closeModal());
            document.getElementById('modal-overlay').addEventListener('click', e => { if (e.target.id === 'modal-overlay') this.closeModal(); });
            document.getElementById('toggle-new-company').addEventListener('click', () => {
                const f = document.getElementById('new-company-form');
                f.style.display = f.style.display === 'none' ? 'block' : 'none';
            });
            document.getElementById('modal-submit').addEventListener('click', e => { e.preventDefault(); this.handleNewAssessmentSubmit(); });
            this.loadCompaniesForModal();
        }

        closeModal() {
            const m = document.getElementById('modal-container');
            if (m) { m.innerHTML = ''; m.style.display = 'none'; }
        }

        showModal(title, bodyHtml, onSubmit) {
            const modal = document.getElementById('modal-container');
            modal.innerHTML = `
                <div class="modal-overlay" id="modal-overlay">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2>${title}</h2>
                            <button class="modal-close" id="modal-close">&times;</button>
                        </div>
                        <div class="modal-body">${bodyHtml}</div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" id="modal-cancel">Annulla</button>
                            <button class="btn btn-primary" id="modal-submit">Salva</button>
                        </div>
                    </div>
                </div>`;
            modal.style.display = 'block';
            document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
            document.getElementById('modal-cancel').addEventListener('click', () => this.closeModal());
            document.getElementById('modal-overlay').addEventListener('click', e => { if (e.target.id === 'modal-overlay') this.closeModal(); });
            document.getElementById('modal-submit').addEventListener('click', async () => {
                const result = await onSubmit();
                if (result !== false) this.closeModal();
            });
        }

        async loadCompaniesForModal() {
            const sel = document.getElementById('modal-company-select');
            if (!sel) return;
            try {
                const companies = await window.apiClient.listCompanies();
                sel.innerHTML = '<option value="">Seleziona azienda...</option>';
                if (companies.length) {
                    companies.forEach(c => { const o = document.createElement('option'); o.value = c.id; o.textContent = c.name; sel.appendChild(o); });
                } else {
                    sel.innerHTML = '<option value="">Nessuna azienda \u2014 crea una nuova azienda</option>';
                    document.getElementById('new-company-form').style.display = 'block';
                }
            } catch (e) {
                sel.innerHTML = '<option value="">Errore caricamento</option>';
            }
        }

        async handleNewAssessmentSubmit() {
            const sel = document.getElementById('modal-company-select');
            const newCoForm = document.getElementById('new-company-form');
            const ateco = document.getElementById('modal-ateco-code').value.trim();
            const desc = document.getElementById('modal-description').value.trim();

            if (!ateco || !/^\d{2}\.\d{2}\.\d{2}$/.test(ateco)) {
                this.showToast('Codice ATECO non valido (formato: XX.XX.XX)', 'error');
                return;
            }

            let companyId;
            try {
                if (newCoForm.style.display !== 'none') {
                    const cn = document.getElementById('new-company-name').value.trim();
                    if (!cn) { this.showToast('Nome azienda obbligatorio', 'error'); return; }
                    const data = { name: cn };
                    const ca = document.getElementById('new-company-ateco').value.trim();
                    const cf = document.getElementById('new-company-fiscal').value.trim();
                    if (ca) data.ateco_primary_code = ca;
                    if (cf) data.fiscal_code = cf;
                    const newCo = await window.apiClient.createCompany(data);
                    companyId = newCo.id;
                    this.showToast('Azienda creata', 'success');
                } else {
                    companyId = sel.value;
                    if (!companyId) { this.showToast('Seleziona un\u2019azienda', 'error'); return; }
                }

                const assessment = await window.apiClient.createAssessment({
                    company_id: companyId,
                    ateco_code: ateco,
                    description: desc || undefined
                });

                this.showToast('Valutazione creata!', 'success');
                this.closeModal();
                window.location.hash = '#assessment/' + assessment.id;
            } catch (e) {
                this.showToast('Errore: ' + (e.message || 'Creazione fallita'), 'error');
            }
        }

        // ── Toast ──
        showToast(message, type = 'info') {
            if (!this.toastContainer) return;
            const t = document.createElement('div');
            t.className = `toast toast-${type}`;
            t.textContent = message;
            this.toastContainer.appendChild(t);
            requestAnimationFrame(() => t.classList.add('show'));
            setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3500);
        }
    }

    window.App = App;

    window.initializeApp = function () {
        if (!window.app) window.app = new App();
    };

    document.addEventListener('DOMContentLoaded', async () => {
        const form = document.getElementById('login-form');
        if (form) form.addEventListener('submit', handleLogin);
        const logout = document.getElementById('logout-btn');
        if (logout) logout.addEventListener('click', () => authService.logout());

        if (authService.isAuthenticated()) {
            const user = await authService.fetchCurrentUser();
            if (user) window.initializeApp();
        } else {
            document.getElementById('login-section').style.display = 'flex';
            document.getElementById('app-section').style.display = 'none';
        }
    });
})();