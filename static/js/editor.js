(function() {
    'use strict';

    class Editor {
        constructor() {
            this.editorEl = null;
            this.toolbarEl = null;
            this.toolbar = null;
            this.currentAssessmentId = null;
            this.autoSaveTimer = null;
            this.autoSaveInterval = 30000;
            this.init();
        }

        init() {
            this.editorEl = document.getElementById('editor-content');
            this.toolbarEl = document.getElementById('editor-toolbar');
            
            if (this.editorEl) {
                if (typeof window.Toolbar !== 'undefined') {
                    this.toolbar = new window.Toolbar('editor-toolbar');
                }
                this.bindEditorEvents();
            }
        }

        bindEditorEvents() {
            this.editorEl.addEventListener('input', () => {
                this.handleContentChange();
            });

            this.editorEl.addEventListener('paste', (e) => {
                e.preventDefault();
                const text = e.clipboardData.getData('text/plain');
                document.execCommand('insertText', false, text);
            });

            document.addEventListener('keydown', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    if (e.key === 's') {
                        e.preventDefault();
                        this.saveCurrentSection();
                    }
                }
            });
        }

        handleContentChange() {
            if (this.autoSaveTimer) {
                clearTimeout(this.autoSaveTimer);
            }

            this.autoSaveTimer = setTimeout(() => {
                this.saveCurrentSection();
            }, this.autoSaveInterval);

            this.updateWordCount();
        }

        updateWordCount() {
            const content = this.editorEl.innerText || '';
            const words = content.trim().split(/\s+/).filter(w => w.length > 0).length;
            const wordCountEl = document.getElementById('word-count');
            if (wordCountEl) {
                wordCountEl.textContent = `${words} parole`;
            }
        }

        async loadSection(assessmentId, sectionId) {
            this.currentAssessmentId = assessmentId;

            if (window.apiClient) {
                try {
                    const section = await this.getSectionFromServer(assessmentId, sectionId);
                    this.setContent(section.content || '');
                } catch (e) {
                    this.setContent('<p>Contenuto sezione...</p>');
                }
            } else {
                this.setContent('<p>Contenuto sezione...</p>');
            }
        }

        async getSectionFromServer(assessmentId, sectionId) {
            const sections = await window.apiClient.getAssessmentSections(assessmentId);
            return sections.find(s => s.id === sectionId || s.id_sezione === sectionId);
        }

        setContent(html) {
            if (this.editorEl) {
                this.editorEl.innerHTML = html;
                this.updateWordCount();
            }
        }

        getContent() {
            return this.editorEl ? this.editorEl.innerHTML : '';
        }

        async saveCurrentSection() {
            if (!this.currentAssessmentId || !window.apiClient) {
                return false;
            }

            const sectionId = this.getCurrentSectionId();
            if (!sectionId) return false;

            try {
                const content = this.getContent();
                await window.apiClient.updateSection(this.currentAssessmentId, sectionId, content);
                this.showSaveIndicator();
                return true;
            } catch (e) {
                this.showToast('Errore nel salvataggio', 'error');
                return false;
            }
        }

        getCurrentSectionId() {
            const activeSection = document.querySelector('.section-item.active');
            return activeSection ? activeSection.dataset.sectionId : null;
        }

        showSaveIndicator() {
            const indicator = document.getElementById('save-indicator');
            if (indicator) {
                indicator.textContent = 'Salvato';
                indicator.classList.add('show');
                setTimeout(() => {
                    indicator.classList.remove('show');
                }, 2000);
            }
        }

        showToast(message, type) {
            if (window.app && window.app.showToast) {
                window.app.showToast(message, type);
            }
        }

        enableEditing(enabled) {
            if (this.editorEl) {
                this.editorEl.contentEditable = enabled ? 'true' : 'false';
                this.editorEl.classList.toggle('editing-disabled', !enabled);
            }
        }

        insertTable(rows, cols) {
            if (!this.editorEl) return;

            let tableHtml = '<table class="editor-table">';
            for (let i = 0; i < rows; i++) {
                tableHtml += '<tr>';
                for (let j = 0; j < cols; j++) {
                    if (i === 0) {
                        tableHtml += '<th>Intestazione</th>';
                    } else {
                        tableHtml += '<td>Cella</td>';
                    }
                }
                tableHtml += '</tr>';
            }
            tableHtml += '</table>';

            this.editorEl.focus();
            document.execCommand('insertHTML', false, tableHtml);
        }

        insertImage(src, alt = '') {
            if (!this.editorEl) return;
            this.editorEl.focus();
            document.execCommand('insertImage', false, src);
        }

        createLink(url, text) {
            if (!this.editorEl) return;
            this.editorEl.focus();
            document.execCommand('createLink', false, url);
        }

        setReadOnly(readOnly) {
            if (this.editorEl) {
                this.editorEl.contentEditable = readOnly ? 'false' : 'true';
                this.editorEl.classList.toggle('readonly', readOnly);
            }
        }

        destroy() {
            if (this.autoSaveTimer) {
                clearTimeout(this.autoSaveTimer);
            }
            if (this.toolbar) {
                this.toolbar.destroy();
            }
            this.editorEl = null;
            this.toolbarEl = null;
        }
    }

    window.Editor = Editor;
})();
