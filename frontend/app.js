/* ============================================================
   WUTT — AI Personal Stylist (Myanmar) — Frontend Logic
   Vanilla JS, no frameworks. Async/await, try/catch always.
   ============================================================ */

/* --------------------------------------------------------
   Config
   -------------------------------------------------------- */
const CONFIG = {
  API_BASE: 'https://wutt-api.onrender.com',
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

// Modals — Register
const registerOverlay = $('#registerModalOverlay');
const registerModal = $('#registerModal');
const registerForm = $('#registerForm');
const registerFormError = $('#registerFormError');
const registerSubmitBtn = $('#registerSubmitBtn');
const registerPasswordToggle = $('#registerPasswordToggle');
const registerConfirmPasswordToggle = $('#registerConfirmPasswordToggle');

// Toast
const toastContainer = $('#toastContainer');

// Triggers
const navLoginBtn = $('#navLoginBtn');
const navGetStartedBtn = $('#navGetStartedBtn');
const heroGetStartedBtn = $('#heroGetStartedBtn');
const heroLearnMoreBtn = $('#heroLearnMoreBtn');

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

navbarToggle.addEventListener('click', toggleMobileNav);

// Close mobile nav when a link is clicked
navbarNav.querySelectorAll('a, button').forEach((el) => {
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

// Open login
function openLoginModal() {
  closeModal(registerOverlay);
  openModal(loginOverlay);
}

// Open register
function openRegisterModal() {
  closeModal(loginOverlay);
  openModal(registerOverlay);
}

// Switch between modals
$('#switchToRegister')?.addEventListener('click', openRegisterModal);
$('#switchToLogin')?.addEventListener('click', openLoginModal);

// Modal close buttons
$('#loginModalClose')?.addEventListener('click', () => closeModal(loginOverlay));
$('#registerModalClose')?.addEventListener('click', () => closeModal(registerOverlay));

// Click overlay to close
loginOverlay?.addEventListener('click', (e) => {
  if (e.target === loginOverlay) closeModal(loginOverlay);
});
registerOverlay?.addEventListener('click', (e) => {
  if (e.target === registerOverlay) closeModal(registerOverlay);
});

// Escape key to close
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (loginOverlay.classList.contains('modal-overlay--open')) {
      closeModal(loginOverlay);
    } else if (registerOverlay.classList.contains('modal-overlay--open')) {
      closeModal(registerOverlay);
    }
  }
});

// Navbar / Hero triggers
navLoginBtn?.addEventListener('click', openLoginModal);
navGetStartedBtn?.addEventListener('click', openRegisterModal);
heroGetStartedBtn?.addEventListener('click', openRegisterModal);

// "Learn more" scrolls to features
heroLearnMoreBtn?.addEventListener('click', () => {
  const features = $('#features');
  if (features) {
    features.scrollIntoView({ behavior: 'smooth' });
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
setupPasswordToggle(registerConfirmPasswordToggle, $('#registerConfirmPassword'));

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

/** Validate login form */
function validateLoginForm() {
  let isValid = true;
  clearFormErrors(loginForm);

  const email = $('#loginEmail');
  const password = $('#loginPassword');

  if (!email.value.trim()) {
    showFieldError($('#loginEmailError'), 'အီးမေးလ်ထည့်ပါ');
    email.classList.add('input__field--error');
    isValid = false;
  } else if (!isValidEmail(email.value)) {
    showFieldError($('#loginEmailError'), 'အီးမေးလ်ပုံစံမှန်အောင်ထည့်ပါ');
    email.classList.add('input__field--error');
    isValid = false;
  }

  if (!password.value) {
    showFieldError($('#loginPasswordError'), 'စကားဝှက်ထည့်ပါ');
    password.classList.add('input__field--error');
    isValid = false;
  } else if (password.value.length < 6) {
    showFieldError($('#loginPasswordError'), 'အနည်းဆုံး ၆ လုံးထည့်ပါ');
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
    showFieldError($('#registerEmailError'), 'အီးမေးလ်ထည့်ပါ');
    email.classList.add('input__field--error');
    isValid = false;
  } else if (!isValidEmail(email.value)) {
    showFieldError($('#registerEmailError'), 'အီးမေးလ်ပုံစံမှန်အောင်ထည့်ပါ');
    email.classList.add('input__field--error');
    isValid = false;
  }

  if (!password.value) {
    showFieldError($('#registerPasswordError'), 'စကားဝှက်ထည့်ပါ');
    password.classList.add('input__field--error');
    isValid = false;
  } else if (password.value.length < 6) {
    showFieldError($('#registerPasswordError'), 'အနည်းဆုံး ၆ လုံးထည့်ပါ');
    password.classList.add('input__field--error');
    isValid = false;
  }

  if (!confirmPassword.value) {
    showFieldError($('#registerConfirmPasswordError'), 'စကားဝှက်ပြန်ထည့်ပါ');
    confirmPassword.classList.add('input__field--error');
    isValid = false;
  } else if (confirmPassword.value !== password.value) {
    showFieldError($('#registerConfirmPasswordError'), 'စကားဝှက်မတူညီပါ');
    confirmPassword.classList.add('input__field--error');
    isValid = false;
  }

  return isValid;
}

/** Handle login form submission */
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
      // Defensive token extraction — try every common field name
      const token = data?.data?.token || data?.token || data?.access_token;
      if (!token) {
        toggleHidden(loginFormError, false);
        loginFormError.textContent = 'Server returned success but no token. Please try again.';
        setButtonLoading(loginSubmitBtn, false);
        return;
      }
      localStorage.setItem('wutt_token', token);
      showToast('အကောင့်ဝင်ပြီးပါပြီ။ Dashboard သို့ခေါ်ဆောင်သွားပါမယ်။', 'success');
      closeModal(loginOverlay);
      // Explicit relative redirect — Render serves real files, no SPA rewrite
      setTimeout(() => {
        window.location.href = './dashboard.html';
      }, 800);
    } else {
      toggleHidden(loginFormError, false);
      loginFormError.textContent = data.message || data?.detail?.message || 'အကောင့်ဝင်မှုမအောင်မြင်ပါ။ ထပ်စမ်းကြည့်ပါ။';
    }
  } catch (err) {
    toggleHidden(loginFormError, false);
    loginFormError.textContent = 'ဆာဗာနဲ့ချိတ်ဆက်မှုမအောင်မြင်ပါ။ အင်တာနက်စစ်ဆေးပါ။';
  } finally {
    setButtonLoading(loginSubmitBtn, false);
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
      // Defensive token extraction — try every common field name
      const token = data?.data?.token || data?.token || data?.access_token;
      if (!token) {
        toggleHidden(registerFormError, false);
        registerFormError.textContent = 'Server returned success but no token. Please try again.';
        setButtonLoading(registerSubmitBtn, false);
        return;
      }
      localStorage.setItem('wutt_token', token);
      showToast('အကောင့်ဖွင့်ပြီးပါပြီ။ Dashboard သို့ခေါ်ဆောင်သွားပါမယ်။', 'success');
      closeModal(registerOverlay);
      setTimeout(() => {
        window.location.href = './dashboard.html';
      }, 800);
    } else {
      toggleHidden(registerFormError, false);
      registerFormError.textContent = data.message || data?.detail?.message || 'အကောင့်ဖွင့်မှုမအောင်မြင်ပါ။ ထပ်စမ်းကြည့်ပါ။';
    }
  } catch (err) {
    toggleHidden(registerFormError, false);
    registerFormError.textContent = 'ဆာဗာနဲ့ချိတ်ဆက်မှုမအောင်မြင်ပါ။ အင်တာနက်စစ်ဆေးပါ။';
  } finally {
    setButtonLoading(registerSubmitBtn, false);
  }
}

