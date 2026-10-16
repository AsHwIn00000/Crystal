/**
 * history.js — Chat history page with pagination and single-row delete.
 */
let currentPage = 1;
const PER_PAGE = 20;

document.addEventListener('DOMContentLoaded', () => {
  loadHistory(1);

  document.getElementById('history-search')?.addEventListener('input', (e) => {
    filterRows(e.target.value.toLowerCase());
  });
});

async function loadHistory(page) {
  currentPage = page;
  const tbody = document.getElementById('history-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" class="loading-text">Loading...</td></tr>';

  try {
    const res = await API.get(`/api/sessions?page=${page}&per_page=${PER_PAGE}`);
    const data = await res.json();
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="4">Failed to load.</td></tr>'; return; }
    renderRows(data.sessions, tbody);
    renderPagination(data.page, data.pages);
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      tbody.innerHTML = '<tr><td colspan="4">Error loading history.</td></tr>';
    }
  }
}

function renderRows(sessions, tbody) {
  if (!sessions.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="loading-text">No conversations yet.</td></tr>';
    return;
  }
  tbody.innerHTML = sessions.map(s => `
    <tr data-session-id="${s.id}" data-title="${escapeAttr(s.title)}">
      <td><a href="/chat?session=${s.id}" class="session-row-title">${escapeHtml(s.title)}</a></td>
      <td>${s.message_count}</td>
      <td>${formatDate(s.updated_at)}</td>
      <td>
        <button class="btn btn-danger btn-small delete-session-btn"
                data-session-id="${s.id}"
                aria-label="Delete conversation: ${escapeAttr(s.title)}">Delete</button>
      </td>
    </tr>
  `).join('');

  tbody.querySelectorAll('.delete-session-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.sessionId, 10);
      if (!confirm('Delete this conversation?')) return;
      await deleteSession(id, btn.closest('tr'));
    });
  });
}

async function deleteSession(id, row) {
  try {
    const res = await API.delete(`/api/sessions/${id}`);
    if (res.status === 204 || res.ok) {
      row?.remove();
      showToast('Conversation deleted.', 'success');
    } else {
      showToast('Could not delete conversation.', 'error');
    }
  } catch (err) {
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
      showToast('Could not delete conversation.', 'error');
    }
  }
}

function renderPagination(page, pages) {
  const container = document.getElementById('history-pagination');
  if (!container || pages <= 1) { if (container) container.innerHTML = ''; return; }
  let html = '';
  if (page > 1) html += `<button class="page-btn" onclick="loadHistory(${page - 1})">← Prev</button>`;
  html += `<span class="page-btn page-btn--active">${page} / ${pages}</span>`;
  if (page < pages) html += `<button class="page-btn" onclick="loadHistory(${page + 1})">Next →</button>`;
  container.innerHTML = html;
}

function filterRows(query) {
  document.querySelectorAll('#history-body tr').forEach(row => {
    const title = (row.dataset.title || '').toLowerCase();
    row.style.display = title.includes(query) ? '' : 'none';
  });
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
function escapeHtml(t) { const d = document.createElement('div'); d.appendChild(document.createTextNode(t || '')); return d.innerHTML; }
function escapeAttr(t) { return (t || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
