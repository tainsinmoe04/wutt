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
  var registerOverlay = document.getElementById('registerModalOverlay');

  if (!btn)     { console.warn('[WUTT] #navbarLoginBtn not found'); return; }
  if (!overlay) { console.warn('[WUTT] #heroLoginOverlay not found'); return; }

  // Authentication always starts in login mode. Neither overlay is allowed
  // to retain stale active classes across initialization.
  overlay.classList.remove('landing-modal-overlay--open');
  overlay.setAttribute('aria-hidden', 'true');
  if (registerOverlay) {
    registerOverlay.classList.remove('landing-modal-overlay--open');
    registerOverlay.setAttribute('aria-hidden', 'true');
  }

  function open() {
    console.log('WUTT hero login opened');
    if (registerOverlay) {
      registerOverlay.classList.remove('landing-modal-overlay--open');
      registerOverlay.setAttribute('aria-hidden', 'true');
    }
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
      overlay.classList.remove('landing-modal-overlay--open');
      overlay.setAttribute('aria-hidden', 'true');
      if (registerOverlay) {
        registerOverlay.classList.add('landing-modal-overlay--open');
        registerOverlay.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        document.body.classList.add('modal-open');
        var firstInput = registerOverlay.querySelector('input');
        if (firstInput) setTimeout(function() { firstInput.focus(); }, 150);
      }
    });
  }

  // Apple sign-in remains a placeholder until its backend flow exists.
  var appleBtn  = document.getElementById('appleLoginBtn');
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

  if (getStartedBtn) {
    getStartedBtn.addEventListener('click', function(e) {
      e.preventDefault();
      open();
    });
  }

});

/* --------------------------------------------------------
   Auth Persistence — Restore the httpOnly-cookie session on page load
   -------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', async function restoreSession() {
  var oauthCallback = getGoogleOAuthCallback();
  var route = getFrontendRoute();
  appState.initialPanel = route.panel || null;

  if (route.name === 'not-found') {
    showNotFoundPage();
    return;
  }

  try {
    await bootstrapAuthenticatedSession();
    if (oauthCallback.isGoogleCallback) clearGoogleOAuthCallback();
    console.log('[WUTT] Session restored');
    if (oauthCallback.hasSuccess && !hasCompletedOnboarding()) markOnboardingPending();
    var onboardingPending = isOnboardingPending();
    if (!oauthCallback.hasSuccess && !onboardingPending) markOnboardingComplete();
    showMainApp({ showWelcome: !hasCompletedOnboarding() && onboardingPending });
  } catch (err) {
    clearAuth();
    if (err && err.status === 401) {
      try {
        localStorage.removeItem('wutt_last_surface');
        localStorage.removeItem('wutt_last_theme');
      } catch (error) { /* ignore */ }
      document.documentElement.setAttribute('data-wutt-theme', 'day');
    }
    finishInitialLoading();

    if (oauthCallback.hasError) {
      clearGoogleOAuthCallback();
      showGoogleOAuthError(
        oauthCallback.reason === 'configuration'
          ? 'Google sign-in is not available right now. Please use your email and password.'
          : 'Google sign-in wasn’t completed. Please try again.'
      );
      return;
    }

    if (oauthCallback.hasSuccess) {
      clearGoogleOAuthCallback();
      showGoogleOAuthError(
        'Google sign-in could not be verified. Please try again or use your email.'
      );
      return;
    }

    if (err && err.status === 401) return;
    showToast(
      'Could not verify your session. Please check your connection and log in again.',
      'error'
    );
  }
});

/* --------------------------------------------------------
   Optional runtime demo helper
   Static production builds contain no demo credentials.
   -------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', function initDemoLoginHelper() {
  var runtimeConfig = window.WUTT_CONFIG || {};
  var isLocalDevelopment = window.location.hostname === 'localhost'
    || window.location.hostname === '127.0.0.1'
    || window.location.hostname === '[::1]';
  var isEnabled = runtimeConfig.DEMO_LOGIN_ENABLED === true
    || runtimeConfig.DEMO_LOGIN_ENABLED === 'true'
    || isLocalDevelopment;
  var email = typeof runtimeConfig.DEMO_LOGIN_EMAIL === 'string'
    ? runtimeConfig.DEMO_LOGIN_EMAIL.trim()
    : 'demo@wutt.ai';
  var password = typeof runtimeConfig.DEMO_LOGIN_PASSWORD === 'string'
    ? runtimeConfig.DEMO_LOGIN_PASSWORD
    : 'wuttdemo2026';
  var triggers = Array.from(document.querySelectorAll('.demo-access-trigger'));
  var overlay = document.getElementById('demoAccessOverlay');
  var closeButton = document.getElementById('demoAccessClose');
  var continueButton = document.getElementById('demoAccessContinue');
  var status = document.getElementById('demoAccessStatus');
  var activeTrigger = null;

  if (!isEnabled || !email || !password || !triggers.length || !overlay) return;
  triggers.forEach(function(trigger) {
    trigger.classList.remove('u-hidden');
  });

  function closeDemoAccess() {
    overlay.classList.remove('demo-access-overlay--open');
    overlay.setAttribute('aria-hidden', 'true');
    window.setTimeout(function() {
      overlay.classList.add('u-hidden');
      if (activeTrigger) activeTrigger.focus();
    }, 180);
  }

  function openDemoAccess(event) {
    activeTrigger = event.currentTarget;
    var emailEl = document.getElementById('demoAccessEmail');
    var passwordEl = document.getElementById('demoAccessPassword');
    if (emailEl) emailEl.textContent = email;
    if (passwordEl) passwordEl.textContent = password;
    if (status) status.textContent = '';
    overlay.classList.remove('u-hidden');
    overlay.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(function() {
      overlay.classList.add('demo-access-overlay--open');
      if (closeButton) closeButton.focus();
    });
  }

  async function copyDemoValue(value, label) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
      } else {
        var copyField = document.createElement('textarea');
        copyField.value = value;
        copyField.setAttribute('readonly', '');
        copyField.style.position = 'fixed';
        copyField.style.opacity = '0';
        document.body.appendChild(copyField);
        copyField.select();
        document.execCommand('copy');
        copyField.remove();
      }
      if (status) status.textContent = label + ' copied.';
    } catch (error) {
      if (status) status.textContent = 'Select and copy the ' + label.toLowerCase() + ' above.';
    }
  }

  triggers.forEach(function(trigger) {
    trigger.addEventListener('click', openDemoAccess);
  });
  if (closeButton) closeButton.addEventListener('click', closeDemoAccess);
  overlay.addEventListener('click', function(event) {
    if (event.target === overlay) closeDemoAccess();
    var copyButton = event.target.closest('[data-demo-copy]');
    if (!copyButton) return;
    var type = copyButton.getAttribute('data-demo-copy');
    copyDemoValue(type === 'email' ? email : password, type === 'email' ? 'Email' : 'Password');
  });
  document.addEventListener('keydown', function(event) {
    if (!overlay.classList.contains('demo-access-overlay--open')) return;
    if (event.key === 'Escape') {
      closeDemoAccess();
      return;
    }
    if (event.key === 'Tab') {
      var focusable = Array.from(overlay.querySelectorAll('button:not([disabled])'));
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  if (continueButton) {
    continueButton.addEventListener('click', function() {
      var useModalForm = activeTrigger && activeTrigger.id === 'tryDemoModalBtn';
      var emailInput = document.getElementById(useModalForm ? 'loginEmail' : 'heroEmail');
      var passwordInput = document.getElementById(useModalForm ? 'loginPassword' : 'heroPassword');
      var form = document.getElementById(useModalForm ? 'loginForm' : 'heroLoginForm');
      if (emailInput) emailInput.value = email;
      if (passwordInput) passwordInput.value = password;
      closeDemoAccess();
      if (form) form.requestSubmit();
    });
  }
});

/* --------------------------------------------------------
   Auth Helpers
   -------------------------------------------------------- */

/** Persist auth state after successful login/register */
function saveAuth(email, token) {
  appState.token = token || null;
}

/** Read the backend's token-free Google OAuth callback markers. */
function getGoogleOAuthCallback() {
  var params = new URLSearchParams(window.location.search);
  var hasSuccess = params.get('auth') === 'google';
  var hasError = params.get('auth_error') === 'google';
  return {
    hasSuccess: hasSuccess,
    hasError: hasError,
    reason: params.get('auth_reason') || '',
    isGoogleCallback: hasSuccess || hasError,
  };
}

/** Remove handled OAuth markers without reloading or disturbing other query parameters. */
function clearGoogleOAuthCallback() {
  var url = new URL(window.location.href);
  url.searchParams.delete('auth');
  url.searchParams.delete('auth_error');
  url.searchParams.delete('auth_reason');
  window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
}

/** Present an OAuth failure in the existing accessible login dialog. */
function showGoogleOAuthError(message) {
  var overlay = document.getElementById('heroLoginOverlay');
  var errorEl = document.getElementById('heroFormError');
  if (!overlay || !errorEl) {
    showToast(message, 'error');
    return;
  }

  overlay.classList.add('landing-modal-overlay--open');
  overlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  document.body.classList.add('modal-open');
  errorEl.textContent = message;
  errorEl.classList.remove('u-hidden');
  errorEl.focus();
}

/** Start the server-managed Google OAuth flow with no token in frontend storage. */
function startGoogleOAuth(e) {
  e.preventDefault();
  var button = e.currentTarget;
  if (!button || button.getAttribute('aria-busy') === 'true') return;

  button.setAttribute('aria-busy', 'true');
  setButtonLoading(button, true);
  window.location.assign(CONFIG.API_BASE + '/auth/google/start');
}

/** Clear authentication state without touching non-sensitive UI preferences. */
function clearAuth() {
  appState.token = null;
  appState.user = null;
  appState.profile = emptyUserProfile();
  appState.wardrobe = [];
}

/** End the server session before clearing in-memory authentication state. */
async function handleLogout(e) {
  var button = e?.currentTarget;
  if (button?.getAttribute('aria-busy') === 'true') return;

  if (button) {
    button.setAttribute('aria-busy', 'true');
    button.disabled = true;
  }

  try {
    await apiRequest('/auth/logout', { method: 'POST' });
    clearAuth();
    try {
      localStorage.removeItem('wutt_last_surface');
      localStorage.removeItem('wutt_last_theme');
    } catch (error) { /* ignore */ }
    window.location.replace(window.location.pathname || '/');
  } catch (error) {
    if (button) {
      button.removeAttribute('aria-busy');
      button.disabled = false;
    }
    showToast(error.message || 'Could not log out. Please try again.', 'error');
  }
}

/* --------------------------------------------------------
   User-Scoped UI Preference Helpers
   -------------------------------------------------------- */

/** Get current user email for scoping */
function getCurrentUser() {
  return appState.user?.email || null;
}

/** Get user-scoped localStorage key */
function userKey(key) {
  var userId = appState.user?.id;
  return userId ? key + '_' + userId : key;
}

/** Keep onboarding separate from the server-managed authentication session. */
function hasCompletedOnboarding() {
  if (!appState.user) return false;
  try {
    return localStorage.getItem(userKey('wutt_onboarding_complete')) === 'true';
  } catch (error) {
    return false;
  }
}

function markOnboardingComplete() {
  if (!appState.user) return;
  try {
    localStorage.setItem(userKey('wutt_onboarding_complete'), 'true');
    localStorage.removeItem(userKey('wutt_onboarding_pending'));
  } catch (error) { /* The app remains usable when storage is unavailable. */ }
}

function isOnboardingPending() {
  if (!appState.user) return false;
  try {
    return localStorage.getItem(userKey('wutt_onboarding_pending')) === 'true';
  } catch (error) {
    return false;
  }
}

