(function() {
    'use strict';

    class TemplateConfig {
        constructor() {
            this.form = null;
            this.preview = null;
            this.logoPreview = null;
            this.init();
        }

        init() {
            this.form = document.getElementById('template-config-form');
            this.preview = document.getElementById('template-preview');
            this.logoPreview = document.getElementById('logo-preview');
            
            if (this.form) {
                this.bindEvents();
                this.loadCurrentConfig();
            }
        }

        bindEvents() {
            const logoInput = document.getElementById('logo-input');
            if (logoInput) {
                logoInput.addEventListener('change', (e) => this.handleLogoUpload(e));
            }

            const paperSizeSelect = document.getElementById('paper-size');
            if (paperSizeSelect) {
                paperSizeSelect.addEventListener('change', () => this.updatePreview());
            }

            const colorInputs = document.querySelectorAll('.color-input');
            colorInputs.forEach(input => {
                input.addEventListener('input', () => this.updatePreview());
            });

            const resetBtn = document.getElementById('reset-template');
            if (resetBtn) {
                resetBtn.addEventListener('click', () => this.resetToDefault());
            }

            const saveBtn = document.getElementById('save-template');
            if (saveBtn) {
                saveBtn.addEventListener('click', () => this.saveConfig());
            }
        }

        handleLogoUpload(e) {
            const file = e.target.files[0];
            if (file && this.logoPreview) {
                if (!file.type.startsWith('image/')) {
                    alert('Selezionare un file immagine valido.');
                    return;
                }
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    this.logoPreview.innerHTML = `<img src="${e.target.result}" alt="Logo anteprima">`;
                };
                reader.readAsDataURL(file);
            }
        }

        updatePreview() {
            if (!this.preview) return;

            const headerText = document.getElementById('header-text')?.value || '';
            const footerText = document.getElementById('footer-text')?.value || '';
            const primaryColor = document.getElementById('primary-color')?.value || '#1a365d';
            const secondaryColor = document.getElementById('secondary-color')?.value || '#2c5282';
            const paperSize = document.getElementById('paper-size')?.value || 'a4';

            const paperSizes = {
                a4: { width: '210mm', height: '297mm' },
                a3: { width: '297mm', height: '420mm' },
                letter: { width: '216mm', height: '279mm' },
                legal: { width: '216mm', height: '356mm' }
            };

            const dims = paperSizes[paperSize] || paperSizes.a4;

            this.preview.innerHTML = `
                <div class="preview-paper" style="
                    width: ${dims.width};
                    height: ${dims.height};
                    border: 1px solid #ccc;
                    background: white;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                ">
                    <div class="preview-header" style="
                        background: ${primaryColor};
                        color: white;
                        padding: 10px;
                        font-size: 12px;
                    ">${headerText || 'Intestazione documento'}</div>
                    <div class="preview-content" style="
                        padding: 20px;
                        color: #333;
                    ">Contenuto del documento...</div>
                    <div class="preview-footer" style="
                        background: ${secondaryColor};
                        color: white;
                        padding: 10px;
                        font-size: 10px;
                    ">${footerText || 'Piè di pagina documento'}</div>
                </div>
            `;
        }

        loadCurrentConfig() {
            if (window.apiClient) {
                window.apiClient.getPrintSettings().then(settings => {
                    if (settings) {
                        this.applySettingsToForm(settings);
                    }
                    this.updatePreview();
                }).catch(() => {
                    this.updatePreview();
                });
            } else {
                this.updatePreview();
            }
        }

        applySettingsToForm(settings) {
            const fields = [
                'header-text', 'footer-text', 'primary-color', 
                'secondary-color', 'paper-size', 'logo-input'
            ];
            
            fields.forEach(field => {
                const el = document.getElementById(field);
                if (el && settings[field.replace('-', '_')]) {
                    el.value = settings[field.replace('-', '_')];
                }
            });
        }

        resetToDefault() {
            const defaults = {
                'header-text': 'MARS - Valutazione Agenti di Rischio',
                'footer-text': 'Documento generato automaticamente - Tutti i diritti riservati',
                'primary-color': '#1a365d',
                'secondary-color': '#2c5282',
                'paper-size': 'a4'
            };

            Object.keys(defaults).forEach(key => {
                const el = document.getElementById(key);
                if (el) {
                    el.value = defaults[key];
                }
            });

            if (this.logoPreview) {
                this.logoPreview.innerHTML = '';
            }

            this.updatePreview();
            this.showNotification('Template reimpostato ai valori predefiniti', 'success');
        }

        async saveConfig() {
            const settings = {
                header_text: document.getElementById('header-text')?.value || '',
                footer_text: document.getElementById('footer-text')?.value || '',
                primary_color: document.getElementById('primary-color')?.value || '#1a365d',
                secondary_color: document.getElementById('secondary-color')?.value || '#2c5282',
                paper_size: document.getElementById('paper-size')?.value || 'a4'
            };

            try {
                if (window.apiClient) {
                    await window.apiClient.savePrintSettings(settings);
                }
                this.showNotification('Configurazione salvata con successo', 'success');
            } catch (error) {
                this.showNotification('Errore nel salvataggio della configurazione', 'error');
            }
        }

        showNotification(message, type) {
            if (window.app && window.app.showToast) {
                window.app.showToast(message, type);
            }
        }

        destroy() {
            this.form = null;
            this.preview = null;
            this.logoPreview = null;
        }
    }

    window.TemplateConfig = TemplateConfig;
})();
