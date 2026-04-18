/**
 * UndoStack — debounced undo/redo history for contenteditable or any text state.
 *
 * Debounce prevents one-state-per-keystroke bloat: only after N ms of inactivity
 * does the current value get pushed to the stack. Undo/redo always commit the
 * pending debounced value first so users don't lose a partial edit.
 */
(function () {
    'use strict';

    class UndoStack {
        constructor({ maxSize = 100, debounceMs = 300 } = {}) {
            this.maxSize = maxSize;
            this.debounceMs = debounceMs;
            this.stack = [];
            this.cursor = -1;
            this._pendingValue = null;
            this._pendingTimer = null;
        }

        /**
         * Mark a new value. Debounced: actual push happens after `debounceMs`
         * of inactivity. Subsequent push calls within the window overwrite
         * the pending value.
         */
        push(value) {
            this._pendingValue = value;
            clearTimeout(this._pendingTimer);
            this._pendingTimer = setTimeout(() => this._commitPending(), this.debounceMs);
        }

        /**
         * Force-commit the pending debounced value immediately.
         * Call this before undo/redo to avoid losing a partial edit.
         */
        flush() {
            clearTimeout(this._pendingTimer);
            this._pendingTimer = null;
            if (this._pendingValue !== null) {
                this._commitPending();
            }
        }

        _commitPending() {
            const value = this._pendingValue;
            this._pendingValue = null;

            // Skip consecutive duplicates
            if (this.cursor >= 0 && this.stack[this.cursor] === value) return;

            // Truncate any redo history past current cursor
            if (this.cursor < this.stack.length - 1) {
                this.stack.length = this.cursor + 1;
            }

            this.stack.push(value);
            if (this.stack.length > this.maxSize) {
                this.stack.shift();
            } else {
                this.cursor++;
            }
        }

        /**
         * Seed the stack without triggering debounce (useful at init).
         */
        seed(value) {
            this.flush();
            this.stack = [value];
            this.cursor = 0;
        }

        undo() {
            this.flush();
            if (this.cursor <= 0) return null;
            this.cursor--;
            return this.stack[this.cursor];
        }

        redo() {
            this.flush();
            if (this.cursor >= this.stack.length - 1) return null;
            this.cursor++;
            return this.stack[this.cursor];
        }

        canUndo() { return this.cursor > 0; }
        canRedo() { return this.cursor < this.stack.length - 1; }

        clear() {
            clearTimeout(this._pendingTimer);
            this._pendingTimer = null;
            this._pendingValue = null;
            this.stack = [];
            this.cursor = -1;
        }
    }

    window.UndoStack = UndoStack;
})();
