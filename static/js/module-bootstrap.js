/**
 * Module Bootstrap — handshake con parent MARS web via postMessage.
 *
 * Modalità operative:
 *   A) Iframe embed in MARS: parent invia {type:'ready', payload:{moduleKey,dvrDocumentId,revisionId,accessToken,marsApiBaseUrl,tenantId}}
 *      -> salva context, skippa login, inizializza app con token MARS
 *   B) Dev via query string: ?token=...&dvr_doc_id=...&revision_id=...
 *      -> popola context, skippa login
 *   C) Standalone (nessuno dei due): lascia fluire authService login esistente (non-breaking)
 *
 * Allowlist origini parent (for security):
 *   Override via <meta name="mars-allowed-origins" content="https://app.mars.local,https://mars.example.com">
 *   Default: localhost:5173 (Vite), localhost:3000 (Next), origine corrente.
 */
(function () {
    'use strict';

    const READY_TIMEOUT_MS = 2500;

    function parseAllowedOrigins() {
        const meta = document.querySelector('meta[name="mars-allowed-origins"]');
        const configured = meta ? meta.content.split(',').map((s) => s.trim()).filter(Boolean) : [];
        const defaults = [
            window.location.origin,
            'http://localhost:5173',
            'http://localhost:3000',
        ];
        return Array.from(new Set([...configured, ...defaults]));
    }

    const ALLOWED_ORIGINS = parseAllowedOrigins();

    const ModuleBootstrap = {
        mode: null,        // 'mars-iframe' | 'standalone-dev' | 'standalone-login'
        context: null,
        ready: false,
        _listeners: [],
        _timeoutId: null,

        onReady(cb) {
            if (this.ready) cb(this.context);
            else this._listeners.push(cb);
        },

        isEmbedded() {
            try {
                return window.parent !== window && window.parent.location !== window.location;
            } catch (_) {
                // cross-origin access throws → parent exists in different origin
                return window.parent !== window;
            }
        },

        _signalReady() {
            if (window.parent !== window) {
                // broadcast to any allowed origin; parent's script filters
                ALLOWED_ORIGINS.forEach((origin) => {
                    try { window.parent.postMessage({ type: 'module-ready' }, origin); } catch (_) { /* noop */ }
                });
            }
        },

        _handleParentMessage(ev) {
            if (!ALLOWED_ORIGINS.includes(ev.origin)) return;
            if (!ev.data || typeof ev.data !== 'object') return;
            if (ev.data.type !== 'ready' || !ev.data.payload) return;

            const { moduleKey, dvrDocumentId, revisionId, accessToken, marsApiBaseUrl, tenantId } = ev.data.payload;
            if (!accessToken || !dvrDocumentId) {
                console.warn('[ModuleBootstrap] Parent ready payload incompleto, ignorato');
                return;
            }

            clearTimeout(this._timeoutId);

            this.mode = 'mars-iframe';
            this.context = {
                moduleKey: moduleKey || 'noise',
                dvrDocumentId,
                revisionId: revisionId || null,
                accessToken,
                marsApiBaseUrl: marsApiBaseUrl || null,
                tenantId: tenantId || null,
                parentOrigin: ev.origin,
            };

            // Use sessionStorage (not localStorage) for iframe isolation
            sessionStorage.setItem('mars_access_token', accessToken);
            sessionStorage.setItem('mars_dvr_doc_id', dvrDocumentId);
            if (revisionId) sessionStorage.setItem('mars_revision_id', revisionId);
            if (tenantId) sessionStorage.setItem('mars_tenant_id', tenantId);

            // Bridge: if authService exists, seed it with MARS token so existing code keeps working
            if (window.authService) {
                window.authService.accessToken = accessToken;
                try {
                    localStorage.setItem('access_token', accessToken);
                } catch (_) { /* private mode */ }
            }

            this.ready = true;
            this._fire();
        },

        _fallbackFromQueryString() {
            const params = new URLSearchParams(window.location.search);
            const devToken = params.get('token');
            const docId = params.get('dvr_doc_id');

            if (!devToken || !docId) return false;

            this.mode = 'standalone-dev';
            this.context = {
                moduleKey: params.get('module_key') || 'noise',
                dvrDocumentId: docId,
                revisionId: params.get('revision_id') || null,
                accessToken: devToken,
                marsApiBaseUrl: params.get('mars_api') || null,
                tenantId: params.get('tenant_id') || null,
                parentOrigin: null,
            };
            sessionStorage.setItem('mars_access_token', devToken);
            sessionStorage.setItem('mars_dvr_doc_id', docId);
            if (this.context.revisionId) sessionStorage.setItem('mars_revision_id', this.context.revisionId);
            if (window.authService) {
                window.authService.accessToken = devToken;
                try { localStorage.setItem('access_token', devToken); } catch (_) { /* noop */ }
            }
            this.ready = true;
            this._fire();
            return true;
        },

        _fire() {
            this._listeners.forEach((cb) => {
                try { cb(this.context); } catch (e) { console.error('[ModuleBootstrap] listener error', e); }
            });
            this._listeners = [];
        },

        _onTimeout() {
            if (this.ready) return;

            // Try query string first (useful in dev + direct-link mode)
            if (this._fallbackFromQueryString()) return;

            // No iframe parent, no dev params → standalone mode (login form)
            this.mode = 'standalone-login';
            this.ready = true;
            this._fire();
        },

        close() {
            if (this.context?.parentOrigin) {
                window.parent.postMessage({ type: 'close' }, this.context.parentOrigin);
            }
        },

        refresh() {
            if (this.context?.parentOrigin) {
                window.parent.postMessage({ type: 'refresh' }, this.context.parentOrigin);
            }
        },

        notifyError(message, extra = null) {
            if (this.context?.parentOrigin) {
                window.parent.postMessage(
                    { type: 'error', payload: { message, extra } },
                    this.context.parentOrigin
                );
            }
        },

        notifySaved(payload = null) {
            if (this.context?.parentOrigin) {
                window.parent.postMessage({ type: 'saved', payload }, this.context.parentOrigin);
            }
        },

        init() {
            if (this.isEmbedded()) {
                this._signalReady();
                this._timeoutId = setTimeout(() => this._onTimeout(), READY_TIMEOUT_MS);
            } else {
                // Not embedded: try query string immediately, otherwise standalone login
                if (!this._fallbackFromQueryString()) {
                    this.mode = 'standalone-login';
                    this.ready = true;
                    this._fire();
                }
            }
        },
    };

    // Attach message listener immediately (not in init) to avoid racing parent postMessage
    window.addEventListener('message', (ev) => ModuleBootstrap._handleParentMessage(ev));

    window.ModuleBootstrap = ModuleBootstrap;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => ModuleBootstrap.init());
    } else {
        ModuleBootstrap.init();
    }
})();
