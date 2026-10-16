# Implementation Plan — Crystal AI Nebula Dark Glass UI Redesign

> Artifact root: `d:\College\SEMESTER_3\AI\CrystalAI\.agents\tasks\redesign-nebula\`  
> Per-feature detail lives in `features/FEAT-001.json` through `FEAT-004.json`.  
> `context.json` has full project context — read it before each feature.

## Execution order

FEAT-001 → FEAT-002 → FEAT-003 → FEAT-004

Each feature must leave the app runnable (`python run.py` starts without error) before the next begins.

---

## FEAT-001 — Core CSS Design System + base.html

**Goal:** Replace the light-purple CSS variables with dark glass Nebula variables. Establish the foundation every other feature builds on.

**Files to modify:**
- `static/css/main.css` — complete rewrite
- `templates/base.html` — add marked.js CDN, confirm Inter font, keep CSRF meta tag, remove any favicon links

**What to do:**

- [ ] 1. Rewrite `static/css/main.css` — `:root` block  
      Replace every existing variable with the Nebula dark glass token set:
      ```css
      :root {
        --bg-base: #0D0D1A;
        --bg-sidebar: #13131F;
        --bg-card: rgba(255,255,255,0.05);
        --bg-card-hover: rgba(255,255,255,0.08);
        --bg-input: rgba(255,255,255,0.07);
        --bg-message-user: #7C3AED;
        --bg-message-ai: rgba(255,255,255,0.06);
        --glass-border: 1px solid rgba(255,255,255,0.1);
        --glass-blur: blur(12px);
        --glass-shadow: 0 8px 32px rgba(0,0,0,0.4);
        --violet: #7C3AED;
        --violet-hover: #6D28D9;
        --violet-glow: rgba(124,58,237,0.3);
        --violet-light: #A78BFA;
        --violet-pale: rgba(124,58,237,0.15);
        --text-primary: #F9FAFB;
        --text-secondary: #9CA3AF;
        --text-muted: #6B7280;
        --border: rgba(255,255,255,0.08);
        --border-active: rgba(124,58,237,0.6);
        --success: #10B981;
        --error: #EF4444;
        --warning: #F59E0B;
        --radius-sm: 8px;  --radius-md: 12px;  --radius-lg: 16px;  --radius-xl: 24px;
        --sidebar-width: 260px;
        --font: 'Inter', system-ui, sans-serif;
        /* backward-compat aliases */
        --font-sans: var(--font);
        --bg-page: var(--bg-base);
        --bg-hover: var(--bg-card-hover);
        --violet-subtle: var(--violet-pale);
        --border-mid: var(--border);
      }
      ```
      Files: `static/css/main.css`  
      Verify: `python run.py` starts; open http://localhost:8080/login — body background is dark (#0D0D1A).

- [ ] 2. Rewrite body/html base, layout rules  
      `body`: `background: var(--bg-base); color: var(--text-primary); font-family: var(--font)`.  
      Layout: `body.has-sidebar .main-content { margin-left: var(--sidebar-width); padding: 2rem; }`.  
      Add `body.chat-page .main-content { margin-left: 0; padding: 0; }` — chat page uses its own `.app-shell`.  
      Files: `static/css/main.css`  
      Verify: Same as above.

- [ ] 3. Rewrite all component styles in dark glass  
      Buttons (`.btn-primary`, `.btn-outline`, `.btn-danger`, `.btn-ghost`), forms (`.form-input`, `.form-label`, `.form-error`), badges (`.badge--*`), cards (`.card`), tables (`.data-table`), toasts (`.toast--*`), modal (`.modal-content`), page-header, pagination, flash messages, error container, scrollbar.  
      Files: `static/css/main.css`  
      Verify: `python -m pytest tests/ -v` — all tests pass (backend unaffected).

- [ ] 4. Add profile-card and upload-zone styles to main.css  
      ```css
      .profile-card { background: var(--bg-card); border: var(--glass-border); border-radius: var(--radius-md); padding: 1.75rem; margin-bottom: 1.5rem; backdrop-filter: var(--glass-blur); }
      .profile-sections { max-width: 640px; }
      .profile-card--danger { border-color: rgba(239,68,68,0.25); }
      .upload-zone { background: var(--bg-card); border: 2px dashed var(--border); border-radius: var(--radius-lg); padding: 3rem 2rem; text-align: center; cursor: pointer; transition: border-color 0.15s, background 0.15s; }
      .upload-zone.dragover { border-color: var(--violet); background: var(--violet-pale); }
      .upload-icon { color: var(--text-muted); width: 40px; height: 40px; margin: 0 auto 1rem; display: block; }
      .upload-text { color: var(--text-secondary); font-size: 0.95rem; }
      .upload-link { color: var(--violet-light); cursor: pointer; text-decoration: underline; }
      .upload-hint { color: var(--text-muted); font-size: 0.8rem; margin-top: 0.4rem; }
      .upload-progress { background: var(--border); border-radius: 99px; height: 6px; margin-top: 1rem; overflow: hidden; }
      .progress-bar { height: 100%; background: var(--violet); border-radius: 99px; transition: width 0.3s; }
      .docs-table-wrap { background: var(--bg-card); border: var(--glass-border); border-radius: var(--radius-md); overflow: hidden; margin-top: 1.5rem; }
      .error-visual { width: 64px; height: 64px; margin: 0 auto 1.5rem; color: var(--text-muted); display: flex; align-items: center; justify-content: center; }
      .error-visual svg { width: 100%; height: 100%; }
      ```
      Files: `static/css/main.css`  
      Verify: page loads without CSS errors in browser console.

- [ ] 5. Update `templates/base.html`  
      (a) Keep `<meta name="csrf-token" content="{{ csrf_token() }}">`.  
      (b) Keep Inter Google Fonts preconnect and load link (already present).  
      (c) Add before `</head>`: `<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>`.  
      (d) Add `<meta name="theme-color" content="#0D0D1A">`.  
      (e) Confirm no favicon `<link>` tags exist (they don't currently — just confirm).  
      Files: `templates/base.html`  
      Verify: `window.marked` is defined in browser console on any page.

---

## FEAT-002 — Sidebar + Chat Page

**Goal:** Rebuild the sidebar partial and chat page with Nebula structure and CSS. Depends on FEAT-001 CSS variables.

**Files to modify:**
- `templates/partials/sidebar.html` — complete rewrite
- `templates/student/chat.html` — complete rewrite
- `static/css/sidebar.css` — complete rewrite
- `static/css/chat.css` — complete rewrite
- `static/js/sidebar.js` — add search filtering, mobile drawer

**What to do:**

- [ ] 6. Rewrite `templates/partials/sidebar.html`  
      New structure (keeping all Jinja2 expressions and critical IDs unchanged):
      ```html
      <aside id="sidebar" class="sidebar" role="navigation" aria-label="Main navigation">
        <!-- Brand -->
        <a href="{{ url_for('pages.dashboard') }}" class="sidebar-brand">
          <div class="brand-icon">C</div>
          <span class="brand-name">Crystal AI</span>
        </a>
        <!-- New Chat button -->
        <button id="new-chat-btn" class="new-chat-btn">
          <!-- plus SVG 16x16 --> New Chat
        </button>
        <!-- Session search -->
        <div class="sidebar-search">
          <span class="search-icon"><!-- search SVG 14x14 --></span>
          <label for="session-search" class="sr-only">Search conversations</label>
          <input type="search" id="session-search" placeholder="Search chats…" autocomplete="off">
        </div>
        <!-- Session list (populated by chat.js) -->
        <div class="sidebar-sessions" id="session-list" role="list">
          <p class="loading-text">Loading…</p>
        </div>
        <!-- Nav links -->
        <nav class="sidebar-nav">
          <a href="{{ url_for('pages.dashboard') }}" class="sidebar-link">
            <span class="nav-icon"><!-- grid SVG --></span>
            <span class="nav-label">Dashboard</span>
          </a>
          <a href="{{ url_for('pages.chat') }}" class="sidebar-link">
            <span class="nav-icon"><!-- chat-bubble SVG --></span>
            <span class="nav-label">Chat</span>
          </a>
          <a href="{{ url_for('pages.history') }}" class="sidebar-link">
            <span class="nav-icon"><!-- clock SVG --></span>
            <span class="nav-label">History</span>
          </a>
          <a href="{{ url_for('pages.documents') }}" class="sidebar-link">
            <span class="nav-icon"><!-- file SVG --></span>
            <span class="nav-label">Documents</span>
          </a>
          <a href="{{ url_for('pages.profile') }}" class="sidebar-link">
            <span class="nav-icon"><!-- user SVG --></span>
            <span class="nav-label">Profile</span>
          </a>
          {% if current_user.is_authenticated and current_user.role.value == 'admin' %}
          <a href="{{ url_for('admin.admin_dashboard') }}" class="sidebar-link sidebar-link--admin">
            <span class="nav-icon"><!-- shield SVG --></span>
            <span class="nav-label">Admin</span>
          </a>
          {% endif %}
        </nav>
        <!-- Footer -->
        <div class="sidebar-footer">
          <div class="user-avatar">{{ (current_user.display_name or current_user.email or 'U')[0].upper() }}</div>
          <div class="user-meta">
            <span class="user-name">{{ current_user.display_name or current_user.email }}</span>
            <span class="user-email">{{ current_user.email }}</span>
          </div>
          <button id="logout-btn" class="btn-logout" aria-label="Log out"><!-- logout SVG --></button>
        </div>
      </aside>
      ```
      All inline SVGs use `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` with appropriate path data. See SVG reference below.  
      Files: `templates/partials/sidebar.html`  
      Verify: http://localhost:8080/dashboard — sidebar renders with logo, nav icons, search input, footer.

      **SVG path data reference:**
      - Plus: `<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>`
      - Search: `<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>`
      - Chat bubble: `<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>`
      - Grid: `<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>`
      - Clock: `<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>`
      - File: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>`
      - User: `<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>`
      - Logout arrow: `<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>`
      - Shield (admin): `<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>`

