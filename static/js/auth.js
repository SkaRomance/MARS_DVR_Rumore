class AuthService {
    constructor() {
        this.apiBase = '/api/v1/noise';
        this.accessToken = null;
        this.refreshToken = null;
        this.currentUser = null;
        this.onAuthChange = null;
    }

    async login(email, password) {
        const response = await fetch(`${this.apiBase}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        if (!response.ok) {
            const err = await response.json();
            const msg = Array.isArray(err.detail)
                ? err.detail.map(e => e.msg).join(', ')
                : (err.detail || 'Login failed');
            throw new Error(msg);
        }
        const data = await response.json();
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        localStorage.setItem('access_token', this.accessToken);
        localStorage.setItem('refresh_token', this.refreshToken);
        await this.fetchCurrentUser();
        return this.currentUser;
    }

    async fetchCurrentUser() {
        const response = await fetch(`${this.apiBase}/auth/me`, {
            headers: this._authHeaders(),
        });
        if (response.ok) {
            this.currentUser = await response.json();
            if (this.onAuthChange) this.onAuthChange(this.currentUser);
        }
        return this.currentUser;
    }

    async refreshAccessToken() {
        if (!this.refreshToken) {
            this.refreshToken = localStorage.getItem('refresh_token');
        }
        if (!this.refreshToken) return false;
        const response = await fetch(`${this.apiBase}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: this.refreshToken }),
        });
        if (!response.ok) {
            this.logout();
            return false;
        }
        const data = await response.json();
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        localStorage.setItem('access_token', this.accessToken);
        localStorage.setItem('refresh_token', this.refreshToken);
        return true;
    }

    logout() {
        this.accessToken = null;
        this.refreshToken = null;
        this.currentUser = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        if (this.onAuthChange) this.onAuthChange(null);
    }

    isAuthenticated() {
        return !!this.accessToken || !!localStorage.getItem('access_token');
    }

    getToken() {
        return this.accessToken || localStorage.getItem('access_token');
    }

    _authHeaders() {
        const token = this.getToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    async fetchWithAuth(url, options = {}) {
        if (!this.isAuthenticated()) {
            window.location.href = '/static/index.html#login';
            return null;
        }
        options.headers = { ...options.headers, ...this._authHeaders() };
        let response = await fetch(url, options);
        if (response.status === 401) {
            const refreshed = await this.refreshAccessToken();
            if (refreshed) {
                options.headers = { ...options.headers, ...this._authHeaders() };
                response = await fetch(url, options);
            } else {
                this.logout();
                window.location.href = '/static/index.html#login';
                return null;
            }
        }
        return response;
    }
}

const authService = new AuthService();

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';
    try {
        await authService.login(email, password);
        document.getElementById('login-section').style.display = 'none';
        document.getElementById('app-section').style.display = 'block';
        if (window.initializeApp) window.initializeApp();
    } catch (err) {
        errorEl.textContent = err.message;
    }
}

function showLoginSection() {
    document.getElementById('login-section').style.display = 'flex';
    document.getElementById('app-section').style.display = 'none';
}

function showAppSection() {
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('app-section').style.display = 'block';
}

authService.onAuthChange = (user) => {
    if (user) {
        showAppSection();
        const userEl = document.getElementById('current-user');
        if (userEl) userEl.textContent = `${user.full_name || user.email} (${user.role})`;
    } else {
        showLoginSection();
    }
};