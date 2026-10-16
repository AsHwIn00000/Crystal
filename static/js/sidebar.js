/**
 * sidebar.js — Sidebar active state, collapse/expand, session search, mobile drawer, logout.
 */
document.addEventListener('DOMContentLoaded', () => {

  // ── Active state ───────────────────────────────────────────────────────
  const current = window.location.pathname;
  document.querySelectorAll('.sidebar-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href && (href === current || (href !== '/' && current.startsWith(href)))) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  });

  // ── Toggle collapse (desktop) / mobile drawer ──────────────────────────
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');

  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        // Mobile: toggle drawer open/close
        sidebar.classList.toggle('mobile-open');
        document.body.classList.toggle('sidebar-open', sidebar.classList.contains('mobile-open'));
      } else {
        // Desktop: collapse/expand
        sidebar.classList.toggle('collapsed');
        document.body.classList.toggle('sidebar-collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        toggle.setAttribute('aria-expanded', String(!isCollapsed));
      }
    });
  }

  // ── Mobile overlay: click outside sidebar to close ─────────────────────
  document.addEventListener('click', (e) => {
    if (!sidebar) return;
    if (window.innerWidth > 768) return;
    if (!sidebar.classList.contains('mobile-open')) return;
    // Close if click is outside the sidebar
    if (!sidebar.contains(e.target) && e.target !== toggle) {
      sidebar.classList.remove('mobile-open');
      document.body.classList.remove('sidebar-open');
    }
  });

  // ── Session search filtering ───────────────────────────────────────────
  const searchInput = document.getElementById('session-search');
  const sessionList = document.getElementById('session-list');

  if (searchInput && sessionList) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.trim().toLowerCase();
      const items = sessionList.querySelectorAll('.session-item');
      const groupLabels = sessionList.querySelectorAll('.session-group-label');

      // Remove any previous no-results message
      const prev = sessionList.querySelector('.no-results-text');
      if (prev) prev.remove();

      let visibleCount = 0;

      items.forEach(item => {
        const titleEl = item.querySelector('.session-item-title');
        const title = titleEl ? titleEl.textContent.toLowerCase() : '';
        const matches = !query || title.includes(query);
        item.style.display = matches ? '' : 'none';
        if (matches) visibleCount++;
      });

      // Hide group labels when their following items are all hidden
      groupLabels.forEach(label => {
        let nextSibling = label.nextElementSibling;
        let groupHasVisible = false;
        while (nextSibling && !nextSibling.classList.contains('session-group-label')) {
          if (nextSibling.classList.contains('session-item') && nextSibling.style.display !== 'none') {
            groupHasVisible = true;
            break;
          }
          nextSibling = nextSibling.nextElementSibling;
        }
        label.style.display = groupHasVisible ? '' : 'none';
      });

      // Show no-results message if nothing matches
      if (query && visibleCount === 0) {
        const msg = document.createElement('p');
        msg.className = 'no-results-text';
        msg.textContent = 'No results';
        sessionList.appendChild(msg);
      }
    });
  }

  // ── Logout ─────────────────────────────────────────────────────────────
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        await fetch('/auth/logout', {
          method: 'POST',
          headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' },
          credentials: 'same-origin'
        });
      } catch (_) { /* ignore network errors, still redirect */ }
      window.location.href = '/login';
    });
  }

});
