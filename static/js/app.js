(function() {
    'use strict';

    class App {
        constructor() {
            this.currentView = 'dashboard';
            this.toastContainer = null;
            this.init();
        }

        init() {
            this.toastContainer = document.getElementById('toast-container');
            this.setupRouting();
            this.setupNavigation();
            
            if (typeof window.APIClient !== 'undefined') {
                window.apiClient = new window.APIClient();
            }
            
            this.loadInitialView();
        }

        setupRouting() {
            window.addEventListener('hashchange', () => this.handleRouteChange());
        }

        setupNavigation() {
            const navLinks = document.querySelectorAll('.nav-links a');
            navLinks.forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const hash = link.getAttribute('href');
                    window.location.hash = hash;
                });
            });
        }

        handleRouteChange() {
            const hash = window.location.hash || '#dashboard';
            const route = hash.substring(1);
            this.navigateTo(route);
        }

        navigateTo(route) {
            const routes = ['dashboard', 'assessments', 'templates', 'settings'];
            if (!routes.includes(route)) {
                route = 'dashboard';
            }

            this.currentView = route;
            this.loadView(route);
        }

        loadView(viewName) {
            const mainContent = document.getElementById('main-content');
            if (!mainContent) return;

            switch(viewName) {
                case 'dashboard':
                    this.renderDashboard(mainContent);
                    break;
                case 'assessments':
                    this.renderAssessments(mainContent);
                    break;
                case 'templates':
                    this.renderTemplates(mainContent);
                    break;
                case 'settings':
                    this.renderSettings(mainContent);
                    break;
                default:
                    this.renderDashboard(mainContent);
            }
        }

        loadInitialView() {
            const hash = window.location.hash || '#dashboard';
            const route = hash.substring(1) || 'dashboard';
            this.navigateTo(route);
        }

        renderDashboard(container) {
            container.innerHTML = `
                <div class="dashboard">
                    <h1>Dashboard</h1>
                    <div class="dashboard-grid">
                        <div class="dashboard-card">
                            <h3>Valutazioni Totali</h3>
                            <p class="card-value" id="total-assessments">-</p>
                        </div>
                        <div class="dashboard-card">
                            <h3>Valutazioni Completate</h3>
                            <p class="card-value" id="completed-assessments">-</p>
                        </div>
                        <div class="dashboard-card">
                            <h3>In Corso</h3>
                            <p class="card-value" id="in-progress-assessments">-</p>
                        </div>
                        <div class="dashboard-card">
                            <h3>Template Disponibili</h3>
                            <p class="card-value" id="available-templates">-</p>
                        </div>
                    </div>
                    <div class="dashboard-section">
                        <h2>Attività Recente</h2>
                        <div id="recent-activity" class="activity-list">
                            <p class="empty-message">Nessuna attività recente.</p>
                        </div>
                    </div>
                </div>
            `;

            this.loadDashboardData();
        }

        async loadDashboardData() {
            if (window.apiClient) {
                try {
                    const [assessments, templates] = await Promise.all([
                        window.apiClient.request('/', 'GET'),
                        window.apiClient.getTemplates().catch(() => [])
                    ]);
                    const totalEl = document.getElementById('total-assessments');
                    if (totalEl) totalEl.textContent = (Array.isArray(assessments) ? assessments.length : 0);
                    const completedEl = document.getElementById('completed-assessments');
                    if (completedEl) completedEl.textContent = Array.isArray(assessments) ? assessments.filter(a => a.status === 'completed').length : 0;
                    const progressEl = document.getElementById('in-progress-assessments');
                    if (progressEl) progressEl.textContent = Array.isArray(assessments) ? assessments.filter(a => a.status === 'in_progress' || a.status === 'draft').length : 0;
                    const templatesEl = document.getElementById('available-templates');
                    if (templatesEl) templatesEl.textContent = templates.length || 0;
                } catch (e) {
                    console.warn('Could not load dashboard data:', e);
                }
            }
        }

        renderAssessments(container) {
            container.innerHTML = `
                <div class="assessments-view">
                    <div class="view-header">
                        <h1>Valutazioni</h1>
                        <button class="btn btn-primary" id="new-assessment-btn">Nuova Valutazione</button>
                    </div>
                    <div class="assessments-filters">
                        <input type="text" id="search-assessments" placeholder="Cerca valutazioni..." class="search-input">
                        <select id="filter-status" class="filter-select">
                            <option value="">Tutti gli stati</option>
                            <option value="completed">Completate</option>
                            <option value="in_progress">In corso</option>
                            <option value="draft">Bozza</option>
                        </select>
                    </div>
                    <div id="assessments-list" class="assessments-list">
                        <p class="empty-message">Caricamento valutazioni...</p>
                    </div>
                </div>
            `;

            this.loadAssessments();
            this.bindAssessmentEvents();
        }

        async loadAssessments() {
            if (!window.apiClient) return;
            try {
                const assessments = await window.apiClient.request('/assessments/', 'GET');
                this.renderAssessmentsList(Array.isArray(assessments) ? assessments : []);
            } catch (e) {
                const list = document.getElementById('assessments-list');
                if (list) list.innerHTML = '<p class="empty-message">Errore nel caricamento delle valutazioni.</p>';
            }
        }

        renderAssessmentsList(assessments) {
            const list = document.getElementById('assessments-list');
            if (!list) return;

            if (!assessments.length) {
                list.innerHTML = '<p class="empty-message">Nessuna valutazione presente. Crea una nuova valutazione per iniziare.</p>';
                return;
            }

            list.innerHTML = assessments.map(a => {
                const statusLabel = { draft: 'Bozza', in_progress: 'In Corso', completed: 'Completata', review: 'In Revisione' }[a.status] || a.status;
                const date = a.assessment_date ? new Date(a.assessment_date).toLocaleDateString('it-IT') : '-';
                return `
                <div class="assessment-card" data-id="${a.id}">
                    <div class="assessment-info">
                        <h3>${a.description || 'Valutazione Rischio Rumore'}</h3>
                        <p class="assessment-meta">${date} &mdash; ${statusLabel}</p>
                    </div>
                    <div class="assessment-actions">
                        <button class="btn btn-small" onclick="window.app.viewAssessment('${a.id}')">Apri</button>
                        <button class="btn btn-small btn-secondary" onclick="window.app.exportAssessment('${a.id}')">Esporta</button>
                    </div>
                </div>`;
            }).join('');
        }

        async viewAssessment(assessmentId) {
            window.location.hash = '#assessment/' + assessmentId;
        }

        async exportAssessment(assessmentId) {
            this.showToast('Preparazione documento...', 'info');
            try {
                const blob = await window.apiClient.exportDOCX(assessmentId, { language: 'it' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `DVR_RUMORE_${assessmentId}.docx`;
                a.click();
                window.URL.revokeObjectURL(url);
                this.showToast('Documento scaricato!', 'success');
            } catch (e) {
                this.showToast('Errore nell\'esportazione: ' + e.message, 'error');
            }
        }

        bindAssessmentEvents() {
            const newBtn = document.getElementById('new-assessment-btn');
            if (newBtn) {
                newBtn.addEventListener('click', () => this.showToast('Creazione nuova valutazione in fase di sviluppo', 'info'));
            }
            const searchInput = document.getElementById('search-assessments');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => this.filterAssessments(e.target.value));
            }
            const statusFilter = document.getElementById('filter-status');
            if (statusFilter) {
                statusFilter.addEventListener('change', (e) => this.filterAssessmentsByStatus(e.target.value));
            }
        }

        renderTemplates(container) {
            container.innerHTML = `
                <div class="templates-view">
                    <div class="view-header">
                        <h1>Template Documentali</h1>
                        <button class="btn btn-primary" id="new-template-btn">Nuovo Template</button>
                    </div>
                    <div id="templates-grid" class="templates-grid">
                        <p class="empty-message">Nessun template disponibile.</p>
                    </div>
                </div>
            `;

            this.loadTemplates();
        }

        async loadTemplates() {
            if (window.apiClient) {
                try {
                    const templates = await window.apiClient.getTemplates();
                    this.renderTemplatesGrid(templates);
                } catch (e) {
                    this.showToast('Errore nel caricamento dei template', 'error');
                }
            }
        }

        renderTemplatesGrid(templates) {
            const grid = document.getElementById('templates-grid');
            if (!grid || !templates.length) return;

            grid.innerHTML = templates.map(t => `
                <div class="template-card" data-template-id="${t.id}">
                    <div class="template-icon">📄</div>
                    <h3>${t.name || t.nome || 'Template'}</h3>
                    <p>${t.description || t.descrizione || ''}</p>
                </div>
            `).join('');
        }

        renderSettings(container) {
            container.innerHTML = `
                <div class="settings-view">
                    <h1>Impostazioni</h1>
                    <div class="settings-section">
                        <h2>Configurazione Stampa</h2>
                        <div id="template-config-form" class="config-form">
                            <div class="form-group">
                                <label for="header-text">Testo Intestazione</label>
                                <input type="text" id="header-text" value="MARS - Valutazione Agenti di Rischio">
                            </div>
                            <div class="form-group">
                                <label for="footer-text">Testo Piè di Pagina</label>
                                <input type="text" id="footer-text" value="Documento generato automaticamente">
                            </div>
                            <div class="form-group">
                                <label for="primary-color">Colore Principale</label>
                                <input type="color" id="primary-color" value="#1a365d" class="color-input">
                            </div>
                            <div class="form-group">
                                <label for="secondary-color">Colore Secondario</label>
                                <input type="color" id="secondary-color" value="#2c5282" class="color-input">
                            </div>
                            <div class="form-group">
                                <label for="paper-size">Formato Carta</label>
                                <select id="paper-size">
                                    <option value="a4" selected>A4 (210mm x 297mm)</option>
                                    <option value="a3">A3 (297mm x 420mm)</option>
                                    <option value="letter">Letter (216mm x 279mm)</option>
                                    <option value="legal">Legal (216mm x 356mm)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Logo Aziendale</label>
                                <div class="logo-upload">
                                    <input type="file" id="logo-input" accept="image/*">
                                    <div id="logo-preview" class="logo-preview"></div>
                                </div>
                            </div>
                            <div class="form-actions">
                                <button class="btn btn-secondary" id="reset-template">Reimposta</button>
                                <button class="btn btn-primary" id="save-template">Salva</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            if (typeof window.TemplateConfig !== 'undefined') {
                new window.TemplateConfig();
            }
        }

        showToast(message, type = 'info') {
            if (!this.toastContainer) return;

            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.textContent = message;

            this.toastContainer.appendChild(toast);

            requestAnimationFrame(() => {
                toast.classList.add('show');
            });

            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        destroy() {
            this.toastContainer = null;
        }
    }

    window.App = App;

    window.initializeApp = function() {
        if (!window.app) {
            window.app = new App();
        }
    };

    document.addEventListener('DOMContentLoaded', async () => {
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', handleLogin);
        }
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                authService.logout();
            });
        }

        if (authService.isAuthenticated()) {
            const user = await authService.fetchCurrentUser();
            if (user) {
                window.initializeApp();
            }
        } else {
            showLoginSection();
        }
    });
})();
