/* ============================================================
   WUTT — AI Personal Stylist (Myanmar) — Frontend Logic
   Vanilla JS, no frameworks. Async/await, try/catch always.
   ============================================================ */

/* --------------------------------------------------------
   Hero Login Modal — Self-contained controller
   Runs inside DOMContentLoaded. Uses getElementById only.
   Does NOT depend on any other code in this file.
   -------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', function initHeroLoginModal() {
  var btn     = document.getElementById('navbarLoginBtn');
  var overlay = document.getElementById('heroLoginOverlay');
  var closeBtn = document.getElementById('heroLoginClose');
  var card    = document.getElementById('heroLoginCard');
  var form    = document.getElementById('heroLoginForm');

  if (!btn)     { console.warn('[WUTT] #navbarLoginBtn not found'); return; }
  if (!overlay) { console.warn('[WUTT] #heroLoginOverlay not found'); return; }

  function open() {
    console.log('WUTT hero login opened');
    overlay.classList.add('landing-modal-overlay--open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.body.classList.add('modal-open');
    // Focus first input
    var firstInput = overlay.querySelector('input');
    if (firstInput) setTimeout(function() { firstInput.focus(); }, 150);
  }

  function clearLoginForm() {
    var emailEl = document.getElementById('heroEmail');
    var passEl = document.getElementById('heroPassword');
    var errorEl = document.getElementById('heroFormError');
    var emailErr = document.getElementById('heroEmailError');
    var passErr = document.getElementById('heroPasswordError');
    if (emailEl) emailEl.value = '';
    if (passEl) passEl.value = '';
    if (errorEl) { errorEl.textContent = ''; errorEl.classList.add('u-hidden'); }
    if (emailErr) { emailErr.textContent = ''; emailErr.classList.add('u-hidden'); }
    if (passErr) { passErr.textContent = ''; passErr.classList.add('u-hidden'); }
    if (emailEl) emailEl.classList.remove('input__field--error');
    if (passEl) passEl.classList.remove('input__field--error');
  }

  function close() {
    clearLoginForm();
    overlay.classList.remove('landing-modal-overlay--open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    document.body.classList.remove('modal-open');
    btn.focus();
  }

  // Open
  btn.addEventListener('click', function(e) {
    e.preventDefault();
    open();
  });

  // Close button
  if (closeBtn) {
    closeBtn.addEventListener('click', function(e) {
      e.preventDefault();
      close();
    });
  }

  // Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && overlay.classList.contains('landing-modal-overlay--open')) {
      close();
    }
  });

  // Sign up link — pointerdown fires before blur, so no red-flash race
  var switchBtn = document.getElementById('heroSwitchToRegister');
  if (switchBtn) {
    switchBtn.addEventListener('pointerdown', function(e) {
      e.preventDefault();
      e.stopPropagation();
      clearLoginForm();
      close();
      var regOverlay = document.getElementById('registerModalOverlay');
      if (regOverlay) {
        regOverlay.classList.add('landing-modal-overlay--open');
        regOverlay.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        document.body.classList.add('modal-open');
        var firstInput = regOverlay.querySelector('input');
        if (firstInput) setTimeout(function() { firstInput.focus(); }, 150);
      }
    });
  }

  // Social buttons (placeholder — show toast, don't navigate)
  var googleBtn = document.getElementById('googleLoginBtn');
  var appleBtn  = document.getElementById('appleLoginBtn');
  if (googleBtn) googleBtn.addEventListener('click', function(e) { e.preventDefault(); showToast('Google sign-in coming soon'); });
  if (appleBtn)  appleBtn.addEventListener('click', function(e)  { e.preventDefault(); showToast('Apple sign-in coming soon'); });

  // Forgot password
  var forgotBtn = document.getElementById('heroForgotPassword');
  if (forgotBtn) {
    forgotBtn.addEventListener('click', function(e) {
      e.preventDefault();
      showToast('Password reset coming soon');
    });
  }

  // Form submission — wired to handleHeroLoginSubmit (defined later in this file)
  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      // Delegate to the API-connected handler if it exists
      if (typeof handleHeroLoginSubmit === 'function') {
        handleHeroLoginSubmit(e);
      } else {
        console.warn('[WUTT] handleHeroLoginSubmit not found');
      }
    });
  }
});

/* --------------------------------------------------------
   Auth Persistence — Restore session on page load
   TODO: replace localStorage with httpOnly cookie at deploy
   -------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', async function restoreSession() {
  var token = localStorage.getItem('wutt_token');
  if (!token) return;

  // Try validating the saved token against the backend
  try {
    var resp = await fetch(CONFIG.API_BASE + '/auth/me', {
      headers: { 'Authorization': 'Bearer ' + token },
      credentials: 'include',
    });
    if (resp.ok) {
      // Token is valid — skip landing, go to main app
      console.log('[WUTT] Session restored');
      showMainApp();
    } else {
      // Token expired or invalid — clear it
      localStorage.removeItem('wutt_token');
      localStorage.removeItem('wutt_user');
    }
  } catch (err) {
    // Network error — restore optimistically
    console.warn('[WUTT] Auth check failed (offline?), restoring session optimistically');
    showMainApp();
  }
});

/* --------------------------------------------------------
   Auth Helpers
   -------------------------------------------------------- */

/** Persist auth state after successful login/register */
function saveAuth(email, token) {
  localStorage.setItem('wutt_token', token);
  if (email) {
    localStorage.setItem('wutt_user', email);
  }
}

/** Log out — clear session and return to landing */
function handleLogout() {
  localStorage.removeItem('wutt_token');
  localStorage.removeItem('wutt_user');
  localStorage.removeItem('wutt_styles');
  window.location.reload();
}

/* --------------------------------------------------------
   Config
   -------------------------------------------------------- */
const CONFIG = {
  API_BASE: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : 'https://wutt-api.onrender.com',
};

/* --------------------------------------------------------
   DOM Cache
   -------------------------------------------------------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Navbar
const navbarToggle = $('#navbarToggle');
const navbarNav = $('#navbarNav');

// Modals — Login
const loginOverlay = $('#loginModalOverlay');
const loginModal = $('#loginModal');
const loginForm = $('#loginForm');
const loginFormError = $('#loginFormError');
const loginSubmitBtn = $('#loginSubmitBtn');
const loginPasswordToggle = $('#loginPasswordToggle');

// Modals — Register (uses landing-modal-overlay / login-card classes)
const registerOverlay = $('#registerModalOverlay');
const registerForm = $('#registerForm');
const registerFormError = $('#registerFormError');
const registerSubmitBtn = $('#registerSubmitBtn');
const registerPasswordToggle = $('#registerPasswordToggle');

// Toast
const toastContainer = $('#toastContainer');

// Hero login form (used by handleHeroLoginSubmit / validateHeroLoginForm)
const heroLoginForm = $('#heroLoginForm');
const heroFormError = $('#heroFormError');
const heroLoginSubmitBtn = $('#heroLoginSubmitBtn');
const heroPasswordToggle = $('#heroPasswordToggle');

/* --------------------------------------------------------
   Utilities
   -------------------------------------------------------- */

/** Toggle element visibility by class */
function toggleHidden(el, hide) {
  if (hide) {
    el.classList.add('u-hidden');
  } else {
    el.classList.remove('u-hidden');
  }
}

/** Show error message with role=alert (accessibility) */
function showFieldError(errorEl, message) {
  errorEl.textContent = message;
  errorEl.classList.remove('u-hidden');
}

