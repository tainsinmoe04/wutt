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

  // Hero CTA buttons
  var getStartedBtn = document.getElementById('heroGetStartedBtn');
  var learnMoreBtn = document.getElementById('heroLearnMoreBtn');

  if (getStartedBtn) {
    getStartedBtn.addEventListener('click', function() {
      // Open signup modal (reuse existing register modal)
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

  if (learnMoreBtn) {
    learnMoreBtn.addEventListener('click', function() {
      var howSection = document.querySelector('.how-it-works');
      if (howSection) {
        howSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  loadUserData();
}

/** Load user-specific data after login */
function loadUserData() {
  applyChatPreferences();
  renderWardrobeSidebar();
}

/** Log out — clear session only, preserve user data */
function handleLogout() {
  localStorage.removeItem('wutt_token');
  localStorage.removeItem('wutt_user');
  window.location.reload();
}

/* --------------------------------------------------------
   User-Scoped localStorage Helpers
   -------------------------------------------------------- */

/** Get current user email for scoping */
function getCurrentUser() {
  return localStorage.getItem('wutt_user') || null;
}

/** Get user-scoped localStorage key */
function userKey(key) {
  var user = getCurrentUser();
  return user ? key + '_' + user.replace(/[^a-zA-Z0-9]/g, '_') : key;
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
      saveAuth($('#registerEmail').value.trim(), token);
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
      localStorage.setItem(userKey('wutt_styles'), JSON.stringify(Array.from(selectedStyles)));
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
  var allViews = ['shopView', 'wishlistView', 'profileView', 'wardrobeView'];

  /** Hide all main views */
  function hideAllViews() {
    allViews.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) { el.classList.add('u-hidden'); el.setAttribute('aria-hidden', 'true'); }
    });
    // Also hide chat
    var chatHeader = document.querySelector('.chat-header');
    var chatBody = document.getElementById('chatBody');
    var chatInput = document.querySelector('.chat-input-bar');
    if (chatHeader) chatHeader.classList.add('u-hidden');
    if (chatBody) chatBody.classList.add('u-hidden');
    if (chatInput) chatInput.classList.add('u-hidden');
    // Hide wardrobe drawer
    var wd = document.getElementById('wardrobeDrawer');
    if (wd) { wd.classList.add('u-hidden'); wd.setAttribute('aria-hidden', 'true'); }
    // Hide AI chat FAB (only show on shop/home)
    var fab = document.getElementById('aiChatFab');
    if (fab) fab.classList.add('u-hidden');
  }

  /** Show shop home page */
  function showHomeView() {
    hideAllViews();
    var shopView = document.getElementById('shopView');
    if (shopView) { shopView.classList.remove('u-hidden'); shopView.setAttribute('aria-hidden', 'false'); }
    var fab = document.getElementById('aiChatFab');
    if (fab) fab.classList.remove('u-hidden');
    renderShopProducts();
  }

  /** Show AI chat view */
  function showChatView() {
    hideAllViews();
    var chatHeader = document.querySelector('.chat-header');
    var chatBody = document.getElementById('chatBody');
    var chatInput = document.querySelector('.chat-input-bar');
    if (chatHeader) chatHeader.classList.remove('u-hidden');
    if (chatBody) chatBody.classList.remove('u-hidden');
    if (chatInput) chatInput.classList.remove('u-hidden');
  }

  /** Show profile page */
  function showProfileView() {
    hideAllViews();
    var profileView = document.getElementById('profileView');
    if (profileView) { profileView.classList.remove('u-hidden'); profileView.setAttribute('aria-hidden', 'false'); }
    renderProfileView();
  }

  /** Show wardrobe page */
  function showWardrobeView() {
    hideAllViews();
    var wardrobeView = document.getElementById('wardrobeView');
    if (wardrobeView) { wardrobeView.classList.remove('u-hidden'); wardrobeView.setAttribute('aria-hidden', 'false'); }
    renderWardrobeView();
  }

  /** Show wishlist page */
  function showWishlistView() {
    hideAllViews();
    var wishlistView = document.getElementById('wishlistView');
    if (wishlistView) { wishlistView.classList.remove('u-hidden'); wishlistView.setAttribute('aria-hidden', 'false'); }
    renderWishlist();
  }

  /** Set active sidebar icon */
  function setActiveSidebar(panelName) {
    sidebarItems.forEach(function(n) { n.classList.remove('chat-sidebar__item--active'); });
    var target = document.querySelector('.chat-sidebar__item[data-panel="' + panelName + '"]');
    if (target) target.classList.add('chat-sidebar__item--active');
  }

  sidebarItems.forEach(function(item) {
    item.addEventListener('click', function() {
      var panel = item.getAttribute('data-panel');

      if (panel === 'wardrobe') {
        showWardrobeView();
        setActiveSidebar('wardrobe');
        return;
      }

      if (panel === 'profile') {
        showProfileView();
        setActiveSidebar('profile');
        return;
      }

      // home — show chat (chat-first experience)
      showChatView();
      setActiveSidebar('home');
    });
  });

  // Wardrobe drawer close
  var drawerClose = document.getElementById('wardrobeDrawerClose');
  if (drawerClose) {
    drawerClose.addEventListener('click', function() {
      var drawer = document.getElementById('wardrobeDrawer');
      if (drawer) { drawer.classList.add('u-hidden'); drawer.setAttribute('aria-hidden', 'true'); }
    });
  }

  // AI Chat FAB
  var aiChatFab = document.getElementById('aiChatFab');
  if (aiChatFab) {
    aiChatFab.addEventListener('click', function() {
      showChatView();
      setActiveSidebar(null);
    });
  }

  /* ---- Profile view ---- */
  var profileEditBtn = document.getElementById('profileEditBtn');
  var profileEditOverlay = document.getElementById('profileEditOverlay');
  var profileEditClose = document.getElementById('profileEditClose');

  // Wire chip/pill/swatch single-select groups
  wireSingleSelectGroup('profileGenderChips', 'pf-chip--active');
  wireSingleSelectGroup('profileTopSizePills', 'pf-size-pill--active');
  wireSingleSelectGroup('profileBottomSizePills', 'pf-size-pill--active');
  wireSingleSelectGroup('profileShoppingStyleChips', 'pf-chip--active');
  wireSingleSelectGroup('profileFitPreferenceChips', 'pf-chip--active');
  wireSingleSelectGroup('profileOutfitVibeChips', 'pf-chip--active');
  wireSingleSelectGroup('profileBudgetRangeChips', 'pf-chip--active');
  wireSingleSelectGroup('profileShoppingPrefChips', 'pf-chip--active');
  wireSkinToneSwatches();

  // Wire multi-select groups
  wireMultiSelectGroup('profileFavoriteStylesChips', 'pf-chip--active');
  wireMultiSelectGroup('profileCategoriesChips', 'pf-chip--active');
  wireMultiSelectGroup('profilePreferredColorsChips', 'pf-color-chip--active');

  function openProfileEdit() {
    loadProfileForm();
    if (profileEditOverlay) profileEditOverlay.classList.add('pf-edit-overlay--open');
  }
  function closeProfileEdit() {
    if (profileEditOverlay) profileEditOverlay.classList.remove('pf-edit-overlay--open');
  }

  if (profileEditBtn) profileEditBtn.addEventListener('click', openProfileEdit);
  if (profileEditClose) profileEditClose.addEventListener('click', closeProfileEdit);

  // Section edit buttons — open the edit modal (except coupon See all)
  document.querySelectorAll('.pf-section__edit').forEach(function(btn) {
    if (btn.id === 'couponSeeAllBtn') return;
    btn.addEventListener('click', function() {
      openProfileEdit();
    });
  });

  // Close on overlay click (not modal body)
  if (profileEditOverlay) {
    profileEditOverlay.addEventListener('click', function(e) {
      if (e.target === profileEditOverlay) closeProfileEdit();
    });
  }

  var profileForm = document.getElementById('profileForm');
  if (profileForm) {
    profileForm.addEventListener('submit', function(e) {
      e.preventDefault();
      saveProfileForm();
      closeProfileEdit();
      renderProfileView();
    });
  }

  /* ---- Profile photo upload ---- */
  var photoUpload = document.getElementById('profilePhotoUpload');
  var photoInput = document.getElementById('profilePhotoInput');
  var editPhotoBtn = document.getElementById('profileEditPhotoBtn');

  if (photoUpload && photoInput) {
    photoUpload.addEventListener('click', function() { photoInput.click(); });
    photoUpload.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); photoInput.click(); }
    });
  }
  if (editPhotoBtn && photoInput) {
    editPhotoBtn.addEventListener('click', function() { photoInput.click(); });
  }
  if (photoInput) {
    photoInput.addEventListener('change', function() {
      var file = photoInput.files && photoInput.files[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) { showToast('Photo must be under 5MB', 'error'); return; }
      var reader = new FileReader();
      reader.onload = function(ev) {
        var dataUrl = ev.target.result;
        localStorage.setItem(userKey('wutt_profile_photo'), dataUrl);
        renderProfilePhoto();
        showToast('Photo updated', 'success');
      };
      reader.readAsDataURL(file);
      photoInput.value = '';
    });
  }

  /* ---- Coupon copy buttons (ticket + sidebar styles) ---- */
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('.pf-ticket__copy, .coupon-card__copy');
    if (!btn) return;
    var code = btn.getAttribute('data-code');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code).then(function() {
        btn.textContent = 'Copied';
        setTimeout(function() { btn.textContent = 'Copy'; }, 1500);
      });
    } else {
      btn.textContent = 'Copied';
      setTimeout(function() { btn.textContent = 'Copy'; }, 1500);
    }
  });

  /* ---- Coupon drawer ---- */
  var couponDrawer = document.getElementById('couponDrawer');
  var couponDrawerOverlay = document.getElementById('couponDrawerOverlay');
  var couponDrawerClose = document.getElementById('couponDrawerClose');
  var couponSeeAllBtn = document.getElementById('couponSeeAllBtn');

  // All coupons data — future backend connection point
  var ALL_COUPONS = [
    { badge: '10% OFF', title: 'First Purchase Discount', desc: 'Get 10% off your very first order on WUTT.', valid: 'Valid until Aug 15, 2026', code: 'STYLE10', variant: '' },
    { badge: 'FREE SHIP', title: 'Free Delivery', desc: 'Free shipping on all orders over 50,000 Ks.', valid: 'Valid until Sep 1, 2026', code: 'SHIPFREE', variant: 'green' },
    { badge: '15% OFF', title: 'Member Reward', desc: 'Exclusive discount for WUTT style members.', valid: 'Valid until Jul 31, 2026', code: 'WUTT15', variant: '' },
    { badge: '20% OFF', title: 'Welcome Offer', desc: 'Special welcome discount for new users.', valid: 'Valid until Aug 30, 2026', code: 'NEWUSER20', variant: 'green' },
    { badge: '5,000 OFF', title: 'Big Saver', desc: 'Save 5,000 Ks on purchases above 30,000 Ks.', valid: 'Valid until Oct 15, 2026', code: 'SAVE5K', variant: '' },
  ];

  function renderCouponDrawer() {
    var body = document.getElementById('couponDrawerBody');
    if (!body) return;
    body.innerHTML = ALL_COUPONS.map(function(c) {
      var badgeCls = c.variant === 'green' ? ' coupon-card__badge--green' : '';
      return '<div class="coupon-card">'
        + '<div class="coupon-card__top">'
        + '<div>'
        + '<span class="coupon-card__badge' + badgeCls + '">' + c.badge + '</span>'
        + '<h4 class="coupon-card__title">' + c.title + '</h4>'
        + '</div>'
        + '</div>'
        + '<p class="coupon-card__desc">' + c.desc + '</p>'
        + '<span class="coupon-card__valid">' + c.valid + '</span>'
        + '<div class="coupon-card__bottom">'
        + '<span class="coupon-card__code">' + c.code + '</span>'
        + '<button class="coupon-card__copy" type="button" data-code="' + c.code + '" aria-label="Copy coupon code">Copy</button>'
        + '</div>'
        + '</div>';
    }).join('');
  }

  function openCouponDrawer() {
    renderCouponDrawer();
    if (couponDrawer) couponDrawer.classList.add('coupon-drawer--open');
    if (couponDrawerOverlay) couponDrawerOverlay.classList.add('coupon-drawer-overlay--open');
    document.body.style.overflow = 'hidden';
  }

  function closeCouponDrawer() {
    if (couponDrawer) couponDrawer.classList.remove('coupon-drawer--open');
    if (couponDrawerOverlay) couponDrawerOverlay.classList.remove('coupon-drawer-overlay--open');
    document.body.style.overflow = '';
  }

  if (couponSeeAllBtn) {
    couponSeeAllBtn.addEventListener('click', openCouponDrawer);
  }
  if (couponDrawerClose) {
    couponDrawerClose.addEventListener('click', closeCouponDrawer);
  }
  if (couponDrawerOverlay) {
    couponDrawerOverlay.addEventListener('click', closeCouponDrawer);
  }

  // Escape key to close coupon drawer
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && couponDrawer && couponDrawer.classList.contains('coupon-drawer--open')) {
      closeCouponDrawer();
    }
  });

  /* ============================================================
     Shop Home — mock product data and rendering
     ============================================================ */
  var MOCK_PRODUCTS = [
    { id: 'p1',  name: 'Oversized Linen Blazer',   shop: 'Yangon Atelier', price: '45,000 Ks', cat: 'tops',        rating: 4.8, color: '#E8E0D8' },
    { id: 'p2',  name: 'Straight Leg Denim',        shop: 'Thiri Store',    price: '32,000 Ks', cat: 'bottoms',     rating: 4.5, color: '#A8B8C8' },
    { id: 'p3',  name: 'Minimal Leather Tote',      shop: 'Mandalay Craft', price: '28,000 Ks', cat: 'accessories', rating: 4.9, color: '#C8B8A8' },
    { id: 'p4',  name: 'Cotton Poplin Dress',       shop: 'Paw Sandy',      price: '38,000 Ks', cat: 'dresses',     rating: 4.6, color: '#D8E8F0' },
    { id: 'p5',  name: 'Canvas Court Sneakers',     shop: 'Street Yangon',  price: '42,000 Ks', cat: 'shoes',       rating: 4.3, color: '#F0ECE8' },
    { id: 'p6',  name: 'Ribbed Knit Top',           shop: 'Nora Boutique',  price: '18,000 Ks', cat: 'tops',        rating: 4.7, color: '#F5E8E0' },
    { id: 'p7',  name: 'Wide Leg Trousers',         shop: 'Thiri Store',    price: '35,000 Ks', cat: 'bottoms',     rating: 4.4, color: '#E0D8D0' },
    { id: 'p8',  name: 'Silk Scarf',                shop: 'Mandalay Craft', price: '15,000 Ks', cat: 'accessories', rating: 4.8, color: '#E8D8E8' },
    { id: 'p9',  name: 'Cropped Cardigan',          shop: 'Nora Boutique',  price: '22,000 Ks', cat: 'tops',        rating: 4.2, color: '#F0E0E8' },
    { id: 'p10', name: 'Pleated Midi Skirt',        shop: 'Yangon Atelier', price: '29,000 Ks', cat: 'bottoms',     rating: 4.6, color: '#E8E8F0' },
    { id: 'p11', name: 'Leather Crossbody Bag',     shop: 'Mandalay Craft', price: '35,000 Ks', cat: 'accessories', rating: 4.9, color: '#D8C8B8' },
    { id: 'p12', name: 'Linen Summer Dress',        shop: 'Paw Sandy',      price: '42,000 Ks', cat: 'dresses',     rating: 4.5, color: '#F0F0E8' },
    { id: 'p13', name: 'Suede Ankle Boots',         shop: 'Street Yangon',  price: '55,000 Ks', cat: 'shoes',       rating: 4.7, color: '#C8B8A0' },
    { id: 'p14', name: 'Oversized Cotton Tee',      shop: 'Thiri Store',    price: '12,000 Ks', cat: 'tops',        rating: 4.1, color: '#E8E8E8' },
    { id: 'p15', name: 'High-Rise Cargo Pants',     shop: 'Street Yangon',  price: '38,000 Ks', cat: 'bottoms',     rating: 4.4, color: '#C8C8C0' },
    { id: 'p16', name: 'Gold Hoop Earrings',        shop: 'Nora Boutique',  price: '8,000 Ks',  cat: 'accessories', rating: 4.9, color: '#F0E8D0' },
    { id: 'p17', name: 'Wrap Blouse',               shop: 'Yangon Atelier', price: '25,000 Ks', cat: 'tops',        rating: 4.6, color: '#E8D8D0' },
    { id: 'p18', name: 'Knit Bodycon Dress',        shop: 'Paw Sandy',      price: '32,000 Ks', cat: 'dresses',     rating: 4.3, color: '#D8D0E0' },
  ];

  function getWishlistIds() {
    try {
      return JSON.parse(localStorage.getItem(userKey('wutt_wishlist')) || '[]');
    } catch (e) { return []; }
  }

  function toggleWishlist(productId) {
    var ids = getWishlistIds();
    var idx = ids.indexOf(productId);
    if (idx >= 0) { ids.splice(idx, 1); } else { ids.push(productId); }
    localStorage.setItem(userKey('wutt_wishlist'), JSON.stringify(ids));
  }

  function isWishlisted(productId) {
    return getWishlistIds().indexOf(productId) >= 0;
  }

  function renderProductCard(product) {
    var wishClass = isWishlisted(product.id) ? 'product-card__wish product-card__wish--active' : 'product-card__wish';
    var heartFill = isWishlisted(product.id) ? 'fill="#e25555"' : '';
    var ratingVal = product.rating || 4.5;
    return '<div class="product-card" data-product-id="' + product.id + '">' +
      '<div class="product-card__img" style="background:' + product.color + '">' +
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg>' +
        '<button class="' + wishClass + '" data-wish-id="' + product.id + '" aria-label="Toggle wishlist" type="button">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" ' + heartFill + '/></svg>' +
        '</button>' +
      '</div>' +
      '<div class="product-card__info">' +
        '<p class="product-card__name">' + escapeHtml(product.name) + '</p>' +
        '<p class="product-card__shop">' + escapeHtml(product.shop) + '</p>' +
        '<div class="product-card__row">' +
          '<span class="product-card__price">' + escapeHtml(product.price) + '</span>' +
          '<span class="product-card__tag">★ ' + ratingVal + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="product-card__actions">' +
        '<button class="product-card__btn" data-view-id="' + product.id + '" type="button">View</button>' +
        '<button class="product-card__btn product-card__btn--primary" data-add-id="' + product.id + '" type="button">+ Wardrobe</button>' +
      '</div>' +
    '</div>';
  }

  function renderShopProducts(filterCat) {
    var grid = document.getElementById('shopGrid');
    var picksGrid = document.getElementById('shopPicksGrid');
    var cat = filterCat || 'all';

    var filtered = cat === 'all' ? MOCK_PRODUCTS : MOCK_PRODUCTS.filter(function(p) { return p.cat === cat; });
    var trending = filtered.slice(0, 4);
    var picks = MOCK_PRODUCTS.slice(0, 6);

    // Trending grid: 4 product cards + explore card
    var exploreHtml = '<button class="product-card product-card--explore" type="button" aria-label="Explore more trending items">' +
      '<span class="product-card--explore__icon" aria-hidden="true">+</span>' +
      '<span class="product-card--explore__label">Explore more</span>' +
    '</button>';
    if (grid) grid.innerHTML = trending.map(renderProductCard).join('') + exploreHtml;
    if (picksGrid) picksGrid.innerHTML = picks.map(renderProductCard).join('');

    // Wire explore card
    var exploreBtn = grid ? grid.querySelector('.product-card--explore') : null;
    if (exploreBtn) {
      exploreBtn.addEventListener('click', function() {
        showShopSearchPlaceholder();
      });
    }

    // Wire wishlist buttons
    document.querySelectorAll('.product-card__wish').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var pid = btn.getAttribute('data-wish-id');
        toggleWishlist(pid);
        renderShopProducts(cat);
      });
    });

    // Wire + Wardrobe buttons
    document.querySelectorAll('.product-card__btn--primary').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var pid = btn.getAttribute('data-add-id');
        var product = MOCK_PRODUCTS.find(function(p) { return p.id === pid; });
        if (product) {
          saveWardrobeItem({
            category: product.cat.charAt(0).toUpperCase() + product.cat.slice(1, -1) || 'Item',
            name: product.name,
            color: product.color,
            styleVibe: product.shop,
            material: '',
            occasions: '',
            notes: 'Added from shop'
          });
          btn.textContent = '✓ Added';
          btn.disabled = true;
          showToast('Added to wardrobe', 'success');
        }
      });
    });
  }

  // Shop search placeholder — opens when explore card is tapped
  function showShopSearchPlaceholder() {
    var overlay = document.createElement('div');
    overlay.className = 'shop-search-overlay';
    overlay.innerHTML =
      '<div class="shop-search-card">' +
        '<div class="shop-search-card__header">' +
          '<h3 class="shop-search-card__title">Search & Explore</h3>' +
          '<button class="shop-search-card__close" aria-label="Close">&times;</button>' +
        '</div>' +
        '<div class="shop-search-card__body">' +
          '<input class="shop-search-card__input" type="text" placeholder="Search styles, shops, items..." disabled>' +
          '<p class="shop-search-card__msg">Shop search coming soon — explore local styles in your area.</p>' +
          '<div class="shop-search-card__tags">' +
            '<span class="shop-search-card__tag">Streetwear</span>' +
            '<span class="shop-search-card__tag">Minimal</span>' +
            '<span class="shop-search-card__tag">Vintage</span>' +
            '<span class="shop-search-card__tag">Office</span>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('shop-search-overlay--open'); });

    function close() {
      overlay.classList.remove('shop-search-overlay--open');
      setTimeout(function() { overlay.remove(); }, 250);
    }
    overlay.querySelector('.shop-search-card__close').addEventListener('click', close);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(); });
  }

  // Category chips
  var shopChips = document.getElementById('shopCategoryChips');
  if (shopChips) {
    shopChips.addEventListener('click', function(e) {
      var chip = e.target.closest('.shop-chip');
      if (!chip) return;
      shopChips.querySelectorAll('.shop-chip').forEach(function(c) { c.classList.remove('shop-chip--active'); });
      chip.classList.add('shop-chip--active');
      renderShopProducts(chip.getAttribute('data-cat'));
    });
  }

  /* ============================================================
     Wishlist — rendering
     ============================================================ */
  function renderWishlist() {
    var grid = document.getElementById('wishlistGrid');
    var empty = document.getElementById('wishlistEmpty');
    var count = document.getElementById('wishlistCount');
    var ids = getWishlistIds();
    var items = MOCK_PRODUCTS.filter(function(p) { return ids.indexOf(p.id) >= 0; });

    if (count) count.textContent = items.length + ' item' + (items.length !== 1 ? 's' : '');

    if (items.length === 0) {
      if (grid) grid.innerHTML = '';
      if (empty) empty.classList.remove('u-hidden');
      return;
    }

    if (empty) empty.classList.add('u-hidden');
    if (grid) {
      grid.innerHTML = items.map(renderProductCard).join('');
      // Wire wishlist buttons
      grid.querySelectorAll('.product-card__wish').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          var pid = btn.getAttribute('data-wish-id');
          toggleWishlist(pid);
          renderWishlist();
        });
      });
    }
  }

  /* ---- Apply saved chat preferences ---- */
  applyChatPreferences();

  /* ---- Settings drawer: mood toggle ---- */
  var moodToggleBtn = document.getElementById('moodToggleBtn');
  if (moodToggleBtn) {
    moodToggleBtn.addEventListener('click', function() {
      var prefs = getChatPreferences();
      prefs.mood = prefs.mood === 'night' ? 'day' : 'night';
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
        { item: 'upload-photo', label: 'Upload photo', cls: '' },
        { item: 'describe', label: 'Describe manually', cls: '' }
      ], item); // pass category to handler
    });
  }

  /* ---- Chat send handler ---- */
  var chatSendBtn = document.getElementById('chatSendBtn');
  var chatInputField = document.getElementById('chatInput');
  var _chatSending = false;

  /** Detect if message is an outfit request (should use /recommend) */
  function isOutfitRequest(text) {
    var lower = text.toLowerCase();
    var outfitKeywords = [
      'wear', 'outfit', 'dress', 'put on', 'should i',
      'what to', 'recommend', 'suggest', 'style for',
      'look for', 'going to', 'attending', 'event',
      'wedding', 'party', 'date', 'interview', 'work outfit',
      'casual', 'formal', 'coffee date', 'dinner',
      'ဘာဝတ်', 'ဝတ်စုံ', 'ဖို့', 'ပွဲ', 'လောင်း'
    ];
    return outfitKeywords.some(function(kw) { return lower.includes(kw); });
  }

  function sendChatMessage() {
    if (_chatSending) return;
    var text = chatInputField ? chatInputField.value.trim() : '';
    if (!text) return;

    // Show messages container, hide welcome
    var welcomeEl = document.getElementById('chatWelcome');
    var messagesEl = document.getElementById('chatMessages');
    if (welcomeEl) welcomeEl.classList.add('u-hidden');
    if (messagesEl) messagesEl.classList.remove('u-hidden');

    // Add user message to UI and history
    addUserMessage(escapeHtml(text));
    addToChatHistory('user', text);
    chatInputField.value = '';

    // Show typing indicator
    var typingEl = document.createElement('div');
    typingEl.className = 'chat-msg chat-msg--bot';
    typingEl.id = 'chatTypingIndicator';
    typingEl.innerHTML =
      '<div class="chat-msg__avatar" aria-hidden="true">' +
        '<svg width="28" height="28" viewBox="0 0 36 36" fill="none"><rect width="36" height="36" rx="12" fill="#1F1F1F"/><path d="M9 25V12l8 5.5-8 5.5zm8 0h8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      '</div>' +
      '<div class="chat-msg__bubble"><p class="chat-typing"><span class="chat-typing__dot"></span><span class="chat-typing__dot"></span><span class="chat-typing__dot"></span></p></div>';
    messagesEl.appendChild(typingEl);
    scrollChatToBottom();

    _chatSending = true;
    if (chatSendBtn) chatSendBtn.disabled = true;

    var token = localStorage.getItem('wutt_token');
    var headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;

    // Get conversation history for context
    var history = getChatHistory();
    var recentHistory = history.slice(-10); // Last 10 messages

    // Decide endpoint based on message content
    var endpoint, body;
    if (isOutfitRequest(text)) {
      endpoint = '/stylist/recommend';
      body = { occasion: text };
    } else {
      endpoint = '/stylist/chat';
      body = {
        message: text,
        conversation_history: recentHistory.slice(0, -1), // Exclude current message
      };
    }

    fetch(CONFIG.API_BASE + endpoint, {
      method: 'POST',
      headers: headers,
      credentials: 'include',
      body: JSON.stringify(body),
    }).then(function(resp) {
      return resp.json();
    }).then(function(data) {
      // Remove typing indicator
      var typing = document.getElementById('chatTypingIndicator');
      if (typing) typing.remove();

      if (data.status === 'success' && data.data) {
        var d = data.data;
        var reply = '';

        // Check source — show styled error for api_error
        var src = d.source || '';
        if (src === 'api_error') {
          reply = '<div class="chat-msg__error">'
            + '⚠️ ' + escapeHtml(d.response || d.explanation || 'Real AI is unavailable.')
            + '</div>';
        }
        // Handle chat response (from /stylist/chat)
        else if (d.response) {
          reply = escapeHtml(d.response).replace(/\n/g, '<br>');
          // Save bot response to history
          addToChatHistory('bot', d.response);
        }
        // Handle outfit recommendation (from /stylist/recommend)
        else if (d.explanation || (d.outfit && d.outfit.length > 0)) {
          if (d.explanation) {
            reply += '<strong>' + escapeHtml(d.explanation) + '</strong>';
          }

          if (d.outfit && d.outfit.length > 0) {
            reply += '<br><br><strong>Recommended outfit:</strong><br>';
            reply += '<ol style="margin:6px 0 0 18px;padding:0;">';
            d.outfit.forEach(function(item) {
              reply += '<li style="margin-bottom:3px;">' + escapeHtml(item) + '</li>';
            });
            reply += '</ol>';
          }

          if (d.weather_based_tip) {
            reply += '<br><em style="color:var(--wutt-text-muted);font-size:0.8125rem;">' + escapeHtml(d.weather_based_tip) + '</em>';
          }

          // Save to history
          var historyText = d.explanation || '';
          if (d.outfit && d.outfit.length > 0) {
            historyText += ' Outfit: ' + d.outfit.join(', ');
          }
          addToChatHistory('bot', historyText);
        }

        if (!reply) {
          reply = 'I\'m not sure how to help with that. Try asking about an outfit for a specific occasion like "What should I wear to a wedding?"';
        }

        addChatMessage('bot', reply);
      } else {
        addChatMessage('bot', 'Sorry, something went wrong. Please try again.');
      }
    }).catch(function(err) {
      console.error('[WUTT] Chat error:', err);
      var typing = document.getElementById('chatTypingIndicator');
      if (typing) typing.remove();
      addChatMessage('bot', 'Connection error. Please check your connection and try again.');
    }).finally(function() {
      _chatSending = false;
      if (chatSendBtn) chatSendBtn.disabled = false;
      if (chatInputField) chatInputField.focus();
    });
  }

  if (chatSendBtn) {
    chatSendBtn.addEventListener('click', sendChatMessage);
  }
  if (chatInputField) {
    chatInputField.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  /* ---- Clear chat history ---- */
  var clearHistoryBtn = document.getElementById('chatClearHistoryBtn');
  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', function() {
      if (confirm('Clear all chat history? This cannot be undone.')) {
        clearChatHistory();
        // Clear the messages UI
        var messagesEl = document.getElementById('chatMessages');
        if (messagesEl) messagesEl.innerHTML = '';
        // Show welcome again
        var welcomeEl = document.getElementById('chatWelcome');
        if (welcomeEl) welcomeEl.classList.remove('u-hidden');
        // Show toast
        if (typeof showToast === 'function') {
          showToast('Chat history cleared', 'success');
        }
      }
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

  // Show chat view on first load (chat-first experience)
  showChatView();
  setActiveSidebar('home');

  // Shop back button — return to AI Stylist chat
  var shopBackBtn = document.getElementById('shopBackToChat');
  if (shopBackBtn) {
    shopBackBtn.addEventListener('click', function() {
      showChatView();
      setActiveSidebar('home');
    });
  }

  /* ---- Wardrobe Upload Modal ---- */
  var wardrobeAddBtn = document.getElementById('wardrobeAddBtn');
  var wardrobeModal = document.getElementById('wardrobeModal');
  var wardrobeModalClose = document.getElementById('wardrobeModalClose');
  var wardrobeModalFileInput = document.getElementById('wardrobeModalFileInput');
  var wardrobeUploadArea = document.getElementById('wardrobeUploadArea');
  var wardrobeModalRetake = document.getElementById('wardrobeModalRetake');
  var wardrobeModalSave = document.getElementById('wardrobeModalSave');
  var wardrobeModalDone = document.getElementById('wardrobeModalDone');

  // Temp state for current upload
  var _pendingUpload = { dataUrl: '', fileName: '' };

  function openWardrobeModal() {
    if (!wardrobeModal) return;
    // Reset to step 1
    var stepUpload = document.getElementById('wardrobeModalUpload');
    var stepPreview = document.getElementById('wardrobeModalPreview');
    var stepSaved = document.getElementById('wardrobeModalSaved');
    if (stepUpload) stepUpload.classList.remove('u-hidden');
    if (stepPreview) stepPreview.classList.add('u-hidden');
    if (stepSaved) stepSaved.classList.add('u-hidden');
    wardrobeModal.classList.remove('u-hidden');
    wardrobeModal.setAttribute('aria-hidden', 'false');
  }

  function closeWardrobeModal() {
    if (!wardrobeModal) return;
    wardrobeModal.classList.add('u-hidden');
    wardrobeModal.setAttribute('aria-hidden', 'true');
    _pendingUpload = { dataUrl: '', fileName: '' };
  }

  if (wardrobeAddBtn) {
    wardrobeAddBtn.addEventListener('click', function() {
      openWardrobeModal();
    });
  }

  if (wardrobeModalClose) {
    wardrobeModalClose.addEventListener('click', closeWardrobeModal);
  }

  // Click overlay to close
  if (wardrobeModal) {
    wardrobeModal.addEventListener('click', function(e) {
      if (e.target === wardrobeModal) closeWardrobeModal();
    });
  }

  // Upload area click → trigger file input
  if (wardrobeUploadArea) {
    wardrobeUploadArea.addEventListener('click', function() {
      if (wardrobeModalFileInput) wardrobeModalFileInput.click();
    });

    // Drag & drop
    wardrobeUploadArea.addEventListener('dragover', function(e) {
      e.preventDefault();
      wardrobeUploadArea.classList.add('dragover');
    });
    wardrobeUploadArea.addEventListener('dragleave', function() {
      wardrobeUploadArea.classList.remove('dragover');
    });
    wardrobeUploadArea.addEventListener('drop', function(e) {
      e.preventDefault();
      wardrobeUploadArea.classList.remove('dragover');
      var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (file && file.type.startsWith('image/')) {
        handleModalFileSelected(file);
      }
    });
  }

  // File input change
  if (wardrobeModalFileInput) {
    wardrobeModalFileInput.addEventListener('change', function() {
      var file = wardrobeModalFileInput.files && wardrobeModalFileInput.files[0];
      if (file) handleModalFileSelected(file);
      wardrobeModalFileInput.value = '';
    });
  }

  function handleModalFileSelected(file) {
    var reader = new FileReader();
    reader.onload = function(e) {
      _pendingUpload.dataUrl = e.target.result;
      _pendingUpload.fileName = file.name || 'Photo';
      showModalPreview();
    };
    reader.readAsDataURL(file);
  }

  function showModalPreview() {
    var stepUpload = document.getElementById('wardrobeModalUpload');
    var stepPreview = document.getElementById('wardrobeModalPreview');
    var previewImg = document.getElementById('wardrobePreviewImg');
    if (stepUpload) stepUpload.classList.add('u-hidden');
    if (stepPreview) stepPreview.classList.remove('u-hidden');
    if (previewImg) previewImg.src = _pendingUpload.dataUrl;

    // Mock AI detection
    var categories = ['Tops', 'Bottoms', 'Dresses', 'Outerwear', 'Shoes', 'Accessories'];
    var colors = ['Black', 'White', 'Navy', 'Beige', 'Olive', 'Blush', 'Brown', 'Grey'];
    var styles = ['Casual', 'Minimal', 'Street', 'Classic', 'Sporty', 'Bohemian'];
    var materials = ['Cotton', 'Denim', 'Leather', 'Silk', 'Wool blend', 'Linen', 'Polyester'];
    var occasions = ['Casual', 'Work', 'Evening', 'Weekend', 'Travel'];

    var detected = {
      category: categories[Math.floor(Math.random() * categories.length)],
      color: colors[Math.floor(Math.random() * colors.length)],
      style: styles[Math.floor(Math.random() * styles.length)],
      material: materials[Math.floor(Math.random() * materials.length)],
      occasions: [occasions[Math.floor(Math.random() * occasions.length)], occasions[Math.floor(Math.random() * occasions.length)]]
    };
    // Dedupe occasions
    detected.occasions = detected.occasions.filter(function(v, i, a) { return a.indexOf(v) === i; });

    var catEl = document.getElementById('detectedCategory');
    var colorEl = document.getElementById('detectedColor');
    var styleEl = document.getElementById('detectedStyle');
    var materialEl = document.getElementById('detectedMaterial');
    var occasionsEl = document.getElementById('detectedOccasions');
    if (catEl) catEl.textContent = detected.category;
    if (colorEl) colorEl.textContent = detected.color;
    if (styleEl) styleEl.textContent = detected.style;
    if (materialEl) materialEl.textContent = detected.material;
    if (occasionsEl) occasionsEl.textContent = detected.occasions.join(', ');

    _pendingUpload.detected = detected;
  }

  // Save button
  if (wardrobeModalSave) {
    wardrobeModalSave.addEventListener('click', function() {
      var d = _pendingUpload.detected;
      if (!d) return;
      saveWardrobeItem({
        category: d.category,
        imageDataUrl: _pendingUpload.dataUrl,
        name: _pendingUpload.fileName,
        color: d.color,
        styleVibe: d.style,
        material: d.material,
        occasions: d.occasions.join(', '),
        notes: ''
      });
      // Show saved step
      var stepPreview = document.getElementById('wardrobeModalPreview');
      var stepSaved = document.getElementById('wardrobeModalSaved');
      if (stepPreview) stepPreview.classList.add('u-hidden');
      if (stepSaved) stepSaved.classList.remove('u-hidden');
    });
  }

  // Retake button
  if (wardrobeModalRetake) {
    wardrobeModalRetake.addEventListener('click', function() {
      var stepUpload = document.getElementById('wardrobeModalUpload');
      var stepPreview = document.getElementById('wardrobeModalPreview');
      if (stepPreview) stepPreview.classList.add('u-hidden');
      if (stepUpload) stepUpload.classList.remove('u-hidden');
      _pendingUpload = { dataUrl: '', fileName: '' };
    });
  }

  // Done button
  if (wardrobeModalDone) {
    wardrobeModalDone.addEventListener('click', function() {
      closeWardrobeModal();
      renderWardrobeView();
    });
  }

  console.log('WUTT Chat initialized');
}