- [ ] 7. Rewrite `static/css/sidebar.css`  
      Full dark glass sidebar CSS as described in FEAT-002.json step 3. Key measurements: width 260px collapsed 60px, bg #13131F, border-right rgba(255,255,255,0.06), session items with glass hover, nav links muted → active violet, mobile drawer at 768px.  
      Files: `static/css/sidebar.css`  
      Verify: Sidebar renders correctly on http://localhost:8080/dashboard.

- [ ] 8. Rewrite `templates/student/chat.html`  
      New structure uses `body_class = 'chat-page'` so `body.chat-page .main-content` has no padding/margin. The template wraps everything in `.app-shell` (includes sidebar partial + `.chat-workspace`). Key IDs to preserve/rename:
      - `id="session-list"` — unchanged (sidebar partial)
      - `id="new-chat-btn"` — unchanged (sidebar partial)
      - `id="sidebar-toggle"` — now in `.topbar-left` as a hamburger button
      - `id="chat-title"` — unchanged, in `.topbar-left`
      - `id="messages-area"` — unchanged, the scrollable viewport div
      - `id="welcome-screen"` — renamed from `welcome-message`
      - `id="messages-list"` — renamed from `chat-messages`
      - `id="typing-indicator"` — unchanged
      - `id="msg-input"` — renamed from `message-input`
      - `id="send-btn"` — unchanged
      - `.suggestion-card[data-prompt]` — renamed from `.suggestion-chip[data-question]`
      
      Suggestion cards include inline SVG icons (calendar, money-bill, check-circle, clock).  
      Typing indicator uses `.typing-row` class with `.dot` spans.  
      Composer uses `.composer-area > .composer-box > textarea#msg-input + .composer-actions`.  
      Files: `templates/student/chat.html`  
      Verify: http://localhost:8080/chat renders full-height dark layout with animated orb welcome screen.