/** Hide field error */
function hideFieldError(errorEl) {
  errorEl.textContent = '';
  errorEl.classList.add('u-hidden');
}

/** Set button loading state */
function setButtonLoading(btn, loading) {
  if (loading) {
    btn.classList.add('btn--loading');
    btn.setAttribute('aria-disabled', 'true');
  } else {
    btn.classList.remove('btn--loading');
    btn.removeAttribute('aria-disabled');
  }
}

/** Show a toast notification. Removes on animationend to avoid JS/CSS timing race. */
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.textContent = message;

  // Remove on animationend (CSS animation handles fade-out timing)
  toast.addEventListener('animationend', (e) => {
    if (e.animationName === 'fadeOut' && toast.parentNode) {
      toast.remove();
    }
  });

  toastContainer.appendChild(toast);
}

/** Validate email format */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/** Normalize raw backend error messages into user-friendly English */
function normalizeAuthError(raw) {
  if (!raw) return 'Something went wrong. Please try again.';
  const msg = String(raw).toLowerCase();
  if (msg.includes('already registered') || msg.includes('already') || msg.includes('exists') || msg.includes('duplicate') || msg.includes('registered')) {
    return 'This email is already registered. Please log in instead.';
  }
  if (msg.includes('invalid') || msg.includes('incorrect') || msg.includes('wrong') || msg.includes('credentials') || msg.includes('unauthorized')) {
    return 'Email or password is incorrect.';
  }
  if (msg.includes('network') || msg.includes('fetch') || msg.includes('timeout') || msg.includes('refused')) {
    return 'Cannot reach server. Check your connection.';
  }
  return 'Something went wrong. Please try again.';
}

/* --------------------------------------------------------
   Mobile Navbar Toggle
   -------------------------------------------------------- */
function toggleMobileNav() {
  const isOpen = navbarNav.classList.toggle('navbar__nav--open');
  navbarToggle.setAttribute('aria-expanded', isOpen);
  if (isOpen) {
    navbarToggle.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>`;
  } else {
    navbarToggle.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <line x1="3" y1="6" x2="21" y2="6"></line>
        <line x1="3" y1="12" x2="21" y2="12"></line>
        <line x1="3" y1="18" x2="21" y2="18"></line>
      </svg>`;
  }
}

navbarToggle?.addEventListener('click', toggleMobileNav);

// Close mobile nav when a link is clicked
navbarNav?.querySelectorAll('a, button').forEach((el) => {
  el.addEventListener('click', () => {
    if (navbarNav.classList.contains('navbar__nav--open')) {
      toggleMobileNav();
    }
  });
});

/* --------------------------------------------------------
   Modal Management
   -------------------------------------------------------- */

/** Open a modal */
function openModal(overlay) {
  overlay.classList.add('modal-overlay--open');
  overlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';

  // Focus the first focusable element
  const firstInput = overlay.querySelector('input, button:not(.modal__close)');
  if (firstInput) {
    setTimeout(() => firstInput.focus(), 100);
  }
}

/** Close a modal */
function closeModal(overlay) {
  overlay.classList.remove('modal-overlay--open');
  overlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

/** Close all modals */
function closeAllModals() {
  closeModal(loginOverlay);
  closeModal(registerOverlay);
}

// Open login (from register modal)
function openLoginModal() {
  closeRegisterModal();
  var heroOverlay = document.getElementById('heroLoginOverlay');
  if (heroOverlay) {
    heroOverlay.classList.add('landing-modal-overlay--open');
    heroOverlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.body.classList.add('modal-open');
    var firstInput = heroOverlay.querySelector('input');
    if (firstInput) setTimeout(function() { firstInput.focus(); }, 150);
  }
}

/** Clear register form fields and errors */
function clearRegisterForm() {
  var nameEl = document.getElementById('registerName');
  var emailEl = document.getElementById('registerEmail');
  var passEl = document.getElementById('registerPassword');
  var formErr = document.getElementById('registerFormError');
  var nameErr = document.getElementById('registerNameError');
  var emailErr = document.getElementById('registerEmailError');
  var passErr = document.getElementById('registerPasswordError');
  if (nameEl) nameEl.value = '';
  if (emailEl) emailEl.value = '';
  if (passEl) passEl.value = '';
  if (formErr) { formErr.textContent = ''; formErr.classList.add('u-hidden'); }
  if (nameErr) { nameErr.textContent = ''; nameErr.classList.add('u-hidden'); }
  if (emailErr) { emailErr.textContent = ''; emailErr.classList.add('u-hidden'); }
  if (passErr) { passErr.textContent = ''; passErr.classList.add('u-hidden'); }
  [nameEl, emailEl, passEl].forEach(function(el) {
    if (el) el.classList.remove('input__field--error');
  });
}

/** Close register modal */
function closeRegisterModal() {
  if (!registerOverlay) return;
  clearRegisterForm();
  registerOverlay.classList.remove('landing-modal-overlay--open');
  registerOverlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  document.body.classList.remove('modal-open');
}

// Switch to login from register — pointerdown fires before blur
$('#switchToLogin')?.addEventListener('pointerdown', function(e) {
  e.preventDefault();
  e.stopPropagation();
  clearRegisterForm();
  openLoginModal();
});

// Register modal close button
$('#registerModalClose')?.addEventListener('click', closeRegisterModal);

// Escape key to close register modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && registerOverlay?.classList.contains('landing-modal-overlay--open')) {
    closeRegisterModal();
  }
});

/* --------------------------------------------------------
   Password Visibility Toggle
   -------------------------------------------------------- */

function setupPasswordToggle(toggleBtn, passwordInput) {
  if (!toggleBtn || !passwordInput) return;

  toggleBtn.addEventListener('click', () => {
    const isPassword = passwordInput.type === 'password';
    passwordInput.type = isPassword ? 'text' : 'password';
    toggleBtn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');

    // Update icon: eye vs eye-off
    toggleBtn.innerHTML = isPassword
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
           <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
           <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
           <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/>
           <line x1="1" y1="1" x2="23" y2="23"/>
         </svg>`
      : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
           <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
           <circle cx="12" cy="12" r="3"/>
         </svg>`;
  });
}

setupPasswordToggle(loginPasswordToggle, $('#loginPassword'));
setupPasswordToggle(registerPasswordToggle, $('#registerPassword'));
setupPasswordToggle(heroPasswordToggle, $('#heroPassword'));

/* --------------------------------------------------------
   Form Validation & Submission
   -------------------------------------------------------- */

/** Clear all form errors */
function clearFormErrors(formEl) {
  formEl.querySelectorAll('.input__error').forEach((el) => {
    hideFieldError(el);
  });
  formEl.querySelectorAll('.input__field--error').forEach((el) => {
    el.classList.remove('input__field--error');
  });
  const formAlert = formEl.querySelector('.alert');
  if (formAlert) toggleHidden(formAlert, true);
}

/** Validate login form (modal) */
function validateLoginForm() {
  let isValid = true;
  clearFormErrors(loginForm);

  const email = $('#loginEmail');
  const password = $('#loginPassword');

  if (!email.value.trim()) {
    showFieldError($('#loginEmailError'), 'Please enter your email');
    email.classList.add('input__field--error');
    isValid = false;
  } else if (!isValidEmail(email.value)) {
    showFieldError($('#loginEmailError'), 'Please enter a valid email');
    email.classList.add('input__field--error');
    isValid = false;
  }

  if (!password.value) {
    showFieldError($('#loginPasswordError'), 'Please enter your password');
    password.classList.add('input__field--error');
    isValid = false;
  } else if (password.value.length < 6) {
    showFieldError($('#loginPasswordError'), 'At least 6 characters');
    password.classList.add('input__field--error');
    isValid = false;
  }

  return isValid;
}

