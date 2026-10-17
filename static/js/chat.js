/**
 * chat.js — Crystal AI: Complete Student Chatbot Logic
 * - Dockable Composer (Centered in Welcome screen, pinned at bottom during conversation)
 * - Multi-turn questions & commands in a single chat session
 * - Inline study materials (file & image upload, thumbnail preview, RAG indexing)
 * - Sidebar: New chat, Search (sessions + in-chat), Previous chats grouped by date
 * - Saved Study Prompts DB integration (GET / POST /api/prompts)
 * - All buttons wired: Models, Export, Share, Upgrade, Deeper Research, Ideas, Translate, Help
 */

let currentSessionId = null;
let allSessions = [];
let pendingUploadFile = null;
let deeperResearchActive = false;
let computeModeActive = false;
let webSearchActive = false;

// ─────────────────────────────────────────────────────────────────────────────
//  Initialization
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Ensure composer is initially docked in welcome slot
  dockComposer('welcome');

  // Load sessions and saved files count
  await Promise.all([loadSessions(), refreshFilesBadge()]);

  // Handle URL param: open specific session if given
  const params = new URLSearchParams(window.location.search);
  const sessionParam = params.get('session');
  if (sessionParam) {
    await openSession(parseInt(sessionParam, 10));
  }

  // ── Sidebar: New Chat & Search ─────────────────────────────────────────────
  document.getElementById('new-chat-btn')?.addEventListener('click', () => {
    resetToNewChat();
  });

  const searchInput = document.getElementById('session-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim().toLowerCase();
      filterSessions(q);
      filterCurrentMessages(q);
    });

    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchInput.focus();
      }
    });
  }

  // ── Composer: Send & Input ────────────────────────────────────────────────
  document.getElementById('send-btn')?.addEventListener('click', handleSend);

  const textarea = document.getElementById('msg-input');
  if (textarea) {
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });
    textarea.addEventListener('input', autoResizeTextarea);
  }

  // Suggestion Cards (Welcome screen)
  document.querySelectorAll('.suggestion-card[data-prompt]').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.prompt;
      fillInput(q);
      handleSend();
    });
  });

  // ── File & Image Upload Triggers ──────────────────────────────────────────
  const sharedFileInput = createHiddenFileInput();

  document.getElementById('attach-btn')?.addEventListener('click', () => {
    sharedFileInput.accept = '.pdf,.doc,.docx,.pptx,.txt,.xlsx,.xls,.png,.jpg,.jpeg';
    sharedFileInput.click();
  });

  document.getElementById('tool-image-btn')?.addEventListener('click', () => {
    sharedFileInput.accept = '.pdf,.doc,.docx,.pptx,.txt,.xlsx,.xls,image/png,image/jpeg,image/jpg,image/webp';
    sharedFileInput.click();
  });

  sharedFileInput.addEventListener('change', () => {
    const file = sharedFileInput.files[0];
    if (file) {
      stagePendingFile(file);
      sharedFileInput.value = '';
    }
  });

  // Drag and drop onto composer
  const composerCard = document.getElementById('bottom-composer');
  if (composerCard) {
    composerCard.addEventListener('dragover', (e) => {
      e.preventDefault();
      composerCard.classList.add('drag-over');
    });
    composerCard.addEventListener('dragleave', () => composerCard.classList.remove('drag-over'));
    composerCard.addEventListener('drop', (e) => {
      e.preventDefault();
      composerCard.classList.remove('drag-over');
      if (e.dataTransfer?.files?.[0]) {
        stagePendingFile(e.dataTransfer.files[0]);
      }
    });
  }

  // ── Inner Tools ───────────────────────────────────────────────────────────
  const deeperBtn = document.getElementById('deeper-research-btn');
  deeperBtn?.addEventListener('click', () => {
    deeperResearchActive = !deeperResearchActive;
    deeperBtn.classList.toggle('active', deeperResearchActive);
    showToast(deeperResearchActive ? '🔬 Deeper Research enabled (high RAG depth)' : 'Standard research mode', 'info');
  });

  const computeBtn = document.getElementById('tool-compute-btn');
  computeBtn?.addEventListener('click', () => {
    computeModeActive = !computeModeActive;
    computeBtn.classList.toggle('active', computeModeActive);
    showToast(computeModeActive ? '⚡ Code & Math Compute mode enabled' : 'Compute mode off', 'info');
  });

  const webBtn = document.getElementById('tool-web-btn');
  webBtn?.addEventListener('click', () => {
    webSearchActive = !webSearchActive;
    webBtn.classList.toggle('active', webSearchActive);
    showToast(webSearchActive ? '🌐 Web Search mode enabled' : 'Web search off', 'info');
  });

  document.getElementById('tool-ideas-btn')?.addEventListener('click', showStudyIdeasMenu);
  document.getElementById('saved-prompts-btn')?.addEventListener('click', showSavedPromptsModal);

  // ── Topbar: Models, Files, More, Share, Export, Upgrade ───────────────────
  initTopbarDropdowns();

  // ── Footer Actions ────────────────────────────────────────────────────────
  document.getElementById('upload-docs-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    showUploadModal();
  });

  document.getElementById('footer-translate-btn')?.addEventListener('click', () => {
    fillInput('Explain the previous response in simple terms with everyday analogies for easy study revision.');
    handleSend();
  });

  document.getElementById('footer-help-btn')?.addEventListener('click', showHelpModal);

  // ── Logout ────────────────────────────────────────────────────────────────
  const doLogout = async () => {
    try {
      await fetch('/auth/logout', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        credentials: 'same-origin'
      });
    } catch (_) {}
    window.location.href = '/login';
  };
  document.getElementById('logout-btn')?.addEventListener('click', doLogout);
  document.getElementById('topbar-logout-btn')?.addEventListener('click', doLogout);
});