- [ ] 9. Rewrite `static/css/chat.css`  
      Full dark glass chat CSS as described in FEAT-002.json step 5. Key: `.app-shell` full-height flex, `.messages-viewport::before` radial gradient, `.welcome-orb` animated conic-gradient, `.suggestion-card` glass cards, message bubbles dark, composer glass card with focus glow, markdown in AI bubbles.  
      Files: `static/css/chat.css`  
      Verify: Chat page visually matches Nebula reference — dark bg, violet orb, glass composer.

- [ ] 10. Update `static/js/sidebar.js`  
       Add session search filtering and mobile drawer behavior as described in FEAT-002.json step 6. Preserve existing active state and logout functionality.  
       Files: `static/js/sidebar.js`  
       Verify: Type in sidebar search → items filter. On mobile (<768px), hamburger opens drawer.

---

## FEAT-003 — Auth, Landing, Documents, Dashboard, History, Profile, Admin, Error Pages

**Goal:** Apply dark glass theme to all remaining pages. Depends on FEAT-001 (CSS variables).

**Files to modify:**
- `static/css/auth.css` — complete rewrite
- `static/css/landing.css` — complete rewrite
- `static/css/dashboard.css` — complete rewrite
- `static/css/admin.css` — complete rewrite
- `templates/auth/login.html` — logo update only
- `templates/auth/register.html` — logo update only
- `templates/index.html` — logo orb + SVG feature icons
- `templates/student/documents.html` — replace emoji upload icon with SVG
- `templates/errors/403.html`, `404.html`, `413.html`, `500.html`, `400.html` — replace emoji with SVG