/** Validate hero login form (landing page) */
function validateHeroLoginForm() {
  let isValid = true;
  clearFormErrors(heroLoginForm);

  const email = $('#heroEmail');
  const password = $('#heroPassword');

  if (!email.value.trim()) {
    showFieldError($('#heroEmailError'), 'Please enter your email');
    email.classList.add('input__field--error');
    isValid = false;
  } else if (!isValidEmail(email.value)) {
    showFieldError($('#heroEmailError'), 'Please enter a valid email');
    email.classList.add('input__field--error');
    isValid = false;
  }

  if (!password.value) {
    showFieldError($('#heroPasswordError'), 'Please enter your password');
    password.classList.add('input__field--error');
    isValid = false;
  } else if (password.value.length < 6) {
    showFieldError($('#heroPasswordError'), 'At least 6 characters');
    password.classList.add('input__field--error');
    isValid = false;
  }

  return isValid;
}

/** Validate register form */
function validateRegisterForm() {
  let isValid = true;
  clearFormErrors(registerForm);

  const email = $('#registerEmail');
  const password = $('#registerPassword');
  const confirmPassword = $('#registerConfirmPassword');

  if (!email.value.trim()) {
    showFieldError($('#registerEmailError'), 'Please enter your email');
    email.classList.add('input__field--error');
    isValid = false;
  } else if (!isValidEmail(email.value)) {
    showFieldError($('#registerEmailError'), 'Please enter a valid email');
    email.classList.add('input__field--error');
    isValid = false;
  }

  if (!password.value) {
    showFieldError($('#registerPasswordError'), 'Please enter your password');
    password.classList.add('input__field--error');
    isValid = false;
  } else if (password.value.length < 8 || !/[a-zA-Z]/.test(password.value) || !/[0-9]/.test(password.value)) {
    showFieldError($('#registerPasswordError'), 'Password must be at least 8 characters and include both letters and numbers.');
    password.classList.add('input__field--error');
    isValid = false;
  }

  if (confirmPassword) {
    if (!confirmPassword.value) {
      showFieldError($('#registerConfirmPasswordError'), 'Please confirm your password');
      confirmPassword.classList.add('input__field--error');
      isValid = false;
    } else if (confirmPassword.value !== password.value) {
      showFieldError($('#registerConfirmPasswordError'), 'Passwords do not match');
      confirmPassword.classList.add('input__field--error');
      isValid = false;
    }
  }

  return isValid;
}

/** Handle login form submission (modal) */
async function handleLoginSubmit(e) {
  e.preventDefault();

  if (!validateLoginForm()) return;

  setButtonLoading(loginSubmitBtn, true);

  try {
    const response = await fetch(`${CONFIG.API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        email: $('#loginEmail').value.trim(),
        password: $('#loginPassword').value,
      }),
    });

    const data = await response.json();

    if (data.status === 'success') {
      const token = data?.data?.token || data?.token || data?.access_token;
      if (!token) {
        toggleHidden(loginFormError, false);
        loginFormError.textContent = 'Server returned success but no token. Please try again.';
        setButtonLoading(loginSubmitBtn, false);
        return;
      }
      saveAuth($('#loginEmail').value.trim(), token);
      showToast('Logged in', 'success');
      closeAllModals();
      showMainApp();
    } else {
      toggleHidden(loginFormError, false);
      loginFormError.textContent = normalizeAuthError(data.message || data?.detail?.message);
    }
  } catch (err) {
    toggleHidden(loginFormError, false);
    loginFormError.textContent = 'Cannot reach server. Check your connection.';
  } finally {
    setButtonLoading(loginSubmitBtn, false);
  }
}

/** Handle hero login form submission (landing page) */
async function handleHeroLoginSubmit(e) {
  e.preventDefault();
  if (!validateHeroLoginForm()) return;

  setButtonLoading(heroLoginSubmitBtn, true);

  try {
    const response = await fetch(`${CONFIG.API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        email: $('#heroEmail').value.trim(),
        password: $('#heroPassword').value,
      }),
    });

    const data = await response.json();

    if (data.status === 'success') {
      const token = data?.data?.token || data?.token || data?.access_token;
      if (!token) {
        toggleHidden(heroFormError, false);
        heroFormError.textContent = 'Server returned success but no token. Please try again.';
        setButtonLoading(heroLoginSubmitBtn, false);
        return;
      }
      saveAuth($('#heroEmail').value.trim(), token);
      showToast('Logged in', 'success');
      closeAllLandingModals();
      showMainApp();
    } else {
      toggleHidden(heroFormError, false);
      heroFormError.textContent = normalizeAuthError(data.message || data?.detail?.message);
    }
  } catch (err) {
    toggleHidden(heroFormError, false);
    heroFormError.textContent = 'Cannot reach server. Check your connection.';
  } finally {
    setButtonLoading(heroLoginSubmitBtn, false);
  }
}

