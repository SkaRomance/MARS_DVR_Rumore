(function () {
    'use strict';

    class APIClient {
        constructor(baseURL = '/api/v1/noise') {
            this.baseURL = baseURL;
        }

        async request(endpoint, options = {}) {
            const url = `${this.baseURL}${endpoint}`;
            const headers = { 'Content-Type': 'application/json', ...options.headers };
            const config = { ...options, headers };

            try {
                const response = await authService.fetchWithAuth(url, config);
                if (!response) throw new APIError('Non autenticato', 401, {});

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    const msg = Array.isArray(errData.detail)
                        ? errData.detail.map(e => e.msg || e.type).join('; ')
                        : (typeof errData.detail === 'string' ? errData.detail : `HTTP ${response.status}`);
                    throw new APIError(msg, response.status, errData);
                }

                const ct = response.headers.get('content-type') || '';
                if (ct.includes('application/json')) return await response.json();
                if (ct.includes('word') || ct.includes('document') || ct.includes('octet-stream')) return await response.blob();
                return await response.text();
            } catch (error) {
                if (error instanceof APIError) throw error;
                throw new APIError(`Errore di rete: ${error.message}`, 0, {});
            }
        }

        // ── Auth ──
        async registerUser(data) {
            return this.request('/auth/register', { method: 'POST', body: JSON.stringify(data) });
        }
        async updateProfile(data) {
            return this.request('/auth/me', { method: 'PUT', body: JSON.stringify(data) });
        }

        // ── Assessments ──
        async listAssessments(skip = 0, limit = 50, status = '') {
            let endpoint = `/?skip=${skip}&limit=${limit}`;
            if (status) endpoint += `&status=${status}`;
            return this.request(endpoint);
        }
        async getAssessment(id) { return this.request(`/${id}`); }
        async createAssessment(data) {
            return this.request('/', { method: 'POST', body: JSON.stringify(data) });
        }
        async updateAssessment(id, data) {
            return this.request(`/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        }
        async deleteAssessment(id) {
            return this.request(`/${id}`, { method: 'DELETE' });
        }
        async calculateNoise(data) {
            return this.request('/calculate', { method: 'POST', body: JSON.stringify(data) });
        }

        // ── Companies ──
        async listCompanies(skip = 0, limit = 50) {
            return this.request(`/companies/?skip=${skip}&limit=${limit}`);
        }
        async getCompany(id) { return this.request(`/companies/${id}`); }
        async createCompany(data) {
            return this.request('/companies/', { method: 'POST', body: JSON.stringify(data) });
        }
        async updateCompany(id, data) {
            return this.request(`/companies/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        }
        async deleteCompany(id) {
            return this.request(`/companies/${id}`, { method: 'DELETE' });
        }

        // ── Job Roles ──
        async listJobRoles(companyId, skip = 0, limit = 50) {
            return this.request(`/job-roles/?company_id=${companyId}&skip=${skip}&limit=${limit}`);
        }
        async getJobRole(id) { return this.request(`/job-roles/${id}`); }
        async createJobRole(data) {
            return this.request('/job-roles/', { method: 'POST', body: JSON.stringify(data) });
        }
        async updateJobRole(id, data) {
            return this.request(`/job-roles/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        }
        async deleteJobRole(id) {
            return this.request(`/job-roles/${id}`, { method: 'DELETE' });
        }

        // ── Mitigations ──
        async listMitigations(assessmentId, skip = 0, limit = 50) {
            return this.request(`/mitigations/?assessment_id=${assessmentId}&skip=${skip}&limit=${limit}`);
        }
        async getMitigation(id) { return this.request(`/mitigations/${id}`); }
        async createMitigation(data) {
            return this.request('/mitigations/', { method: 'POST', body: JSON.stringify(data) });
        }
        async updateMitigation(id, data) {
            return this.request(`/mitigations/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        }
        async deleteMitigation(id) {
            return this.request(`/mitigations/${id}`, { method: 'DELETE' });
        }

        // ── Machine Assets ──
        async listMachineAssets(companyId, skip = 0, limit = 50) {
            return this.request(`/machine-assets/?company_id=${companyId}&skip=${skip}&limit=${limit}`);
        }
        async getMachineAsset(id) { return this.request(`/machine-assets/${id}`); }
        async createMachineAsset(data) {
            return this.request('/machine-assets/', { method: 'POST', body: JSON.stringify(data) });
        }
        async updateMachineAsset(id, data) {
            return this.request(`/machine-assets/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        }
        async deleteMachineAsset(id) {
            return this.request(`/machine-assets/${id}`, { method: 'DELETE' });
        }

        // ── Noise Source Catalog ──
        async listCatalog(filters = {}) {
            const params = new URLSearchParams();
            if (filters.skip) params.set('skip', filters.skip);
            if (filters.limit) params.set('limit', filters.limit);
            if (filters.tipologia) params.set('tipologia', filters.tipologia);
            if (filters.marca) params.set('marca', filters.marca);
            if (filters.min_laeq !== undefined) params.set('min_laeq', filters.min_laeq);
            if (filters.max_laeq !== undefined) params.set('max_laeq', filters.max_laeq);
            return this.request(`/catalog/?${params.toString()}`);
        }
        async getCatalogStats() { return this.request('/catalog/stats'); }
        async getCatalogEntry(id) { return this.request(`/catalog/${id}`); }

        // ── ATECO ──
        async getAtecoMacroCategories() { return this.request('/ateco/macro-categories'); }
        async getAtecoMacroCategory(code) { return this.request(`/ateco/macro-categories/${code}`); }
        async resolveAtecoCode(code) { return this.request(`/ateco/code/${code}`); }

        // ── AI Agents ──
        async getAIHealth() { return this.request('/ai/health'); }
        async aiBootstrap(assessmentId, data) {
            return this.request(`/${assessmentId}/ai/bootstrap`, { method: 'POST', body: JSON.stringify(data) });
        }
        async aiReview(assessmentId, data) {
            return this.request(`/${assessmentId}/ai/review`, { method: 'POST', body: JSON.stringify(data) });
        }
        async aiExplain(assessmentId, data) {
            return this.request(`/${assessmentId}/ai/explain`, { method: 'POST', body: JSON.stringify(data) });
        }
        async aiNarrative(assessmentId, data) {
            return this.request(`/${assessmentId}/ai/narrative`, { method: 'POST', body: JSON.stringify(data) });
        }
        async aiSuggestMitigations(assessmentId, data) {
            return this.request(`/${assessmentId}/ai/suggest-mitigations`, { method: 'POST', body: JSON.stringify(data) });
        }
        async aiDetectSources(assessmentId, data) {
            return this.request(`/${assessmentId}/ai/detect-sources`, { method: 'POST', body: JSON.stringify(data) });
        }
        async listAISuggestions(assessmentId, status = '') {
            let endpoint = `/${assessmentId}/ai/suggestions`;
            if (status) endpoint += `?status=${status}`;
            return this.request(endpoint);
        }
        async aiSuggestionAction(assessmentId, suggestionId, status, feedback = '') {
            const body = { status };
            if (feedback) body.feedback = feedback;
            return this.request(`/${assessmentId}/ai/suggestions/${suggestionId}/action`, {
                method: 'POST', body: JSON.stringify(body)
            });
        }
        async listAIInteractions(assessmentId) {
            return this.request(`/${assessmentId}/ai/interactions`);
        }

        // ── Export ──
        async getAssessmentDocument(assessmentId) {
            return this.request(`/export/assessments/${assessmentId}/document`);
        }
        async getAssessmentSections(assessmentId) {
            return this.request(`/export/assessments/${assessmentId}/document/sections`);
        }
        async getAssessmentSection(assessmentId, sectionId) {
            return this.request(`/export/assessments/${assessmentId}/document/sections/${sectionId}`);
        }
        async updateSection(assessmentId, sectionId, contentHtml) {
            return this.request(`/export/assessments/${assessmentId}/document/sections/${sectionId}`, {
                method: 'PUT',
                body: JSON.stringify({ content_html: contentHtml })
            });
        }
        async getExportPreview(assessmentId) {
            return this.request(`/export/assessments/${assessmentId}/preview`);
        }
        async exportDOCX(assessmentId, options = {}) {
            const url = `${this.baseURL}/export/assessments/${assessmentId}/docx`;
            const response = await authService.fetchWithAuth(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format: 'dvr_full', language: options.language || 'it' })
            });
            if (response && response.ok) return await response.blob();
            throw new APIError('Export fallito', response ? response.status : 0, {});
        }
        async exportJSON(assessmentId, language = 'it') {
            return this.request(`/export/assessments/${assessmentId}/json?language=${language}`, { method: 'POST' });
        }
        async getTemplates() { return this.request('/export/templates'); }
        async getTemplate(id) { return this.request(`/export/templates/${id}`); }
        async updateTemplate(id, data) {
            return this.request(`/export/templates/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        }
        async getPrintSettings(companyId = '') {
            let endpoint = '/export/print-settings';
            if (companyId) endpoint += `?company_id=${companyId}`;
            return this.request(endpoint);
        }
        async savePrintSettings(settings) {
            return this.request('/export/print-settings', { method: 'PUT', body: JSON.stringify(settings) });
        }

        // ── Admin ──
        async getTenant() { return this.request('/admin/tenant'); }
        async uploadLogo(file) {
            const formData = new FormData();
            formData.append('file', file);
            const url = `${this.baseURL}/admin/tenant/logo`;
            const response = await authService.fetchWithAuth(url, {
                method: 'POST',
                body: formData
            });
            if (response && response.ok) return await response.json();
            throw new APIError('Upload logo fallito', response ? response.status : 0, {});
        }
        async getLogo() { return this.request('/admin/tenant/logo'); }
        async deleteLogo() { return this.request('/admin/tenant/logo', { method: 'DELETE' }); }

        // ── License ──
        async getLicenseStatus() { return this.request('/license/status'); }
        async getLicenseUsage() { return this.request('/license/usage'); }
        async activateLicense(licenseKey, machineFingerprint) {
            return this.request('/license/activate', {
                method: 'POST',
                body: JSON.stringify({ license_key: licenseKey, machine_fingerprint: machineFingerprint })
            });
        }
        async deactivateLicense() {
            return this.request('/license/deactivate', { method: 'POST', body: JSON.stringify({}) });
        }

        // ── RAG ──
        async ragQuery(query, nResults = 5, category = '') {
            const body = { query, n_results: nResults };
            if (category) body.category = category;
            return this.request('/rag/query', { method: 'POST', body: JSON.stringify(body) });
        }
        async ragIndex(reset = false) {
            return this.request('/rag/index', { method: 'POST', body: JSON.stringify({ reset }) });
        }
        async getRAGStats() { return this.request('/rag/stats'); }
    }

    class APIError extends Error {
        constructor(message, status, data) {
            super(message);
            this.name = 'APIError';
            this.status = status;
            this.data = data;
        }
    }

    window.APIClient = APIClient;
    window.APIError = APIError;
})();