**What to do:**

- [ ] 11. Rewrite `static/css/auth.css`  
       Dark glass auth card with centered radial violet glow behind it. Glass card, dark inputs (inherit from main.css), violet full-width pill button, dark links. Password strength bar uses `--success/--warning/--error` colors. `.logo-circle` replaces `.logo-text`.  
       Files: `static/css/auth.css`  
       Verify: http://localhost:8080/login — dark background, glass card centered, violet C circle logo.

- [ ] 12. Update `templates/auth/login.html` and `templates/auth/register.html`  
       Replace `<div class="auth-logo"><span class="logo-text">Crystal</span></div>` with `<div class="auth-logo"><div class="logo-circle">C</div></div>`. No other changes.  
       Files: `templates/auth/login.html`, `templates/auth/register.html`  
       Verify: Login page shows violet circle logo.

- [ ] 13. Rewrite `static/css/landing.css`  
       Dark glass landing: body.landing bg-base, landing-header glass (rgba(19,19,31,0.8) + blur), hero with violet gradient accent text, chat preview card as glass card with dark bubbles, feature cards as glass cards, CTA inner as glass card, footer dark.  
       Files: `static/css/landing.css`  
       Verify: http://localhost:8080 (unauthenticated) — dark background, glass header, violet gradient title.

- [ ] 14. Update `templates/index.html`  
       (a) Add `.logo-orb` div inside `.landing-logo`: `<div class="logo-orb">C</div><span class="logo-text">Crystal AI</span>`.  
       (b) Replace letter placeholders in `.feature-icon-wrap` with inline SVGs (16px, stroke, currentColor):
       - D (Document Intelligence): file-text SVG
       - A (Cited Answers): check-square SVG  
       - P (Private): lock SVG
       - F (Lightning Fast): zap SVG
       (c) Add `.logo-orb` CSS to `landing.css`: `width: 32px; height: 32px; background: var(--violet); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; font-weight: 700; color: #fff; flex-shrink: 0;`  
       Files: `templates/index.html`, `static/css/landing.css`  
       Verify: Landing page shows violet logo orb and SVG feature icons.

