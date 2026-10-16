/**
 * documents.js — Upload, list, status polling, delete.
 */
let pollTimers = {};
let currentPage = 1;
const PER_PAGE = 20;

document.addEventListener('DOMContentLoaded', () => {
  loadDocuments(1);
  setupUploadZone();

  document.getElementById('file-input')?.addEventListener('change', (e) => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
  });
});

function setupUploadZone() {
  const zone = document.getElementById('upload-zone');
  if (!zone) return;

  zone.addEventListener('dragover', (e) => {
    e.preventDefault(); zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault(); zone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
}

async function uploadFile(file) {
  const maxSize = 50 * 1024 * 1024;
  if (file.size > maxSize) { showToast('File exceeds 50 MB limit.', 'error'); return; }

  const progress = document.getElementById('upload-progress');
  const bar = document.getElementById('progress-bar');
  const text = document.getElementById('progress-text');
  if (progress) { progress.style.display = 'block'; }
  if (bar) bar.style.width = '30%';
  if (text) text.textContent = 'Uploading…';

  const formData = new FormData();
  formData.append('file', file);

  try {
    if (bar) bar.style.width = '60%';
    const res = await API.upload('/api/documents', formData);
    if (bar) bar.style.width = '100%';
    if (text) text.textContent = 'Upload complete.';
    setTimeout(() => { if (progress) progress.style.display = 'none'; if (bar) bar.style.width = '0'; }, 2000);

    const data = await res.json();
    if (res.ok) {
      showToast('Document uploaded. Processing...', 'success');
      await loadDocuments(1);
      pollStatus(data.document.id);
    } else {
      showToast(data.error || 'Upload failed.', 'error');
    }
  } catch (err) {
    if (progress) progress.style.display = 'none';
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
      showToast('Upload failed. Please try again.', 'error');
    }
  }
}

async function loadDocuments(page) {
  currentPage = page;
  const tbody = document.getElementById('docs-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" class="loading-text">Loading...</td></tr>';

  try {
    const res = await API.get(`/api/documents?page=${page}&per_page=${PER_PAGE}`);
    const data = await res.json();
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="6">Failed to load.</td></tr>'; return; }
    renderDocs(data.documents, tbody);
    renderPagination(data.page, data.pages);

    // Start polling for any processing docs
    data.documents.forEach(doc => {
      if (doc.status === 'pending' || doc.status === 'processing') {
        pollStatus(doc.id);
      }
    });
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      tbody.innerHTML = '<tr><td colspan="6">Error loading documents.</td></tr>';
    }
  }
}

function renderDocs(docs, tbody) {
  if (!docs.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading-text">No documents yet. Upload one above.</td></tr>';
    return;
  }
  tbody.innerHTML = docs.map(d => `
    <tr id="doc-row-${d.id}">
      <td>${escapeHtml(d.filename_original)}</td>
      <td>${d.file_type.toUpperCase()}</td>
      <td>${formatSize(d.file_size)}</td>
      <td><span class="badge badge--${d.status}" id="status-${d.id}">${d.status}</span></td>
      <td>${formatDate(d.created_at)}</td>
      <td>
        <button class="btn btn-danger btn-small" onclick="deleteDoc(${d.id})" aria-label="Delete ${escapeAttr(d.filename_original)}">Delete</button>
      </td>
    </tr>
  `).join('');
}

async function deleteDoc(id) {
  if (!confirm('Delete this document?')) return;
  try {
    const res = await API.delete(`/api/documents/${id}`);
    if (res.status === 204 || res.ok) {
      document.getElementById(`doc-row-${id}`)?.remove();
      clearInterval(pollTimers[id]);
      delete pollTimers[id];
      showToast('Document deleted.', 'success');
    } else {
      showToast('Could not delete document.', 'error');
    }
  } catch (err) {
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
      showToast('Could not delete document.', 'error');
    }
  }
}

function pollStatus(docId) {
  if (pollTimers[docId]) return;
  pollTimers[docId] = setInterval(async () => {
    try {
      const res = await API.get(`/api/documents/${docId}/status`);
      const data = await res.json();
      if (!res.ok) { clearInterval(pollTimers[docId]); delete pollTimers[docId]; return; }
      const badge = document.getElementById(`status-${docId}`);
      if (badge) {
        badge.textContent = data.status;
        badge.className = `badge badge--${data.status}`;
      }
      if (data.status === 'ready' || data.status === 'failed') {
        clearInterval(pollTimers[docId]);
        delete pollTimers[docId];
        if (data.status === 'failed' && data.job?.error_message) {
          showToast(`Processing failed: ${data.job.error_message}`, 'error');
        }
      }
    } catch (err) {
      clearInterval(pollTimers[docId]); delete pollTimers[docId];
    }
  }, 5000);
}

function renderPagination(page, pages) {
  const container = document.getElementById('docs-pagination');
  if (!container || pages <= 1) { if (container) container.innerHTML = ''; return; }
  let html = '';
  if (page > 1) html += `<button class="page-btn" onclick="loadDocuments(${page - 1})">← Prev</button>`;
  html += `<span class="page-btn page-btn--active">${page} / ${pages}</span>`;
  if (page < pages) html += `<button class="page-btn" onclick="loadDocuments(${page + 1})">Next →</button>`;
  container.innerHTML = html;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
function formatDate(iso) { return iso ? new Date(iso).toLocaleDateString() : '—'; }
function escapeHtml(t) { const d = document.createElement('div'); d.appendChild(document.createTextNode(t || '')); return d.innerHTML; }
function escapeAttr(t) { return (t || '').replace(/"/g, '&quot;'); }
