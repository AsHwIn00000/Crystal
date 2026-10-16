/**
 * admin.js — Admin dashboard: stats, college docs, users, audit log.
 */
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadCollegeDocs();
  loadUsers();
  loadAuditLog();
  setupTabs();
  setupCollegeUpload();
});

function setupTabs() {
  const tabs = [
    { btn: 'tab-docs-btn', panel: 'tab-documents' },
    { btn: 'tab-users-btn', panel: 'tab-users' },
    { btn: 'tab-audit-btn', panel: 'tab-audit' },
  ];
  tabs.forEach(({ btn, panel }) => {
    document.getElementById(btn)?.addEventListener('click', () => {
      tabs.forEach(t => {
        document.getElementById(t.btn)?.classList.remove('tab-btn--active');
        const p = document.getElementById(t.panel);
        if (p) p.style.display = 'none';
        document.getElementById(t.btn)?.setAttribute('aria-selected', 'false');
      });
      document.getElementById(btn)?.classList.add('tab-btn--active');
      document.getElementById(btn)?.setAttribute('aria-selected', 'true');
      const p = document.getElementById(panel);
      if (p) p.style.display = '';
    });
  });
}

async function loadStats() {
  try {
    const res = await API.get('/admin/stats');
    const data = await res.json();
    if (!res.ok) return;
    document.getElementById('stat-users').textContent = data.total_users ?? '—';
    document.getElementById('stat-sessions').textContent = data.active_sessions_today ?? '—';
    document.getElementById('stat-college-docs').textContent = data.college_docs ?? '—';
    document.getElementById('stat-failed').textContent = data.failed_docs ?? '—';
  } catch (err) { }
}

async function loadCollegeDocs() {
  const tbody = document.getElementById('college-docs-body');
  if (!tbody) return;
  try {
    const res = await API.get('/admin/documents?per_page=50');
    const data = await res.json();
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="5">Failed to load.</td></tr>'; return; }
    if (!data.documents?.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="loading-text">No college documents yet.</td></tr>';
      return;
    }
    tbody.innerHTML = data.documents.map(d => `
      <tr id="college-doc-${d.id}">
        <td>${escapeHtml(d.filename_original)}</td>
        <td>${d.file_type.toUpperCase()}</td>
        <td><span class="badge badge--${d.status}">${d.status}</span></td>
        <td>${formatDate(d.created_at)}</td>
        <td>
          <button class="btn btn-danger btn-small" onclick="deleteCollegeDoc(${d.id})" aria-label="Delete ${escapeAttr(d.filename_original)}">Delete</button>
        </td>
      </tr>
    `).join('');
  } catch (err) { }
}

async function deleteCollegeDoc(id) {
  if (!confirm('Delete this college document?')) return;
  try {
    const res = await API.delete(`/admin/documents/${id}`);
    if (res.status === 204 || res.ok) {
      document.getElementById(`college-doc-${id}`)?.remove();
      showToast('Document deleted.', 'success');
      loadStats();
    } else {
      showToast('Could not delete.', 'error');
    }
  } catch (err) {
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') showToast('Error.', 'error');
  }
}

function setupCollegeUpload() {
  document.getElementById('upload-college-btn')?.addEventListener('click', () => {
    document.getElementById('college-file-input')?.click();
  });
  document.getElementById('college-file-input')?.addEventListener('change', (e) => {
    if (e.target.files[0]) uploadCollegeDoc(e.target.files[0]);
  });
}

async function uploadCollegeDoc(file) {
  const formData = new FormData();
  formData.append('file', file);
  const progress = document.getElementById('college-upload-progress');
  const bar = document.getElementById('college-progress-bar');
  if (progress) progress.style.display = 'block';
  if (bar) bar.style.width = '50%';
  try {
    const res = await API.upload('/admin/documents', formData);
    if (bar) bar.style.width = '100%';
    setTimeout(() => { if (progress) progress.style.display = 'none'; if (bar) bar.style.width = '0'; }, 1500);
    const data = await res.json();
    if (res.ok) {
      showToast('Uploaded and processing...', 'success');
      loadCollegeDocs();
      loadStats();
    } else {
      showToast(data.error || 'Upload failed.', 'error');
    }
  } catch (err) {
    if (progress) progress.style.display = 'none';
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') showToast('Upload failed.', 'error');
  }
}

async function loadUsers() {
  const tbody = document.getElementById('users-body');
  if (!tbody) return;
  try {
    const res = await API.get('/admin/users?per_page=50');
    const data = await res.json();
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="6">Failed.</td></tr>'; return; }
    tbody.innerHTML = data.users.map(u => `
      <tr id="user-row-${u.id}">
        <td>${escapeHtml(u.email)}</td>
        <td>${escapeHtml(u.display_name || '—')}</td>
        <td><span class="badge badge--${u.role}">${u.role}</span></td>
        <td><span class="badge badge--${u.is_active ? 'ready' : 'failed'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
        <td>${formatDate(u.created_at)}</td>
        <td>
          <button class="btn btn-outline btn-small" onclick="toggleUser(${u.id}, ${u.is_active})"
                  aria-label="${u.is_active ? 'Deactivate' : 'Activate'} user ${escapeAttr(u.email)}">
            ${u.is_active ? 'Deactivate' : 'Activate'}
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) { }
}

async function toggleUser(id, isActive) {
  try {
    const res = await API.put(`/admin/users/${id}/toggle-active`, {});
    const data = await res.json();
    if (res.ok) {
      showToast(`User ${data.user.is_active ? 'activated' : 'deactivated'}.`, 'success');
      loadUsers();
    }
  } catch (err) {
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') showToast('Error.', 'error');
  }
}

async function loadAuditLog() {
  const tbody = document.getElementById('audit-body');
  if (!tbody) return;
  try {
    const res = await API.get('/admin/audit?per_page=50');
    const data = await res.json();
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="4">Failed.</td></tr>'; return; }
    if (!data.events?.length) { tbody.innerHTML = '<tr><td colspan="4" class="loading-text">No events yet.</td></tr>'; return; }
    tbody.innerHTML = data.events.map(e => `
      <tr>
        <td>${escapeHtml(e.event_type)}</td>
        <td>${e.user_id ?? '—'}</td>
        <td>${escapeHtml(e.ip_address || '—')}</td>
        <td>${formatDate(e.created_at)}</td>
      </tr>
    `).join('');
  } catch (err) { }
}

function formatDate(iso) { return iso ? new Date(iso).toLocaleString() : '—'; }
function escapeHtml(t) { const d = document.createElement('div'); d.appendChild(document.createTextNode(t || '')); return d.innerHTML; }
function escapeAttr(t) { return (t || '').replace(/"/g, '&quot;'); }