/* --------------------------------------------------------
   Live Validation (on blur)
   -------------------------------------------------------- */

function setupLiveValidation(inputEl, errorEl, validateFn) {
  if (!inputEl || !errorEl) return;
  inputEl.addEventListener('blur', () => {
    const error = validateFn(inputEl.value);
    if (error) {
      showFieldError(errorEl, error);
      inputEl.classList.add('input__field--error');
    } else {
      hideFieldError(errorEl);
      inputEl.classList.remove('input__field--error');
    }
  });
}

// Login live validation
setupLiveValidation($('#loginEmail'), $('#loginEmailError'), (val) => {
  if (!val.trim()) return 'အီးမေးလ်ထည့်ပါ';
  if (!isValidEmail(val)) return 'အီးမေးလ်ပုံစံမှန်အောင်ထည့်ပါ';
  return null;
});

setupLiveValidation($('#loginPassword'), $('#loginPasswordError'), (val) => {
  if (!val) return 'စကားဝှက်ထည့်ပါ';
  if (val.length < 6) return 'အနည်းဆုံး ၆ လုံးထည့်ပါ';
  return null;
});

// Register live validation
setupLiveValidation($('#registerEmail'), $('#registerEmailError'), (val) => {
  if (!val.trim()) return 'အီးမေးလ်ထည့်ပါ';
  if (!isValidEmail(val)) return 'အီးမေးလ်ပုံစံမှန်အောင်ထည့်ပါ';
  return null;
});

setupLiveValidation($('#registerPassword'), $('#registerPasswordError'), (val) => {
  if (!val) return 'စကားဝှက်ထည့်ပါ';
  if (val.length < 6) return 'အနည်းဆုံး ၆ လုံးထည့်ပါ';
  return null;
});

setupLiveValidation($('#registerConfirmPassword'), $('#registerConfirmPasswordError'), (val) => {
  if (!val) return 'စကားဝှက်ပြန်ထည့်ပါ';
  if (val !== $('#registerPassword')?.value) return 'စကားဝှက်မတူညီပါ';
  return null;
});

/* --------------------------------------------------------
   Event Listeners
   -------------------------------------------------------- */

loginForm?.addEventListener('submit', handleLoginSubmit);
registerForm?.addEventListener('submit', handleRegisterSubmit);

/* --------------------------------------------------------
   Intersection Observer — Animate feature cards on scroll
   -------------------------------------------------------- */
if ('IntersectionObserver' in window) {
  const featureCards = $$('.feature-card');
  if (featureCards.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
          }
        });
      },
      { threshold: 0.2 }
    );

    featureCards.forEach((card) => {
      card.style.opacity = '0';
      card.style.transform = 'translateY(24px)';
      card.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
      observer.observe(card);
    });
  }
}

/* --------------------------------------------------------
   Smooth scroll for all anchor links
   -------------------------------------------------------- */
$$('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener('click', function (e) {
    const targetId = this.getAttribute('href');
    if (targetId === '#') return;
    const target = document.querySelector(targetId);
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  });
});

console.log('WUTT — AI Personal Stylist ready 💫');