/* ---- Wardrobe helpers ---- */

/** Get all wardrobe items from localStorage */
function getWardrobeItems() {
  try {
    return JSON.parse(localStorage.getItem(userKey('wutt_wardrobe_items')) || '[]');
  } catch (e) { return []; }
}

/* ---- Chat preferences — theme & background ---- */

/** Get saved chat preferences, with defaults */
function getChatPreferences() {
  try {
    var saved = JSON.parse(localStorage.getItem(userKey('wutt_chat_preferences')));
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
  localStorage.setItem(userKey('wutt_chat_preferences'), JSON.stringify(prefs));
}

/* ---- Chat history — conversation context ---- */

/** Get chat history from localStorage */
function getChatHistory() {
  try {
    return JSON.parse(localStorage.getItem(userKey('wutt_chat_history')) || '[]');
  } catch (e) { return []; }
}

/** Save chat history to localStorage */
function saveChatHistory(history) {
  // Keep only last 20 messages to avoid localStorage bloat
  var trimmed = history.slice(-20);
  localStorage.setItem(userKey('wutt_chat_history'), JSON.stringify(trimmed));
}

/** Add a message to chat history */
function addToChatHistory(role, content) {
  var history = getChatHistory();
  history.push({ role: role, content: content });
  saveChatHistory(history);
}

/** Clear chat history */
function clearChatHistory() {
  localStorage.removeItem(userKey('wutt_chat_history'));
  console.log('[WUTT] Chat history cleared');
}

/** Apply saved preferences to the chat UI */
function applyChatPreferences() {
  var prefs = getChatPreferences();
  var app = document.getElementById('chatApp');
  if (!app) return;

  // Remove old mood classes
  app.classList.remove('chat-app--night');

  // Apply mood
  if (prefs.mood === 'night') {
    app.classList.add('chat-app--night');
  }

  // Sync mood toggle state
  var moodToggleBtn = document.getElementById('moodToggleBtn');
  if (moodToggleBtn) {
    var isNight = prefs.mood === 'night';
    moodToggleBtn.setAttribute('aria-checked', isNight ? 'true' : 'false');
  }
}

/* ---- User Profile ---- */

/** Gender/style label map */
var GENDER_LABELS = {
  'female': 'Female',
  'male': 'Male',
  'unisex': 'Unisex',
  'prefer-not': 'Prefer not to say'
};

/** Skin tone label map */
var SKIN_LABELS = {
  'fair': 'Fair',
  'light': 'Light',
  'medium': 'Medium',
  'olive': 'Olive',
  'tan': 'Tan',
  'brown': 'Brown',
  'dark': 'Dark'
};

/** Body shape label map */
var BODY_SHAPE_LABELS = {
  'slim': 'Slim',
  'athletic': 'Athletic',
  'average': 'Average',
  'curvy': 'Curvy',
  'plus': 'Plus'
};

/** Shopping style label map */
var SHOPPING_STYLE_LABELS = {
  'local-markets': 'Local Markets',
  'online': 'Online',
  'malls': 'Malls',
  'thrift': 'Thrift',
  'boutique': 'Boutique'
};

/** Skin tone background colors for swatches */
var SKIN_TONE_COLORS = {
  'fair': '#FDEBD0',
  'light': '#F5CBA7',
  'medium': '#E0B38A',
  'olive': '#C4A76C',
  'tan': '#B5815E',
  'brown': '#8D5E3C',
  'dark': '#5D3A1A'
};

/** Fit preference labels */
var FIT_LABELS = {
  'oversized': 'Oversized',
  'regular': 'Regular',
  'slim': 'Slim'
};

/** Outfit vibe labels */
var VIBE_LABELS = {
  'simple': 'Simple',
  'confident': 'Confident',
  'soft': 'Soft',
  'statement': 'Statement'
};

/** Budget range labels */
var BUDGET_LABELS = {
  'under-30k': 'Under 30k Ks',
  '30k-80k': '30k – 80k Ks',
  '80k-150k': '80k – 150k Ks',
  '150k-plus': '150k+ Ks'
};

/** Shopping preference labels */
var SHOPPING_PREF_LABELS = {
  'wardrobe-first': 'Use wardrobe first',
  'shop-missing': 'Shop missing pieces'
};

/** Style quiz labels (for display) */
var STYLE_LABELS = {
  'minimal': 'Minimal',
  'streetwear': 'Streetwear',
  'old-money': 'Old Money',
  'clean-fit': 'Clean Fit',
  'korean-casual': 'Korean Casual',
  'vintage': 'Vintage',
  'y2k': 'Y2K',
  'dark-academia': 'Dark Academia'
};

/** Preferred color display colors */
var PREF_COLOR_MAP = {
  'black': '#1a1a1a',
  'white': '#f5f5f5',
  'beige': '#E8DCC8',
  'navy': '#253A82',
  'brown': '#8B6F47',
  'olive': '#6B7B3A',
  'blush': '#E8B4B8',
  'grey': '#9E9E9E'
};

/** Get user profile from localStorage */
function getUserProfile() {
  try {
    var saved = JSON.parse(localStorage.getItem(userKey('wutt_user_profile')));
    if (saved && typeof saved === 'object') return saved;
  } catch (e) { /* ignore */ }
  return {
    name: '', gender: '', height: '',
    topSize: '', bottomSize: '', shoeSize: '',
    skinTone: '', city: '', area: '', shoppingStyle: '',
    fitPreference: '', outfitVibe: '',
    preferredColors: [], budgetRange: '',
    favoriteShops: '', preferredCategories: [],
    shoppingPreference: '', favoriteStyles: []
  };
}

/** Save user profile to localStorage */
function saveUserProfile(profile) {
  localStorage.setItem(userKey('wutt_user_profile'), JSON.stringify(profile));
}

/** Render the profile view card and sections */
function renderProfileView() {
  var profile = getUserProfile();
  var user = getCurrentUser();

  // Sidebar avatars
  var initial = profile.name ? profile.name.charAt(0).toUpperCase() : (user ? user.charAt(0).toUpperCase() : '?');
  var avatarEl = document.getElementById('profileCardAvatar');
  if (avatarEl) avatarEl.textContent = initial;
  var editAvatar = document.getElementById('profileEditAvatar');
  if (editAvatar) editAvatar.textContent = initial;

  // Sidebar name + email
  var nameEl = document.getElementById('profileCardName');
  if (nameEl) nameEl.textContent = profile.name || 'Your Name';
  var emailEl = document.getElementById('profileCardEmail');
  if (emailEl) emailEl.textContent = user || '';

  // Sidebar badges
  var styleTag = document.getElementById('profileCardStyle');
  if (styleTag) styleTag.textContent = profile.gender ? (GENDER_LABELS[profile.gender] || profile.gender) : '—';
  var cityTag = document.getElementById('profileCardCity');
  if (cityTag) cityTag.textContent = profile.city ? (profile.city + (profile.area ? ', ' + profile.area : '')) : '—';

  // Public Profile section
  var name2 = document.getElementById('profileCardName2');
  if (name2) name2.textContent = profile.name || '—';
  var genderEl = document.getElementById('profileCardGender');
  if (genderEl) genderEl.textContent = profile.gender ? (GENDER_LABELS[profile.gender] || profile.gender) : '—';
  var locEl = document.getElementById('profileCardLocation');
  if (locEl) locEl.textContent = profile.city ? (profile.city + (profile.area ? ', ' + profile.area : '')) : '—';

  // Style Identity
  var savedStyles = [];
  try { savedStyles = JSON.parse(localStorage.getItem(userKey('wutt_styles'))) || []; } catch (e) { /* ignore */ }
  var styleTagsEl = document.getElementById('profileCardStyleTags');
  if (styleTagsEl) {
    if (savedStyles.length > 0) {
      styleTagsEl.innerHTML = savedStyles.map(function(s) {
        return '<span class="pf-tag pf-tag--active">' + escapeHtml(STYLE_LABELS[s] || s) + '</span>';
      }).join('');
    } else {
      styleTagsEl.innerHTML = '<span class="pf-tag pf-tag--empty">Complete the style quiz to set preferences</span>';
    }
  }

  var favStylesEl = document.getElementById('profileCardFavoriteStyles');
  if (favStylesEl) {
    var favStyles = profile.favoriteStyles || [];
    if (favStyles.length > 0) {
      favStylesEl.innerHTML = favStyles.map(function(s) {
        return '<span class="pf-tag pf-tag--active">' + escapeHtml(STYLE_LABELS[s] || s) + '</span>';
      }).join('');
    } else {
      favStylesEl.innerHTML = '<span class="pf-tag pf-tag--empty">—</span>';
    }
  }

  var prefColorsEl = document.getElementById('profileCardPreferredColors');
  if (prefColorsEl) {
    var prefColors = profile.preferredColors || [];
    if (prefColors.length > 0) {
      prefColorsEl.innerHTML = prefColors.map(function(c) {
        var bg = PREF_COLOR_MAP[c] || '#ccc';
        var border = c === 'white' ? 'border: 1px solid #ddd; ' : '';
        return '<span class="pf-color-chip" style="background:' + bg + '; ' + border + 'width:22px; height:22px;" title="' + escapeHtml(c) + '"></span>';
      }).join('');
    } else {
      prefColorsEl.innerHTML = '<span class="pf-color-empty">—</span>';
    }
  }

  var vibeVal = document.getElementById('profileCardOutfitVibe');
  if (vibeVal) vibeVal.textContent = profile.outfitVibe ? (VIBE_LABELS[profile.outfitVibe] || profile.outfitVibe) : '—';

  // Shopping Preferences
  var budgetVal = document.getElementById('profileCardBudgetRange');
  if (budgetVal) budgetVal.textContent = profile.budgetRange ? (BUDGET_LABELS[profile.budgetRange] || profile.budgetRange) : '—';
  var shopsVal = document.getElementById('profileCardFavoriteShops');
  if (shopsVal) shopsVal.textContent = profile.favoriteShops || '—';
  var shopStyleVal = document.getElementById('profileCardShoppingStyle');
  if (shopStyleVal) shopStyleVal.textContent = profile.shoppingStyle ? (SHOPPING_STYLE_LABELS[profile.shoppingStyle] || profile.shoppingStyle) : '—';
  var shopPrefVal = document.getElementById('profileCardShoppingPreference');
  if (shopPrefVal) shopPrefVal.textContent = profile.shoppingPreference ? (SHOPPING_PREF_LABELS[profile.shoppingPreference] || profile.shoppingPreference) : '—';

  // Sizes & Fit
  var heightVal = document.getElementById('profileCardHeight');
  if (heightVal) heightVal.textContent = profile.height || '—';
  var topSizeVal = document.getElementById('profileCardTopSize');
  if (topSizeVal) topSizeVal.textContent = profile.topSize || '—';
  var bottomSizeVal = document.getElementById('profileCardBottomSize');
  if (bottomSizeVal) bottomSizeVal.textContent = profile.bottomSize || '—';
  var shoeSizeVal = document.getElementById('profileCardShoeSize');
  if (shoeSizeVal) shoeSizeVal.textContent = profile.shoeSize || '—';
  var fitPrefVal = document.getElementById('profileCardFitPreference');
  if (fitPrefVal) fitPrefVal.textContent = profile.fitPreference ? (FIT_LABELS[profile.fitPreference] || profile.fitPreference) : '—';
  var skinVal = document.getElementById('profileCardSkinTone');
  if (skinVal) skinVal.textContent = profile.skinTone ? (SKIN_LABELS[profile.skinTone] || profile.skinTone) : '—';

  var prefColors2El = document.getElementById('profileCardPrefColors2');
  if (prefColors2El) {
    var prefColors2 = profile.preferredColors || [];
    if (prefColors2.length > 0) {
      prefColors2El.innerHTML = prefColors2.map(function(c) {
        var bg = PREF_COLOR_MAP[c] || '#ccc';
        var border = c === 'white' ? 'border: 1px solid #ddd; ' : '';
        return '<span class="pf-color-chip" style="background:' + bg + '; ' + border + 'width:22px; height:22px;" title="' + escapeHtml(c) + '"></span>';
      }).join('');
    } else {
      prefColors2El.innerHTML = '<span class="pf-color-empty">—</span>';
    }
  }

  var budget2Val = document.getElementById('profileCardBudgetRange2');
  if (budget2Val) budget2Val.textContent = profile.budgetRange ? (BUDGET_LABELS[profile.budgetRange] || profile.budgetRange) : '—';

  // Wardrobe Summary + Sidebar stats
  var wardrobeItems = getWardrobeItems();
  var uniqueCats = {};
  var uniqueColors = {};
  wardrobeItems.forEach(function(item) {
    if (item.category) uniqueCats[item.category] = true;
    if (item.color) uniqueColors[item.color] = true;
  });

  // Sidebar stats
  var sc = document.getElementById('profileCardWardrobeCount');
  if (sc) sc.textContent = wardrobeItems.length;
  var ss = document.getElementById('profileCardWardrobeCats');
  if (ss) ss.textContent = Object.keys(uniqueCats).length;
  var sd = document.getElementById('profileCardWardrobeColors');
  if (sd) sd.textContent = Object.keys(uniqueColors).length;

  // Main section stats
  var lc = document.getElementById('profileCardWardrobeCountLg');
  if (lc) lc.textContent = wardrobeItems.length;
  var ls = document.getElementById('profileCardWardrobeCatsLg');
  if (ls) ls.textContent = Object.keys(uniqueCats).length;
  var ld = document.getElementById('profileCardWardrobeColorsLg');
  if (ld) ld.textContent = Object.keys(uniqueColors).length;

  var wardrobeHint = document.getElementById('profileCardWardrobeHint');
  if (wardrobeHint) {
    if (wardrobeItems.length === 0) {
      wardrobeHint.textContent = 'Add items through the chat to build your wardrobe.';
    } else {
      wardrobeHint.textContent = wardrobeItems.length + ' item' + (wardrobeItems.length !== 1 ? 's' : '') + ' in your wardrobe.';
    }
  }

  // Photo upload
  renderProfilePhoto();
}

/** Render profile photo from localStorage */
function renderProfilePhoto() {
  var photoData = localStorage.getItem(userKey('wutt_profile_photo'));
  var img = document.getElementById('profilePhotoImg');
  var avatar = document.getElementById('profileCardAvatar');
  var editAvatar = document.getElementById('profileEditAvatar');

  if (photoData) {
    if (img) { img.src = photoData; img.classList.remove('u-hidden'); }
    if (editAvatar) {
      editAvatar.style.backgroundImage = 'url(' + photoData + ')';
      editAvatar.style.backgroundSize = 'cover';
      editAvatar.style.backgroundPosition = 'center';
      editAvatar.textContent = '';
    }
  } else {
    if (img) { img.src = ''; img.classList.add('u-hidden'); }
    if (editAvatar) {
      editAvatar.style.backgroundImage = '';
      var profile = getUserProfile();
      var user = getCurrentUser();
      editAvatar.textContent = profile.name ? profile.name.charAt(0).toUpperCase() : (user ? user.charAt(0).toUpperCase() : '?');
    }
  }
}

/** Wire chip-row and size-pill single-select groups */
function wireSingleSelectGroup(containerId, activeClass) {
  var container = document.getElementById(containerId);
  if (!container) return;
  container.addEventListener('click', function(e) {
    var chip = e.target.closest('[data-value]');
    if (!chip) return;
    container.querySelectorAll('[data-value]').forEach(function(c) { c.classList.remove(activeClass); });
    chip.classList.add(activeClass);
  });
}

/** Wire multi-select chip group (toggle on/off) */
function wireMultiSelectGroup(containerId, activeClass) {
  var container = document.getElementById(containerId);
  if (!container) return;
  container.addEventListener('click', function(e) {
    var chip = e.target.closest('[data-value]');
    if (!chip) return;
    chip.classList.toggle(activeClass);
  });
}

/** Wire skin tone swatches */
function wireSkinToneSwatches() {
  var container = document.getElementById('profileSkinToneSwatches');
  var label = document.getElementById('profileSkinToneName');
  if (!container) return;
  container.addEventListener('click', function(e) {
    var chip = e.target.closest('.pf-tone-chip');
    if (!chip) return;
    container.querySelectorAll('.pf-tone-chip').forEach(function(c) { c.classList.remove('pf-tone-chip--active'); });
    chip.classList.add('pf-tone-chip--active');
    if (label) label.textContent = SKIN_LABELS[chip.getAttribute('data-value')] || '—';
  });
}

/** Set active chip in a group by value */
function setActiveChipInGroup(containerId, activeClass, value) {
  var container = document.getElementById(containerId);
  if (!container || !value) return;
  container.querySelectorAll('[data-value]').forEach(function(c) {
    c.classList.toggle(activeClass, c.getAttribute('data-value') === value);
  });
}

/** Get selected value from a chip/pill group */
function getSelectedValue(containerId, activeClass) {
  var container = document.getElementById(containerId);
  if (!container) return '';
  var active = container.querySelector('.' + activeClass);
  return active ? active.getAttribute('data-value') || '' : '';
}

/** Load edit form with saved data */
function loadProfileForm() {
  var profile = getUserProfile();

  // Text inputs
  var fields = ['profileName', 'profileHeight', 'profileShoeSize', 'profileCity', 'profileArea', 'profileFavoriteShops'];
  var keys = ['name', 'height', 'shoeSize', 'city', 'area', 'favoriteShops'];
  fields.forEach(function(id, i) {
    var el = document.getElementById(id);
    if (el) el.value = profile[keys[i]] || '';
  });

  // Single-select chip groups
  setActiveChipInGroup('profileGenderChips', 'pf-chip--active', profile.gender);
  setActiveChipInGroup('profileTopSizePills', 'pf-size-pill--active', profile.topSize);
  setActiveChipInGroup('profileBottomSizePills', 'pf-size-pill--active', profile.bottomSize);
  setActiveChipInGroup('profileShoppingStyleChips', 'pf-chip--active', profile.shoppingStyle);
  setActiveChipInGroup('profileFitPreferenceChips', 'pf-chip--active', profile.fitPreference);
  setActiveChipInGroup('profileOutfitVibeChips', 'pf-chip--active', profile.outfitVibe);
  setActiveChipInGroup('profileBudgetRangeChips', 'pf-chip--active', profile.budgetRange);
  setActiveChipInGroup('profileShoppingPrefChips', 'pf-chip--active', profile.shoppingPreference);

  // Multi-select: favorite styles
  var favStylesContainer = document.getElementById('profileFavoriteStylesChips');
  if (favStylesContainer) {
    var favStyles = profile.favoriteStyles || [];
    favStylesContainer.querySelectorAll('[data-value]').forEach(function(c) {
      c.classList.toggle('pf-chip--active', favStyles.indexOf(c.getAttribute('data-value')) !== -1);
    });
  }

  // Multi-select: preferred colors
  var prefColorsContainer = document.getElementById('profilePreferredColorsChips');
  if (prefColorsContainer) {
    var prefColors = profile.preferredColors || [];
    prefColorsContainer.querySelectorAll('[data-value]').forEach(function(c) {
      c.classList.toggle('pf-color-chip--active', prefColors.indexOf(c.getAttribute('data-value')) !== -1);
    });
  }

  // Multi-select: preferred categories
  var catsContainer = document.getElementById('profileCategoriesChips');
  if (catsContainer) {
    var cats = profile.preferredCategories || [];
    catsContainer.querySelectorAll('[data-value]').forEach(function(c) {
      c.classList.toggle('pf-chip--active', cats.indexOf(c.getAttribute('data-value')) !== -1);
    });
  }

  // Skin tone swatches
  var toneContainer = document.getElementById('profileSkinToneSwatches');
  var toneLabel = document.getElementById('profileSkinToneName');
  if (toneContainer) {
    toneContainer.querySelectorAll('.pf-tone-chip').forEach(function(c) {
      c.classList.toggle('pf-tone-chip--active', c.getAttribute('data-value') === profile.skinTone);
    });
  }
  if (toneLabel) toneLabel.textContent = profile.skinTone ? (SKIN_LABELS[profile.skinTone] || profile.skinTone) : '—';
}

/** Save profile from edit form */
function saveProfileForm() {
  var profile = {
    name: (document.getElementById('profileName') || {}).value.trim() || '',
    gender: getSelectedValue('profileGenderChips', 'pf-chip--active'),
    height: (document.getElementById('profileHeight') || {}).value.trim() || '',
    topSize: getSelectedValue('profileTopSizePills', 'pf-size-pill--active'),
    bottomSize: getSelectedValue('profileBottomSizePills', 'pf-size-pill--active'),
    shoeSize: (document.getElementById('profileShoeSize') || {}).value.trim() || '',
    skinTone: getSelectedValue('profileSkinToneSwatches', 'pf-tone-chip--active'),
    city: (document.getElementById('profileCity') || {}).value.trim() || '',
    area: (document.getElementById('profileArea') || {}).value.trim() || '',
    shoppingStyle: getSelectedValue('profileShoppingStyleChips', 'pf-chip--active'),
    fitPreference: getSelectedValue('profileFitPreferenceChips', 'pf-chip--active'),
    outfitVibe: getSelectedValue('profileOutfitVibeChips', 'pf-chip--active'),
    preferredColors: getMultiSelectValues('profilePreferredColorsChips', 'pf-color-chip--active'),
    budgetRange: getSelectedValue('profileBudgetRangeChips', 'pf-chip--active'),
    favoriteShops: (document.getElementById('profileFavoriteShops') || {}).value.trim() || '',
    preferredCategories: getMultiSelectValues('profileCategoriesChips', 'pf-chip--active'),
    shoppingPreference: getSelectedValue('profileShoppingPrefChips', 'pf-chip--active'),
    favoriteStyles: getMultiSelectValues('profileFavoriteStylesChips', 'pf-chip--active')
  };
  saveUserProfile(profile);
  showToast('Profile saved', 'success');
}

/** Get all selected values from a multi-select chip group */
function getMultiSelectValues(containerId, activeClass) {
  var container = document.getElementById(containerId);
  if (!container) return [];
  var values = [];
  container.querySelectorAll('.' + activeClass).forEach(function(c) {
    var v = c.getAttribute('data-value');
    if (v) values.push(v);
  });
  return values;
}

/** Save a wardrobe item to localStorage */
function saveWardrobeItem(item) {
  var items = getWardrobeItems();
  item.id = Date.now();
  item.createdAt = new Date().toISOString();
  items.push(item);
  localStorage.setItem(userKey('wutt_wardrobe_items'), JSON.stringify(items));
  renderWardrobeSidebar();
  // Also refresh wardrobe page if visible
  var wv = document.getElementById('wardrobeView');
  if (wv && !wv.classList.contains('u-hidden')) renderWardrobeView();
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

    // Real AI analysis via backend
    var token = localStorage.getItem('wutt_token');
    var headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;

    fetch(CONFIG.API_BASE + '/stylist/analyze', {
      method: 'POST',
      headers: headers,
      credentials: 'include',
      body: JSON.stringify({
        image_data: img,
        mime_type: 'image/jpeg',
      }),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      clearInterval(interval);
      analyzing.remove();

      if (data.status === 'success' && data.data) {
        showAnalysisCard(cat, img, fname, data.data);
      } else {
        // Vision failed — show error
        var errMsg = document.createElement('div');
        errMsg.className = 'chat-msg chat-msg--bot';
        errMsg.innerHTML = '<div class="chat-msg__bubble"><p class="chat-msg__error">'
          + '⚠️ ' + escapeHtml(data.message || 'AI analysis unavailable. Please check API key or quota.')
          + '</p></div>';
        var messagesEl = document.getElementById('chatMessages');
        if (messagesEl) messagesEl.appendChild(errMsg);
      }
      scrollChatToBottom();
    })
    .catch(function(err) {
      console.error('[WUTT] Vision analysis error:', err);
      clearInterval(interval);
      analyzing.remove();
      var errMsg = document.createElement('div');
      errMsg.className = 'chat-msg chat-msg--bot';
      errMsg.innerHTML = '<div class="chat-msg__bubble"><p class="chat-msg__error">'
        + '⚠️ Connection error. Please check your connection and try again.'
        + '</p></div>';
      var messagesEl = document.getElementById('chatMessages');
      if (messagesEl) messagesEl.appendChild(errMsg);
      scrollChatToBottom();
    });
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
function deleteWardrobeItem(itemId) {
  var items = getWardrobeItems();
  items = items.filter(function(item) { return item.id !== itemId; });
  localStorage.setItem(userKey('wutt_wardrobe_items'), JSON.stringify(items));
  renderWardrobeSidebar();
  // Also refresh wardrobe page if visible
  var wv = document.getElementById('wardrobeView');
  if (wv && !wv.classList.contains('u-hidden')) renderWardrobeView();
}

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
      '</div>' +
      '<button class="sidebar-wardrobe__delete" data-delete-id="' + item.id + '" aria-label="Delete item" type="button">' +
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
      '</button>' +
    '</div>';
  });
  html += '</div>';

  container.innerHTML = html;

  // Wire delete buttons
  container.querySelectorAll('.sidebar-wardrobe__delete').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      var itemId = parseInt(btn.getAttribute('data-delete-id'), 10);
      deleteWardrobeItem(itemId);
    });
  });
}