function markOnboardingPending() {
  if (!appState.user || hasCompletedOnboarding()) return;
  try {
    localStorage.setItem(userKey('wutt_onboarding_pending'), 'true');
  } catch (error) { /* The current sign-in can still continue without storage. */ }
}

function getLastAppPanel() {
  if (!appState.user) return 'home';
  try {
    var panel = localStorage.getItem(userKey('wutt_current_panel'));
    return ['home', 'wardrobe', 'profile', 'wishlist'].indexOf(panel) !== -1 ? panel : 'home';
  } catch (error) {
    return 'home';
  }
}

function saveLastAppPanel(panel) {
  if (!appState.user || ['home', 'wardrobe', 'profile', 'wishlist'].indexOf(panel) === -1) return;
  try {
    localStorage.setItem(userKey('wutt_current_panel'), panel);
    localStorage.setItem('wutt_last_surface', panel === 'home' ? 'stylist' : panel);
  } catch (error) { /* Navigation does not depend on persistent storage. */ }
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
   Authenticated API client and server-backed app state
   -------------------------------------------------------- */
var appState = {
  token: null,
  user: null,
  profile: null,
  wardrobe: [],
  profileLoading: false,
  wardrobeLoading: false,
  profileError: '',
  wardrobeError: '',
  profilePhoto: '',
  initialPanel: null,
};

function getFrontendRoute() {
  var path = window.location.pathname.replace(/\/+$/, '') || '/';
  var hashPanel = {
    '#/stylist': 'home',
    '#/wardrobe': 'wardrobe',
    '#/profile': 'profile',
    '#/wishlist': 'wishlist',
  }[window.location.hash];
  if (hashPanel && (path === '/' || path === '/index.html')) {
    return { name: 'app', panel: hashPanel };
  }
  if (window.location.hash.indexOf('#/') === 0 && !hashPanel) {
    return { name: 'not-found', panel: null };
  }
  var routes = {
    '/': { name: 'landing', panel: null },
    '/index.html': { name: 'landing', panel: null },
    '/app': { name: 'app', panel: 'home' },
    '/stylist': { name: 'app', panel: 'home' },
    '/wardrobe': { name: 'app', panel: 'wardrobe' },
    '/profile': { name: 'app', panel: 'profile' },
    '/wishlist': { name: 'app', panel: 'wishlist' },
  };
  return routes[path] || { name: 'not-found', panel: null };
}

function appPanelPath(panel) {
  return {
    home: '#/stylist',
    wardrobe: '#/wardrobe',
    profile: '#/profile',
    wishlist: '#/wishlist',
  }[panel] || '#/stylist';
}

function setAppRoute(panel, replace) {
  var hash = appPanelPath(panel);
  if (window.location.hash === hash) return;
  var basePath = window.location.pathname === '/index.html' ? '/index.html' : '/';
  window.history[replace ? 'replaceState' : 'pushState']({ panel: panel }, '', basePath + hash);
}

function setBootSkeleton(panel) {
  var surface = panel === 'home' ? 'stylist' : panel;
  var validSurfaces = ['landing', 'profile', 'wardrobe', 'stylist'];
  if (validSurfaces.indexOf(surface) === -1) surface = 'stylist';
  document.documentElement.setAttribute('data-wutt-boot-surface', surface);
}

var initialLoadingFinishTimer = null;
function finishInitialLoading() {
  if (initialLoadingFinishTimer !== null) return;
  var boot = document.getElementById('appBootScreen');
  var startedAt = window.__WUTT_BOOT_STARTED__ || performance.now();
  var remaining = Math.max(0, 380 - (performance.now() - startedAt));
  initialLoadingFinishTimer = window.setTimeout(function() {
    if (boot) {
      boot.classList.add('app-boot-screen--complete');
      boot.setAttribute('aria-hidden', 'true');
    }
    document.documentElement.classList.remove('wutt-auth-pending');
  }, remaining);
}

function showNotFoundPage() {
  var notFound = document.getElementById('notFoundPage');
  if (notFound) {
    notFound.classList.remove('u-hidden');
    notFound.setAttribute('aria-hidden', 'false');
  }
  document.body.classList.add('not-found-active');
  document.title = '404 — WUTT';
  finishInitialLoading();
}

function emptyUserProfile() {
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

function getApiErrorMessage(payload, fallback) {
  return payload?.message || payload?.detail?.message || fallback || 'Something went wrong. Please try again.';
}

async function apiRequest(path, options) {
  var requestOptions = Object.assign({}, options || {});
  var headers = new Headers(requestOptions.headers || {});
  var token = appState.token;
  if (token) headers.set('Authorization', 'Bearer ' + token);
  if (requestOptions.body && !(requestOptions.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  requestOptions.headers = headers;
  requestOptions.credentials = 'include';

  var response;
  try {
    response = await fetch(CONFIG.API_BASE + path, requestOptions);
  } catch (error) {
    var networkError = new Error('Cannot reach server. Check your connection.');
    networkError.cause = error;
    throw networkError;
  }

  var payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    // A missing/invalid JSON body is handled as a regular API failure below.
  }

  if (!response.ok || !payload || payload.status === 'error') {
    var apiError = new Error(getApiErrorMessage(payload, 'The server could not complete this request.'));
    apiError.status = response.status;
    apiError.payload = payload;
    if (response.status === 401) clearAuth();
    throw apiError;
  }
  return payload.data;
}

function mapProfileFromApi(profile) {
  var mapped = emptyUserProfile();
  if (!profile) return mapped;
  mapped.name = profile.name || '';
  mapped.gender = profile.gender || '';
  mapped.height = profile.height_cm ? String(profile.height_cm) + ' cm' : '';
  mapped.topSize = profile.top_size || '';
  mapped.bottomSize = profile.bottom_size || '';
  mapped.shoeSize = profile.shoe_size || '';
  mapped.skinTone = profile.skin_tone || '';
  mapped.city = profile.location_city || '';
  mapped.area = profile.location_area || '';
  mapped.fitPreference = profile.fit_preference || '';
  mapped.outfitVibe = profile.outfit_vibe || '';
  mapped.preferredColors = profile.preferred_colors
    ? profile.preferred_colors.split(',').map(function(value) { return value.trim(); }).filter(Boolean)
    : [];
  mapped.shoppingStyle = profile.shopping_style || '';
  mapped.favoriteStyles = profile.style_preference
    ? profile.style_preference.split(',').map(function(value) { return value.trim(); }).filter(Boolean)
    : [];
  return mapped;
}

function mapWardrobeFromApi(item) {
  return {
    id: item.id,
    userId: item.user_id,
    imageDataUrl: wardrobeImageUrlFromApi(item),
    name: item.subtype || item.description || item.category || 'Wardrobe item',
    subtype: item.subtype || '',
    category: item.category || 'Item',
    color: item.color || '',
    styleVibe: item.style_tags || '',
    material: item.material_tags || '',
    occasions: item.occasion_tags || '',
    brand: item.brand || '',
    formalityLevel: item.formality_level || '',
    seasonSuitability: item.season_suitability || '',
    notes: item.description || '',
    createdAt: item.uploaded_at || '',
  };
}

async function loadServerProfile() {
  appState.profileLoading = true;
  appState.profileError = '';
  renderProfileView();
  try {
    var profile = await apiRequest('/profile/' + appState.user.id);
    appState.profile = mapProfileFromApi(profile);
  } catch (error) {
    if (error.status === 404) {
      appState.profile = emptyUserProfile();
    } else {
      appState.profileError = error.message;
      throw error;
    }
  } finally {
    appState.profileLoading = false;
    renderProfileView();
  }
}

async function loadServerWardrobe() {
  appState.wardrobeLoading = true;
  appState.wardrobeError = '';
  renderWardrobeSidebar();
  renderWardrobeView();
  try {
    var items = await apiRequest('/wardrobe/' + appState.user.id);
    appState.wardrobe = Array.isArray(items) ? items.map(mapWardrobeFromApi) : [];
  } catch (error) {
    appState.wardrobeError = error.message;
    throw error;
  } finally {
    appState.wardrobeLoading = false;
    renderWardrobeSidebar();
    renderWardrobeView();
  }
}

async function bootstrapAuthenticatedSession() {
  appState.user = await apiRequest('/auth/me');
  setBootSkeleton(appState.initialPanel || getLastAppPanel());
  await Promise.all([loadServerProfile(), loadServerWardrobe()]);
  applyChatPreferences();
}

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
      await bootstrapAuthenticatedSession();
      markOnboardingPending();
      closeAllModals();
      showMainApp({ showWelcome: !hasCompletedOnboarding() });
    } else {
      toggleHidden(loginFormError, false);
      loginFormError.textContent = normalizeAuthError(data.message || data?.detail?.message);
    }
  } catch (err) {
    clearAuth();
    toggleHidden(loginFormError, false);
    loginFormError.textContent = normalizeAuthError(err.message);
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
      await bootstrapAuthenticatedSession();
      markOnboardingPending();
      closeAllLandingModals();
      showMainApp({ showWelcome: !hasCompletedOnboarding() });
    } else {
      toggleHidden(heroFormError, false);
      heroFormError.textContent = normalizeAuthError(data.message || data?.detail?.message);
    }
  } catch (err) {
    clearAuth();
    toggleHidden(heroFormError, false);
    heroFormError.textContent = normalizeAuthError(err.message);
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
      await bootstrapAuthenticatedSession();
      markOnboardingPending();
      closeAllLandingModals();
      showStyleQuiz();
    } else {
      toggleHidden(registerFormError, false);
      registerFormError.textContent = normalizeAuthError(data.message || data?.detail?.message);
    }
  } catch (err) {
    clearAuth();
    toggleHidden(registerFormError, false);
    registerFormError.textContent = normalizeAuthError(err.message);
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
  if (!appState.user) {
    showToast('Please log in or create an account to continue.', 'error');
    return;
  }
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

/** Show the main app, with onboarding controlled independently from authentication. */
function showMainApp(options) {
  if (!appState.user) {
    showToast('Please log in to continue.', 'error');
    return;
  }
  var shouldShowWelcome = Boolean(options && options.showWelcome);
  var hero = document.querySelector('.landing-hero');
  var navbar = document.querySelector('.navbar--landing');
  var quiz = document.getElementById('styleQuiz');
  var welcome = document.getElementById('welcomeScreen');
  var chat = document.getElementById('chatApp');

  if (hero) hero.style.display = 'none';
  if (navbar) navbar.style.display = 'none';
  if (quiz) quiz.classList.add('u-hidden');
  document.body.style.overflow = shouldShowWelcome ? 'hidden' : 'auto';
  document.body.classList.remove('modal-open');

  // The welcome is onboarding, not a session-loading screen.
  if (welcome) {
    welcome.classList.toggle('u-hidden', !shouldShowWelcome);
    welcome.setAttribute('aria-hidden', String(!shouldShowWelcome));
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

  if (!shouldShowWelcome) {
    transitionToChat();
    finishInitialLoading();
    return;
  }

  finishInitialLoading();

  // Auto-transition to chat after welcome
  var transitioned = false;
  function doTransition() {
    if (transitioned) return;
    transitioned = true;
    markOnboardingComplete();
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
  showMainApp({ showWelcome: !hasCompletedOnboarding() });
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
   -------------------------------------------------------- */

var _chatInitDone = false;

function initChatApp() {
  if (_chatInitDone) return;
  _chatInitDone = true;

  /* ---- Sidebar navigation: single-panel, view switching ---- */
  var sidebarItems = document.querySelectorAll('.chat-sidebar__item[data-panel]');
  var allViews = ['shopView', 'wishlistView', 'profileView', 'wardrobeView'];
  var shoppingSoonOverlay = document.getElementById('shoppingSoonOverlay');
  var shoppingSoonClose = document.getElementById('shoppingSoonClose');
  var shoppingSoonTrigger = null;
  var shoppingSoonCloseTimer = null;

  function openShoppingSoon(trigger) {
    if (!shoppingSoonOverlay) return;
    if (shoppingSoonCloseTimer) {
      clearTimeout(shoppingSoonCloseTimer);
      shoppingSoonCloseTimer = null;
    }
    shoppingSoonTrigger = trigger || document.activeElement;
    shoppingSoonOverlay.classList.remove('u-hidden');
    shoppingSoonOverlay.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(function() {
      shoppingSoonOverlay.classList.add('shopping-soon-overlay--open');
      if (shoppingSoonClose) shoppingSoonClose.focus();
    });
  }

  function closeShoppingSoon() {
    if (!shoppingSoonOverlay || shoppingSoonOverlay.classList.contains('u-hidden')) return;
    shoppingSoonOverlay.classList.remove('shopping-soon-overlay--open');
    shoppingSoonOverlay.setAttribute('aria-hidden', 'true');
    shoppingSoonCloseTimer = setTimeout(function() {
      shoppingSoonOverlay.classList.add('u-hidden');
      shoppingSoonCloseTimer = null;
    }, 180);
    if (shoppingSoonTrigger && typeof shoppingSoonTrigger.focus === 'function') {
      shoppingSoonTrigger.focus();
    }
  }

  if (shoppingSoonClose) {
    shoppingSoonClose.addEventListener('click', closeShoppingSoon);
  }
  if (shoppingSoonOverlay) {
    shoppingSoonOverlay.addEventListener('click', function(e) {
      if (e.target === shoppingSoonOverlay) closeShoppingSoon();
    });
  }
  document.addEventListener('keydown', function(e) {
    var isShoppingDialogOpen = shoppingSoonOverlay
      && shoppingSoonOverlay.classList.contains('shopping-soon-overlay--open');
    if (!isShoppingDialogOpen) return;
    if (e.key === 'Escape') {
      closeShoppingSoon();
      return;
    }
    if (e.key === 'Tab' && shoppingSoonClose) {
      e.preventDefault();
      shoppingSoonClose.focus();
    }
  });

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
    var chatMenuButton = document.getElementById('chatMenuBtn');
    var chatMenu = document.getElementById('chatHeaderMenu');
    if (chatHeader) chatHeader.classList.add('u-hidden');
    if (chatBody) chatBody.classList.add('u-hidden');
    if (chatInput) chatInput.classList.add('u-hidden');
    if (chatMenuButton) chatMenuButton.setAttribute('aria-expanded', 'false');
    if (chatMenu) {
      chatMenu.classList.add('u-hidden');
      chatMenu.setAttribute('aria-hidden', 'true');
    }
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
    loadTodayStyleSessions();
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
        saveLastAppPanel('wardrobe');
        setAppRoute('wardrobe');
        return;
      }

      if (panel === 'profile') {
        showProfileView();
        setActiveSidebar('profile');
        saveLastAppPanel('profile');
        setAppRoute('profile');
        return;
      }

      if (panel === 'shopping') {
        openShoppingSoon(item);
        return;
      }

      // home — show chat (chat-first experience)
      showChatView();
      setActiveSidebar('home');
      saveLastAppPanel('home');
      setAppRoute('home');
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
      setActiveSidebar('home');
      saveLastAppPanel('home');
      setAppRoute('home');
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
  wireSkinToneSwatches();

  // Wire multi-select groups
  wireMultiSelectGroup('profileFavoriteStylesChips', 'pf-chip--active');
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
    profileForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      if (await saveProfileForm()) {
        closeProfileEdit();
        renderProfileView();
      }
    });
  }

  // Direct click handler on Save button (outside form)
  var profileSaveBtn = document.getElementById('profileSaveBtn');
  if (profileSaveBtn && profileForm) {
    profileSaveBtn.addEventListener('click', async function(e) {
      e.preventDefault();
      if (await saveProfileForm()) {
        closeProfileEdit();
        renderProfileView();
      }
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
        openAvatarCrop(ev.target.result);
      };
      reader.readAsDataURL(file);
      photoInput.value = '';
    });
  }

  /* ---- Avatar Crop Modal ---- */
  var avatarCropOverlay = document.getElementById('avatarCropOverlay');
  var avatarCropPreview = document.getElementById('avatarCropPreview');
  var avatarCropImage = document.getElementById('avatarCropImage');
  var avatarCropZoom = document.getElementById('avatarCropZoom');
  var avatarCropSave = document.getElementById('avatarCropSave');
  var avatarCropCancel = document.getElementById('avatarCropCancel');
  var avatarCropClose = document.getElementById('avatarCropClose');

  var avatarCropData = { dataUrl: null, offsetX: 0, offsetY: 0, zoom: 100, dragging: false, startX: 0, startY: 0, imgW: 0, imgH: 0 };

  function openAvatarCrop(dataUrl) {
    avatarCropData.dataUrl = dataUrl;
    avatarCropData.offsetX = 0;
    avatarCropData.offsetY = 0;
    avatarCropData.zoom = 100;
    avatarCropZoom.value = 100;
    avatarCropImage.style.backgroundImage = 'url(' + dataUrl + ')';
    var tempImg = new Image();
    tempImg.onload = function() {
      avatarCropData.imgW = tempImg.naturalWidth;
      avatarCropData.imgH = tempImg.naturalHeight;
      updateAvatarCropTransform();
    };
    tempImg.src = dataUrl;
    avatarCropOverlay.classList.remove('u-hidden');
    avatarCropOverlay.setAttribute('aria-hidden', 'false');
  }

  function closeAvatarCrop() {
    avatarCropOverlay.classList.add('u-hidden');
    avatarCropOverlay.setAttribute('aria-hidden', 'true');
    avatarCropData.dataUrl = null;
  }

  function getAvatarCropMaxOffset() {
    var containerSize = 180;
    var scale = avatarCropData.zoom / 100;
    var imgW = avatarCropData.imgW || containerSize;
    var imgH = avatarCropData.imgH || containerSize;
    var coverScale = Math.max(containerSize / imgW, containerSize / imgH);
    var renderedW = imgW * coverScale * scale;
    var renderedH = imgH * coverScale * scale;
    return { x: Math.max(0, (renderedW - containerSize) / 2), y: Math.max(0, (renderedH - containerSize) / 2) };
  }

  function clampAvatarCropOffset() {
    var max = getAvatarCropMaxOffset();
    avatarCropData.offsetX = Math.max(-max.x, Math.min(max.x, avatarCropData.offsetX));
    avatarCropData.offsetY = Math.max(-max.y, Math.min(max.y, avatarCropData.offsetY));
  }

  function updateAvatarCropTransform() {
    clampAvatarCropOffset();
    var scale = avatarCropData.zoom / 100;
    var tx = avatarCropData.offsetX;
    var ty = avatarCropData.offsetY;
    avatarCropImage.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + scale + ')';
  }

  if (avatarCropSave) {
    avatarCropSave.addEventListener('click', function() {
      if (!avatarCropData.dataUrl) return;
      var containerSize = 180;
      var img = new Image();
      img.onload = function() {
        var scale = avatarCropData.zoom / 100;
        var coverScale = Math.max(containerSize / img.naturalWidth, containerSize / img.naturalHeight);
        var renderedW = img.naturalWidth * coverScale * scale;
        var renderedH = img.naturalHeight * coverScale * scale;
        var offsetX = avatarCropData.offsetX;
        var offsetY = avatarCropData.offsetY;
        var renderedLeft = (containerSize - renderedW) / 2 + offsetX;
        var renderedTop = (containerSize - renderedH) / 2 + offsetY;
        var renderedScale = coverScale * scale;
        var srcX = Math.max(0, -renderedLeft / renderedScale);
        var srcY = Math.max(0, -renderedTop / renderedScale);
        var srcW = Math.min(img.naturalWidth - srcX, containerSize / renderedScale);
        var srcH = Math.min(img.naturalHeight - srcY, containerSize / renderedScale);
        var canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 512;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, 512, 512);
        var croppedDataUrl = canvas.toDataURL('image/jpeg', 0.92);
        appState.profilePhoto = croppedDataUrl;
        renderProfilePhoto();
        closeAvatarCrop();
        showToast('Photo updated', 'success');
      };
      img.src = avatarCropData.dataUrl;
    });
  }

  if (avatarCropCancel) {
    avatarCropCancel.addEventListener('click', closeAvatarCrop);
  }
  if (avatarCropClose) {
    avatarCropClose.addEventListener('click', closeAvatarCrop);
  }
  if (avatarCropOverlay) {
    avatarCropOverlay.addEventListener('click', function(e) {
      if (e.target === avatarCropOverlay) closeAvatarCrop();
    });
  }

  if (avatarCropZoom) {
    avatarCropZoom.addEventListener('input', function() {
      avatarCropData.zoom = parseInt(avatarCropZoom.value, 10);
      updateAvatarCropTransform();
    });
  }

  /* ---- Drag to reposition avatar ---- */
  if (avatarCropPreview) {
    avatarCropPreview.addEventListener('pointerdown', function(e) {
      if (!avatarCropData.dataUrl) return;
      avatarCropData.dragging = true;
      avatarCropData.startX = e.clientX - avatarCropData.offsetX;
      avatarCropData.startY = e.clientY - avatarCropData.offsetY;
      avatarCropPreview.setPointerCapture(e.pointerId);
      e.preventDefault();
    });

    avatarCropPreview.addEventListener('pointermove', function(e) {
      if (!avatarCropData.dragging) return;
      var newX = e.clientX - avatarCropData.startX;
      var newY = e.clientY - avatarCropData.startY;
      var max = getAvatarCropMaxOffset();
      avatarCropData.offsetX = Math.max(-max.x, Math.min(max.x, newX));
      avatarCropData.offsetY = Math.max(-max.y, Math.min(max.y, newY));
      updateAvatarCropTransform();
    });

    avatarCropPreview.addEventListener('pointerup', function() {
      avatarCropData.dragging = false;
    });
    avatarCropPreview.addEventListener('pointercancel', function() {
      avatarCropData.dragging = false;
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
      var card = e.target.closest('[data-action="occasion"]');
      if (!card) return;
      var occasion = card.getAttribute('data-value') || '';
      sendChatMessage('What should I wear for ' + occasion + '?');
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
      addChatMessage('bot', 'Nice. Upload a photo, then add the details manually.');

      // 3. Show the photo upload action
      addChipsToChat([
        { item: 'upload-photo', label: 'Upload photo', cls: '' }
      ], item); // pass category to handler
    });
  }

  /* ---- Chat send handler ---- */
  var chatSendBtn = document.getElementById('chatSendBtn');
  var chatInputField = document.getElementById('chatInput');
  var chatImageAttachBtn = document.getElementById('chatImageAttachBtn');
  var chatImageInput = document.getElementById('chatImageInput');
  var chatImagePreview = document.getElementById('chatImagePreview');
  var chatImagePreviewImage = document.getElementById('chatImagePreviewImage');
  var chatImagePreviewName = document.getElementById('chatImagePreviewName');
  var chatImagePreviewRemove = document.getElementById('chatImagePreviewRemove');
  // Keep initial/history loading separate from live AI response generation.
  var _chatGenerating = false;
  var _chatHistoryLoading = false;
  var _chatHistoryLoaded = false;
  var _chatImage = null;

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

  function parseStylistResponseSections(rawResponse) {
    var response = String(rawResponse || '')
      .replace(/\r\n?/g, '\n')
      .replace(/\*\*(Recommended|Why|Small tip)\s*:?\*\*/gi, '$1:')
      .trim();
    var sections = {};
    var headings = [];
    var headingPattern = /(Recommended|Why|Small tip)\s*:/gi;
    var match;

    while ((match = headingPattern.exec(response)) !== null) {
      headings.push({
        key: match[1].toLowerCase() === 'recommended'
          ? 'recommended'
          : (match[1].toLowerCase() === 'why' ? 'why' : 'tip'),
        start: match.index,
        contentStart: headingPattern.lastIndex,
      });
    }

    headings.forEach(function(heading, index) {
      var next = headings[index + 1];
      sections[heading.key] = response
        .slice(heading.contentStart, next ? next.start : response.length)
        .trim();
    });

    if (!headings.length && response) sections.why = response;
    return sections;
  }

  function parseStylistItems(rawItems) {
    return String(rawItems || '')
      .split(/\n+|(?:^|\s)[•*-]\s+|(?:^|\s)\d+[.)]\s+/)
      .map(function(item) {
        return item.replace(/^[\s•*-]+|[\s•*-]+$/g, '').trim();
      })
      .filter(Boolean);
  }

  function normalizeStylistRecommendation(data) {
    var source = data || {};
    var parsed = parseStylistResponseSections(source.response);
    var outfit = Array.isArray(source.outfit)
      ? source.outfit.slice()
      : [];

    if (!outfit.length && parsed.recommended) {
      outfit = parseStylistItems(parsed.recommended);
    }

    return {
      outfit: outfit.map(stylistItemLabel).filter(Boolean),
      explanation: stylistFriendlyCopy(source.explanation || parsed.why || ''),
      weather_based_tip: stylistFriendlyCopy(source.weather_based_tip || parsed.tip || ''),
    };
  }

  function buildStylistRecommendation(data, requestText) {
    var recommendation = normalizeStylistRecommendation(data);
    var outfit = recommendation.outfit;
    var occasionLabel = stylistOccasionLabel(requestText);
    var title = occasionLabel
      ? occasionLabel + ' Look'
      : 'Styled Look';
    var html = '<article class="stylist-look" aria-label="WUTT outfit recommendation">';
    html += '<header class="stylist-look__header">'
      + '<h3 class="stylist-look__title"><span aria-hidden="true">✨</span> '
      + escapeHtml(title) + '</h3>'
      + '</header>';

    if (outfit.length) {
      html += '<section class="stylist-look__section">'
        + '<h4 class="stylist-look__label">Recommended:</h4>'
        + '<ul class="stylist-look__pieces">';
      outfit.forEach(function(item) {
        html += '<li class="stylist-look__piece">'
          + '<span>' + escapeHtml(item) + '</span></li>';
      });
      html += '</ul></section>';
    }

    if (recommendation.explanation) {
      html += '<section class="stylist-look__section stylist-look__section--why">'
        + '<h4 class="stylist-look__label">Why:</h4>'
        + '<p class="stylist-look__copy">' + escapeHtml(recommendation.explanation) + '</p></section>';
    }

    if (recommendation.weather_based_tip) {
      html += '<section class="stylist-look__section stylist-look__section--tip">'
        + '<h4 class="stylist-look__label">Small tip:</h4>'
        + '<p class="stylist-look__copy">' + escapeHtml(recommendation.weather_based_tip) + '</p></section>';
    }

    return html + '</article>';
  }

  function stylistItemLabel(rawItem) {
    var text = String(rawItem || '').trim();
    var ids = Array.from(text.matchAll(/(?:\bid\s*=?\s*|#)(\d+)\b/gi))
      .map(function(match) { return Number(match[1]); });
    var mapped = ids.map(function(id) {
      var item = getWardrobeItems().find(function(candidate) { return candidate.id === id; });
      if (!item) return '';
      var itemName = item.subtype || item.name || item.category || '';
      return [item.color, itemName].filter(Boolean).join(' ');
    }).filter(Boolean);
    var label = mapped.length
      ? Array.from(new Set(mapped)).join(' + ')
      : text.replace(/\s*[\[(]?\s*(?:id\s*=?\s*|#)\d+\s*[\])]?/gi, '').trim();
    label = label.replace(/^suggested:\s*/i, '');
    return label.split(/\s+/).map(function(word) {
      return /^[a-z]/i.test(word) ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase() : word;
    }).join(' ');
  }

  function stylistFriendlyCopy(rawCopy) {
    var copy = String(rawCopy || '');
    getWardrobeItems().forEach(function(item) {
      var label = item.subtype || item.name || item.category || '';
      copy = copy.replace(
        new RegExp('\\s*[\\[(]\\s*(?:id\\s*=?\\s*|#)' + item.id + '\\s*[\\])]', 'gi'),
        ''
      );
      copy = copy.replace(
        new RegExp('\\b(?:id\\s*=?\\s*|#)' + item.id + '\\b', 'gi'),
        label
      );
    });
    return copy.replace(/\s*[\[(]?\s*(?:id\s*=?\s*|#)\d+\s*[\])]?/gi, '').replace(/\s+/g, ' ').trim();
  }

  function stylistOccasionLabel(requestText) {
    var text = String(requestText || '').trim();
    var lower = text.toLowerCase();
    var knownOccasions = [
      { terms: ['ဘုရား', 'pagoda', 'temple', 'monastery', 'ဘုန်းကြီးကျောင်း'], label: 'Pagoda Visit' },
      { terms: ['dinner date'], label: 'Dinner Date' },
      { terms: ['myanmar wedding', 'မြန်မာ wedding'], label: 'Myanmar Wedding' },
      { terms: ['wedding', 'မင်္ဂလာဆောင်'], label: 'Wedding' },
      { terms: ['interview'], label: 'Interview' },
      { terms: ['coffee date'], label: 'Coffee Date' },
      { terms: ['date'], label: 'Date' },
      { terms: ['work', 'office'], label: 'Work' },
      { terms: ['party'], label: 'Party' },
      { terms: ['campus', 'university'], label: 'Campus' },
      { terms: ['casual'], label: 'Casual' },
    ];
    for (var i = 0; i < knownOccasions.length; i += 1) {
      if (knownOccasions[i].terms.some(function(term) { return lower.includes(term); })) {
        return knownOccasions[i].label;
      }
    }
    var cleaned = text
      .replace(/^(what should i wear (to|for)?|recommend|suggest|an outfit for|outfit for)\s*/i, '')
      .replace(/(သွားမလို့|သွားဖို့|အတွက်|ဘာဝတ်ရမလဲ)/g, ' ')
      .replace(/[?.!]+$/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    return cleaned
      .split(' ')
      .slice(0, 5)
      .map(function(word) {
        return /^[a-z]/i.test(word) ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase() : word;
      })
      .join(' ');
  }

  function setChatGeneratingState(isGenerating) {
    _chatGenerating = isGenerating;
    if (chatSendBtn) {
      chatSendBtn.disabled = isGenerating;
      chatSendBtn.setAttribute('aria-busy', String(isGenerating));
      chatSendBtn.setAttribute('aria-label', isGenerating ? 'WUTT is typing' : 'Send message');
    }
    if (chatInputField) chatInputField.disabled = isGenerating;
    if (chatImageAttachBtn) chatImageAttachBtn.disabled = isGenerating;
    if (welcomeCards) {
      welcomeCards.querySelectorAll('[data-action="occasion"]').forEach(function(button) {
        button.disabled = isGenerating;
      });
      welcomeCards.classList.toggle('chat-welcome__cards--generating', isGenerating);
    }
  }

  function clearChatImage() {
    _chatImage = null;
    if (chatImagePreview) chatImagePreview.classList.add('u-hidden');
    if (chatImagePreviewImage) {
      chatImagePreviewImage.removeAttribute('src');
    }
    if (chatImageInput) chatImageInput.value = '';
  }

  function sendStagedImage() {
    if (!_chatImage) return false;
    var caption = chatInputField ? chatInputField.value.trim() : '';
    var imageHtml = '<img class="chat-msg__attached-image" src="' + _chatImage.dataUrl + '" alt="Uploaded outfit">'
      + (caption ? '<span class="chat-msg__image-caption">' + escapeHtml(caption) + '</span>' : '');
    var welcomeEl = document.getElementById('chatWelcome');
    var messagesEl = document.getElementById('chatMessages');
    if (welcomeEl) welcomeEl.classList.add('u-hidden');
    if (messagesEl) messagesEl.classList.remove('u-hidden');
    addUserMessage(imageHtml);
    addChatMessage(
      'bot',
      '<span class="chat-coming-soon"><strong>Image styling is coming soon.</strong>'
        + ' Your photo is ready, but WUTT is not analyzing images yet. Ask me about the look in text for now.</span>'
    );
    if (chatInputField) chatInputField.value = '';
    clearChatImage();
    return true;
  }

  function sendChatMessage(overrideText) {
    if (_chatGenerating) return;
    if (!overrideText && sendStagedImage()) return;
    var text = overrideText || (chatInputField ? chatInputField.value.trim() : '');
    if (!text) return;

    // Show messages container, hide welcome
    var welcomeEl = document.getElementById('chatWelcome');
    var messagesEl = document.getElementById('chatMessages');
    if (welcomeEl) welcomeEl.classList.add('u-hidden');
    if (messagesEl) messagesEl.classList.remove('u-hidden');

    // Add user message to UI and history
    addUserMessage(escapeHtml(text));
    addToChatHistory('user', text);
    if (chatInputField) chatInputField.value = '';

    // Live generation uses a conversational typing bubble. Skeletons are
    // reserved for initial data loading and refreshing existing content.
    var typingEl = document.createElement('div');
    typingEl.className = 'chat-msg chat-msg--bot';
    typingEl.id = 'chatTypingIndicator';
    typingEl.innerHTML =
      '<div class="chat-msg__avatar" aria-hidden="true">' +
        '<svg width="28" height="28" viewBox="0 0 36 36" fill="none"><rect width="36" height="36" rx="12" fill="#1F1F1F"/><path d="M9 25V12l8 5.5-8 5.5zm8 0h8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      '</div>' +
      '<div class="chat-msg__bubble chat-msg__bubble--typing" role="status" aria-live="polite" aria-label="WUTT is typing">' +
        '<span class="chat-typing" aria-hidden="true">' +
          '<span class="chat-typing__dot"></span>' +
          '<span class="chat-typing__dot"></span>' +
          '<span class="chat-typing__dot"></span>' +
        '</span>' +
      '</div>';
    messagesEl.appendChild(typingEl);
    scrollChatToBottom();

    setChatGeneratingState(true);

    var token = appState.token;
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

        // Every successful stylist payload uses the same card renderer. Text
        // fallbacks are normalized into outfit, explanation, and tip sections.
        var src = d.source || '';
        if (src === 'api_error') {
          var failureCopy = d.response || d.explanation
            || 'I could not finish that suggestion. Try describing the occasion again.';
          reply = buildStylistRecommendation({ response: failureCopy }, text);
        }
        else if (d.response || d.explanation || (d.outfit && d.outfit.length > 0)) {
          reply = buildStylistRecommendation(d, text);

          // Save the original response so history can normalize it identically.
          var historyText = d.response || '';
          if (!historyText) {
            var historySections = [];
            if (d.outfit && d.outfit.length > 0) {
              historySections.push('Recommended:\n- ' + d.outfit.join('\n- '));
            }
            if (d.explanation) historySections.push('Why:\n' + d.explanation);
            if (d.weather_based_tip) historySections.push('Small tip:\n' + d.weather_based_tip);
            historyText = historySections.join('\n');
          }
          addToChatHistory('bot', historyText);
        }

        if (!reply) {
          reply = buildStylistRecommendation({
            response: 'I\'m not sure how to help with that. Try asking about an outfit for a specific occasion like "What should I wear to a wedding?"',
          }, text);
        }

        addChatMessage('bot', reply);
      } else {
        addChatMessage('bot', buildStylistRecommendation({
          response: 'I could not finish that suggestion. Try describing the occasion again.',
        }, text));
      }
    }).catch(function(err) {
      console.error('[WUTT] Chat error:', err);
      var typing = document.getElementById('chatTypingIndicator');
      if (typing) typing.remove();
      addChatMessage('bot', buildStylistRecommendation({
        response: 'I lost the thread for a second. Try sending the occasion again.',
      }, text));
    }).finally(function() {
      setChatGeneratingState(false);
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

  if (chatImageAttachBtn && chatImageInput) {
    chatImageAttachBtn.addEventListener('click', function() {
      chatImageInput.click();
    });
    chatImageInput.addEventListener('change', function() {
      var file = chatImageInput.files && chatImageInput.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(event) {
        _chatImage = { file: file, dataUrl: event.target.result };
        if (chatImagePreviewImage) chatImagePreviewImage.src = event.target.result;
        if (chatImagePreviewName) chatImagePreviewName.textContent = file.name || 'Selected image';
        if (chatImagePreview) chatImagePreview.classList.remove('u-hidden');
      };
      reader.readAsDataURL(file);
    });
  }
  if (chatImagePreviewRemove) {
    chatImagePreviewRemove.addEventListener('click', clearChatImage);
  }

  function isTodayValue(value) {
    if (!value) return false;
    var date = new Date(value);
    var today = new Date();
    return !Number.isNaN(date.getTime())
      && date.getFullYear() === today.getFullYear()
      && date.getMonth() === today.getMonth()
      && date.getDate() === today.getDate();
  }

  function resetChatMessages() {
    var messagesEl = document.getElementById('chatMessages');
    var welcomeEl = document.getElementById('chatWelcome');
    if (messagesEl) {
      messagesEl.innerHTML = '';
      messagesEl.classList.add('u-hidden');
    }
    if (welcomeEl) welcomeEl.classList.remove('u-hidden');
  }

  function showTodayConversation() {
    var messagesEl = document.getElementById('chatMessages');
    var welcomeEl = document.getElementById('chatWelcome');
    if (!messagesEl) return null;
    messagesEl.innerHTML = '<div class="chat-history-day"><span>Today</span></div>';
    messagesEl.classList.remove('u-hidden');
    if (welcomeEl) welcomeEl.classList.add('u-hidden');
    return messagesEl;
  }

  function renderLocalTodayChat() {
    var history = getChatHistory().filter(function(entry) {
      return !entry.createdAt || isTodayValue(entry.createdAt);
    });
    if (!history.length) {
      resetChatMessages();
      return;
    }
    showTodayConversation();
    var lastUserRequest = '';
    history.forEach(function(entry) {
      var content = String(entry.content || '');
      if (entry.role === 'user') {
        lastUserRequest = content;
        addChatMessage('user', escapeHtml(content).replace(/\n/g, '<br>'));
      } else {
        addChatMessage('bot', buildStylistRecommendation({ response: content }, lastUserRequest));
      }
    });
  }

  function renderTodayStyleSessions(sessions) {
    var todaySessions = sessions
      .filter(function(session) { return isTodayValue(session.created_at); })
      .sort(function(a, b) { return new Date(a.created_at) - new Date(b.created_at); });
    if (!todaySessions.length) {
      renderLocalTodayChat();
      return;
    }
    showTodayConversation();
    todaySessions.forEach(function(session) {
      var payload = {};
      try {
        payload = JSON.parse(session.ai_response || '{}');
      } catch (error) {
        payload = {};
      }
      if (session.occasion === 'chat') {
        if (payload.message) addUserMessage(escapeHtml(payload.message));
        if (payload.response) {
          addChatMessage('bot', buildStylistRecommendation(payload, payload.message || ''));
        }
        return;
      }
      var requestText = session.occasion || 'an outfit';
      addUserMessage(escapeHtml('What should I wear for ' + requestText + '?'));
      addChatMessage('bot', buildStylistRecommendation(payload, requestText));
    });
  }

  async function loadTodayStyleSessions() {
    if (_chatHistoryLoading || _chatHistoryLoaded || !appState.user) return;
    _chatHistoryLoading = true;
    try {
      var sessions = await apiRequest('/stylist/history/' + appState.user.id);
      renderTodayStyleSessions(Array.isArray(sessions) ? sessions : []);
      _chatHistoryLoaded = true;
    } catch (error) {
      renderLocalTodayChat();
      _chatHistoryLoaded = true;
      console.warn('[WUTT] Could not load style history:', error.message);
    } finally {
      _chatHistoryLoading = false;
    }
  }

  /* ---- Delete only today's chat history ---- */
  var chatMenuBtn = document.getElementById('chatMenuBtn');
  var chatHeaderMenu = document.getElementById('chatHeaderMenu');
  var clearHistoryBtn = document.getElementById('chatClearHistoryBtn');

  function setChatMenuOpen(isOpen, returnFocus) {
    if (!chatMenuBtn || !chatHeaderMenu) return;
    chatMenuBtn.setAttribute('aria-expanded', String(isOpen));
    chatHeaderMenu.setAttribute('aria-hidden', String(!isOpen));
    chatHeaderMenu.classList.toggle('u-hidden', !isOpen);
    if (isOpen && clearHistoryBtn) {
      clearHistoryBtn.focus();
    } else if (returnFocus) {
      chatMenuBtn.focus();
    }
  }

  if (chatMenuBtn && chatHeaderMenu) {
    chatMenuBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      setChatMenuOpen(chatMenuBtn.getAttribute('aria-expanded') !== 'true', false);
    });
    chatHeaderMenu.addEventListener('click', function(e) {
      e.stopPropagation();
    });
    document.addEventListener('click', function() {
      if (chatMenuBtn.getAttribute('aria-expanded') === 'true') {
        setChatMenuOpen(false, false);
      }
    });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && chatMenuBtn.getAttribute('aria-expanded') === 'true') {
        setChatMenuOpen(false, true);
      }
    });
  }

  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', async function() {
      setChatMenuOpen(false, false);
      if (!confirm('Delete today’s stylist conversation? Older style history will be kept.')) return;
      clearHistoryBtn.disabled = true;
      clearHistoryBtn.setAttribute('aria-busy', 'true');
      try {
        await apiRequest('/stylist/history/' + appState.user.id + '/today', { method: 'DELETE' });
        clearTodayChatHistory();
        resetChatMessages();
        showToast('Today’s chat deleted', 'success');
      } catch (error) {
        showToast(error.message, 'error');
      } finally {
        clearHistoryBtn.disabled = false;
        clearHistoryBtn.removeAttribute('aria-busy');
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
      openWardrobeModal();
      handleModalFileSelected(file, category);
      fileInput.value = '';
    });
  }

  // Restore the user's last stable panel after a refresh.
  var initialPanel = appState.initialPanel || getLastAppPanel();
  appState.initialPanel = null;
  if (initialPanel === 'wardrobe') {
    showWardrobeView();
    setActiveSidebar('wardrobe');
  } else if (initialPanel === 'profile') {
    showProfileView();
    setActiveSidebar('profile');
  } else if (initialPanel === 'wishlist') {
    showWishlistView();
    setActiveSidebar('wishlist');
  } else {
    showChatView();
    setActiveSidebar('home');
  }
  saveLastAppPanel(initialPanel);
  setAppRoute(initialPanel, true);

  window.addEventListener('popstate', function() {
    var route = getFrontendRoute();
    if (route.name !== 'app') {
      window.location.reload();
      return;
    }
    if (route.panel === 'wardrobe') {
      showWardrobeView();
      setActiveSidebar('wardrobe');
    } else if (route.panel === 'profile') {
      showProfileView();
      setActiveSidebar('profile');
    } else if (route.panel === 'wishlist') {
      showWishlistView();
      setActiveSidebar('wishlist');
    } else {
      showChatView();
      setActiveSidebar('home');
    }
    saveLastAppPanel(route.panel);
  });

  // Shop back button — return to AI Stylist chat
  var shopBackBtn = document.getElementById('shopBackToChat');
  if (shopBackBtn) {
    shopBackBtn.addEventListener('click', function() {
      showChatView();
      setActiveSidebar('home');
      saveLastAppPanel('home');
      setAppRoute('home');
    });
  }

  /* ---- Wardrobe Upload Modal ---- */
  var wardrobeAddBtn = document.getElementById('wardrobeAddBtn');
  var wardrobeEmptyAddBtn = document.getElementById('wardrobeEmptyAddBtn');
  var wardrobeModal = document.getElementById('wardrobeModal');
  var wardrobeModalClose = document.getElementById('wardrobeModalClose');
  var wardrobeModalFileInput = document.getElementById('wardrobeModalFileInput');
  var wardrobeUploadArea = document.getElementById('wardrobeUploadArea');
  var wardrobeModalRetake = document.getElementById('wardrobeModalRetake');
  var wardrobeModalSave = document.getElementById('wardrobeModalSave');
  var wardrobeModalDone = document.getElementById('wardrobeModalDone');

  // Temp state for current upload
  var _pendingUpload = { dataUrl: '', fileName: '', file: null, mode: 'create', itemId: null };

  function setWardrobeModalCopy(mode) {
    var eyebrow = wardrobeModal?.querySelector('.wardrobe-modal__eyebrow');
    var title = wardrobeModal?.querySelector('.wardrobe-modal__title');
    var detailsTitle = wardrobeModal?.querySelector('.wardrobe-modal__details-title');
    var detailsHint = wardrobeModal?.querySelector('.wardrobe-modal__details-hint');
    var previewNote = wardrobeModal?.querySelector('.wardrobe-modal__preview-note');
    var savedTitle = wardrobeModal?.querySelector('.wardrobe-modal__saved-title');
    var savedHint = wardrobeModal?.querySelector('.wardrobe-modal__saved-hint');
    if (eyebrow) eyebrow.textContent = mode === 'edit' ? 'Wardrobe piece' : 'New wardrobe piece';
    if (title) title.textContent = mode === 'edit' ? 'Edit closet details' : 'Add to your closet';
    if (detailsTitle) detailsTitle.textContent = mode === 'edit' ? 'Refine this piece' : 'Tell WUTT about this piece';
    if (detailsHint) detailsHint.textContent = mode === 'edit'
      ? 'Keep the details accurate so your stylist can make better recommendations.'
      : 'A few useful details help your stylist create better looks.';
    if (previewNote) previewNote.textContent = mode === 'edit'
      ? 'The saved image stays with this wardrobe piece.'
      : 'Make sure the piece is clearly visible. You can choose another photo before saving.';
    if (savedTitle) savedTitle.textContent = mode === 'edit' ? 'Updated!' : 'Saved!';
    if (savedHint) savedHint.textContent = mode === 'edit'
      ? 'Your wardrobe details are up to date.'
      : 'Item added to your wardrobe.';
    if (wardrobeModalRetake) {
      wardrobeModalRetake.textContent = mode === 'edit' ? 'Cancel' : 'Choose another photo';
    }
    if (wardrobeModalSave) {
      wardrobeModalSave.textContent = mode === 'edit' ? 'Save changes' : 'Save to Wardrobe';
    }
  }

  function openWardrobeModal() {
    if (!wardrobeModal) return;
    _pendingUpload = { dataUrl: '', fileName: '', file: null, mode: 'create', itemId: null };
    setWardrobeModalCopy('create');
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

  function openWardrobeEditModal(itemId) {
    var item = getWardrobeItems().find(function(candidate) { return candidate.id === itemId; });
    if (!item || !wardrobeModal) return;
    _pendingUpload = {
      dataUrl: item.imageDataUrl || '',
      fileName: item.name || 'Wardrobe piece',
      file: null,
      mode: 'edit',
      itemId: item.id,
      draft: {
        category: item.category || 'Item',
        subtype: item.subtype || item.name || '',
        color: item.color || '',
        description: item.notes || '',
        styleTags: item.styleVibe || '',
        occasionTags: Array.isArray(item.occasions) ? item.occasions.join(', ') : (item.occasions || ''),
        material: item.material || '',
        brand: item.brand || '',
        formalityLevel: item.formalityLevel || '',
        seasonSuitability: item.seasonSuitability || '',
      },
    };
    setWardrobeModalCopy('edit');
    var stepUpload = document.getElementById('wardrobeModalUpload');
    var stepPreview = document.getElementById('wardrobeModalPreview');
    var stepSaved = document.getElementById('wardrobeModalSaved');
    if (stepUpload) stepUpload.classList.add('u-hidden');
    if (stepPreview) stepPreview.classList.remove('u-hidden');
    if (stepSaved) stepSaved.classList.add('u-hidden');
    wardrobeModal.classList.remove('u-hidden');
    wardrobeModal.setAttribute('aria-hidden', 'false');
    showModalPreview();
  }
  window.openWardrobeEditModal = openWardrobeEditModal;

  function closeWardrobeModal() {
    if (!wardrobeModal) return;
    wardrobeModal.classList.add('u-hidden');
    wardrobeModal.setAttribute('aria-hidden', 'true');
    _pendingUpload = { dataUrl: '', fileName: '', file: null, mode: 'create', itemId: null };
  }

  if (wardrobeAddBtn) {
    wardrobeAddBtn.addEventListener('click', function() {
      openWardrobeModal();
    });
  }
  if (wardrobeEmptyAddBtn) {
    wardrobeEmptyAddBtn.addEventListener('click', function() {
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

  function setSuggestionState(container) {
    var target = document.getElementById(container.getAttribute('data-suggestion-target'));
    if (!target) return;
    var selected = String(target.value || '').split(',').map(function(value) {
      return value.trim().toLowerCase();
    });
    container.querySelectorAll('button[data-value]').forEach(function(button) {
      var active = selected.indexOf(button.getAttribute('data-value').toLowerCase()) !== -1;
      button.classList.toggle('is-selected', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  if (wardrobeModal) {
    wardrobeModal.querySelectorAll('.wardrobe-modal__suggestions').forEach(function(container) {
      var target = document.getElementById(container.getAttribute('data-suggestion-target'));
      container.querySelectorAll('button[data-value]').forEach(function(button) {
        button.addEventListener('click', function() {
          if (!target) return;
          var values = String(target.value || '').split(',').map(function(value) {
            return value.trim();
          }).filter(Boolean);
          var suggestion = button.getAttribute('data-value');
          var existingIndex = values.findIndex(function(value) {
            return value.toLowerCase() === suggestion.toLowerCase();
          });
          if (existingIndex === -1) values.push(suggestion);
          else values.splice(existingIndex, 1);
          target.value = values.join(', ');
          target.dispatchEvent(new Event('input', { bubbles: true }));
          setSuggestionState(container);
        });
      });
      if (target) {
        target.addEventListener('input', function() { setSuggestionState(container); });
      }
    });
  }

  function handleModalFileSelected(file, suggestedCategory) {
    var draft = createEmptyWardrobeDraft(suggestedCategory);
    var pendingUpload = {
      dataUrl: '',
      fileName: file.name || 'Photo',
      file: file,
      draft: draft,
    };
    _pendingUpload = pendingUpload;
    var reader = new FileReader();
    reader.onload = function(e) {
      // Ignore a stale FileReader if the user chose another image meanwhile.
      if (_pendingUpload !== pendingUpload) return;
      pendingUpload.dataUrl = e.target.result;
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

    var categoryEl = document.getElementById('wardrobeManualCategory');
    var subtypeEl = document.getElementById('wardrobeManualSubtype');
    var colorEl = document.getElementById('wardrobeManualColor');
    var descriptionEl = document.getElementById('wardrobeManualDescription');
    var stylesEl = document.getElementById('wardrobeManualStyles');
    var occasionsEl = document.getElementById('wardrobeManualOccasions');
    var materialEl = document.getElementById('wardrobeManualMaterial');
    var brandEl = document.getElementById('wardrobeManualBrand');
    var formalityEl = document.getElementById('wardrobeManualFormality');
    var seasonEl = document.getElementById('wardrobeManualSeason');
    var draft = _pendingUpload.draft || createEmptyWardrobeDraft('Item');
    if (categoryEl) categoryEl.value = draft.category;
    if (subtypeEl) subtypeEl.value = draft.subtype;
    if (colorEl) colorEl.value = draft.color;
    if (descriptionEl) descriptionEl.value = draft.description;
    if (stylesEl) stylesEl.value = draft.styleTags;
    if (occasionsEl) occasionsEl.value = draft.occasionTags;
    if (materialEl) materialEl.value = draft.material;
    if (brandEl) brandEl.value = draft.brand;
    if (formalityEl) formalityEl.value = draft.formalityLevel;
    if (seasonEl) seasonEl.value = draft.seasonSuitability;
    if (wardrobeModal) {
      wardrobeModal.querySelectorAll('.wardrobe-modal__suggestions').forEach(setSuggestionState);
    }
    if (wardrobeModalSave) wardrobeModalSave.disabled = false;
  }

  // Save button
  if (wardrobeModalSave) {
    wardrobeModalSave.addEventListener('click', async function() {
      if (_pendingUpload.mode !== 'edit' && !_pendingUpload.file) return;
      var categoryEl = document.getElementById('wardrobeManualCategory');
      var subtypeEl = document.getElementById('wardrobeManualSubtype');
      var colorEl = document.getElementById('wardrobeManualColor');
      var descriptionEl = document.getElementById('wardrobeManualDescription');
      var stylesEl = document.getElementById('wardrobeManualStyles');
      var occasionsEl = document.getElementById('wardrobeManualOccasions');
      var materialEl = document.getElementById('wardrobeManualMaterial');
      var brandEl = document.getElementById('wardrobeManualBrand');
      var formalityEl = document.getElementById('wardrobeManualFormality');
      var seasonEl = document.getElementById('wardrobeManualSeason');
      var requiredFields = [categoryEl, subtypeEl, colorEl, stylesEl, occasionsEl];
      var invalidField = requiredFields.find(function(field) {
        return !field || !String(field.value || '').trim();
      });
      if (invalidField) {
        invalidField.reportValidity();
        invalidField.focus();
        showToast('Add the required wardrobe details before saving.', 'error');
        return;
      }
      var originalLabel = wardrobeModalSave.textContent;
      wardrobeModalSave.disabled = true;
      wardrobeModalSave.textContent = 'Saving…';
      try {
        var changes = {
          category: categoryEl?.value || 'Item',
          subtype: subtypeEl?.value.trim() || _pendingUpload.fileName,
          color: colorEl?.value.trim() || '',
          styleVibe: stylesEl?.value.trim() || '',
          occasions: occasionsEl?.value.trim() || '',
          material: materialEl?.value.trim() || '',
          brand: brandEl?.value.trim() || '',
          formalityLevel: formalityEl?.value || '',
          seasonSuitability: seasonEl?.value.trim() || '',
          notes: descriptionEl?.value.trim() || ''
        };
        if (_pendingUpload.mode === 'edit') {
          await updateWardrobeItem(_pendingUpload.itemId, changes);
        } else {
          changes.imageDataUrl = _pendingUpload.dataUrl;
          changes.file = _pendingUpload.file;
          changes.name = _pendingUpload.fileName;
          await saveWardrobeItem(changes);
        }
        // Show saved step
        var stepPreview = document.getElementById('wardrobeModalPreview');
        var stepSaved = document.getElementById('wardrobeModalSaved');
        if (stepPreview) stepPreview.classList.add('u-hidden');
        if (stepSaved) stepSaved.classList.remove('u-hidden');
      } catch (error) {
        showToast(error.message, 'error');
      } finally {
        wardrobeModalSave.disabled = false;
        wardrobeModalSave.textContent = originalLabel;
      }
    });
  }

  // Retake button
  if (wardrobeModalRetake) {
    wardrobeModalRetake.addEventListener('click', function() {
      if (_pendingUpload.mode === 'edit') {
        closeWardrobeModal();
        return;
      }
      var stepUpload = document.getElementById('wardrobeModalUpload');
      var stepPreview = document.getElementById('wardrobeModalPreview');
      if (stepPreview) stepPreview.classList.add('u-hidden');
      if (stepUpload) stepUpload.classList.remove('u-hidden');
      _pendingUpload = { dataUrl: '', fileName: '', file: null, mode: 'create', itemId: null };
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

/** Return wardrobe items loaded from the backend for this session. */
function getWardrobeItems() {
  return appState.wardrobe || [];
}

/* ---- Wardrobe select mode state ---- */
var wardrobeSelectMode = false;
var wardrobeSelected = {}; // { itemId: true }
var wardrobeActionMenuId = null;

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
  localStorage.setItem('wutt_last_theme', prefs.mood === 'night' ? 'night' : 'day');
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
  history.push({ role: role, content: content, createdAt: new Date().toISOString() });
  saveChatHistory(history);
}

/** Clear only entries from the user's current local calendar day. */
function clearTodayChatHistory() {
  var today = new Date();
  var retained = getChatHistory().filter(function(entry) {
    if (!entry.createdAt) return false;
    var created = new Date(entry.createdAt);
    return created.getFullYear() !== today.getFullYear()
      || created.getMonth() !== today.getMonth()
      || created.getDate() !== today.getDate();
  });
  saveChatHistory(retained);
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
  document.documentElement.setAttribute('data-wutt-theme', prefs.mood === 'night' ? 'night' : 'day');

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

/** Return the server-backed profile currently loaded for this session. */
function getUserProfile() {
  return appState.profile || emptyUserProfile();
}

/** Render the profile view card and sections */
function renderProfileView() {
  var profileView = document.getElementById('profileView');
  var profileLayout = profileView ? profileView.querySelector('.pf-layout') : null;
  var loadingShell = profileView ? profileView.querySelector('.profile-skeleton') : null;

  if (appState.profileLoading) {
    if (profileLayout) profileLayout.setAttribute('aria-hidden', 'true');
    if (!loadingShell && profileLayout) {
      loadingShell = document.createElement('div');
      loadingShell.className = 'profile-skeleton';
      loadingShell.setAttribute('role', 'status');
      loadingShell.setAttribute('aria-label', 'Loading profile');
      loadingShell.innerHTML =
        '<aside class="profile-skeleton__sidebar">' +
          '<div class="wutt-skeleton profile-skeleton__avatar" aria-hidden="true"></div>' +
          '<div class="wutt-skeleton profile-skeleton__name" aria-hidden="true"></div>' +
          '<div class="wutt-skeleton profile-skeleton__email" aria-hidden="true"></div>' +
          '<div class="profile-skeleton__chips" aria-hidden="true"><span class="wutt-skeleton"></span><span class="wutt-skeleton"></span></div>' +
          '<div class="wutt-skeleton profile-skeleton__button" aria-hidden="true"></div>' +
          '<div class="profile-skeleton__stats" aria-hidden="true"><span class="wutt-skeleton"></span><span class="wutt-skeleton"></span><span class="wutt-skeleton"></span></div>' +
        '</aside>' +
        '<div class="profile-skeleton__main" aria-hidden="true">' +
          [0, 1, 2].map(function() {
            return '<section class="profile-skeleton__section">' +
              '<span class="wutt-skeleton profile-skeleton__heading"></span>' +
              '<span class="wutt-skeleton profile-skeleton__field"></span>' +
              '<span class="wutt-skeleton profile-skeleton__field profile-skeleton__field--short"></span>' +
            '</section>';
          }).join('') +
        '</div>';
      profileLayout.insertAdjacentElement('beforebegin', loadingShell);
    }
    return;
  }

  if (loadingShell) loadingShell.remove();
  if (profileLayout) profileLayout.removeAttribute('aria-hidden');

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
  if (emailEl) {
    emailEl.textContent = user || '';
    emailEl.title = user || '';
  }

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

/** Render the session-only profile photo (backend has no photo field yet). */
function renderProfilePhoto() {
  var photoRaw = appState.profilePhoto;
  var img = document.getElementById('profilePhotoImg');
  var avatar = document.getElementById('profileCardAvatar');
  var editAvatar = document.getElementById('profileEditAvatar');

  var photoData = null;

  if (photoRaw) {
    try {
      var parsed = JSON.parse(photoRaw);
      photoData = parsed.dataUrl;
    } catch (e) {
      photoData = photoRaw;
    }
  }

  if (photoData) {
    if (img) {
      img.src = photoData;
      img.style.objectPosition = '50% 50%';
      img.classList.remove('u-hidden');
    }
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
  var fields = ['profileName', 'profileHeight', 'profileShoeSize', 'profileCity', 'profileArea'];
  var keys = ['name', 'height', 'shoeSize', 'city', 'area'];
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

/** Save the subset of profile fields supported by the backend contract. */
async function saveProfileForm() {
  if (!appState.user) {
    showToast('Your session could not be verified. Please log in again.', 'error');
    return false;
  }

  var heightInput = (document.getElementById('profileHeight') || {}).value || '';
  var heightMatch = heightInput.match(/\d+(?:\.\d+)?/);
  var height = heightMatch ? Number(heightMatch[0]) : null;
  if (height !== null && (height < 50 || height > 250)) {
    showToast('Height must be between 50 and 250 cm.', 'error');
    return false;
  }

  var favoriteStyles = getMultiSelectValues('profileFavoriteStylesChips', 'pf-chip--active');
  var payload = {
    height_cm: height,
    name: ((document.getElementById('profileName') || {}).value || '').trim(),
    gender: getSelectedValue('profileGenderChips', 'pf-chip--active'),
    top_size: getSelectedValue('profileTopSizePills', 'pf-size-pill--active'),
    bottom_size: getSelectedValue('profileBottomSizePills', 'pf-size-pill--active'),
    shoe_size: ((document.getElementById('profileShoeSize') || {}).value || '').trim(),
    skin_tone: getSelectedValue('profileSkinToneSwatches', 'pf-tone-chip--active'),
    style_preference: favoriteStyles.join(', '),
    location_city: ((document.getElementById('profileCity') || {}).value || '').trim(),
    location_area: ((document.getElementById('profileArea') || {}).value || '').trim(),
    fit_preference: getSelectedValue('profileFitPreferenceChips', 'pf-chip--active'),
    outfit_vibe: getSelectedValue('profileOutfitVibeChips', 'pf-chip--active'),
    preferred_colors: getMultiSelectValues('profilePreferredColorsChips', 'pf-color-chip--active').join(', '),
    shopping_style: getSelectedValue('profileShoppingStyleChips', 'pf-chip--active'),
  };
  var saveBtn = document.getElementById('profileSaveBtn');
  var originalLabel = saveBtn ? saveBtn.textContent : '';
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';
  }

  try {
    var saved = await apiRequest('/profile/' + appState.user.id, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    appState.profile = mapProfileFromApi(saved);
    appState.profileError = '';
    showToast('Profile saved', 'success');
    return true;
  } catch (error) {
    appState.profileError = error.message;
    showToast(error.message, 'error');
    return false;
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = originalLabel || 'Save Changes';
    }
  }
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

function dataUrlToFile(dataUrl, fileName) {
  var parts = dataUrl.split(',');
  var mimeMatch = parts[0].match(/data:([^;]+)/);
  var mimeType = mimeMatch ? mimeMatch[1] : 'image/jpeg';
  var binary = atob(parts[1] || '');
  var bytes = new Uint8Array(binary.length);
  for (var i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], fileName || 'wardrobe-item.jpg', { type: mimeType });
}

/** Upload a wardrobe item and user-confirmed metadata to the backend. */
async function saveWardrobeItem(item) {
  if (!appState.user) throw new Error('Your session could not be verified. Please log in again.');
  var file = item.file || (item.imageDataUrl ? dataUrlToFile(item.imageDataUrl, item.name) : null);
  if (!file) throw new Error('A clothing image is required to save this wardrobe item.');

  var formData = new FormData();
  formData.append('file', file, file.name || item.name || 'wardrobe-item.jpg');
  formData.append('category', item.category || '');
  formData.append('subtype', item.subtype || item.name || '');
  formData.append('style_tags', item.styleVibe || '');
  formData.append('material_tags', item.material || '');
  formData.append('occasion_tags', Array.isArray(item.occasions) ? item.occasions.join(', ') : (item.occasions || ''));
  formData.append('brand', item.brand || '');
  formData.append('formality_level', item.formalityLevel || '');
  formData.append('season_suitability', item.seasonSuitability || '');
  formData.append('color', item.color || '');
  formData.append('description', item.notes || item.description || '');

  var saved = await apiRequest('/wardrobe/upload', {
    method: 'POST',
    body: formData,
  });
  appState.wardrobe.unshift(mapWardrobeFromApi(saved));
  appState.wardrobeError = '';
  renderWardrobeSidebar();
  var wv = document.getElementById('wardrobeView');
  if (wv && !wv.classList.contains('u-hidden')) renderWardrobeView();
  return saved;
}

/** Update user-confirmed wardrobe metadata while preserving the saved image. */
async function updateWardrobeItem(itemId, item) {
  var updated = await apiRequest('/wardrobe/' + itemId, {
    method: 'PATCH',
    body: JSON.stringify({
      category: item.category || 'Item',
      subtype: item.subtype || '',
      color: item.color || '',
      description: item.notes || '',
      style_tags: item.styleVibe || '',
      material_tags: item.material || '',
      occasion_tags: Array.isArray(item.occasions) ? item.occasions.join(', ') : (item.occasions || ''),
      brand: item.brand || '',
      formality_level: item.formalityLevel || '',
      season_suitability: item.seasonSuitability || '',
    }),
  });
  var mapped = mapWardrobeFromApi(updated);
  appState.wardrobe = getWardrobeItems().map(function(existing) {
    return existing.id === itemId ? mapped : existing;
  });
  renderWardrobeSidebar();
  renderWardrobeView();
  renderProfileView();
  showToast('Wardrobe details updated', 'success');
  return mapped;
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

/** Legacy chat preview retained as a manual-details fallback. */
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
    '<button class="upload-card__save" data-category="' + category + '" data-img="' + dataUrl + '" data-filename="' + escapeHtml(fileName || category) + '">Add details manually</button>';

  messages.appendChild(card);
  scrollChatToBottom();

  card.querySelector('.upload-card__save').addEventListener('click', function() {
    var cat = this.getAttribute('data-category');
    var img = this.getAttribute('data-img');
    var fname = this.getAttribute('data-filename');

    card.remove();
    showAnalysisCard(cat, img, fname, {
      category: cat,
      subtype: fname,
      color: '',
      style_tags: [],
      occasion_tags: [],
      description: '',
    });
  });
}

/** Show editable manual wardrobe draft card — compact fashion-item layout */
function showAnalysisCard(category, imageDataUrl, fileName, analysis) {
  var messages = document.getElementById('chatMessages');
  if (!messages) return;

  var cardId = 'analysisCard-' + Date.now();
  var normalizedAnalysis = {
    category: analysis.category || category,
    subtype: analysis.subtype || fileName || category,
    color: analysis.color || '',
    styleVibe: analysis.styleVibe || analysis.style || (Array.isArray(analysis.style_tags) ? analysis.style_tags.join(', ') : ''),
    material: analysis.material || analysis.material_guess || '',
    occasions: Array.isArray(analysis.occasions || analysis.occasion_tags)
      ? (analysis.occasions || analysis.occasion_tags)
      : String(analysis.occasions || analysis.occasion_tags || '').split(',').map(function(value) { return value.trim(); }).filter(Boolean),
    notes: analysis.notes || analysis.description || '',
  };
  analysis = normalizedAnalysis;
  category = normalizedAnalysis.category;

  // Inject bot preamble message
  addChatMessage('bot', "Add the details you know, then <strong>confirm to save.</strong>");

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
          getDraftSvg() + ' Manual details' +
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
  document.getElementById(cardId + '-save').addEventListener('click', async function() {
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
    var saveBtn = this;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';
    try {
      await saveWardrobeItem(item);
      saveBtn.textContent = '✓ Saved';
    } catch (error) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save to Wardrobe';
      showToast(error.message, 'error');
    }
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
          '<span class="analysis-card__draft-badge">' + getDraftSvg() + ' Manual details</span>' +
          '<div class="analysis-card__category">' + escapeHtml(category) + '</div>' +
          newTags +
        '</div>';
      card.querySelector('.analysis-card__footer').classList.remove('u-hidden');

      // Re-wire save with updated tag IDs
      document.getElementById(cardId + '-save').addEventListener('click', async function() {
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
        var saveButton = document.getElementById(cardId + '-save');
        saveButton.disabled = true;
        saveButton.textContent = 'Saving…';
        try {
          await saveWardrobeItem(item);
          saveButton.textContent = '✓ Saved';
        } catch (error) {
          saveButton.disabled = false;
          saveButton.textContent = 'Save to Wardrobe';
          showToast(error.message, 'error');
        }
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

/** Render wardrobe items in sidebar drawer */
async function deleteWardrobeItem(itemId) {
  try {
    await apiRequest('/wardrobe/' + itemId, { method: 'DELETE' });
    appState.wardrobe = getWardrobeItems().filter(function(item) { return item.id !== itemId; });
    delete wardrobeSelected[itemId];
    renderWardrobeSidebar();
    var wv = document.getElementById('wardrobeView');
    if (wv && !wv.classList.contains('u-hidden')) renderWardrobeView();
    return true;
  } catch (error) {
    showToast(error.message, 'error');
    return false;
  }
}

/** Toggle wardrobe select mode on/off */
function toggleWardrobeSelectMode() {
  wardrobeSelectMode = !wardrobeSelectMode;
  wardrobeActionMenuId = null;
  if (!wardrobeSelectMode) {
    wardrobeSelected = {};
  }
  var wv = document.getElementById('wardrobeView');
  if (wv && !wv.classList.contains('u-hidden')) renderWardrobeView();
}

/** Delete multiple wardrobe items at once */
async function deleteWardrobeItems(ids) {
  var results = await Promise.all(ids.map(deleteWardrobeItem));
  return results.every(Boolean);
}

/** Update bulk action bar count and visibility */
function updateBulkBar() {
  var count = Object.keys(wardrobeSelected).length;
  var bar = document.getElementById('wardrobeBulkBar');
  var countEl = document.getElementById('wardrobeBulkCount');
  var deleteBtn = document.getElementById('wardrobeBulkDelete');
  if (bar) {
    bar.classList.toggle('u-hidden', !wardrobeSelectMode);
  }
  if (countEl) {
    countEl.textContent = count + ' selected';
  }
  if (deleteBtn) {
    deleteBtn.disabled = count === 0;
  }
}

function renderWardrobeSidebar() {
  var container = document.getElementById('sidebarWardrobe');
  if (!container) return;

  if (appState.wardrobeLoading) {
    container.innerHTML = '<p class="sidebar-wardrobe__empty">Loading wardrobe…</p>';
    return;
  }
  if (appState.wardrobeError) {
    container.innerHTML = '<p class="sidebar-wardrobe__empty">' + escapeHtml(appState.wardrobeError) + '</p>';
    return;
  }

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
  var view = document.getElementById('wardrobeView');
  if (!grid) return;

  var items = getWardrobeItems();

  if (appState.wardrobeLoading) {
    grid.setAttribute('aria-busy', 'true');
    var skeletonHtml = Array.from({ length: 8 }, function() {
      return '<div class="wardrobe-card wardrobe-card--skeleton" aria-hidden="true">' +
        '<div class="wardrobe-card__img wutt-skeleton"></div>' +
        '<div class="wardrobe-card__info">' +
          '<div class="wutt-skeleton wardrobe-skeleton__title"></div>' +
          '<div class="wutt-skeleton wardrobe-skeleton__meta"></div>' +
          '<div class="wardrobe-card__tags">' +
            '<span class="wutt-skeleton wardrobe-skeleton__tag"></span>' +
            '<span class="wutt-skeleton wardrobe-skeleton__tag wardrobe-skeleton__tag--short"></span>' +
          '</div>' +
        '</div>' +
      '</div>';
    }).join('');
    grid.innerHTML = '';
    if (empty) {
      empty.style.display = 'none';
      grid.appendChild(empty);
    }
    grid.insertAdjacentHTML('beforeend', skeletonHtml);
    return;
  }

  grid.removeAttribute('aria-busy');

  if (appState.wardrobeError) {
    grid.innerHTML = '<div class="wardrobe-view__empty">'
      + '<h3 class="wardrobe-view__empty-title">'
      + 'Could not load your wardrobe'
      + '</h3>'
      + (appState.wardrobeError ? '<p class="wardrobe-view__empty-hint">' + escapeHtml(appState.wardrobeError) + '</p>' : '')
      + '</div>';
    return;
  }

  // Sync select mode class
  if (view) {
    view.classList.toggle('wardrobe-view--select-mode', wardrobeSelectMode);
  }

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
    var tagValues = [];
    [item.color, item.styleVibe].forEach(function(value) {
      if (value) tagValues = tagValues.concat(String(value).split(','));
    });
    if (Array.isArray(item.occasions)) {
      tagValues = tagValues.concat(item.occasions);
    } else if (item.occasions) {
      tagValues = tagValues.concat(String(item.occasions).split(','));
    }
    var tagHtml = tagValues
      .map(function(value) { return String(value).trim(); })
      .filter(Boolean)
      .slice(0, 3)
      .map(function(value) {
        return '<span class="wardrobe-card__tag">' + escapeHtml(value) + '</span>';
      })
      .join('');

    var isSelected = wardrobeSelected[item.id];
    var selectedClass = isSelected ? ' wardrobe-card--selected' : '';
    var menuOpenClass = wardrobeActionMenuId === item.id
      ? ' wardrobe-card--menu-open'
      : '';
    var checkedAttr = isSelected ? ' checked' : '';
    var itemLabel = escapeHtml(item.name || item.category || 'wardrobe item');

    html += '<div class="wardrobe-card' + selectedClass + menuOpenClass + '" data-category="' + escapeHtml(item.category || '') + '" data-item-id="' + item.id + '">' +
      '<div class="wardrobe-card__select">' +
        '<input type="checkbox" data-select-id="' + item.id + '" aria-label="Select ' + itemLabel + '"' + checkedAttr + '>' +
      '</div>' +
      imgHtml +
      '<div class="wardrobe-card__info">' +
        '<div class="wardrobe-card__name">' + escapeHtml(item.name || item.category || 'Untitled') + '</div>' +
        '<div class="wardrobe-card__meta">' + colorDot + escapeHtml(metaParts.join(' · ')) + '</div>' +
        (tagHtml ? '<div class="wardrobe-card__tags">' + tagHtml + '</div>' : '') +
      '</div>' +
      '<div class="wardrobe-card__actions">' +
        '<button class="wardrobe-card__menu-trigger" type="button" aria-label="Actions for ' + itemLabel + '" aria-haspopup="menu" aria-expanded="' + String(wardrobeActionMenuId === item.id) + '" aria-controls="wardrobeMenu' + item.id + '">' +
          '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg>' +
        '</button>' +
        '<div class="wardrobe-card__menu" id="wardrobeMenu' + item.id + '" role="menu" aria-hidden="' + String(wardrobeActionMenuId !== item.id) + '">' +
          '<button class="wardrobe-card__edit" data-edit-id="' + item.id + '" type="button" role="menuitem">Edit</button>' +
          '<button class="wardrobe-card__delete" data-delete-id="' + item.id + '" type="button" role="menuitem">Remove</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  });

  // Keep empty state node, replace cards only
  if (empty) {
    grid.innerHTML = '';
    grid.appendChild(empty);
  }
  grid.insertAdjacentHTML('beforeend', html);

  // Wire single delete buttons
  grid.querySelectorAll('.wardrobe-card__edit').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      closeWardrobeActionMenu();
      if (typeof window.openWardrobeEditModal === 'function') {
        window.openWardrobeEditModal(parseInt(btn.getAttribute('data-edit-id'), 10));
      }
    });
  });

  grid.querySelectorAll('.wardrobe-card__delete').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      var id = parseInt(btn.getAttribute('data-delete-id'), 10);
      closeWardrobeActionMenu();
      if (confirm('Delete this item from your wardrobe?')) {
        btn.disabled = true;
        deleteWardrobeItem(id);
      }
    });
  });

  function applyWardrobeActionMenuState(options) {
    var focusFirstItem = options && options.focusFirstItem;
    grid.querySelectorAll('.wardrobe-card').forEach(function(card) {
      var itemId = parseInt(card.getAttribute('data-item-id'), 10);
      var isOpen = itemId === wardrobeActionMenuId && !wardrobeSelectMode;
      var trigger = card.querySelector('.wardrobe-card__menu-trigger');
      var menu = card.querySelector('.wardrobe-card__menu');
      card.classList.toggle('wardrobe-card--menu-open', isOpen);
      if (trigger) trigger.setAttribute('aria-expanded', String(isOpen));
      if (menu) menu.setAttribute('aria-hidden', String(!isOpen));
      if (isOpen && focusFirstItem && menu) {
        var firstItem = menu.querySelector('[role="menuitem"]');
        if (firstItem) firstItem.focus();
      }
    });
  }

  function closeWardrobeActionMenu(restoreFocus) {
    var previousId = wardrobeActionMenuId;
    wardrobeActionMenuId = null;
    applyWardrobeActionMenuState();
    if (restoreFocus && previousId !== null) {
      var trigger = grid.querySelector('[data-item-id="' + previousId + '"] .wardrobe-card__menu-trigger');
      if (trigger) trigger.focus();
    }
  }

  function closeWardrobeCardActions() {
    wardrobeActionMenuId = null;
    applyWardrobeActionMenuState();
  }

  applyWardrobeActionMenuState();

  if (!grid.dataset.cardMenuWired) {
    grid.dataset.cardMenuWired = 'true';
    grid.addEventListener('click', function(e) {
      var card = e.target.closest('.wardrobe-card');
      if (!card) return;
      if (wardrobeSelectMode) {
        if (e.target.closest('.wardrobe-card__select')) return;
        var checkbox = card.querySelector('.wardrobe-card__select input');
        if (checkbox) {
          checkbox.checked = !checkbox.checked;
          checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        }
        return;
      }
      var trigger = e.target.closest('.wardrobe-card__menu-trigger');
      if (!trigger) return;
      e.stopPropagation();
      var itemId = parseInt(card.getAttribute('data-item-id'), 10);
      wardrobeActionMenuId = wardrobeActionMenuId === itemId ? null : itemId;
      applyWardrobeActionMenuState();
    });

    grid.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeWardrobeActionMenu(true);
        return;
      }
      var trigger = e.target.closest('.wardrobe-card__menu-trigger');
      if (trigger && e.key === 'ArrowDown') {
        e.preventDefault();
        var card = trigger.closest('.wardrobe-card');
        wardrobeActionMenuId = parseInt(card.getAttribute('data-item-id'), 10);
        applyWardrobeActionMenuState({ focusFirstItem: true });
      }
    });

    document.addEventListener('click', function(e) {
      if (e.target.closest('.wardrobe-card__actions')) return;
      closeWardrobeCardActions();
    });

    var wardrobeScroll = grid.closest('.wardrobe-view__scroll');
    if (wardrobeScroll) {
      wardrobeScroll.addEventListener('scroll', function() {
        closeWardrobeCardActions();
      }, { passive: true });
    }
  }

  // Wire select checkboxes
  grid.querySelectorAll('.wardrobe-card__select input[type="checkbox"]').forEach(function(cb) {
    cb.addEventListener('change', function() {
      var id = parseInt(cb.getAttribute('data-select-id'), 10);
      var card = cb.closest('.wardrobe-card');
      if (cb.checked) {
        wardrobeSelected[id] = true;
        if (card) {
          card.classList.add('wardrobe-card--selected');
        }
      } else {
        delete wardrobeSelected[id];
        if (card) {
          card.classList.remove('wardrobe-card--selected');
        }
      }
      updateBulkBar();
    });
  });

  // Wire select mode toggle
  var selectBtn = document.getElementById('wardrobeSelectBtn');
  if (selectBtn) {
    selectBtn.setAttribute('aria-pressed', String(wardrobeSelectMode));
    selectBtn.onclick = toggleWardrobeSelectMode;
  }

  // Wire bulk action bar
  var bulkDelete = document.getElementById('wardrobeBulkDelete');
  var bulkCancel = document.getElementById('wardrobeBulkCancel');
  if (bulkDelete) {
    bulkDelete.onclick = async function() {
      var ids = Object.keys(wardrobeSelected).map(Number);
      if (!ids.length) return;
      if (confirm('Delete ' + ids.length + ' item' + (ids.length > 1 ? 's' : '') + ' from your wardrobe?')) {
        bulkDelete.disabled = true;
        if (await deleteWardrobeItems(ids)) toggleWardrobeSelectMode();
        bulkDelete.disabled = false;
      }
    };
  }
  if (bulkCancel) {
    bulkCancel.onclick = toggleWardrobeSelectMode;
  }

  // Update bulk bar count
  updateBulkBar();

  // Wire filter chips
  var filterContainer = document.getElementById('wardrobeFilters');
  if (filterContainer) {
    filterContainer.querySelectorAll('.wardrobe-view__filter').forEach(function(btn) {
      btn.addEventListener('click', function() {
        filterContainer.querySelectorAll('.wardrobe-view__filter').forEach(function(b) { b.classList.remove('wardrobe-view__filter--active'); });
        btn.classList.add('wardrobe-view__filter--active');
        var filter = btn.getAttribute('data-filter');
        grid.querySelectorAll('.wardrobe-card').forEach(function(card) {
          var category = card.getAttribute('data-category').toLowerCase();
          var normalizedCategory = category === 'top' ? 'tops'
            : category === 'bottom' ? 'bottoms'
            : category === 'dress' ? 'dresses'
            : category === 'shoe' ? 'shoes'
            : category === 'accessory' ? 'accessories'
            : category;
          if (filter === 'all' || normalizedCategory === filter) {
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
      + '<div class="chat-msg__bubble">'
      + (html.indexOf('<article') === 0 ? html : '<p>' + html + '</p>')
      + '</div>';
  } else {
    msg.innerHTML = '<div class="chat-msg__bubble">'
      + (html.indexOf('<img') === 0 ? html : '<p>' + html + '</p>')
      + '</div>';
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

// Google login and registration share the same server-managed OAuth flow.
$('#googleLoginBtn')?.addEventListener('click', startGoogleOAuth);
$('#googleRegisterBtn')?.addEventListener('click', startGoogleOAuth);
$('#appleRegisterBtn')?.addEventListener('click', (e) => { e.preventDefault(); showToast('Apple sign-in coming soon'); });

console.log('WUTT — Your city. Your weather. Your look. 💫');
