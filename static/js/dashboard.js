/**
 * dashboard.js — Dashboard widgets: recent sessions and document summary.
 */
document.addEventListener('DOMContentLoaded', async () => {
  loadRecentSessions();
  loadDocsSummary();
});

async function loadRecentSessions() {
  const container = document.getElementById('recent-sessions-list');
  if (!container) return;
  try {
    const res = await API.get('/api/sessions?page=1&per_page=3');
    const data = await res.json();
    if (!res.ok || !data.sessions?.length) {
      container.innerHTML = '<p class="loading-text">No conversations yet. <a href="/chat">Start one</a>.</p>';
      return;
    }
    container.innerHTML = data.sessions.map(s => `
      <div class="session-row">
        <a href="/chat?session=${s.id}" class="session-row-title">${escapeHtml(s.title)}</a>
        <span class="session-row-meta">${s.message_count} msg</span>
      </div>
    `).join('');
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      container.innerHTML = '<p class="loading-text">Could not load sessions.</p>';
    }
  }
}

async function loadDocsSummary() {
  const container = document.getElementById('docs-summary');
  if (!container) return;
  try {
    const res = await API.get('/api/documents?page=1&per_page=5');
    const data = await res.json();
    if (!res.ok) { container.innerHTML = '<p class="loading-text">Could not load.</p>'; return; }
    if (!data.documents?.length) {
      container.innerHTML = '<p class="loading-text">No documents yet. <a href="/documents">Upload one</a>.</p>';
      return;
    }
    container.innerHTML = data.documents.map(d => `
      <div class="doc-row">
        <span>${escapeHtml(d.filename_original)}</span>
        <span class="badge badge--${d.status}">${d.status}</span>
      </div>
    `).join('');
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      container.innerHTML = '<p class="loading-text">Could not load documents.</p>';
    }
  }
}

function startChatWith(text) {
  sessionStorage.setItem('initialMessage', text);
  window.location.href = '/chat';
}

function escapeHtml(t) { const d = document.createElement('div'); d.appendChild(document.createTextNode(t || '')); return d.innerHTML; }