/** Render wardrobe full page view */
function renderWardrobeView() {
  var grid = document.getElementById('wardrobeGrid');
  var empty = document.getElementById('wardrobeEmpty');
  if (!grid) return;

  var items = getWardrobeItems();

  // Show/hide empty state
  if (empty) empty.style.display = items.length ? 'none' : '';

  // Render cards
  var html = '';
  items.forEach(function(item) {
    var imgHtml = '';
    if (item.imageDataUrl) {
      imgHtml = '<img class="wardrobe-card__img" src="' + item.imageDataUrl + '" alt="' + escapeHtml(item.name || item.category || '') + '">';
    } else {
      imgHtml = '<div class="wardrobe-card__img wardrobe-card__img--placeholder">' +
        '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg></div>';
    }

    var colorHex = PREF_COLOR_MAP[item.color] || '';
    var colorDot = colorHex
      ? '<span class="wardrobe-card__color-dot" style="background:' + colorHex + '"></span>'
      : '';

    var metaParts = [item.category];
    if (item.styleVibe) metaParts.push(item.styleVibe);

    html += '<div class="wardrobe-card" data-category="' + escapeHtml(item.category || '') + '">' +
      imgHtml +
      '<div class="wardrobe-card__info">' +
        '<div class="wardrobe-card__name">' + escapeHtml(item.name || item.category || 'Untitled') + '</div>' +
        '<div class="wardrobe-card__meta">' + colorDot + escapeHtml(metaParts.join(' · ')) + '</div>' +
      '</div>' +
    '</div>';
  });

  // Keep empty state node, replace cards only
  if (empty) {
    grid.innerHTML = '';
    grid.appendChild(empty);
  }
  grid.insertAdjacentHTML('beforeend', html);

  // Wire filter chips
  var filterContainer = document.getElementById('wardrobeFilters');
  if (filterContainer) {
    filterContainer.querySelectorAll('.wardrobe-view__filter').forEach(function(btn) {
      btn.addEventListener('click', function() {
        filterContainer.querySelectorAll('.wardrobe-view__filter').forEach(function(b) { b.classList.remove('wardrobe-view__filter--active'); });
        btn.classList.add('wardrobe-view__filter--active');
        var filter = btn.getAttribute('data-filter');
        grid.querySelectorAll('.wardrobe-card').forEach(function(card) {
          if (filter === 'all' || card.getAttribute('data-category').toLowerCase() === filter) {
            card.style.display = '';
          } else {
            card.style.display = 'none';
          }
        });
      });
    });
  }

  // Wire search
  var searchInput = document.getElementById('wardrobeSearchInput');
  if (searchInput) {
    searchInput.value = '';
    searchInput.addEventListener('input', function() {
      var q = searchInput.value.toLowerCase();
      grid.querySelectorAll('.wardrobe-card').forEach(function(card) {
        var text = card.textContent.toLowerCase();
        card.style.display = text.indexOf(q) !== -1 ? '' : 'none';
      });
    });
  }
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
