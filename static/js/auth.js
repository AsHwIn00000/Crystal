/**
 * auth.js — Login and registration form handling.
 */
document.addEventListener('DOMContentLoaded', () => {
  // ── Login ──────────────────────────────────────────────────────────
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(['email-error', 'password-error', 'login-error']);
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const rememberMe = document.getElementById('remember-me')?.checked || false;
      const btn = document.getElementById('login-btn');

      if (!email) { setError('email-error', 'Email is required.'); return; }
      if (!password) { setError('password-error', 'Password is required.'); return; }

      btn.disabled = true;
      btn.textContent = 'Signing in...';
      try {
        const res = await API.post('/auth/login', { email, password, remember_me: rememberMe });
        const data = await res.json();
        if (res.ok) {
          window.location.href = '/chat';
        } else {
          setError('login-error', data.error || 'Login failed.');
        }
      } catch (err) {
        if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
          setError('login-error', 'Connection error. Please try again.');
        }
      } finally {
        btn.disabled = false;
        btn.textContent = 'Sign In';
      }
    });
  }

  // ── Register ───────────────────────────────────────────────────────
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
      passwordInput.addEventListener('input', () => {
        updateStrengthMeter(passwordInput.value);
      });
    }

    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(['email-error', 'password-error', 'confirm-error', 'display-name-error', 'register-error']);

      const displayName = document.getElementById('display-name')?.value.trim() || '';
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const confirm = document.getElementById('confirm-password').value;
      const btn = document.getElementById('register-btn');

      let valid = true;
      if (!email) { setError('email-error', 'Email is required.'); valid = false; }
      if (!password) { setError('password-error', 'Password is required.'); valid = false; }
      else if (password.length < 8) { setError('password-error', 'Password must be at least 8 characters.'); valid = false; }
      if (password !== confirm) { setError('confirm-error', 'Passwords do not match.'); valid = false; }
      if (!valid) return;

      btn.disabled = true;
      btn.textContent = 'Creating account...';
      try {
        const res = await API.post('/auth/register', {
          email, password, confirm_password: confirm, display_name: displayName
        });
        const data = await res.json();
        if (res.ok) {
          window.location.href = '/chat';
        } else {
          setError('register-error', data.error || 'Registration failed.');
        }
      } catch (err) {
        if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
          setError('register-error', 'Connection error. Please try again.');
        }
      } finally {
        btn.disabled = false;
        btn.textContent = 'Create Account';
      }
    });
  }
});

function setError(id, msg) {
  const el = document.getElementById(id);
  if (el) el.textContent = msg;
}

function clearErrors(ids) {
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = ''; });
}

function updateStrengthMeter(password) {
  const bar = document.getElementById('strength-bar');
  if (!bar) return;
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  bar.className = 'strength-bar';
  if (score <= 1) bar.classList.add('weak');
  else if (score <= 2) bar.classList.add('medium');
  else bar.classList.add('strong');
}
