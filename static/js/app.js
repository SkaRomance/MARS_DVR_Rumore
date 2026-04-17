(function () {
    'use strict';

    class App {
        constructor() {
            this.currentView = 'dashboard';
            this.allAssessments = [];
            this.allCompanies = [];
            this.searchFilter = '';
            this.statusFilter = '';
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
            const valid = ['dashboard', 'assessments', 'templates', 'settings'];
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
                    window.apiClient.request('/assessments/').catch(() => []),
                    window.apiClient.listCompanies().catch(() => [])
                ]);
                const t = document.getElementById('stat-total');
                const a = document.getElementById('stat-active');
                const ar = document.getElementById('stat-archived');
                const co = document.getElementById('stat-companies');
                if (t) t.textContent = assessments.length;
                if (a) a.textContent = assessments.filter(x => x.status === 'active').length;
                if (ar) ar.textContent = assessments.filter(x => x.status === 'archived').length;
                if (co) co.textContent = companies.length;

                const el = document.getElementById('recent-activity');
                if (!assessments.length) {
                    el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna valutazione</p><p class="empty-state-desc">Crea la prima valutazione dalla sezione Valutazioni</p></div>';
                    return;
                }
                el.innerHTML = assessments.slice(0, 8).map(a => `
                    <div class="activity-item">
                        <span class="activity-date">${a.assessment_date ? new Date(a.assessment_date).toLocaleDateString('it-IT') : '-'}</span>
                        <span class="activity-desc">${a.description || 'Valutazione Rischio Rumore'}</span>
                        <span class="status-badge badge-${a.status}">${{ active: 'Attiva', archived: 'Archiviata', inactive: 'Inattiva' }[a.status] || a.status}</span>
                    </div>`).join('');
            } catch (e) {
                console.warn('Dashboard load error:', e);
            }
        }

        // ── Assessments ──
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
                const data = await window.apiClient.request('/assessments/');
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

        showAssessmentDetail(id) {
            this.setActiveNav('');
            const mc = document.getElementById('main-content');
            mc.innerHTML = `
                <div class="view-header">
                    <h1>Dettaglio Valutazione</h1>
                    <button class="btn btn-secondary" onclick="window.location.hash='#assessments'">&larr; Torna alle valutazioni</button>
                </div>
                <div id="assessment-sections"><div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento sezioni...</p></div></div>
                <div class="form-actions" style="margin-top:1.5rem">
                    <button class="btn btn-accent" onclick="window.app.exportAssessment('${id}')">Esporta DOCX</button>
                </div>`;
            this.loadAssessmentSections(id);
        }

        async loadAssessmentSections(id) {
            try {
                const sections = await window.apiClient.getAssessmentSections(id);
                const el = document.getElementById('assessment-sections');
                if (!sections.length) {
                    el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessuna sezione</p><p class="empty-state-desc">Nessuna sezione disponibile per questa valutazione</p></div>';
                    return;
                }
                el.innerHTML = sections.map(s => `
                    <div class="assessment-card" onclick="window.app.editSection('${id}','${s.id}')">
                        <div class="assessment-info">
                            <h3>${s.title || s.id}</h3>
                            <p class="assessment-meta">${s.is_modified ? 'Modificato' : 'Originale'}</p>
                        </div>
                    </div>`).join('');
            } catch (e) {
                const el = document.getElementById('assessment-sections');
                if (el) el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u26a0\ufe0f</div><p class="empty-state-desc">Errore caricamento sezioni</p></div>';
            }
        }

        editSection(assessmentId, sectionId) {
            const mc = document.getElementById('main-content');
            mc.innerHTML = `
                <div class="view-header">
                    <h1>Modifica Sezione</h1>
                    <button class="btn btn-secondary" onclick="window.app.showAssessmentDetail('${assessmentId}')">&larr; Torna alla valutazione</button>
                </div>
                <div id="editor-content" contenteditable="true" style="min-height:300px;padding:1rem;border:1px solid var(--c-slate-200);border-radius:var(--radius-md);background:white;outline:none;line-height:1.8;font-family:var(--font-body);"></div>
                <div class="form-actions">
                    <button class="btn btn-accent" id="save-section-btn">Salva Sezione</button>
                    <span id="save-indicator" style="color:var(--c-green);font-weight:600;display:none;margin-left:0.5rem">Salvato</span>
                </div>`;
            this.currentAssessmentId = assessmentId;
            this.currentSectionId = sectionId;
            this.loadSectionContent(assessmentId, sectionId);
            document.getElementById('save-section-btn').addEventListener('click', () => this.saveSectionEdit(assessmentId, sectionId));
        }

        async loadSectionContent(assessmentId, sectionId) {
            try {
                const sections = await window.apiClient.getAssessmentSections(assessmentId);
                const section = sections.find(s => s.id === sectionId);
                const ed = document.getElementById('editor-content');
                if (ed && section) ed.innerHTML = section.content_html || section.content || '<p>Contenuto sezione...</p>';
            } catch (e) {
                const ed = document.getElementById('editor-content');
                if (ed) ed.innerHTML = '<p>Errore nel caricamento.</p>';
            }
        }

        async saveSectionEdit(assessmentId, sectionId) {
            const ed = document.getElementById('editor-content');
            if (!ed) return;
            try {
                await window.apiClient.updateSection(assessmentId, sectionId, ed.innerHTML);
                this.showToast('Sezione salvata', 'success');
                const ind = document.getElementById('save-indicator');
                if (ind) { ind.style.display = 'inline'; setTimeout(() => ind.style.display = 'none', 3000); }
            } catch (e) {
                this.showToast('Errore salvataggio: ' + e.message, 'error');
            }
        }

        // ── Templates ──
        renderTemplates(c) {
            c.innerHTML = `
                <div class="view-header"><h1>Template Documentali</h1></div>
                <div id="templates-grid" class="templates-grid">
                    <div class="empty-state"><div class="empty-state-icon">\u23f3</div><p class="empty-state-desc">Caricamento template...</p></div>
                </div>`;
            this.loadTemplates();
        }

        async loadTemplates() {
            try {
                const templates = await window.apiClient.getTemplates();
                const grid = document.getElementById('templates-grid');
                if (!templates.length) {
                    grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">\u{1F4CB}</div><p class="empty-state-title">Nessun template</p><p class="empty-state-desc">I template saranno disponibili dopo la prima valutazione</p></div>';
                    return;
                }
                grid.innerHTML = templates.map(t => `
                    <div class="template-card">
                        <div class="template-icon">\u{1F4C4}</div>
                        <h3>${t.name || t.nome || 'Template'}</h3>
                        <p>${t.description || t.descrizione || ''}</p>
                    </div>`).join('');
            } catch (e) {
                this.showToast('Errore caricamento template', 'error');
            }
        }

        // ── Settings ──
        renderSettings(c) {
            c.innerHTML = `
                <div class="settings-view">
                    <h1 style="margin-bottom:1.5rem">Impostazioni</h1>
                    <div class="settings-section">
                        <h2>Configurazione Stampa</h2>
                        <div class="config-form">
                            <div class="form-group">
                                <label for="header-text">Testo Intestazione</label>
                                <input type="text" id="header-text" value="MARS - Valutazione Agenti di Rischio">
                            </div>
                            <div class="form-group">
                                <label for="footer-text">Testo Pi\u00e8 di Pagina</label>
                                <input type="text" id="footer-text" value="Documento generato automaticamente">
                            </div>
                            <div class="form-group">
                                <label for="primary-color">Colore Principale</label>
                                <input type="color" id="primary-color" value="#0c2340">
                            </div>
                            <div class="form-group">
                                <label for="secondary-color">Colore Secondario</label>
                                <input type="color" id="secondary-color" value="#d4870e">
                            </div>
                            <div class="form-group">
                                <label for="paper-size">Formato Carta</label>
                                <select id="paper-size">
                                    <option value="a4" selected>A4 (210mm \u00d7 297mm)</option>
                                    <option value="a3">A3 (297mm \u00d7 420mm)</option>
                                    <option value="letter">Letter</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Logo Aziendale</label>
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
                </div>`;

            const logoInput = document.getElementById('logo-input');
            if (logoInput) {
                logoInput.addEventListener('change', e => {
                    const file = e.target.files[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = ev => {
                        const prev = document.getElementById('logo-preview');
                        prev.innerHTML = `<img src="${ev.target.result}" alt="Logo">`;
                    };
                    reader.readAsDataURL(file);
                });
            }

            const saveBtn = document.getElementById('save-settings');
            if (saveBtn) saveBtn.addEventListener('click', () => this.showToast('Impostazioni salvate', 'success'));
            const resetBtn = document.getElementById('reset-settings');
            if (resetBtn) resetBtn.addEventListener('click', () => this.showToast('Impostazioni ripristinate', 'info'));
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