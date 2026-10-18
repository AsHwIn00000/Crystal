/**
 * api.js — Fetch API wrapper with CSRF injection and auth error handling.
 * All callers MUST wrap in try/catch. On 401/403, this throws typed errors
 * instead of returning undefined.
 */

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  toast.setAttribute('role', 'status');
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

const API = {
  _csrfToken() {
    // Try meta tag first (set by Jinja2 on every page load)
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    // Fallback: read from the csrf_token cookie that Flask-WTF sets
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  },

  async request(method, url, body = null, isFormData = false, timeoutMs = 45000) {
    const headers = { 'X-CSRFToken': this._csrfToken() };
    if (!isFormData) headers['Content-Type'] = 'application/json';
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const opts = { method, headers, credentials: 'same-origin', signal: controller.signal };
    if (body) opts.body = isFormData ? body : JSON.stringify(body);

    let res;
    try {
      res = await fetch(url, opts);
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        showToast('Request timed out. Please try again.', 'error');
        throw new Error('Request timed out. Please try again.');
      }
      // Network-level error (DNS failure, offline, etc.)
      showToast('Network error. Please check your connection.', 'error');
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }

    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (res.status === 403) {
      showToast('Access denied.', 'error');
      throw new Error('Forbidden');
    }
    return res;
  },

  get(url)           { return this.request('GET',    url); },
  post(url, body)    { return this.request('POST',   url, body); },
  put(url, body)     { return this.request('PUT',    url, body); },
  delete(url)        { return this.request('DELETE', url); },
  upload(url, form)  { return this.request('POST',   url, form, true); },
};