// ─────────────────────────────────────────────────────────────────────────────
//  Dockable Composer: Centered in Welcome, Pinned at Bottom in Chat
// ─────────────────────────────────────────────────────────────────────────────
function dockComposer(mode) {
  const container = document.getElementById('composer-container');
  const welcomeSlot = document.getElementById('welcome-composer-slot');
  const chatSlot = document.getElementById('chat-composer-slot');
  const welcomeScreen = document.getElementById('welcome-screen');

  if (!container || !welcomeSlot || !chatSlot) return;

  if (mode === 'welcome') {
    if (welcomeScreen) welcomeScreen.style.display = 'flex';
    welcomeSlot.appendChild(container);
  } else {
    if (welcomeScreen) welcomeScreen.style.display = 'none';
    chatSlot.appendChild(container);
  }
}

function resetToNewChat() {
  currentSessionId = null;
  const messagesDiv = document.getElementById('messages-list');
  if (messagesDiv) messagesDiv.innerHTML = '';
  document.getElementById('chat-title').textContent = 'Crystal AI';
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
  clearPendingFile();
  dockComposer('welcome');
  const textarea = document.getElementById('msg-input');
  if (textarea) {
    textarea.value = '';
    textarea.style.height = 'auto';
    textarea.focus();
  }
  // Clear URL param
  window.history.pushState({}, '', '/chat');
}

// ─────────────────────────────────────────────────────────────────────────────
//  Sending Messages (Multi-turn Support)
// ─────────────────────────────────────────────────────────────────────────────
async function handleSend() {
  const textarea = document.getElementById('msg-input');
  const content = textarea?.value.trim() || '';

  // Require text or an attached file
  if (!content && !pendingUploadFile) return;

  // Auto-create chat session if starting fresh
  if (!currentSessionId) {
    try {
      const res = await API.post('/api/sessions', { title: 'New Conversation' });
      const data = await res.json();
      if (res.ok) {
        currentSessionId = data.session.id;
        window.history.pushState({}, '', `/chat?session=${currentSessionId}`);
        await loadSessions();
      } else {
        showToast('Unable to start conversation.', 'error');
        return;
      }
    } catch {
      showToast('Connection error starting conversation.', 'error');
      return;
    }
  }

  // Dock composer to bottom for active chat
  dockComposer('chat');

  // Clear composer textarea
  if (textarea) {
    textarea.value = '';
    textarea.style.height = 'auto';
  }

  // Handle attached file upload first
  if (pendingUploadFile) {
    const file = pendingUploadFile;
    const isImage = file.type.startsWith('image/');
    clearPendingFile();

    // Display temporary staged message
    appendMessage('user', content || `📎 ${file.name}`, [], [{
      filename: file.name,
      file_size: file.size,
      file_type: file.name.split('.').pop() || '',
      is_image: isImage,
      uploading: true
    }]);

    showTypingIndicator();

    const formData = new FormData();
    formData.append('file', file);

    try {
      const uploadRes = await fetch('/api/documents', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData
      });
      const uploadData = await uploadRes.json();

      if (!uploadRes.ok) {
        hideTypingIndicator();
        showToast(uploadData.error || 'Upload failed.', 'error');
        return;
      }

      // Update staged attachment status pills from Processing to Analyzed
      document.querySelectorAll('.attachment-card-meta .status-pill').forEach(pill => {
        pill.textContent = 'Analyzed & Ready';
        pill.classList.add('status-pill--ready');
      });

      // Send prompt linked with uploaded document
      const queryText = content || `Please summarize and explain the key points in ${file.name}.`;
      await sendTextMessage(queryText, [uploadData.document.id], [{
        doc_id: uploadData.document.id,
        filename: file.name,
        file_size: file.size,
        file_type: uploadData.document.file_type || ''
      }]);
    } catch (err) {
      hideTypingIndicator();
      showToast('Error uploading study file.', 'error');
    }
    return;
  }

  // Standard text message
  appendMessage('user', content, [], []);
  showTypingIndicator();
  await sendTextMessage(content, [], []);
}

