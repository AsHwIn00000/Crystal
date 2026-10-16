/**
 * profile.js — Profile settings, password change, account deletion.
 */
document.addEventListener('DOMContentLoaded', () => {
  // Profile form
  document.getElementById('profile-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const displayName = document.getElementById('display-name').value.trim();
    const msg = document.getElementById('profile-msg');
    const err = document.getElementById('display-name-error');
    if (msg) msg.textContent = '';
    if (err) err.textContent = '';

    if (!displayName) { if (err) err.textContent = 'Display name is required.'; return; }

    try {
      const res = await API.put('/auth/profile', { display_name: displayName });
      const data = await res.json();
      if (res.ok) {
        if (msg) msg.textContent = 'Profile updated successfully.';
        showToast('Profile updated.', 'success');
      } else {
        if (err) err.textContent = data.error || 'Update failed.';
      }
    } catch (ex) {
      if (ex.message !== 'Unauthorized' && ex.message !== 'Forbidden') {
        if (err) err.textContent = 'Connection error.';
      }
    }
  });

  // Password form
  document.getElementById('password-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const cur = document.getElementById('current-password').value;
    const nw = document.getElementById('new-password').value;
    const conf = document.getElementById('confirm-new-password').value;
    const msg = document.getElementById('password-msg');
    const errEl = document.getElementById('password-err');
    if (msg) msg.textContent = '';
    if (errEl) errEl.textContent = '';

    if (nw !== conf) { if (errEl) errEl.textContent = 'New passwords do not match.'; return; }

    try {
      const res = await API.put('/auth/password', {
        current_password: cur, new_password: nw, confirm_new_password: conf
      });
      const data = await res.json();
      if (res.ok) {
        if (msg) msg.textContent = 'Password updated.';
        document.getElementById('password-form').reset();
        showToast('Password updated.', 'success');
      } else {
        if (errEl) errEl.textContent = data.error || 'Update failed.';
      }
    } catch (ex) {
      if (ex.message !== 'Unauthorized' && ex.message !== 'Forbidden') {
        if (errEl) errEl.textContent = 'Connection error.';
      }
    }
  });

  // Delete account modal
  document.getElementById('delete-account-btn')?.addEventListener('click', () => {
    document.getElementById('delete-modal').style.display = 'flex';
    document.getElementById('delete-password').focus();
  });

  document.getElementById('cancel-delete-btn')?.addEventListener('click', () => {
    document.getElementById('delete-modal').style.display = 'none';
    document.getElementById('delete-password').value = '';
    document.getElementById('delete-pw-error').textContent = '';
  });

  document.getElementById('delete-modal-overlay')?.addEventListener('click', () => {
    document.getElementById('delete-modal').style.display = 'none';
  });

  document.getElementById('confirm-delete-btn')?.addEventListener('click', async () => {
    const password = document.getElementById('delete-password').value;
    const errEl = document.getElementById('delete-pw-error');
    if (errEl) errEl.textContent = '';
    if (!password) { if (errEl) errEl.textContent = 'Password is required.'; return; }

    try {
      const res = await API.delete('/auth/account', { password });
      if (res.status === 204 || res.ok) {
        window.location.href = '/login';
      } else {
        const data = await res.json();
        if (errEl) errEl.textContent = data.error || 'Deletion failed.';
      }
    } catch (ex) {
      if (ex.message !== 'Unauthorized' && ex.message !== 'Forbidden') {
        if (errEl) errEl.textContent = 'Connection error.';
      }
    }
  });

  // Handle delete with body (API.delete doesn't support body, use direct request)
  const origDelete = API.delete.bind(API);
  API.delete = (url, body) => {
    if (body) return API.request('DELETE', url, body);
    return origDelete(url);
  };
});