/** Handle register form submission */
async function handleRegisterSubmit(e) {
  e.preventDefault();

  if (!validateRegisterForm()) return;

  setButtonLoading(registerSubmitBtn, true);

  try {
    const response = await fetch(`${CONFIG.API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        email: $('#registerEmail').value.trim(),
        password: $('#registerPassword').value,
      }),
    });

    const data = await response.json();

    if (data.status === 'success') {
      const token = data?.data?.token || data?.token || data?.access_token;
      if (!token) {
        toggleHidden(registerFormError, false);
        registerFormError.textContent = 'Server returned success but no token. Please try again.';
        setButtonLoading(registerSubmitBtn, false);
        return;
      }
      saveAuth(email.value.trim(), token);
      showToast('Account created', 'success');
      closeAllLandingModals();
      showStyleQuiz();
    } else {
      toggleHidden(registerFormError, false);
      registerFormError.textContent = normalizeAuthError(data.message || data?.detail?.message);
    }
  } catch (err) {
    toggleHidden(registerFormError, false);
    registerFormError.textContent = 'Cannot reach server. Check your connection.';
  } finally {
    setButtonLoading(registerSubmitBtn, false);
  }
}

/* --------------------------------------------------------
   Style Quiz — Onboarding Controller
   -------------------------------------------------------- */

/** Close all landing-page modals (login + register) */
function closeAllLandingModals() {
  // Close hero login modal
  var heroOverlay = document.getElementById('heroLoginOverlay');
  if (heroOverlay) {
    heroOverlay.classList.remove('landing-modal-overlay--open');
    heroOverlay.setAttribute('aria-hidden', 'true');
  }
  // Close register modal
  if (registerOverlay) {
    registerOverlay.classList.remove('landing-modal-overlay--open');
    registerOverlay.setAttribute('aria-hidden', 'true');
  }
  // Close legacy login modal
  closeModal(loginOverlay);
  document.body.style.overflow = '';
  document.body.classList.remove('modal-open');
}

/** Show the style quiz screen */
function showStyleQuiz() {
  var quiz = document.getElementById('styleQuiz');
  if (!quiz) return;
  // Hide landing content
  var hero = document.querySelector('.landing-hero');
  var navbar = document.querySelector('.navbar--landing');
  if (hero) hero.style.display = 'none';
  if (navbar) navbar.style.display = 'none';
  // Show quiz
  quiz.classList.remove('u-hidden');
  document.body.style.overflow = 'auto';
}

/** Show the main app — hides all landing/quiz screens, shows welcome then chat */
function showMainApp() {
  var hero = document.querySelector('.landing-hero');
  var navbar = document.querySelector('.navbar--landing');
  var quiz = document.getElementById('styleQuiz');
  var welcome = document.getElementById('welcomeScreen');
  var chat = document.getElementById('chatApp');

  if (hero) hero.style.display = 'none';
  if (navbar) navbar.style.display = 'none';
  if (quiz) quiz.classList.add('u-hidden');
  document.body.style.overflow = 'hidden';
  document.body.classList.remove('modal-open');

  // Show welcome loading screen
  if (welcome) {
    welcome.classList.remove('u-hidden');
    welcome.setAttribute('aria-hidden', 'false');
  }
  showToast('Welcome to WUTT', 'success');

  // Transition to chat — inner function so we can call it from both
  // the timer and a defensive fallback
  function transitionToChat() {
    if (welcome) {
      welcome.classList.add('u-hidden');
      welcome.setAttribute('aria-hidden', 'true');
    }
    if (chat) {
      chat.classList.remove('u-hidden');
      chat.setAttribute('aria-hidden', 'false');
    } else {
      // Defensive: re-query in case the reference went stale
      var chatRetry = document.getElementById('chatApp');
      if (chatRetry) {
        chatRetry.classList.remove('u-hidden');
        chatRetry.setAttribute('aria-hidden', 'false');
      }
    }
    document.body.style.overflow = 'auto';
    initChatApp();
  }

  // Auto-transition to chat after welcome
  var transitioned = false;
  function doTransition() {
    if (transitioned) return;
    transitioned = true;
    transitionToChat();
  }

  setTimeout(doTransition, 3600);

  // Defensive fallback: if the welcome screen is still visible after 5s,
  // force the transition (handles timer-throttled backgrounds)
  setTimeout(doTransition, 5000);
}

/** Complete style quiz and enter main app */
function completeStyleQuiz() {
  var quiz = document.getElementById('styleQuiz');
  if (quiz) quiz.classList.add('u-hidden');
  showMainApp();
}

// Style quiz — card selection
(function initStyleQuiz() {
  var grid = document.getElementById('styleQuizGrid');
  var continueBtn = document.getElementById('styleQuizContinue');
  var skipBtn = document.getElementById('styleQuizSkip');
  if (!grid || !continueBtn) return;

  var selectedStyles = new Set();

  function updateContinueState() {
    if (selectedStyles.size > 0) {
      continueBtn.disabled = false;
      continueBtn.removeAttribute('disabled');
    } else {
      continueBtn.disabled = true;
    }
  }

  grid.addEventListener('click', function(e) {
    var card = e.target.closest('.style-card');
    if (!card) return;

    var style = card.getAttribute('data-style');
    var isSelected = card.getAttribute('aria-pressed') === 'true';

    if (isSelected) {
      card.setAttribute('aria-pressed', 'false');
      selectedStyles.delete(style);
    } else {
      card.setAttribute('aria-pressed', 'true');
      selectedStyles.add(style);
    }

    updateContinueState();
  });

  continueBtn.addEventListener('click', function() {
    if (selectedStyles.size === 0) return;
    // Store selected styles
    try {
      localStorage.setItem('wutt_styles', JSON.stringify(Array.from(selectedStyles)));
    } catch (e) { /* ignore */ }
    completeStyleQuiz();
  });

  skipBtn.addEventListener('click', function() {
    completeStyleQuiz();
  });
})();

/* --------------------------------------------------------
   Chat App & Sidebar — Main screen controller
   TODO: LLM integration — replace mock responses with API calls
   TODO: Wardrobe backend sync — sync localStorage to API
   -------------------------------------------------------- */

var _chatInitDone = false;

function initChatApp() {
  if (_chatInitDone) return;
  _chatInitDone = true;

  /* ---- Sidebar navigation: single-panel, view switching ---- */
  var sidebarItems = document.querySelectorAll('.chat-sidebar__item[data-panel]');

  /** Close all side drawers (wardrobe, settings) and hide feed view */
  function hideAllSidePanels() {
    var panels = ['wardrobeDrawer', 'settingsDrawer'];
    panels.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) { el.classList.add('u-hidden'); el.setAttribute('aria-hidden', 'true'); }
    });
  }

  /** Show chat view (header + body + input bar), hide feed */
  function showChatView() {
    var feedView = document.getElementById('feedView');
    var chatHeader = document.querySelector('.chat-header');
    var chatBody = document.getElementById('chatBody');
    var chatInput = document.querySelector('.chat-input-bar');
    if (feedView) feedView.classList.add('u-hidden');
    if (chatHeader) chatHeader.classList.remove('u-hidden');
    if (chatBody) chatBody.classList.remove('u-hidden');
    if (chatInput) chatInput.classList.remove('u-hidden');
  }

  /** Show Style Feed full-page view, hide chat content */
  function showStyleFeedView() {
    var feedView = document.getElementById('feedView');
    var chatHeader = document.querySelector('.chat-header');
    var chatBody = document.getElementById('chatBody');
    var chatInput = document.querySelector('.chat-input-bar');
    if (feedView) feedView.classList.remove('u-hidden');
    if (chatHeader) chatHeader.classList.add('u-hidden');
    if (chatBody) chatBody.classList.add('u-hidden');
    if (chatInput) chatInput.classList.add('u-hidden');
    renderFeedCards();
  }

  /** Set active sidebar icon */
  function setActiveSidebar(panelName) {
    sidebarItems.forEach(function(n) { n.classList.remove('chat-sidebar__item--active'); });
    var target = document.querySelector('.chat-sidebar__item[data-panel="' + panelName + '"]');
    if (target) target.classList.add('chat-sidebar__item--active');
  }

  /** Open a side drawer with mutual exclusion */
  function openSidePanel(panelName) {
    hideAllSidePanels();
    var drawerId = panelName === 'wardrobe' ? 'wardrobeDrawer' : panelName === 'settings' ? 'settingsDrawer' : null;
    if (drawerId) {
      var el = document.getElementById(drawerId);
      if (el) {
        el.classList.remove('u-hidden');
        el.setAttribute('aria-hidden', 'false');
      }
    }
  }

  sidebarItems.forEach(function(item) {
    item.addEventListener('click', function() {
      var panel = item.getAttribute('data-panel');

      if (panel === 'wardrobe') {
        showChatView();
        openSidePanel('wardrobe');
        renderWardrobeSidebar();
        setActiveSidebar('wardrobe');
        return;
      }

      if (panel === 'settings') {
        showChatView();
        openSidePanel('settings');
        setActiveSidebar('settings');
        return;
      }

      if (panel === 'feed') {
        hideAllSidePanels();
        showStyleFeedView();
        setActiveSidebar('feed');
        return;
      }

      // home / chat / saved — show chat, close side panels
      hideAllSidePanels();
      showChatView();
      setActiveSidebar(panel);
    });
  });

  // Drawer close buttons
  var drawerClose = document.getElementById('wardrobeDrawerClose');
  if (drawerClose) {
    drawerClose.addEventListener('click', function() {
      var drawer = document.getElementById('wardrobeDrawer');
      if (drawer) { drawer.classList.add('u-hidden'); drawer.setAttribute('aria-hidden', 'true'); }
    });
  }
  var settingsClose = document.getElementById('settingsDrawerClose');
  if (settingsClose) {
    settingsClose.addEventListener('click', function() {
      var sDrawer = document.getElementById('settingsDrawer');
      if (sDrawer) { sDrawer.classList.add('u-hidden'); sDrawer.setAttribute('aria-hidden', 'true'); }
    });
  }

  /* ============================================================
     Style Feed — mock social fashion feed (frontend-only)
     TODO: Backend feed API, image upload, privacy, moderation
     ============================================================ */
  var FEED_STORAGE_KEY = 'wutt_style_feed_posts';

  var mockFeedPosts = [
    { id: 'mock-1', user: 'Mia', mood: 'Chic', caption: 'Black blazer + gold hoops. Instant confidence.', item: 'Blazer', time: '2h ago', color: '#3a3540' },
    { id: 'mock-2', user: 'Lena', mood: 'Casual', caption: 'Weekend errand fit — oversized tee and white sneakers.', item: 'T-shirt', time: '5h ago', color: '#88A2FF' },
    { id: 'mock-3', user: 'Yuki', mood: 'Minimal', caption: 'Less is more. Cream knit, straight leg denim.', item: 'Knit sweater', time: '1d ago', color: '#E3FC87' },
    { id: 'mock-4', user: 'Ava', mood: 'Bold', caption: 'Red dress for dinner. Sometimes you just commit.', item: 'Dress', time: '1d ago', color: '#FFB2F7' },
    { id: 'mock-5', user: 'Sora', mood: 'Street', caption: 'Cargo pants + cropped hoodie. City walk ready.', item: 'Hoodie', time: '2d ago', color: '#C0E0FF' },
  ];

  function loadFeedPosts() {
    try {
      var saved = localStorage.getItem(FEED_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch (e) { return []; }
  }

  function saveFeedPosts(posts) {
    try { localStorage.setItem(FEED_STORAGE_KEY, JSON.stringify(posts)); } catch (e) { /* silent */ }
  }

  function renderFeedCards() {
    var grid = document.getElementById('feedGrid');
    if (!grid) return;
    var userPosts = loadFeedPosts();
    var allPosts = userPosts.concat(mockFeedPosts);

    if (allPosts.length === 0) {
      grid.innerHTML = '<div class="feed-empty">' +
        '<svg class="feed-empty__icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="18" rx="2"/><path d="M6 8h12M6 12h8M6 16h10"/></svg>' +
        'No looks yet.<br>Share your first outfit!</div>';
      return;
    }

    var html = '';
    allPosts.forEach(function(post) {
      var moodTag = post.mood ? '<span class="feed-card__mood">' + escapeHtml(post.mood) + '</span>' : '';
      var itemTag = post.item ? '<span class="feed-card__item-tag"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg>' + escapeHtml(post.item) + '</span>' : '';
      var timeLabel = post.time || 'just now';
      var bgColor = post.color || '#f3eee8';

      html += '<div class="feed-card">' +
        '<div class="feed-card__image feed-card__image--placeholder" style="background:' + bgColor + '">' +
          '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4"><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg>' +
        '</div>' +
        '<div class="feed-card__body">' +
          '<div class="feed-card__meta">' +
            '<span class="feed-card__user">' + escapeHtml(post.user) + '</span>' +
            moodTag +
          '</div>' +
          '<p class="feed-card__caption">' + escapeHtml(post.caption) + '</p>' +
          '<span class="feed-card__time">' + escapeHtml(timeLabel) + '</span>' +
          itemTag +
        '</div>' +
      '</div>';
    });
    grid.innerHTML = html;
  }

  // Composer toggle
  var feedShareBtn = document.getElementById('feedShareBtn');
  var feedComposer = document.getElementById('feedComposer');
  var feedComposerCancel = document.getElementById('feedComposerCancel');
  var feedComposerPost = document.getElementById('feedComposerPost');

  if (feedShareBtn && feedComposer) {
    feedShareBtn.addEventListener('click', function() {
      feedComposer.classList.toggle('u-hidden');
      if (!feedComposer.classList.contains('u-hidden')) {
        var captionInput = document.getElementById('feedComposerCaption');
        if (captionInput) captionInput.focus();
      }
    });
  }

  if (feedComposerCancel && feedComposer) {
    feedComposerCancel.addEventListener('click', function() {
      feedComposer.classList.add('u-hidden');
    });
  }

  if (feedComposerPost) {
    feedComposerPost.addEventListener('click', function() {
      var captionInput = document.getElementById('feedComposerCaption');
      var moodSelect = document.getElementById('feedComposerMood');

      var caption = captionInput ? captionInput.value.trim() : '';
      if (!caption) {
        if (captionInput) captionInput.focus();
        return;
      }

      var newPost = {
        id: 'user-' + Date.now(),
        user: 'You',
        mood: moodSelect ? moodSelect.value : '',
        caption: caption,
        time: 'just now',
        color: '#f3eee8'
      };

      var posts = loadFeedPosts();
      posts.unshift(newPost);
      saveFeedPosts(posts);

      if (captionInput) captionInput.value = '';
      if (moodSelect) moodSelect.selectedIndex = 0;
      feedComposer.classList.add('u-hidden');

      renderFeedCards();
    });
  }

  // Back button in feed header
  var feedBackBtn = document.getElementById('feedBackBtn');
  if (feedBackBtn) {
    feedBackBtn.addEventListener('click', function() {
      showChatView();
      setActiveSidebar('chat');
    });
  }

  /* ---- Apply saved chat preferences ---- */
  applyChatPreferences();

  /* ---- Settings drawer: mood chips ---- */
  var moodChips = document.getElementById('moodChips');
  if (moodChips) {
    moodChips.addEventListener('click', function(e) {
      var chip = e.target.closest('.settings-chip');
      if (!chip) return;
      moodChips.querySelectorAll('.settings-chip').forEach(function(c) { c.classList.remove('settings-chip--active'); });
      chip.classList.add('settings-chip--active');
      var prefs = getChatPreferences();
      prefs.mood = chip.getAttribute('data-mood');
      saveChatPreferences(prefs);
      applyChatPreferences();
    });
  }

  /* ---- Settings drawer: background chips ---- */
  var bgChips = document.getElementById('bgChips');
  if (bgChips) {
    bgChips.addEventListener('click', function(e) {
      var chip = e.target.closest('.settings-bg-chip');
      if (!chip) return;
      bgChips.querySelectorAll('.settings-bg-chip').forEach(function(c) { c.classList.remove('settings-bg-chip--active'); });
      chip.classList.add('settings-bg-chip--active');
      var prefs = getChatPreferences();
      prefs.background = chip.getAttribute('data-bg');
      saveChatPreferences(prefs);
      applyChatPreferences();
    });
  }

  /* ---- Welcome action cards ---- */
  var welcomeCards = document.getElementById('chatWelcomeCards');
  var welcome = document.getElementById('chatWelcome');
  var messages = document.getElementById('chatMessages');

  if (welcomeCards && welcome && messages) {
    welcomeCards.addEventListener('click', function(e) {
      var card = e.target.closest('.action-card');
      if (!card) return;

      var action = card.getAttribute('data-action');
      welcome.classList.add('u-hidden');
      messages.classList.remove('u-hidden');

      var responses = {
        'add-top': "Great! Let&rsquo;s find the perfect top. What style do you have in mind?",
        'build-outfit': "Love that. Tell me about the occasion and I&rsquo;ll style a full look.",
        'save-look': "You can save any outfit we create together. Let&rsquo;s build something first!",
        'ask-wutt': "I&rsquo;m here for you. Ask me anything about fashion, fit, or color."
      };
      addChatMessage('bot', responses[action] || "Let&rsquo;s get started. What would you like to do?");
    });
  }

  /* ---- Chat chips — wardrobe add flow ---- */
  var chipsContainer = document.getElementById('chatChips');

  if (chipsContainer && messages) {
    chipsContainer.addEventListener('click', function(e) {
      var chip = e.target.closest('.chat-chip');
      if (!chip) return;
      var item = chip.getAttribute('data-item');

      // Remove any old chips
      chipsContainer.innerHTML = '';

      if (item === 'skip') {
        addChatMessage('bot', 'No problem at all. Take your time — I&rsquo;m here whenever you&rsquo;re ready.');
        return;
      }

      // 1. Add user message
      addUserMessage('Add a <strong>' + item + '</strong>');

      // 2. Bot reply
      addChatMessage('bot', 'Nice. Upload a photo or describe it manually.');

      // 3. Show upload/describe chips
      addChipsToChat([
        { item: 'upload-photo', label: '\u{1F4F7} Upload photo', cls: '' },
        { item: 'describe', label: '\u{270F}\u{FE0F} Describe manually', cls: '' }
      ], item); // pass category to handler
    });
  }

  /* ---- Logout ---- */
  var logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);

  /* ---- File input for wardrobe upload ---- */
  var fileInput = document.getElementById('wardrobeFileInput');
  if (fileInput) {
    fileInput.addEventListener('change', function() {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      var category = fileInput.getAttribute('data-wardrobe-category') || 'Item';
      var reader = new FileReader();
      reader.onload = function(ev) {
        showUploadPreview(category, ev.target.result, file.name);
      };
      reader.readAsDataURL(file);
      fileInput.value = '';
    });
  }

  console.log('WUTT Chat initialized');
}

/* ---- Wardrobe helpers ---- */

/** Get all wardrobe items from localStorage */
function getWardrobeItems() {
  try {
    return JSON.parse(localStorage.getItem('wutt_wardrobe_items') || '[]');
  } catch (e) { return []; }
}

/* ---- Chat preferences — theme & background ---- */

/** Get saved chat preferences, with defaults */
function getChatPreferences() {
  try {
    var saved = JSON.parse(localStorage.getItem('wutt_chat_preferences'));
    if (saved && typeof saved === 'object') {
      saved.mood = saved.mood || 'day';
      saved.background = saved.background || 'clean';
      return saved;
    }
  } catch (e) { /* ignore */ }
  return { mood: 'day', background: 'clean' };
}

/** Save chat preferences to localStorage */
function saveChatPreferences(prefs) {
  localStorage.setItem('wutt_chat_preferences', JSON.stringify(prefs));
}

/** Apply saved preferences to the chat UI */
function applyChatPreferences() {
  var prefs = getChatPreferences();
  var app = document.getElementById('chatApp');
  if (!app) return;

  // Remove old mood and background classes
  app.classList.remove('chat-app--night');
  app.classList.remove('chat-app--bg-grid', 'chat-app--bg-fabric', 'chat-app--bg-wardrobe', 'chat-app--bg-midnight');

  // Apply mood
  if (prefs.mood === 'night') {
    app.classList.add('chat-app--night');
  }

  // Apply background (skip 'clean' — it's the default)
  if (prefs.background && prefs.background !== 'clean') {
    app.classList.add('chat-app--bg-' + prefs.background);
  }

  // Sync settings drawer active states
  var moodChips = document.querySelectorAll('#moodChips .settings-chip');
  moodChips.forEach(function(c) {
    c.classList.toggle('settings-chip--active', c.getAttribute('data-mood') === prefs.mood);
  });
  var bgChips = document.querySelectorAll('#bgChips .settings-bg-chip');
  bgChips.forEach(function(c) {
    c.classList.toggle('settings-bg-chip--active', c.getAttribute('data-bg') === prefs.background);
  });
}

/** Save a wardrobe item to localStorage */
function saveWardrobeItem(item) {
  var items = getWardrobeItems();
  item.id = Date.now();
  item.createdAt = new Date().toISOString();
  items.push(item);
  localStorage.setItem('wutt_wardrobe_items', JSON.stringify(items));
  renderWardrobeSidebar();
}

/**
 * Mock AI analysis — simulates what a vision model would return.
 * TODO: replace with real vision model at deploy stage
 */
function mockAnalyzeWardrobeItem(selectedCategory) {
  var mockByCategory = {
    'Top':    { color: 'Off-white',  styleVibe: 'Minimal clean',    material: 'Cotton poplin',   occasions: ['Casual', 'Brunch', 'Work'],   notes: 'Classic relaxed-fit button-down' },
    'Pants':  { color: 'Charcoal',   styleVibe: 'Tailored smart',   material: 'Wool blend',      occasions: ['Office', 'Dinner', 'Smart casual'], notes: 'Slim-straight cut, mid-rise' },
    'Shoes':  { color: 'White/cream',styleVibe: 'Clean sneaker',    material: 'Leather + rubber',occasions: ['Everyday', 'Travel', 'Casual'],  notes: 'Low-top court sneaker silhouette' },
    'Jacket': { color: 'Olive',      styleVibe: 'Utility casual',   material: 'Cotton twill',     occasions: ['Outdoor', 'Layering', 'Weekend'], notes: 'Oversized chore coat, four-pocket' }
  };
  return mockByCategory[selectedCategory] || {
    color: 'Neutral', styleVibe: 'Classic everyday', material: 'Mixed fabric',
    occasions: ['Casual'], notes: 'Versatile wardrobe staple'
  };
}

/** Add chips into the chat messages */
function addChipsToChat(list, category) {
  var messages = document.getElementById('chatMessages');
  if (!messages) return;

  var chipsDiv = document.createElement('div');
  chipsDiv.className = 'chat-chips';

  list.forEach(function(c) {
    var btn = document.createElement('button');
    btn.className = 'chat-chip' + (c.cls ? ' ' + c.cls : '');
    btn.setAttribute('data-item', c.item);
    btn.textContent = c.label;
    chipsDiv.appendChild(btn);
  });

  messages.appendChild(chipsDiv);

  chipsDiv.addEventListener('click', function(e) {
    var chip = e.target.closest('.chat-chip');
    if (!chip) return;
    var action = chip.getAttribute('data-item');
    chipsDiv.remove();

    if (action === 'upload-photo') {
      handleWardrobeUpload(category);
    } else if (action === 'describe') {
      handleWardrobeDescribe(category);
    }
  });

  scrollChatToBottom();
}

/** Upload photo flow */
function handleWardrobeUpload(category) {
  var fileInput = document.getElementById('wardrobeFileInput');
  if (!fileInput) return;
  fileInput.setAttribute('data-wardrobe-category', category);
  fileInput.click();
}

/** Show upload preview card in chat, then run analyzing → analysis card */
function showUploadPreview(category, dataUrl, fileName) {
  var messages = document.getElementById('chatMessages');
  if (!messages) return;

  // Show preview card with Save button
  var previewId = 'uploadCard-' + Date.now();
  var card = document.createElement('div');
  card.className = 'upload-card';
  card.id = previewId;
  card.innerHTML =
    '<img class="upload-card__thumb" src="' + dataUrl + '" alt="Preview">' +
    '<div class="upload-card__info">' +
      '<div class="upload-card__name">' + escapeHtml(fileName || category) + '</div>' +
      '<div class="upload-card__meta">' + category + ' &middot; Ready to save</div>' +
    '</div>' +
    '<button class="upload-card__save" data-category="' + category + '" data-img="' + dataUrl + '" data-filename="' + escapeHtml(fileName || category) + '">Analyze &amp; Save</button>';

  messages.appendChild(card);
  scrollChatToBottom();

  card.querySelector('.upload-card__save').addEventListener('click', function() {
    var cat = this.getAttribute('data-category');
    var img = this.getAttribute('data-img');
    var fname = this.getAttribute('data-filename');

    // Replace preview with analyzing card
    card.classList.add('u-hidden');
    var analyzing = document.createElement('div');
    analyzing.className = 'analyzing-card';
    analyzing.id = 'analyzing-' + previewId;
    card.insertAdjacentElement('afterend', analyzing);

    var dots = 0; var maxDots = 3;
    var interval = setInterval(function() {
      dots = (dots + 1) % (maxDots + 1);
      analyzing.innerHTML =
        '<div class="analyzing-card__spinner"></div>' +
        '<div class="analyzing-card__text">Analyzing your ' + cat.toLowerCase() + '…' + Array(dots + 1).join('.') + '</div>';
    }, 300);

    scrollChatToBottom();

    // Simulate AI analysis
    setTimeout(function() {
      clearInterval(interval);
      analyzing.remove();

      var analysis = mockAnalyzeWardrobeItem(cat);
      showAnalysisCard(cat, img, fname, analysis);

      scrollChatToBottom();
    }, 1400);
  });
}

/** Show editable AI draft analysis card — compact fashion-item layout */
function showAnalysisCard(category, imageDataUrl, fileName, analysis) {
  var messages = document.getElementById('chatMessages');
  if (!messages) return;

  var cardId = 'analysisCard-' + Date.now();

  // Inject bot preamble message
  addChatMessage('bot', "Here&rsquo;s my first guess — <strong>you can edit it.</strong>");

  var card = document.createElement('div');
  card.className = 'analysis-card';
  card.id = cardId;

  // Build inline pill tags instead of full-width inputs
  var tagsHtml =
    '<div class="analysis-tags">' +
      '<div class="analysis-tag" contenteditable="true" id="' + cardId + '-color" aria-label="Edit color"><span class="analysis-tag__label">Color</span> ' + escapeHtml(analysis.color) + '</div>' +
      '<div class="analysis-tag" contenteditable="true" id="' + cardId + '-styleVibe" aria-label="Edit style"><span class="analysis-tag__label">Style</span> ' + escapeHtml(analysis.styleVibe) + '</div>' +
      '<div class="analysis-tag" contenteditable="true" id="' + cardId + '-material" aria-label="Edit material"><span class="analysis-tag__label">Material</span> ' + escapeHtml(analysis.material) + '</div>' +
      '<div class="analysis-tag" contenteditable="true" id="' + cardId + '-occasions" aria-label="Edit occasions"><span class="analysis-tag__label">For</span> ' + escapeHtml(analysis.occasions.join(', ')) + '</div>' +
      '<div class="analysis-tag" contenteditable="true" id="' + cardId + '-notes" aria-label="Edit notes"><span class="analysis-tag__label">Note</span> ' + escapeHtml(analysis.notes) + '</div>' +
    '</div>';

  var thumbHtml = imageDataUrl
    ? '<img class="analysis-card__thumb" src="' + imageDataUrl + '" alt="">'
    : '<div class="analysis-card__thumb analysis-card__thumb--placeholder">' + getCategorySvg() + '</div>';

  card.innerHTML =
    '<div class="analysis-card__body">' +
      thumbHtml +
      '<div class="analysis-card__summary">' +
        '<span class="analysis-card__draft-badge">' +
          getDraftSvg() + ' AI draft' +
        '</span>' +
        '<div class="analysis-card__category">' + escapeHtml(category) + '</div>' +
        tagsHtml +
      '</div>' +
    '</div>' +
    '<div class="analysis-card__footer">' +
      '<button class="analysis-card__save" id="' + cardId + '-save">Save to Wardrobe</button>' +
      '<button class="analysis-card__action-ghost" id="' + cardId + '-edit">Edit details</button>' +
    '</div>';

  messages.appendChild(card);

  /* ---- Wire save ---- */
  document.getElementById(cardId + '-save').addEventListener('click', function() {
    var extract = function(fieldId) {
      var el = document.getElementById(fieldId);
      return el ? el.textContent.replace(/^[^ ]+ /, '').trim() : '';
    };
    var item = {
      category: category,
      imageDataUrl: imageDataUrl,
      name: fileName || category,
      color: extract(cardId + '-color'),
      styleVibe: extract(cardId + '-styleVibe'),
      material: extract(cardId + '-material'),
      occasions: extract(cardId + '-occasions'),
      notes: extract(cardId + '-notes')
    };
    saveWardrobeItem(item);
    this.textContent = '✓ Saved';
    this.disabled = true;
  });

  /* ---- Edit details: switch tags to real inputs for full editing ---- */
  document.getElementById(cardId + '-edit').addEventListener('click', function() {
    var extract = function(fieldId) {
      var el = document.getElementById(fieldId);
      return el ? el.textContent.replace(/^[^ ]+ /, '').trim() : '';
    };
    var fields = [
      ['Color', 'color'],
      ['Style', 'styleVibe'],
      ['Material', 'material'],
      ['For', 'occasions'],
      ['Note', 'notes']
    ];

    var formHtml = '<div class="describe-form" style="margin-top:' + (imageDataUrl ? '0' : 'var(--space-sm)') + '">' +
      '<div class="describe-form__fields">';

    fields.forEach(function(f) {
      formHtml += '<input class="describe-form__field" placeholder="' + f[0] + '" id="' + cardId + '-big-' + f[1] + '" value="' + escapeHtml(extract(cardId + '-' + f[1])) + '">';
    });

    formHtml += '</div>' +
      '<button class="describe-form__save" id="' + cardId + '-apply-edit">Apply</button>' +
      '</div>';

    // Swap card body for edit form
    card.querySelector('.analysis-card__body').innerHTML = '';
    card.querySelector('.analysis-card__body').appendChild(
      (function() { var d = document.createElement('div'); d.innerHTML = formHtml; return d.firstElementChild; })()
    );
    // Hide footer during edit
    card.querySelector('.analysis-card__footer').classList.add('u-hidden');

    document.getElementById(cardId + '-apply-edit').addEventListener('click', function() {
      // Rebuild with new values, keep footer hidden
      var updated = {};
      fields.forEach(function(f) {
        var el = document.getElementById(cardId + '-big-' + f[1]);
        updated[f[1]] = el ? el.value.trim() : '';
      });
      // Re-render body
      var newTags = '<div class="analysis-tags">';
      fields.forEach(function(f) {
        newTags += '<div class="analysis-tag" contenteditable="true" id="' + cardId + '-' + f[1] + '" aria-label="Edit ' + f[0].toLowerCase() + '"><span class="analysis-tag__label">' + f[0] + '</span> ' + escapeHtml(updated[f[1]]) + '</div>';
      });
      newTags += '</div>';

      card.querySelector('.analysis-card__body').innerHTML =
        thumbHtml +
        '<div class="analysis-card__summary">' +
          '<span class="analysis-card__draft-badge">' + getDraftSvg() + ' AI draft</span>' +
          '<div class="analysis-card__category">' + escapeHtml(category) + '</div>' +
          newTags +
        '</div>';
      card.querySelector('.analysis-card__footer').classList.remove('u-hidden');

      // Re-wire save with updated tag IDs
      document.getElementById(cardId + '-save').addEventListener('click', function() {
        var ext = function(fid) {
          var el = document.getElementById(fid);
          return el ? el.textContent.replace(/^[^ ]+ /, '').trim() : '';
        };
        var item = {
          category: category, imageDataUrl: imageDataUrl, name: fileName || category,
          color: ext(cardId + '-color'), styleVibe: ext(cardId + '-styleVibe'),
          material: ext(cardId + '-material'), occasions: ext(cardId + '-occasions'),
          notes: ext(cardId + '-notes')
        };
        saveWardrobeItem(item);
        document.getElementById(cardId + '-save').textContent = '✓ Saved';
        document.getElementById(cardId + '-save').disabled = true;
      });
    });
  });

  scrollChatToBottom();
}

/** Small SVG for draft badge */
function getDraftSvg() {
  return '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>';
}

/** Small SVG for placeholder thumb */
function getCategorySvg() {
  return '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg>';
}

/** Describe manually flow — shows form, then analyzing, then analysis card */
function handleWardrobeDescribe(category) {
  var messages = document.getElementById('chatMessages');
  if (!messages) return;

  var form = document.createElement('div');
  form.className = 'describe-form';
  var formId = 'describeForm-' + Date.now();
  form.id = formId;
  form.innerHTML =
    '<div class="describe-form__fields">' +
      '<input class="describe-form__field" placeholder="Color" id="descColor' + formId + '">' +
      '<input class="describe-form__field" placeholder="Fit" id="descFit' + formId + '">' +
      '<input class="describe-form__field" placeholder="Material" id="descMaterial' + formId + '">' +
    '</div>' +
    '<button class="describe-form__save" data-category="' + category + '" data-formid="' + formId + '">Next — preview analysis</button>';

  messages.appendChild(form);
  scrollChatToBottom();

  form.querySelector('.describe-form__save').addEventListener('click', function() {
    var fid = this.getAttribute('data-formid');
    var cat = this.getAttribute('data-category');
    var colorEl = document.getElementById('descColor' + fid);
    var fitEl = document.getElementById('descFit' + fid);
    var materialEl = document.getElementById('descMaterial' + fid);

    var partial = {
      color: (colorEl && colorEl.value.trim()) || 'Not specified',
      fit: (fitEl && fitEl.value.trim()) || 'Not specified',
      material: (materialEl && materialEl.value.trim()) || 'Not specified'
    };

    // Replace form with analyzing
    form.classList.add('u-hidden');
    var analyzing = document.createElement('div');
    analyzing.className = 'analyzing-card';
    analyzing.id = 'analyzing-' + fid;
    form.insertAdjacentElement('afterend', analyzing);

    var dots = 0;
    var interval = setInterval(function() {
      dots = (dots + 1) % 4;
      analyzing.innerHTML =
        '<div class="analyzing-card__spinner"></div>' +
        '<div class="analyzing-card__text">Analyzing your ' + cat.toLowerCase() + '…' + Array(dots + 1).join('.') + '</div>';
    }, 300);

    // After delay, show analysis card merged with user's inputs
    setTimeout(function() {
      clearInterval(interval);
      form.remove();
      analyzing.remove();

      var analysis = mockAnalyzeWardrobeItem(cat);
      // Pre-fill with user's manual inputs
      if (partial.color !== 'Not specified') analysis.color = partial.color;
      if (partial.material !== 'Not specified') analysis.material = partial.material;
      if (partial.fit !== 'Not specified') {
        analysis.styleVibe = partial.fit;
        analysis.notes = partial.fit;
      }
      showAnalysisCard(cat, '', cat, analysis);
      scrollChatToBottom();
    }, 1400);
  });
}

/** Render wardrobe items in sidebar drawer */
function renderWardrobeSidebar() {
  var container = document.getElementById('sidebarWardrobe');
  if (!container) return;

  var items = getWardrobeItems();

  if (!items.length) {
    container.innerHTML = '<p class="sidebar-wardrobe__empty">No items yet. Use the chat to add wardrobe pieces.</p>';
    return;
  }

  var html = '<div class="sidebar-wardrobe__grid">';
  items.forEach(function(item) {
    var thumbHtml = '';
    if (item.imageDataUrl) {
      thumbHtml = '<img class="sidebar-wardrobe__thumb" src="' + item.imageDataUrl + '" alt="">';
    } else {
      thumbHtml = '<div class="sidebar-wardrobe__thumb sidebar-wardrobe__thumb--placeholder">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg></div>';
    }
    var detail = [item.category];
    if (item.color) detail.push(item.color);
    if (item.styleVibe) detail.push(item.styleVibe);

    html += '<div class="sidebar-wardrobe__item">' + thumbHtml +
      '<div class="sidebar-wardrobe__item-info">' +
        '<div class="sidebar-wardrobe__item-name">' + escapeHtml(detail.join(' · ')) + '</div>' +
        '<div class="sidebar-wardrobe__item-cat">' + escapeHtml(item.category) +
          (item.occasions ? ' · ' + escapeHtml(item.occasions) : '') +
        '</div>' +
      '</div></div>';
  });
  html += '</div>';

  container.innerHTML = html;
}

/** Add a user message */
function addUserMessage(html) {
  addChatMessage('user', html);
}

/** Add a chat message to the messages container */
function addChatMessage(type, html) {
  var messages = document.getElementById('chatMessages');
  if (!messages) return;

  var msg = document.createElement('div');
  msg.className = 'chat-msg chat-msg--' + type;

  if (type === 'bot') {
    msg.innerHTML = '<div class="chat-msg__avatar" aria-hidden="true">'
      + '<svg width="28" height="28" viewBox="0 0 36 36" fill="none"><rect width="36" height="36" rx="12" fill="#1F1F1F"/><path d="M9 25V12l8 5.5-8 5.5zm8 0h8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      + '</div>'
      + '<div class="chat-msg__bubble"><p>' + html + '</p></div>';
  } else {
    msg.innerHTML = '<div class="chat-msg__bubble"><p>' + html + '</p></div>';
  }

  messages.appendChild(msg);
  scrollChatToBottom();
}

/** Scroll chat body to bottom */
function scrollChatToBottom() {
  var body = document.getElementById('chatBody');
  if (body) body.scrollTop = body.scrollHeight;
}

/** Escape HTML */
function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

loginForm?.addEventListener('submit', handleLoginSubmit);
registerForm?.addEventListener('submit', handleRegisterSubmit);
// heroLoginForm submit is handled by initHeroLoginModal above

// Register social buttons (placeholder — show toast, don't navigate)
$('#googleRegisterBtn')?.addEventListener('click', (e) => { e.preventDefault(); showToast('Google sign-in coming soon'); });
$('#appleRegisterBtn')?.addEventListener('click', (e) => { e.preventDefault(); showToast('Apple sign-in coming soon'); });

console.log('WUTT — Your city. Your weather. Your look. 💫');