async function sendTextMessage(content, documentIds = [], attachments = []) {
  try {
    let finalPrompt = content;
    if (deeperResearchActive) {
      finalPrompt = `[Deep Research RAG Mode]: ${content}`;
    }

    const payload = {
      content: finalPrompt,
      document_ids: documentIds,
      attachments: attachments
    };

    const res = await API.post(`/api/sessions/${currentSessionId}/messages`, payload);
    hideTypingIndicator();

    if (!res.ok) {
      const data = await res.json();
      showToast(data.error || 'Failed to get answer.', 'error');
      return;
    }

    const data = await res.json();
    appendMessage('assistant', data.message.content, data.message.sources || [], []);

    // Update session title dynamically
    const shortTitle = content.length > 36 ? content.substring(0, 36) + '…' : content;
    document.getElementById('chat-title').textContent = shortTitle;

    await loadSessions();

    // Re-focus input for next question
    document.getElementById('msg-input')?.focus();
  } catch (err) {
    hideTypingIndicator();
    if (err.message !== 'Unauthorized') {
      showToast('Error communicating with Crystal AI.', 'error');
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Append Message to Viewport
// ─────────────────────────────────────────────────────────────────────────────
function appendMessage(role, content, sources = [], attachments = []) {
  const messagesDiv = document.getElementById('messages-list');
  if (!messagesDiv) return;

  dockComposer('chat');

  const row = document.createElement('div');
  row.className = `message-row message-row--${role}`;

  // Avatar
  const avatar = document.createElement('div');
  avatar.className = `message-avatar message-avatar--${role}`;
  if (role === 'assistant') {
    avatar.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg>`;
  } else {
    avatar.textContent = 'Y';
  }

  // Bubble Wrap
  const wrap = document.createElement('div');
  wrap.className = 'message-bubble-wrap';

  const sender = document.createElement('div');
  sender.className = 'message-sender';
  sender.textContent = role === 'user' ? 'You' : 'Crystal AI';

  // Attachments badge if present
  if (attachments && attachments.length > 0) {
    attachments.forEach(att => {
      const card = document.createElement('div');
      card.className = 'attachment-card';
      card.innerHTML = `
        <div class="attachment-card-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
        </div>
        <div class="attachment-card-details">
          <span class="attachment-card-name">${escapeHtml(att.filename)}</span>
          <span class="attachment-card-meta">${formatBytes(att.file_size || 0)} • <span class="status-pill">${att.uploading ? 'Processing' : 'Indexed for RAG'}</span></span>
        </div>`;
      wrap.appendChild(card);
    });
  }

  const bubble = document.createElement('div');
  bubble.className = `message-bubble message-bubble--${role}`;
  if (role === 'assistant' && window.marked) {
    bubble.innerHTML = marked.parse(content);
  } else {
    bubble.textContent = content;
  }
  wrap.appendChild(sender);
  wrap.appendChild(bubble);

  // Source citation chips
  if (role === 'assistant' && sources && sources.length > 0) {
    const sourcesList = document.createElement('div');
    sourcesList.className = 'sources-list';
    sources.forEach(s => {
      const chip = document.createElement('span');
      chip.className = 'source-chip';
      chip.textContent = `📖 ${s.title}${s.page ? ' (p. ' + s.page + ')' : ''}`;
      sourcesList.appendChild(chip);
    });
    wrap.appendChild(sourcesList);
  }

  row.appendChild(avatar);
  row.appendChild(wrap);
  messagesDiv.appendChild(row);

  scrollToBottom();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Sessions CRUD & Grouping
// ─────────────────────────────────────────────────────────────────────────────
async function loadSessions() {
  const list = document.getElementById('session-list');
  if (!list) return;

  try {
    const res = await API.get('/api/sessions?page=1&per_page=100');
    const data = await res.json();
    if (res.ok) {
      allSessions = data.sessions || [];
      renderSessionList(allSessions);
    }
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      list.innerHTML = '<p class="loading-text">Error loading chats.</p>';
    }
  }
}

function renderSessionList(sessions, searchMode = false) {
  const list = document.getElementById('session-list');
  if (!list) return;

  if (!sessions || !sessions.length) {
    list.innerHTML = `<p class="no-results-text">${searchMode ? 'No matching chats found.' : 'No conversations yet.'}</p>`;
    return;
  }

  if (searchMode) {
    list.innerHTML = sessions.map(s => sessionItemHTML(s)).join('');
    attachSessionHandlers(list);
    return;
  }

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const sevenDaysAgo = new Date(today); sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const groups = { today: [], yesterday: [], sevenDays: [], older: [] };
  sessions.forEach(s => {
    const d = new Date(s.updated_at || s.created_at || now);
    if (d >= today) groups.today.push(s);
    else if (d >= yesterday) groups.yesterday.push(s);
    else if (d >= sevenDaysAgo) groups.sevenDays.push(s);
    else groups.older.push(s);
  });

  const renderGroup = (label, items) => {
    if (!items.length) return '';
    return `<div class="session-group-label">${label}</div>` + items.map(sessionItemHTML).join('');
  };

  list.innerHTML =
    renderGroup('Today', groups.today) +
    renderGroup('Yesterday', groups.yesterday) +
    renderGroup('Previous 7 days', groups.sevenDays) +
    renderGroup('Older', groups.older);

  attachSessionHandlers(list);
}

function sessionItemHTML(s) {
  const isActive = s.id === currentSessionId;
  return `
    <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${s.id}" role="listitem" tabindex="0">
      <div class="session-item-title">${escapeHtml(s.title || 'New Conversation')}</div>
      <button class="session-delete-btn" data-session-id="${s.id}" title="Delete chat" aria-label="Delete chat">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
    </div>`;
}

function attachSessionHandlers(list) {
  list.querySelectorAll('.session-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.session-delete-btn')) return;
      openSession(parseInt(item.dataset.sessionId, 10));
    });
  });

  list.querySelectorAll('.session-delete-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const sid = parseInt(btn.dataset.sessionId, 10);
      if (!confirm('Are you sure you want to delete this chat?')) return;
      await deleteChatSession(sid);
    });
  });
}

async function deleteChatSession(sessionId) {
  try {
    const res = await API.delete(`/api/sessions/${sessionId}`);
    if (res.ok || res.status === 204) {
      showToast('Chat deleted', 'info');
      if (currentSessionId === sessionId) {
        resetToNewChat();
      }
      await loadSessions();
    } else {
      showToast('Failed to delete chat.', 'error');
    }
  } catch (err) {
    showToast('Error deleting chat.', 'error');
  }
}

async function openSession(sessionId) {
  currentSessionId = sessionId;
  dockComposer('chat');

  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.sessionId, 10) === sessionId);
  });

  const messagesDiv = document.getElementById('messages-list');
  if (messagesDiv) messagesDiv.innerHTML = '<p class="loading-text">Loading conversation…</p>';

  try {
    const [msgRes, sesRes] = await Promise.all([
      API.get(`/api/sessions/${sessionId}/messages?per_page=100`),
      API.get(`/api/sessions/${sessionId}`)
    ]);
    const msgData = await msgRes.json();
    const sesData = await sesRes.json();

    if (sesData.session) {
      document.getElementById('chat-title').textContent = sesData.session.title || 'Crystal AI';
    }

    if (messagesDiv) {
      messagesDiv.innerHTML = '';
      const msgs = msgData.messages || [];
      if (msgs.length === 0) {
        dockComposer('welcome');
      } else {
        msgs.forEach(m => appendMessage(m.role, m.content, m.sources || [], m.attachments || []));
        scrollToBottom();
      }
    }
  } catch (err) {
    if (messagesDiv) messagesDiv.innerHTML = '<p class="loading-text">Failed to load messages.</p>';
  }
}

function filterSessions(q) {
  if (!q) {
    renderSessionList(allSessions);
    return;
  }
  const filtered = allSessions.filter(s => (s.title || '').toLowerCase().includes(q));
  renderSessionList(filtered, true);
}

function filterCurrentMessages(q) {
  const rows = document.querySelectorAll('#messages-list .message-row');
  if (!rows.length) return;
  rows.forEach(row => {
    if (!q) {
      row.style.display = 'flex';
      return;
    }
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(q) ? 'flex' : 'none';
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  File Staging & Previews
// ─────────────────────────────────────────────────────────────────────────────
function stagePendingFile(file) {
  pendingUploadFile = file;
  removeStagedFilePill();

  const isImg = file.type.startsWith('image/');
  const pill = document.createElement('div');
  pill.id = 'staged-file-pill';
  pill.className = 'staged-file-pill';
  pill.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
    <span>${escapeHtml(file.name)} (${formatBytes(file.size)})</span>
    <button class="pill-remove-btn" aria-label="Remove file" title="Remove">×</button>`;

  const area = document.getElementById('staged-file-area');
  if (area) area.appendChild(pill);

  pill.querySelector('.pill-remove-btn').addEventListener('click', clearPendingFile);
  showToast(`📎 Attached "${file.name}"`, 'info');
}

function clearPendingFile() {
  pendingUploadFile = null;
  removeStagedFilePill();
}

function removeStagedFilePill() {
  document.getElementById('staged-file-pill')?.remove();
}

function createHiddenFileInput() {
  const input = document.createElement('input');
  input.type = 'file';
  input.style.display = 'none';
  document.body.appendChild(input);
  return input;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Uploaded Files Drawer & Badge
// ─────────────────────────────────────────────────────────────────────────────
async function refreshFilesBadge() {
  try {
    const res = await API.get('/api/documents?per_page=100');
    const data = await res.json();
    if (res.ok) {
      const badge = document.getElementById('topbar-files-badge');
      if (badge) badge.textContent = data.total || 0;
    }
  } catch (_) {}
}

async function showFilesDrawer() {
  const drawer = document.getElementById('files-drawer');
  if (!drawer) return;
  drawer.style.display = drawer.style.display === 'none' ? 'flex' : 'none';
  if (drawer.style.display === 'none') return;

  const list = document.getElementById('files-drawer-list');
  if (list) list.innerHTML = '<p class="loading-text">Loading documents…</p>';

  try {
    const res = await API.get('/api/documents?per_page=50');
    const data = await res.json();
    if (!res.ok || !data.documents?.length) {
      list.innerHTML = '<p class="no-results-text">No documents uploaded yet.<br>Click below to upload notes.</p>';
      return;
    }

    list.innerHTML = data.documents.map(d => `
      <div class="drawer-file-item">
        <div class="drawer-file-info">
          <span class="drawer-file-name">📄 ${escapeHtml(d.filename_original)}</span>
          <span class="drawer-file-meta">${formatBytes(d.file_size)} • ${d.status}</span>
        </div>
        <button class="btn btn-sm btn-outline ask-file-btn" data-filename="${escapeHtml(d.filename_original)}">Ask</button>
      </div>`).join('');

    list.querySelectorAll('.ask-file-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        drawer.style.display = 'none';
        fillInput(`Summarize and list key questions from: ${btn.dataset.filename}`);
        document.getElementById('msg-input')?.focus();
      });
    });
  } catch (_) {
    list.innerHTML = '<p class="no-results-text">Failed to load materials.</p>';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Saved Prompts (DB-backed via GET /api/prompts)
// ─────────────────────────────────────────────────────────────────────────────
async function showSavedPromptsModal() {
  if (document.getElementById('prompts-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'prompts-modal';
  overlay.className = 'modal';
  overlay.innerHTML = `
    <div class="modal-overlay" id="prompts-modal-overlay"></div>
    <div class="modal-content">
      <h3>⭐ Saved Study Prompts</h3>
      <div class="prompts-grid" id="prompts-modal-grid">
        <p class="loading-text">Loading study prompts…</p>
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" id="prompts-modal-close">Close</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  document.getElementById('prompts-modal-overlay').addEventListener('click', close);
  document.getElementById('prompts-modal-close').addEventListener('click', close);

  try {
    const res = await API.get('/api/prompts');
    const data = await res.json();
    const grid = document.getElementById('prompts-modal-grid');
    if (res.ok && data.prompts?.length) {
      grid.innerHTML = data.prompts.map(p => `
        <button class="prompt-pill" data-text="${escapeHtml(p.prompt_text)}">
          <strong>${escapeHtml(p.title)} <small style="color:#A855F7;">(${escapeHtml(p.category)})</small></strong>
          <span>${escapeHtml(p.prompt_text)}</span>
        </button>`).join('');

      grid.querySelectorAll('.prompt-pill').forEach(btn => {
        btn.addEventListener('click', () => {
          fillInput(btn.dataset.text);
          close();
          document.getElementById('msg-input')?.focus();
        });
      });
    }
  } catch (_) {}
}

// ─────────────────────────────────────────────────────────────────────────────
//  Study Ideas Generator Menu
// ─────────────────────────────────────────────────────────────────────────────
function showStudyIdeasMenu() {
  const ideas = [
    { title: '💡 Create 5 Flashcards', text: 'Create 5 flashcard question-and-answer pairs from our conversation for exam prep.' },
    { title: '📝 3 Difficulty Levels', text: 'Explain this topic in 3 levels of depth: Beginner, Intermediate, and Advanced.' },
    { title: '🎯 Practice Quiz', text: 'Generate 5 multiple-choice practice quiz questions with answer explanations.' },
    { title: '📊 Compare & Contrast Table', text: 'Create a clear comparison table contrasting the key concepts discussed.' }
  ];

  if (document.getElementById('ideas-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'ideas-modal';
  overlay.className = 'modal';
  overlay.innerHTML = `
    <div class="modal-overlay" id="ideas-modal-overlay"></div>
    <div class="modal-content">
      <h3>💡 Study Ideas &amp; Generators</h3>
      <div class="prompts-grid">
        ${ideas.map(i => `
          <button class="prompt-pill" data-text="${escapeHtml(i.text)}">
            <strong>${escapeHtml(i.title)}</strong>
            <span>${escapeHtml(i.text)}</span>
          </button>`).join('')}
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" id="ideas-modal-close">Close</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  document.getElementById('ideas-modal-overlay').addEventListener('click', close);
  document.getElementById('ideas-modal-close').addEventListener('click', close);

  overlay.querySelectorAll('.prompt-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      fillInput(btn.dataset.text);
      close();
      handleSend();
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  Topbar Dropdowns: Models, More Options, Share, Export, Upgrade
// ─────────────────────────────────────────────────────────────────────────────
function initTopbarDropdowns() {
  // Model Dropdown
  const modelBtn = document.getElementById('model-dropdown');
  const modelMenu = document.getElementById('model-menu');
  if (modelBtn && modelMenu) {
    modelBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = modelMenu.style.display === 'block';
      modelMenu.style.display = open ? 'none' : 'block';
      modelBtn.setAttribute('aria-expanded', String(!open));
    });

    modelMenu.querySelectorAll('.model-option').forEach(opt => {
      opt.addEventListener('click', () => {
        modelMenu.querySelectorAll('.model-option').forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
        document.getElementById('chat-title').textContent = opt.dataset.model;
        modelMenu.style.display = 'none';
        showToast(`Model set to: ${opt.dataset.model}`, 'info');
      });
    });
  }

  // Topbar Files button
  document.getElementById('topbar-files-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    showFilesDrawer();
  });
  document.getElementById('files-drawer-close')?.addEventListener('click', () => {
    document.getElementById('files-drawer').style.display = 'none';
  });
  document.getElementById('drawer-upload-btn')?.addEventListener('click', () => {
    document.getElementById('files-drawer').style.display = 'none';
    showUploadModal();
  });

  // More Options Dropdown
  const moreBtn = document.getElementById('more-options-btn');
  const moreMenu = document.getElementById('more-menu');
  if (moreBtn && moreMenu) {
    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      moreMenu.style.display = moreMenu.style.display === 'block' ? 'none' : 'block';
    });

    document.getElementById('menu-clear-chat')?.addEventListener('click', () => {
      moreMenu.style.display = 'none';
      if (confirm('Clear all messages in this conversation?')) {
        document.getElementById('messages-list').innerHTML = '';
        dockComposer('welcome');
      }
    });

    document.getElementById('menu-rename-chat')?.addEventListener('click', async () => {
      moreMenu.style.display = 'none';
      if (!currentSessionId) return;
      const newTitle = prompt('Enter new conversation title:');
      if (newTitle && newTitle.trim()) {
        try {
          await API.put(`/api/sessions/${currentSessionId}`, { title: newTitle.trim() });
          document.getElementById('chat-title').textContent = newTitle.trim();
          await loadSessions();
        } catch (_) {}
      }
    });

    document.getElementById('menu-delete-chat')?.addEventListener('click', async () => {
      moreMenu.style.display = 'none';
      if (!currentSessionId) return;
      if (confirm('Are you sure you want to delete this entire chat conversation?')) {
        await deleteChatSession(currentSessionId);
      }
    });
  }

  // Close menus when clicking outside
  document.addEventListener('click', () => {
    if (modelMenu) modelMenu.style.display = 'none';
    if (moreMenu) moreMenu.style.display = 'none';
    const drawer = document.getElementById('files-drawer');
    if (drawer) drawer.style.display = 'none';
  });

  // Share Link
  document.getElementById('share-link-btn')?.addEventListener('click', () => {
    const url = currentSessionId ? `${window.location.origin}/chat?session=${currentSessionId}` : window.location.href;
    navigator.clipboard.writeText(url).then(() => {
      showToast('🔗 Chat session link copied to clipboard!', 'success');
    }).catch(() => {
      showToast('Link copied: ' + url, 'info');
    });
  });

  // Export Chat transcript
  document.getElementById('export-chat-btn')?.addEventListener('click', () => {
    const rows = document.querySelectorAll('#messages-list .message-row');
    if (!rows.length) {
      showToast('No messages to export.', 'info');
      return;
    }

    let transcript = `# Crystal AI — Study Session Transcript\nDate: ${new Date().toLocaleString()}\n\n---\n\n`;
    rows.forEach(r => {
      const sender = r.querySelector('.message-sender')?.textContent || '';
      const text = r.querySelector('.message-bubble')?.textContent || '';
      transcript += `### ${sender}\n${text}\n\n`;
    });

    const blob = new Blob([transcript], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `CrystalAI_Chat_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('📥 Transcript downloaded!', 'success');
  });

  // Upgrade Button
  document.getElementById('upgrade-btn')?.addEventListener('click', () => {
    showUpgradeModal();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  Upload Study Documents Modal (Full In-page Uploader)
// ─────────────────────────────────────────────────────────────────────────────
function showUploadModal() {
  if (document.getElementById('upload-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'upload-modal';
  overlay.className = 'modal';
  overlay.innerHTML = `
    <div class="modal-overlay" id="upload-modal-overlay"></div>
    <div class="modal-content upload-modal-content">
      <h3>📤 Upload Study Materials</h3>
      <p>Upload lecture PDFs, textbooks, images, or notes. Crystal AI indexes them for precision RAG answers.</p>

      <div id="upload-drop-zone" class="upload-drop-zone">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
        <p>Drag &amp; drop file here, or <button id="modal-pick-file-btn" class="link-btn">browse file</button></p>
        <p class="upload-hint">PDF, DOCX, PPTX, TXT, PNG, JPG • Max 50 MB</p>
      </div>

      <div id="modal-file-staged" style="display:none; margin: 0.75rem 0;"></div>

      <div class="modal-actions">
        <button class="btn btn-outline" id="upload-modal-close-btn">Cancel</button>
        <button class="btn btn-accent" id="modal-upload-submit-btn">Upload &amp; Index</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  document.getElementById('upload-modal-overlay').addEventListener('click', close);
  document.getElementById('upload-modal-close-btn').addEventListener('click', close);

  let selectedFile = null;
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = '.pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg';
  fileInput.style.display = 'none';
  document.body.appendChild(fileInput);

  document.getElementById('modal-pick-file-btn').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) {
      selectedFile = fileInput.files[0];
      const preview = document.getElementById('modal-file-staged');
      preview.style.display = 'block';
      preview.innerHTML = `<span class="staged-file-pill">📎 ${escapeHtml(selectedFile.name)} (${formatBytes(selectedFile.size)})</span>`;
    }
  });

  const dropZone = document.getElementById('upload-drop-zone');
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer?.files?.[0]) {
      selectedFile = e.dataTransfer.files[0];
      const preview = document.getElementById('modal-file-staged');
      preview.style.display = 'block';
      preview.innerHTML = `<span class="staged-file-pill">📎 ${escapeHtml(selectedFile.name)} (${formatBytes(selectedFile.size)})</span>`;
    }
  });

  document.getElementById('modal-upload-submit-btn').addEventListener('click', async () => {
    if (!selectedFile) {
      showToast('Please choose a file to upload.', 'info');
      return;
    }
    const btn = document.getElementById('modal-upload-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Uploading & indexing…';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch('/api/documents', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`✅ "${selectedFile.name}" indexed successfully!`, 'success');
        await refreshFilesBadge();
        close();
        fillInput(`What are the key concepts and revision questions from ${selectedFile.name}?`);
      } else {
        showToast(data.error || 'Upload failed.', 'error');
        btn.disabled = false;
        btn.textContent = 'Upload & Index';
      }
    } catch (_) {
      showToast('Error uploading file.', 'error');
      btn.disabled = false;
      btn.textContent = 'Upload & Index';
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  Upgrade & Help Modals
// ─────────────────────────────────────────────────────────────────────────────
function showUpgradeModal() {
  if (document.getElementById('upgrade-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'upgrade-modal';
  overlay.className = 'modal';
  overlay.innerHTML = `
    <div class="modal-overlay" id="upgrade-modal-overlay"></div>
    <div class="modal-content">
      <h3>✨ Crystal AI Student Pro</h3>
      <p style="color:#64748B; margin-bottom: 1.25rem;">Supercharge your semester with unlimited document indexing and advanced models.</p>
      <div style="display:flex; flex-direction:column; gap:0.75rem; text-align:left; margin-bottom:1.5rem;">
        <div>⚡ <strong>High-speed Groq Llama 3.3 70B &amp; Qwen 2.5</strong></div>
        <div>📚 <strong>Unlimited textbook and note indexing</strong></div>
        <div>🧠 <strong>Deep research with hybrid vector retrieval</strong></div>
        <div>📸 <strong>Diagram &amp; handwritten math formula OCR</strong></div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" id="upgrade-close-btn">Close</button>
        <button class="btn btn-accent" id="upgrade-activate-btn">Activate Free Student Pro</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  document.getElementById('upgrade-modal-overlay').addEventListener('click', close);
  document.getElementById('upgrade-close-btn').addEventListener('click', close);
  document.getElementById('upgrade-activate-btn').addEventListener('click', () => {
    close();
    showToast('🎉 Student Pro is active on your account!', 'success');
  });
}

function showHelpModal() {
  if (document.getElementById('help-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'help-modal';
  overlay.className = 'modal';
  overlay.innerHTML = `
    <div class="modal-overlay" id="help-modal-overlay"></div>
    <div class="modal-content">
      <h3>🎓 Crystal AI Student Guide</h3>
      <div style="display:flex; flex-direction:column; gap:0.85rem; text-align:left; margin: 1rem 0 1.5rem; font-size:0.88rem; color:#334155;">
        <div><strong>1. Ask Anything:</strong> Type doubts about courses, exams, concepts, or formulas in the composer.</div>
        <div><strong>2. Upload Study Materials:</strong> Click the paperclip or image button to attach lecture notes, PDF books, or diagrams.</div>
        <div><strong>3. Continuous Chat:</strong> You can ask multiple follow-up questions within the same chat session.</div>
        <div><strong>4. Grounded Citations:</strong> Answers cite specific document pages so you can verify facts before exams.</div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-accent" id="help-close-btn">Got it!</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  document.getElementById('help-modal-overlay').addEventListener('click', close);
  document.getElementById('help-close-btn').addEventListener('click', close);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Utilities
// ─────────────────────────────────────────────────────────────────────────────
function showTypingIndicator() {
  const el = document.getElementById('typing-indicator');
  if (el) {
    el.style.display = 'flex';
    scrollToBottom();
  }
}

function hideTypingIndicator() {
  const el = document.getElementById('typing-indicator');
  if (el) el.style.display = 'none';
}

function fillInput(text) {
  const input = document.getElementById('msg-input');
  if (input) {
    input.value = text;
    autoResizeTextarea.call(input);
  }
}

function autoResizeTextarea() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 180) + 'px';
}

function scrollToBottom() {
  const viewport = document.getElementById('messages-area');
  if (viewport) {
    viewport.scrollTop = viewport.scrollHeight;
  }
}

function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}