- [ ] 15. Rewrite `static/css/dashboard.css`  
       Dark glass dashboard cards, suggestion chips, session rows. Also add: `.history-table-wrap { background: var(--bg-card); border: var(--glass-border); border-radius: var(--radius-md); overflow: hidden; }` and `.history-controls .form-input { margin-bottom: 1rem; }` for the history page.  
       Files: `static/css/dashboard.css`  
       Verify: http://localhost:8080/dashboard and http://localhost:8080/history — dark glass cards.

- [ ] 16. Rewrite `static/css/admin.css`  
       Dark glass stat cards, tabs, admin actions area.  
       Files: `static/css/admin.css`  
       Verify: http://localhost:8080/admin (as admin user) — dark stat cards, glass tabs.

- [ ] 17. Update `templates/student/documents.html`  
       Replace `<div class="upload-icon" aria-hidden="true">📁</div>` with:
       ```html
       <div class="upload-icon" aria-hidden="true">
         <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
           <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>
           <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
         </svg>
       </div>
       ```
       Add `{% block extra_css %}<link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">{% endblock %}` (it currently has no extra_css block).  
       Files: `templates/student/documents.html`  
       Verify: http://localhost:8080/documents — SVG upload icon, glass dashed upload zone.

- [ ] 18. Update error templates (403, 404, 413, 500, 400)  
       Replace emoji `.error-visual` content with inline SVG icons. Use stroke SVGs from Heroicons / Feather style:
       - 403: shield-off SVG
       - 404: search SVG  
       - 413: file-x SVG (file too large)
       - 500: alert-triangle SVG
       - 400: alert-circle SVG
       Example for 404:
       ```html
       <div class="error-visual" aria-hidden="true">
         <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
           <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
         </svg>
       </div>
       ```
       Files: `templates/errors/403.html`, `templates/errors/404.html`, `templates/errors/413.html`, `templates/errors/500.html`, `templates/errors/400.html`  
       Verify: Visit http://localhost:8080/nonexistent — dark error page with SVG icon, no emoji.

---

## FEAT-004 — JS Fixes (chat.js, sidebar.js, documents.js)

**Goal:** Fix chat.js bugs and add enhancements. Depends on FEAT-002 (new HTML IDs).

**Files to modify:**
- `static/js/chat.js` — complete rewrite

**What to do:**

