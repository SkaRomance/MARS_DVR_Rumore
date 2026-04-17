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

        async getAssessment(id) { return this.request(`/assessments/${id}`); }

        async getAssessmentSections(id) { return this.request(`/export/assessments/${id}/document/sections`); }

        async updateSection(id, sectionId, contentHtml) {
            return this.request(`/export/assessments/${id}/document/sections/${sectionId}`, {
                method: 'PUT',
                body: JSON.stringify({ content_html: contentHtml })
            });
        }

        async exportDOCX(id, options = {}) {
            const url = `${this.baseURL}/export/assessments/${id}/docx`;
            const response = await authService.fetchWithAuth(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format: 'dvr_full', language: options.language || 'it' })
            });
            if (response && response.ok) return await response.blob();
            throw new APIError(`Export fallito`, response ? response.status : 0, {});
        }

        async getTemplates() { return this.request('/export/templates'); }
        async getTemplate(id) { return this.request(`/export/templates/${id}`); }
        async getPrintSettings() { return this.request('/export/print-settings'); }

        async savePrintSettings(settings) {
            return this.request('/export/print-settings', { method: 'PUT', body: JSON.stringify(settings) });
        }

        async listCompanies(skip = 0, limit = 50) {
            return this.request(`/companies/?skip=${skip}&limit=${limit}`);
        }

        async createCompany(data) {
            return this.request('/companies/', { method: 'POST', body: JSON.stringify(data) });
        }

        async createAssessment(data) {
            return this.request('/assessments/', { method: 'POST', body: JSON.stringify(data) });
        }

        async listJobRoles(companyId) {
            return this.request(`/job-roles/?company_id=${companyId}`);
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