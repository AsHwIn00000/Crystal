/**
 * chat.js — Chat page: sessions, messages, typing indicator, source citations.
 */
let currentSessionId = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadSessions();

  // URL param: open specific session
  const params = new URLSearchParams(window.location.search);
  const sessionParam = params.get('session');
  if (sessionParam) {
    openSession(parseInt(sessionParam, 10));
  }

  // New chat button
  document.getElementById('new-chat-btn')?.addEventListener('click', createNewSession);

  // Send button
  document.getElementById('send-btn')?.addEventListener('click', handleSend);

  // Textarea — Enter to send (Shift+Enter for newline), auto-resize, char count
  const textarea = document.getElementById('msg-input');
  if (textarea) {
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
      const count = document.getElementById('char-count');
      if (count) count.textContent = `${textarea.value.length}/4000`;
    });
  }

  // Suggestion cards
  document.querySelectorAll('.suggestion-card[data-prompt]').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.prompt;
      if (!currentSessionId) {
        createNewSession().then(() => {
          fillInput(q);
          handleSend();
        });
      } else {
        fillInput(q);
        handleSend();
      }
    });
  });
});

async function loadSessions() {
  const list = document.getElementById('session-list');
  if (!list) return;
  try {
    const res = await API.get('/api/sessions?page=1&per_page=30');
    const data = await res.json();
    if (!res.ok) { list.innerHTML = '<p class="loading-text">Failed to load.</p>'; return; }
    renderSessionList(data.sessions);
  } catch (err) {
    if (err.message !== 'Unauthorized') list.innerHTML = '<p class="loading-text">Error loading sessions.</p>';
  }
}

function renderSessionList(sessions) {
  const list = document.getElementById('session-list');
  if (!list) return;
  if (!sessions.length) {
    list.innerHTML = '<p class="loading-text">No conversations yet.</p>';
    return;
  }
  list.innerHTML = sessions.map(s => `
    <div class="session-item ${s.id === currentSessionId ? 'active' : ''}"
         data-session-id="${s.id}"
         role="listitem"
         tabindex="0"
         aria-label="Conversation: ${escapeHtml(s.title)}">
      <div class="session-item-title">${escapeHtml(s.title)}</div>
      <div class="session-item-meta">${s.message_count} msg · ${formatDate(s.updated_at)}</div>
    </div>
  `).join('');

  list.querySelectorAll('.session-item').forEach(item => {
    item.addEventListener('click', () => openSession(parseInt(item.dataset.sessionId, 10)));
    item.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') openSession(parseInt(item.dataset.sessionId, 10));
    });
  });
}

async function createNewSession() {
  try {
    const res = await API.post('/api/sessions', { title: 'New Conversation' });
    const data = await res.json();
    if (res.ok) {
      await openSession(data.session.id);
      await loadSessions();
    }
  } catch (err) {
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
      showToast('Could not create session.', 'error');
    }
  }
}

async function openSession(sessionId) {
  currentSessionId = sessionId;
  document.getElementById('welcome-screen')?.style && (document.getElementById('welcome-screen').style.display = 'none');
  document.getElementById('msg-input')?.removeAttribute('disabled');
  document.getElementById('send-btn')?.removeAttribute('disabled');

  // Update active state
  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.sessionId) === sessionId);
  });

  const messagesDiv = document.getElementById('messages-list');
  if (messagesDiv) messagesDiv.innerHTML = '<p class="loading-text">Loading...</p>';

  try {
    const res = await API.get(`/api/sessions/${sessionId}/messages?per_page=50`);
    const data = await res.json();
    if (!res.ok) { if (messagesDiv) messagesDiv.innerHTML = ''; return; }

    // Update title
    const sessionRes = await API.get(`/api/sessions/${sessionId}`);
    const sessionData = await sessionRes.json();
    if (sessionData.session) {
      document.getElementById('chat-title').textContent = sessionData.session.title;
    }

    if (messagesDiv) {
      messagesDiv.innerHTML = '';
      data.messages.forEach(msg => appendMessage(msg.role, msg.content, msg.sources || []));
      scrollToBottom();
    }
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      if (messagesDiv) messagesDiv.innerHTML = '';
    }
  }
}

async function handleSend() {
  if (!currentSessionId) {
    showToast('Please start or select a conversation first.', 'info');
    return;
  }
  const textarea = document.getElementById('msg-input');
  const content = textarea?.value.trim();
  if (!content) return;

  textarea.value = '';
  textarea.style.height = 'auto';
  const countEl = document.getElementById('char-count');
  if (countEl) countEl.textContent = '';

  appendMessage('user', content, []);
  showTypingIndicator();

  try {
    const res = await API.post(`/api/sessions/${currentSessionId}/messages`, { content });
    hideTypingIndicator();
    if (!res.ok) {
      const data = await res.json();
      showToast(data.error || 'Failed to send.', 'error');
      return;
    }
    const data = await res.json();
    appendMessage('assistant', data.message.content, data.message.sources || []);
    // Update session title in sidebar
    await loadSessions();
    document.getElementById('chat-title').textContent = data.message.content.length > 60
      ? content.substring(0, 60) + '…'
      : document.getElementById('chat-title').textContent;
  } catch (err) {
    hideTypingIndicator();
    if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
      showToast('Failed to send message. Please try again.', 'error');
    }
  }
}

function appendMessage(role, content, sources) {
  const messagesDiv = document.getElementById('messages-list');
  if (!messagesDiv) return;

  // Hide welcome screen once we have real messages
  const welcome = document.getElementById('welcome-screen');
  if (welcome) welcome.style.display = 'none';

  const row = document.createElement('div');
  row.className = `message-row message-row--${role}`;

  // Avatar
  const avatar = document.createElement('div');
  avatar.className = `message-avatar message-avatar--${role}`;
  avatar.textContent = role === 'user' ? 'Y' : 'AI';

  // Bubble wrap
  const wrap = document.createElement('div');
  wrap.className = 'message-bubble-wrap';

  const sender = document.createElement('div');
  sender.className = 'message-sender';
  sender.textContent = role === 'user' ? 'You' : 'Crystal';

  const bubble = document.createElement('div');
  bubble.className = `message-bubble message-bubble--${role}`;
  bubble.textContent = content;

  wrap.appendChild(sender);
  wrap.appendChild(bubble);

  if (role === 'assistant' && sources && sources.length > 0) {
    const sourcesList = document.createElement('div');
    sourcesList.className = 'sources-list';
    sources.forEach(s => {
      const chip = document.createElement('span');
      chip.className = 'source-chip';
      chip.textContent = `${s.title} p.${s.page}`;
      sourcesList.appendChild(chip);
    });
    wrap.appendChild(sourcesList);
  }

  row.appendChild(avatar);
  row.appendChild(wrap);
  messagesDiv.appendChild(row);
  scrollToBottom();
}

function fillInput(text) {
  const textarea = document.getElementById('msg-input');
  if (textarea) { textarea.value = text; textarea.focus(); }
}

function showTypingIndicator() {
  const indicator = document.getElementById('typing-indicator');
  if (indicator) indicator.style.display = 'flex';
  scrollToBottom();
}

function hideTypingIndicator() {
  const indicator = document.getElementById('typing-indicator');
  if (indicator) indicator.style.display = 'none';
}

function scrollToBottom() {
  const area = document.getElementById('messages-area');
  if (area) area.scrollTop = area.scrollHeight;
}

function formatDate(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text || ''));
  return div.innerHTML;
}

function startChatWith(text) {
  window.location.href = '/chat';
}
