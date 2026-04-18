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

        // ── MARS context (Wave 26) ──
        async bootstrapContext(dvrDocumentId, revisionId = null) {
            const body = { mars_dvr_document_id: dvrDocumentId };
            if (revisionId) body.mars_revision_id = revisionId;
            return this.request('/contexts/bootstrap', { method: 'POST', body: JSON.stringify(body) });
        }

        async getContextByDvr(dvrDocumentId) {
            return this.request(`/contexts/by-dvr/${dvrDocumentId}`);
        }

        // ── AI Autopilot (Wave 27) ──
        async runAutopilot(contextId, onEvent) {
            const url = `${this.baseURL}/autopilot/${contextId}/run`;
            return this._sseRequest(url, { method: 'POST' }, onEvent);
        }

        async getAutopilotStatus(contextId) {
            return this.request(`/autopilot/${contextId}/status`);
        }

        async cancelAutopilot(contextId) {
            return this.request(`/autopilot/${contextId}/cancel`, { method: 'POST' });
        }

        // ── AI Suggestions v2 (Wave 27, context-scoped) ──
        async listSuggestionsByContext(contextId, statusFilter = null) {
            let path = `/suggestions/by-context/${contextId}`;
            if (statusFilter) path += `?status=${encodeURIComponent(statusFilter)}`;
            return this.request(path);
        }

        async approveSuggestionV2(suggestionId, editedPayload = null) {
            const body = editedPayload ? { edited_payload: editedPayload } : {};
            return this.request(`/suggestions/${suggestionId}/approve`, {
                method: 'POST',
                body: JSON.stringify(body),
            });
        }

        async rejectSuggestionV2(suggestionId, reason = null) {
            return this.request(`/suggestions/${suggestionId}/reject`, {
                method: 'POST',
                body: JSON.stringify({ reason }),
            });
        }

        async bulkSuggestionAction(suggestionIds, action, options = {}) {
            return this.request('/suggestions/bulk', {
                method: 'POST',
                body: JSON.stringify({ suggestion_ids: suggestionIds, action, ...options }),
            });
        }

        // ── Audit log (Wave 29 frontend; backend from Wave 25+26) ──
        async listAuditByContext(contextId, filters = {}) {
            const params = new URLSearchParams();
            if (filters.source) params.set('source', filters.source);
            if (filters.action) params.set('action', filters.action);
            if (filters.limit) params.set('limit', filters.limit);
            const q = params.toString() ? `?${params}` : '';
            return this.request(`/audit/by-context/${contextId}${q}`);
        }

        auditExportCsvUrl(contextId) {
            return `${this.baseURL}/audit/by-context/${contextId}/export.csv`;
        }

        // ── SSE helper (Server-Sent Events over POST with fetch streaming) ──
        async _sseRequest(url, options, onEvent) {
            const token = window.authService?.getToken() || sessionStorage.getItem('mars_access_token') || '';
            const response = await fetch(url, {
                method: options.method || 'POST',
                headers: {
                    'Accept': 'text/event-stream',
                    'Authorization': token ? `Bearer ${token}` : '',
                    ...(options.headers || {}),
                },
                body: options.body || undefined,
            });

            if (response.status === 401) {
                window.ModuleBootstrap?.refresh?.();
                throw new APIError('Session expired', 401, {});
            }
            if (response.status === 402) {
                const data = await response.json().catch(() => ({}));
                throw new APIError('Modulo non acquistato', 402, data);
            }
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new APIError(data.detail || `SSE failed (${response.status})`, response.status, data);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let lastEvent = null;

            // Parse SSE frames: events separated by blank line, lines prefixed "data: " carry JSON payload
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Split on double-newline (SSE frame boundary)
                const frames = buffer.split(/\n\n/);
                buffer = frames.pop(); // keep partial last frame

                for (const frame of frames) {
                    const dataLines = frame.split('\n')
                        .filter((l) => l.startsWith('data: '))
                        .map((l) => l.slice(6))
                        .join('\n');
                    if (!dataLines) continue;
                    try {
                        const ev = JSON.parse(dataLines);
                        lastEvent = ev;
                        if (typeof onEvent === 'function') onEvent(ev);
                        if (ev.kind === 'completed' || ev.kind === 'failed') {
                            return ev;
                        }
                    } catch (e) {
                        console.warn('[APIClient] SSE frame parse error', e, dataLines);
                    }
                }
            }
            return lastEvent;
        }
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