- [ ] 19. Rewrite `static/js/chat.js`  
       Preserve all API contracts. Apply all fixes listed below. The new chat.js must:
       
       **ID changes** (must match new chat.html from FEAT-002):
       - `document.getElementById('message-input')` → `document.getElementById('msg-input')`
       - `document.getElementById('chat-messages')` → `document.getElementById('messages-list')`
       - `document.getElementById('welcome-message')` → `document.getElementById('welcome-screen')`
       - `.suggestion-chip[data-question]` → `.suggestion-card[data-prompt]`
       - `chip.dataset.question` → `chip.dataset.prompt`

       **Fix 1 — isSending guard:**
       ```js
       let isSending = false;
       async function handleSend() {
         if (isSending) return;
         isSending = true;
         const textarea = document.getElementById('msg-input');
         const savedContent = textarea?.value.trim();
         if (!savedContent || !currentSessionId) { isSending = false; return; }
         // ... rest of send logic ...
         try { ... } catch(err) {
           textarea.value = savedContent; // restore on error
           // show retry button
         } finally { isSending = false; }
       }
       ```

       **Fix 2 — marked.js for AI messages:**
       ```js
       // In appendMessage(), for assistant role:
       if (window.marked) {
         bubble.innerHTML = marked.parse(content);
       } else {
         bubble.textContent = content;
       }
       // For user role, always use textContent (XSS safety):
       bubble.textContent = content;
       ```
       Configure marked at DOMContentLoaded: `if (window.marked) { marked.setOptions({ breaks: true, gfm: true }); }`

       **Fix 3 — Smart auto-scroll:**
       ```js
       let autoScroll = true;
       // On DOMContentLoaded, after getting messages-area:
       document.getElementById('messages-area')?.addEventListener('scroll', () => {
         const area = document.getElementById('messages-area');
         if (!area) return;
         autoScroll = (area.scrollHeight - area.scrollTop - area.clientHeight) < 100;
       });
       function scrollToBottom() {
         const area = document.getElementById('messages-area');
         if (area && autoScroll) area.scrollTop = area.scrollHeight;
       }
       ```

       **Fix 4 — Throttled loadSessions:**
       ```js
       let lastSessionLoad = 0;
       function throttledLoadSessions() {
         const now = Date.now();
         if (now - lastSessionLoad < 2000) return Promise.resolve();
         lastSessionLoad = now;
         return loadSessions();
       }
       // Call throttledLoadSessions() after successful send instead of loadSessions()
       ```

       **Fix 5 — Suggestion cards (new selector + auto-create session):**
       ```js
       document.querySelectorAll('.suggestion-card[data-prompt]').forEach(card => {
         card.addEventListener('click', async () => {
           const q = card.dataset.prompt;
           if (!currentSessionId) {
             await createNewSession();
           }
           const textarea = document.getElementById('msg-input');
           if (textarea) { textarea.value = q; textarea.disabled = false; }
           await handleSend();
         });
       });
       ```

       **Fix 6 — Retry button on failed message:**
       After catch in handleSend (not Unauthorized/Forbidden), append a failed row:
       ```js
       appendFailedMessage(savedContent);
       ```
       ```js
       function appendFailedMessage(content) {
         const list = document.getElementById('messages-list');
         if (!list) return;
         const row = document.createElement('div');
         row.className = 'message-row message-row--error';
         row.innerHTML = `
           <div class="message-bubble-wrap">
             <div class="message-bubble message-bubble--error">
               Failed to send. <button class="retry-btn" aria-label="Retry sending message">Retry</button>
             </div>
           </div>`;
         row.querySelector('.retry-btn').addEventListener('click', () => {
           row.remove();
           const textarea = document.getElementById('msg-input');
           if (textarea) textarea.value = content;
           handleSend();
         });
         list.appendChild(row);
         scrollToBottom();
       }
       ```

       **Fix 7 — Session groups in renderSessionList:**
       ```js
       function groupSessions(sessions) {
         const now = new Date();
         const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
         const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7);
         return sessions.reduce((acc, s) => {
           const d = new Date(s.updated_at);
           if (d >= today) acc.today.push(s);
           else if (d >= weekAgo) acc.thisWeek.push(s);
           else acc.older.push(s);
           return acc;
         }, { today: [], thisWeek: [], older: [] });
       }
       ```
       In `renderSessionList()`, use `groupSessions()` and render group labels as:
       `<div class="session-group-label">Today</div>` before each non-empty group.

       **Fix 8 — Hide welcome screen on first message:**
       In `appendMessage()`, add: `document.getElementById('welcome-screen')?.remove();` (remove it from DOM on first real message so it doesn't interfere with flex layout).

       Files: `static/js/chat.js`  
       Verify: `python -m pytest tests/ -v` — all pass. Browser: suggestion cards work, AI responses render markdown, double-click send only sends once.

---

## Verification after all features

```
python -m pytest tests/ -v
python run.py
# Then manually verify in browser:
# http://localhost:8080          — dark landing
# http://localhost:8080/login    — dark glass auth
# http://localhost:8080/register — dark glass auth
# http://localhost:8080/dashboard — dark cards, sidebar
# http://localhost:8080/chat      — full Nebula chat
# http://localhost:8080/documents — glass upload zone
# http://localhost:8080/history   — glass table
# http://localhost:8080/profile   — glass cards
# http://localhost:8080/nonexistent — dark 404 with SVG
```

## Constraints reminder

- DO NOT change any Flask routes, Python files, or DB schema
- DO NOT add new Python dependencies  
- DO NOT expose API keys in templates
- DO NOT use emoji as icons — use inline SVG only
- Single font: Inter from Google Fonts (already in base.html)
- marked.js via CDN (added to base.html in FEAT-001)
- CSRF meta tag must remain in base.html
- Server runs on port 8080 (`python run.py`)
