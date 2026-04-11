(function() {
    'use strict';

    class Toolbar {
        constructor(containerId) {
            this.container = document.getElementById(containerId);
            this.buttons = [];
            this.activeCommands = new Set();
            this.init();
        }

        init() {
            if (this.container) {
                this.render();
                this.bindEvents();
            }
        }

        render() {
            this.container.innerHTML = `
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="undo" title="Annulla (Ctrl+Z)">↶</button>
                    <button class="toolbar-btn" data-command="redo" title="Ripeti (Ctrl+Y)">↷</button>
                </div>
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="bold" title="Grassetto (Ctrl+B)"><b>B</b></button>
                    <button class="toolbar-btn" data-command="italic" title="Corsivo (Ctrl+I)"><i>I</i></button>
                    <button class="toolbar-btn" data-command="underline" title="Sottolineato (Ctrl+U)"><u>U</u></button>
                    <button class="toolbar-btn" data-command="strikeThrough" title="Barrato"><s>S</s></button>
                </div>
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="formatBlock" data-value="h1" title="Titolo 1">H1</button>
                    <button class="toolbar-btn" data-command="formatBlock" data-value="h2" title="Titolo 2">H2</button>
                    <button class="toolbar-btn" data-command="formatBlock" data-value="h3" title="Titolo 3">H3</button>
                    <button class="toolbar-btn" data-command="formatBlock" data-value="h4" title="Titolo 4">H4</button>
                    <button class="toolbar-btn" data-command="formatBlock" data-value="p" title="Paragrafo">¶</button>
                </div>
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="insertUnorderedList" title="Elenco puntato">•</button>
                    <button class="toolbar-btn" data-command="insertOrderedList" title="Elenco numerato">1.</button>
                </div>
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="justifyLeft" title="Allinea a sinistra">⫷</button>
                    <button class="toolbar-btn" data-command="justifyCenter" title="Centra">⫷⫸</button>
                    <button class="toolbar-btn" data-command="justifyRight" title="Allinea a destra">⫸</button>
                </div>
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="indent" title="Aumenta rientro">⇥</button>
                    <button class="toolbar-btn" data-command="outdent" title="Diminuisci rientro">⇤</button>
                </div>
                <div class="toolbar-group">
                    <button class="toolbar-btn" data-command="insertTable" title="Inserisci tabella">▦</button>
                    <button class="toolbar-btn" data-command="createLink" title="Inserisci collegamento">🔗</button>
                </div>
            `;
        }

        bindEvents() {
            this.container.addEventListener('click', (e) => {
                const btn = e.target.closest('.toolbar-btn');
                if (btn) {
                    e.preventDefault();
                    this.handleCommand(btn.dataset.command, btn.dataset.value);
                }
            });

            document.addEventListener('selectionchange', () => {
                this.updateActiveStates();
            });
        }

        handleCommand(command, value) {
            if (command === 'createLink') {
                const url = prompt('Inserire URL del collegamento:');
                if (url) {
                    document.execCommand(command, false, url);
                }
            } else if (command === 'insertTable') {
                this.insertTable(3, 3);
            } else {
                document.execCommand(command, false, value);
            }
            this.updateActiveStates();
        }

        insertTable(rows, cols) {
            let html = '<table>';
            for (let i = 0; i < rows; i++) {
                html += '<tr>';
                for (let j = 0; j < cols; j++) {
                    html += i === 0 ? '<th>Contenuto</th>' : '<td>Contenuto</td>';
                }
                html += '</tr>';
            }
            html += '</table>';
            document.execCommand('insertHTML', false, html);
        }

        updateActiveStates() {
            const commands = ['bold', 'italic', 'underline', 'strikeThrough', 'insertUnorderedList', 'insertOrderedList'];
            commands.forEach(cmd => {
                const btn = this.container.querySelector(`[data-command="${cmd}"]`);
                if (btn) {
                    btn.classList.toggle('active', document.queryCommandState(cmd));
                }
            });
        }

        enableButton(command, enabled) {
            const btn = this.container.querySelector(`[data-command="${command}"]`);
            if (btn) {
                btn.disabled = !enabled;
                btn.style.opacity = enabled ? '1' : '0.5';
            }
        }

        destroy() {
            if (this.container) {
                this.container.innerHTML = '';
            }
        }
    }

    window.Toolbar = Toolbar;
})();
