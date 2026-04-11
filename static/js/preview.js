(function() {
    'use strict';

    class Preview {
        constructor() {
            this.container = null;
            this.currentAssessment = null;
            this.init();
        }

        init() {
            this.container = document.getElementById('preview-container');
        }

        async loadAssessment(assessmentId) {
            if (!this.container) return;

            try {
                if (window.apiClient) {
                    this.currentAssessment = await window.apiClient.getAssessment(assessmentId);
                    const sections = await window.apiClient.getAssessmentSections(assessmentId);
                    this.render(sections);
                } else {
                    this.render(this.getMockSections());
                }
            } catch (error) {
                this.showError('Errore nel caricamento dell\'anteprima');
            }
        }

        render(sections) {
            if (!this.container || !sections) return;

            const headerText = document.getElementById('preview-header-text')?.value || 'MARS - Valutazione Agenti di Rischio';
            const footerText = document.getElementById('preview-footer-text')?.value || 'Documento di valutazione del rumore';

            this.container.innerHTML = `
                <div class="preview-document">
                    <div class="preview-header">
                        <h1>${headerText}</h1>
                        ${this.currentAssessment ? `<p class="assessment-info">Valutazione N. ${this.currentAssessment.id} - ${this.currentAssessment.date || new Date().toLocaleDateString('it-IT')}</p>` : ''}
                    </div>
                    <div class="preview-body">
                        ${sections.map(section => this.renderSection(section)).join('')}
                    </div>
                    <div class="preview-footer">
                        <p>${footerText}</p>
                        <p class="page-number">Pagina <span class="page"></span> di <span class="total-pages"></span></p>
                    </div>
                </div>
            `;

            this.addPrintStyles();
        }

        renderSection(section) {
            const title = section.title || section.nome || 'Sezione';
            const content = section.content || section.contenuto || '';

            return `
                <div class="preview-section" data-section-id="${section.id || section.id_sezione || ''}">
                    <h2 class="section-title">${title}</h2>
                    <div class="section-content">${content}</div>
                </div>
            `;
        }

        getMockSections() {
            return [
                {
                    id: 1,
                    title: 'Informazioni Generali',
                    content: '<p>Valutazione del rischio rumore per ambiente di lavoro</p>'
                },
                {
                    id: 2,
                    title: 'Descrizione Attività',
                    content: '<p>Analisi delle attività lavorative che comportano esposizione al rumore.</p>'
                },
                {
                    id: 3,
                    title: 'Valutazione Rischio',
                    content: '<p>Livelli di esposizione calcolati e confronto con limiti normativi.</p>'
                }
            ];
        }

        addPrintStyles() {
            if (!document.getElementById('preview-print-styles')) {
                const style = document.createElement('style');
                style.id = 'preview-print-styles';
                style.textContent = `
                    @media print {
                        .preview-document {
                            box-shadow: none !important;
                            margin: 0 !important;
                            padding: 20mm !important;
                        }
                        .preview-header, .preview-footer {
                            display: block !important;
                        }
                        .preview-section {
                            page-break-inside: avoid;
                        }
                    }
                `;
                document.head.appendChild(style);
            }
        }

        exportToPDF() {
            window.print();
        }

        showError(message) {
            if (this.container) {
                this.container.innerHTML = `<div class="preview-error"><p>${message}</p></div>`;
            }
        }

        destroy() {
            this.container = null;
            this.currentAssessment = null;
        }
    }

    window.Preview = Preview;
})();
