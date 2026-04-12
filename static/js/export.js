(function() {
    'use strict';

    class Export {
        constructor() {
            this.exportModal = null;
            this.init();
        }

        init() {
            this.exportModal = document.getElementById('export-modal');
        }

        async showExportModal(assessmentId) {
            if (!this.exportModal) {
                this.createModal();
            }

            this.exportModal.classList.add('active');
            this.exportModal.dataset.assessmentId = assessmentId;
        }

        createModal() {
            const modal = document.createElement('div');
            modal.id = 'export-modal';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Esporta Documento</h3>
                        <button class="modal-close" id="close-export-modal">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="export-options">
                            <h4>Seleziona il formato di esportazione:</h4>
                            <div class="export-format" data-format="json">
                                <input type="radio" id="export-json" name="export-format" value="json" checked>
                                <label for="export-json">
                                    <span class="format-icon">📄</span>
                                    <span class="format-name">JSON</span>
                                    <span class="format-desc">Formato dati strutturato</span>
                                </label>
                            </div>
                            <div class="export-format" data-format="docx">
                                <input type="radio" id="export-docx" name="export-format" value="docx">
                                <label for="export-docx">
                                    <span class="format-icon">📝</span>
                                    <span class="format-name">DOCX</span>
                                    <span class="format-desc">Documento Word modificabile</span>
                                </label>
                            </div>
                            <div class="export-format" data-format="pdf">
                                <input type="radio" id="export-pdf" name="export-format" value="pdf">
                                <label for="export-pdf">
                                    <span class="format-icon">📕</span>
                                    <span class="format-name">PDF</span>
                                    <span class="format-desc">Documento per stampa</span>
                                </label>
                            </div>
                        </div>
                        <div class="export-options-docx" id="docx-options" style="display: none;">
                            <h4>Opzioni DOCX:</h4>
                            <div class="form-group">
                                <label for="include-header">Includi intestazione</label>
                                <input type="checkbox" id="include-header" checked>
                            </div>
                            <div class="form-group">
                                <label for="include-footer">Includi piè di pagina</label>
                                <input type="checkbox" id="include-footer" checked>
                            </div>
                            <div class="form-group">
                                <label for="include-logo">Includi logo</label>
                                <input type="checkbox" id="include-logo">
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="cancel-export">Annulla</button>
                        <button class="btn btn-primary" id="confirm-export">Esporta</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            this.exportModal = modal;
            this.bindModalEvents();
        }

        bindModalEvents() {
            const closeBtn = document.getElementById('close-export-modal');
            const cancelBtn = document.getElementById('cancel-export');
            const confirmBtn = document.getElementById('confirm-export');
            const jsonRadio = document.getElementById('export-json');
            const docxRadio = document.getElementById('export-docx');
            const docxOptions = document.getElementById('docx-options');

            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.hideExportModal());
            }
            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => this.hideExportModal());
            }
            if (confirmBtn) {
                confirmBtn.addEventListener('click', () => this.handleExport());
            }
            if (jsonRadio) {
                jsonRadio.addEventListener('change', () => {
                    if (docxOptions) docxOptions.style.display = 'none';
                });
            }
            if (docxRadio) {
                docxRadio.addEventListener('change', () => {
                    if (docxOptions) docxOptions.style.display = 'block';
                });
            }

            this.exportModal.addEventListener('click', (e) => {
                if (e.target === this.exportModal) {
                    this.hideExportModal();
                }
            });
        }

        async handleExport() {
            const assessmentId = this.exportModal.dataset.assessmentId;
            const format = document.querySelector('input[name="export-format"]:checked')?.value || 'json';

            try {
                if (format === 'json') {
                    await this.exportJSON(assessmentId);
                } else if (format === 'docx') {
                    await this.exportDOCX(assessmentId);
                } else if (format === 'pdf') {
                    await this.exportPDF(assessmentId);
                }
            } catch (error) {
                this.showNotification('Errore durante l\'esportazione', 'error');
            }
        }

        async exportJSON(assessmentId) {
            if (window.apiClient) {
                const blob = await window.apiClient.exportJSON(assessmentId);
                this.downloadBlob(blob, `valutazione_${assessmentId}.json`);
            } else {
                this.showNotification('API client non disponibile', 'error');
            }
        }

        async exportDOCX(assessmentId) {
            const options = {
                include_header: document.getElementById('include-header')?.checked ?? true,
                include_footer: document.getElementById('include-footer')?.checked ?? true,
                include_logo: document.getElementById('include-logo')?.checked ?? false
            };

            if (window.apiClient) {
                const blob = await window.apiClient.exportDOCX(assessmentId, options);
                this.downloadBlob(blob, `valutazione_${assessmentId}.docx`);
            } else {
                this.showNotification('API client non disponibile', 'error');
            }
        }

        exportPDF(assessmentId) {
            window.print();
        }

        downloadBlob(blob, filename) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.showNotification('Esportazione completata', 'success');
            this.hideExportModal();
        }

        hideExportModal() {
            if (this.exportModal) {
                this.exportModal.classList.remove('active');
            }
        }

        showNotification(message, type) {
            if (window.app && window.app.showToast) {
                window.app.showToast(message, type);
            }
        }

        destroy() {
            if (this.exportModal) {
                this.exportModal.remove();
                this.exportModal = null;
            }
        }
    }

    window.Export = Export;
})();
