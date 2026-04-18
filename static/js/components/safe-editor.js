/**
 * SafeEditor — contenteditable wrapper con undo/redo + sanitizzazione paste.
 *
 * Features:
 *   - Undo/redo con debounce 300ms (UndoStack)
 *   - Paste sanitizzato via DOMPurify (CDN) con allowlist per DVR (headings,
 *     listings, tabelle, link, formattazione base). Fallback: plain text.
 *   - Keyboard: Ctrl/Cmd+Z (undo), Ctrl/Cmd+Y o Ctrl/Cmd+Shift+Z (redo),
 *     Tab (indent 4 spazi), Ctrl/Cmd+B/I/U (bold/italic/underline).
 *   - onChange callback invocato ad ogni mutazione (incluso paste/undo).
 *
 * Security rationale (XSS):
 *   Sanitizzare AL paste, non al save — altrimenti uno script iniettato
 *   avrebbe tempo di eseguire mentre è mostrato nell'editor.
 */
(function () {
    'use strict';

    const DEFAULT_ALLOWED_TAGS = [
        'p', 'br', 'div', 'span', 'strong', 'b', 'em', 'i', 'u',
        'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'a', 'blockquote', 'code', 'pre',
        'table', 'thead', 'tbody', 'tr', 'td', 'th',
        'hr',
    ];

    const DEFAULT_ALLOWED_ATTR = ['href', 'title', 'target', 'rel', 'colspan', 'rowspan'];

    function defaultSanitize(html, config = {}) {
        if (window.DOMPurify) {
            return window.DOMPurify.sanitize(html, {
                ALLOWED_TAGS: config.allowedTags || DEFAULT_ALLOWED_TAGS,
                ALLOWED_ATTR: config.allowedAttr || DEFAULT_ALLOWED_ATTR,
                FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick'],
                KEEP_CONTENT: true,
            });
        }
        // Fallback: plain text (strip all HTML)
        const tmp = document.createElement('div');
        tmp.textContent = html;
        return tmp.innerHTML;
    }

    class SafeEditor {
        constructor(element, options = {}) {
            if (!element) throw new Error('SafeEditor: element required');
            this.el = element;
            this.el.contentEditable = 'true';
            this.el.setAttribute('role', 'textbox');
            this.el.setAttribute('aria-multiline', 'true');
            this.el.spellcheck = options.spellcheck !== false;

            this.onChange = options.onChange || (() => {});
            this.sanitizer = options.sanitizer || ((html) => defaultSanitize(html, options));
            this.undoStack = new UndoStack({
                maxSize: options.maxUndoSteps || 100,
                debounceMs: options.debounceMs || 300,
            });

            this._inputHandler = this._onInput.bind(this);
            this._pasteHandler = this._onPaste.bind(this);
            this._keydownHandler = this._onKeyDown.bind(this);

            this._bindEvents();
            this.undoStack.seed(this.el.innerHTML);
        }

        _bindEvents() {
            this.el.addEventListener('input', this._inputHandler);
            this.el.addEventListener('paste', this._pasteHandler);
            this.el.addEventListener('keydown', this._keydownHandler);
        }

        _onInput() {
            const value = this.el.innerHTML;
            this.undoStack.push(value);
            this.onChange(value);
        }

        _onPaste(ev) {
            ev.preventDefault();
            const cd = ev.clipboardData;
            if (!cd) return;

            const html = cd.getData('text/html');
            const text = cd.getData('text/plain');
            const raw = html || text;
            const sanitized = this.sanitizer(raw);

            // Insert at caret using DOM range (compatible, preserves selection)
            const selection = window.getSelection();
            if (!selection || !selection.rangeCount) {
                this.el.insertAdjacentHTML('beforeend', sanitized);
            } else {
                const range = selection.getRangeAt(0);
                range.deleteContents();
                const tmp = document.createElement('div');
                tmp.innerHTML = sanitized;
                const frag = document.createDocumentFragment();
                let lastNode = null;
                while (tmp.firstChild) {
                    lastNode = frag.appendChild(tmp.firstChild);
                }
                range.insertNode(frag);
                if (lastNode) {
                    // Place caret after inserted content
                    range.setStartAfter(lastNode);
                    range.setEndAfter(lastNode);
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
            }

            this.undoStack.flush();
            this.undoStack.push(this.el.innerHTML);
            this.onChange(this.el.innerHTML);
        }

        _onKeyDown(ev) {
            const mod = ev.ctrlKey || ev.metaKey;
            if (!mod) {
                if (ev.key === 'Tab') {
                    ev.preventDefault();
                    document.execCommand('insertText', false, '    ');
                }
                return;
            }

            const key = ev.key.toLowerCase();
            if (key === 'z' && !ev.shiftKey) {
                ev.preventDefault();
                const prev = this.undoStack.undo();
                if (prev != null) {
                    this.el.innerHTML = prev;
                    this.onChange(prev);
                }
            } else if (key === 'y' || (key === 'z' && ev.shiftKey)) {
                ev.preventDefault();
                const next = this.undoStack.redo();
                if (next != null) {
                    this.el.innerHTML = next;
                    this.onChange(next);
                }
            } else if (key === 'b') {
                ev.preventDefault();
                document.execCommand('bold');
            } else if (key === 'i') {
                ev.preventDefault();
                document.execCommand('italic');
            } else if (key === 'u') {
                ev.preventDefault();
                document.execCommand('underline');
            }
        }

        getValue() {
            return this.el.innerHTML;
        }

        setValue(html, { seed = false } = {}) {
            const sanitized = this.sanitizer(html);
            this.el.innerHTML = sanitized;
            if (seed) {
                this.undoStack.seed(sanitized);
            } else {
                this.undoStack.flush();
                this.undoStack.push(sanitized);
            }
            this.onChange(sanitized);
        }

        focus() {
            this.el.focus();
        }

        destroy() {
            this.el.removeEventListener('input', this._inputHandler);
            this.el.removeEventListener('paste', this._pasteHandler);
            this.el.removeEventListener('keydown', this._keydownHandler);
            this.undoStack.clear();
        }
    }

    window.SafeEditor = SafeEditor;
})();
