(function() {
    'use strict';

    class APIClient {
        constructor(baseURL = '/api/v1/noise') {
            this.baseURL = baseURL;
            this.defaultHeaders = {
                'Content-Type': 'application/json'
            };
        }

        async request(endpoint, options = {}) {
            const url = `${this.baseURL}${endpoint}`;
            const config = {
                headers: { ...this.defaultHeaders, ...options.headers },
                ...options
            };

            try {
                const response = await authService.fetchWithAuth(url, config);
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new APIError(
                        errorData.message || `HTTP ${response.status}`,
                        response.status,
                        errorData
                    );
                }

                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return await response.json();
                }
                
                if (contentType && (contentType.includes('word') || contentType.includes('document'))) {
                    return await response.blob();
                }

                return await response.text();
            } catch (error) {
                if (error instanceof APIError) {
                    throw error;
                }
                throw new APIError(`Errore di rete: ${error.message}`, 0, {});
            }
        }

        async getAssessment(id) {
            return this.request(`/assessments/${id}`);
        }

        async getAssessmentSections(id) {
            return this.request(`/export/assessments/${id}/document/sections`);
        }

        async updateSection(id, sectionId, content) {
            return this.request(`/export/assessments/${id}/document/sections/${sectionId}`, {
                method: 'PUT',
                body: JSON.stringify({ content })
            });
        }

        async exportJSON(id) {
            const response = await authService.fetchWithAuth(`${this.baseURL}/export/assessments/${id}/json`, {
                method: 'POST',
                headers: this.defaultHeaders
            });
            
            if (!response.ok) {
                throw new APIError(`Export failed: HTTP ${response.status}`, response.status);
            }
            
            return await response.blob();
        }

        async exportDOCX(id, options = {}) {
            const response = await authService.fetchWithAuth(`${this.baseURL}/export/assessments/${id}/docx`, {
                method: 'POST',
                headers: this.defaultHeaders,
                body: JSON.stringify(options)
            });
            
            if (!response.ok) {
                throw new APIError(`Export failed: HTTP ${response.status}`, response.status);
            }
            
            return await response.blob();
        }

        async getExportPreview(id) {
            return this.request(`/export/assessments/${id}/preview`);
        }

        async getTemplates() {
            return this.request('/export/templates');
        }

        async getTemplate(id) {
            return this.request(`/export/templates/${id}`);
        }

        async saveTemplateOverride(id, content) {
            return this.request(`/export/templates/${id}`, {
                method: 'PUT',
                body: JSON.stringify({ content })
            });
        }

        async getPrintSettings() {
            return this.request('/export/print-settings');
        }

        async savePrintSettings(settings) {
            return this.request('/export/print-settings', {
                method: 'PUT',
                body: JSON.stringify(settings)
            });
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
