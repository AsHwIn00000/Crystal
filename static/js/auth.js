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
      const passwordInput = document.getElementById('password');
      const emailInput = document.getElementById('email');
      passwordInput?.classList.remove('input-error');
      emailInput?.classList.remove('input-error');

      try {
        const res = await API.post('/auth/login', { email, password, remember_me: rememberMe });
        const data = await res.json();
        if (res.ok) {
          window.location.href = '/chat';
        } else {
          const errMsg = data.error || 'Invalid email or password.';
          passwordInput?.classList.add('input-error');
          setError('password-error', '⚠️ ' + errMsg);
          setError('login-error', '⚠️ Incorrect credentials. Please check your email and password, or use "Forgot password?".');
        }
      } catch (err) {
        if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
          setError('login-error', '⚠️ Connection error. Please try again.');
        }
      } finally {
        btn.disabled = false;
        btn.textContent = 'Sign In';
      }
    });

    // ── Show / Hide Password Toggle ─────────────────────────────────
    const togglePassBtn = document.getElementById('toggle-password-btn');
    const passInput = document.getElementById('password');
    if (togglePassBtn && passInput) {
      togglePassBtn.addEventListener('click', () => {
        const isPassword = passInput.type === 'password';
        passInput.type = isPassword ? 'text' : 'password';
        togglePassBtn.innerHTML = isPassword
          ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`
          : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
      });
    }

    // ── Forgot Password Modal Logic ─────────────────────────────────
    const forgotLink = document.getElementById('forgot-password-link');
    const forgotModal = document.getElementById('forgot-modal');
    const closeForgotModal = document.getElementById('close-forgot-modal');
    const submitForgotEmail = document.getElementById('submit-forgot-email');
    const submitResetPassword = document.getElementById('submit-reset-password');
    let resetToken = null;

    if (forgotLink && forgotModal) {
      forgotLink.addEventListener('click', (e) => {
        e.preventDefault();
        forgotModal.style.display = 'flex';
        document.getElementById('forgot-step-1').style.display = 'block';
        document.getElementById('forgot-step-2').style.display = 'none';
        document.getElementById('forgot-email-error').textContent = '';
      });

      closeForgotModal?.addEventListener('click', () => {
        forgotModal.style.display = 'none';
      });

      submitForgotEmail?.addEventListener('click', async () => {
        const email = document.getElementById('forgot-email')?.value.trim();
        const errEl = document.getElementById('forgot-email-error');
        if (!email) {
          errEl.textContent = 'Please enter your email.';
          return;
        }
        submitForgotEmail.disabled = true;
        submitForgotEmail.textContent = 'Verifying...';

        try {
          const res = await API.post('/auth/forgot-password', { email });
          const data = await res.json();
          if (res.ok && data.reset_token) {
            resetToken = data.reset_token;
            document.getElementById('forgot-step-1').style.display = 'none';
            document.getElementById('forgot-step-2').style.display = 'block';
          } else {
            errEl.textContent = data.error || 'Unable to process request.';
          }
        } catch (_) {
          errEl.textContent = 'Connection error. Please try again.';
        } finally {
          submitForgotEmail.disabled = false;
          submitForgotEmail.textContent = 'Continue';
        }
      });

      submitResetPassword?.addEventListener('click', async () => {
        const newPassword = document.getElementById('reset-new-password')?.value;
        const confirmPassword = document.getElementById('reset-confirm-password')?.value;
        const errEl = document.getElementById('reset-error');
        errEl.textContent = '';

        if (!newPassword || newPassword.length < 8) {
          errEl.textContent = 'Password must be at least 8 characters with uppercase, digit, and symbol.';
          return;
        }
        if (newPassword !== confirmPassword) {
          errEl.textContent = 'Passwords do not match.';
          return;
        }

        submitResetPassword.disabled = true;
        submitResetPassword.textContent = 'Saving...';

        try {
          const res = await API.post('/auth/reset-password', {
            token: resetToken,
            new_password: newPassword,
            confirm_new_password: confirmPassword
          });
          const data = await res.json();
          if (res.ok) {
            alert(data.message || 'Password reset successfully! Please sign in.');
            forgotModal.style.display = 'none';
            document.getElementById('password').value = '';
          } else {
            errEl.textContent = data.error || 'Failed to reset password.';
          }
        } catch (_) {
          errEl.textContent = 'Connection error. Please try again.';
        } finally {
          submitResetPassword.disabled = false;
          submitResetPassword.textContent = 'Save New Password';
        }
      });
    }
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
