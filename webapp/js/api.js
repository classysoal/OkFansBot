/**
 * ApiClient — Authoritative API client for OkFansBot Mini App.
 * Returns discriminated {ok, data} | {ok, error, message, status} — never throws.
 * Backend is sole authority. Never trust frontend state for authorization.
 */

import Cache from './cache.js';
import TelegramSDK from './telegram.js';

const API_BASE = window.location.hostname.includes('vercel.app')
  ? 'https://okfansbot-826r.onrender.com'
  : window.location.origin;

const REQUEST_TIMEOUT_MS = 12000;

// In-flight deduplication map: url -> Promise
const _inFlight = new Map();

// Error code mapping
const ERROR_CODES = {
  401: 'AUTH_REQUIRED',
  403: 'AUTH_REQUIRED',
  429: 'RATE_LIMITED',
  404: 'NOT_FOUND',
  422: 'VALIDATION_ERROR',
  500: 'SERVER_ERROR',
  502: 'SERVER_ERROR',
  503: 'SERVER_ERROR',
};

// Human-readable messages for each error code
const ERROR_MESSAGES = {
  AUTH_REQUIRED: 'Please open this app through Telegram.',
  AUTH_EXPIRED: 'Your session has expired. Please reload.',
  RATE_LIMITED: 'Too many requests. Please wait a moment.',
  NETWORK_ERROR: 'No connection. Check your network and try again.',
  TELEGRAM_UNAVAILABLE: 'Telegram is temporarily unavailable. Try again shortly.',
  VALIDATION_ERROR: 'Invalid request. Please try again.',
  NOT_FOUND: 'The requested resource was not found.',
  SERVER_ERROR: 'Something went wrong on our end. Try again shortly.',
};

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const initData = TelegramSDK.getInitData();
  if (initData) headers['X-Telegram-Init-Data'] = initData;
  const token = Cache.getSession();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function handleCacheInvalidation(response) {
  const invalidate = response.headers.get('X-Cache-Invalidate');
  if (!invalidate) return;
  invalidate.split(',').map(s => s.trim()).forEach(key => Cache.evict(key));
}

async function _request(method, path, body = null) {
  const url = `${API_BASE}${path}`;
  const isGet = method === 'GET';

  // Deduplication for GET requests
  if (isGet && _inFlight.has(url)) {
    return _inFlight.get(url);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  const fetchOptions = {
    method,
    headers: getHeaders(),
    signal: controller.signal,
  };
  if (body) fetchOptions.body = JSON.stringify(body);

  const promise = (async () => {
    try {
      const response = await fetch(url, fetchOptions);
      clearTimeout(timeout);
      handleCacheInvalidation(response);

      let data;
      const ct = response.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        // Try to extract typed error code from response body
        const errorCode = data?.error || ERROR_CODES[response.status] || 'SERVER_ERROR';
        const message = data?.message || ERROR_MESSAGES[errorCode] || 'An error occurred.';
        
        // Special handling for auth expiry vs auth required
        const finalCode = (response.status === 401 && data?.detail?.includes('Expired')) 
          ? 'AUTH_EXPIRED' : errorCode;
        
        return { ok: false, error: finalCode, message, status: response.status };
      }

      return { ok: true, data };
    } catch (err) {
      clearTimeout(timeout);
      if (err.name === 'AbortError') {
        return { ok: false, error: 'NETWORK_ERROR', message: 'Request timed out. Check your connection.', status: 0 };
      }
      if (!navigator.onLine) {
        return { ok: false, error: 'NETWORK_ERROR', message: ERROR_MESSAGES.NETWORK_ERROR, status: 0 };
      }
      return { ok: false, error: 'SERVER_ERROR', message: ERROR_MESSAGES.SERVER_ERROR, status: 0 };
    } finally {
      if (isGet) _inFlight.delete(url);
    }
  })();

  if (isGet) _inFlight.set(url, promise);
  return promise;
}

// Debounce helper
const _debounceTimers = {};
function debounce(key, fn, delay = 300) {
  if (_debounceTimers[key]) clearTimeout(_debounceTimers[key]);
  _debounceTimers[key] = setTimeout(fn, delay);
}

const ApiClient = {
  // Auth
  async auth(initData) {
    return _request('POST', '/api/auth/miniapp', { initData });
  },
  async logout() {
    return _request('POST', '/api/auth/logout');
  },

  // Dashboard & Profile
  async getDashboard() {
    return _request('GET', '/api/dashboard');
  },
  async getMe() {
    return _request('GET', '/api/me');
  },

  // Verification
  async getVerification() {
    return _request('GET', '/api/verification');
  },
  async checkVerification() {
    // Verification results are NEVER cached
    return _request('POST', '/api/verification/check');
  },

  // Rewards
  async claimDaily() {
    return _request('POST', '/api/rewards/claim-daily');
  },
  async redeemBundle() {
    return _request('POST', '/api/rewards/redeem');
  },

  // Referrals
  async getReferrals() {
    return _request('GET', '/api/referrals');
  },

  // History (always paginated, never cached)
  async getRewardHistory(page = 1) {
    return _request('GET', `/api/user/history/rewards?page=${page}`);
  },
  async getVerificationHistory(page = 1) {
    return _request('GET', `/api/user/history/verification?page=${page}`);
  },
  async getReferralHistory(page = 1) {
    return _request('GET', `/api/user/history/referrals?page=${page}`);
  },

  // Notifications
  async getNotifications(page = 1) {
    return _request('GET', `/api/notifications?page=${page}`);
  },
  async markNotificationsRead(ids = []) {
    return _request('POST', '/api/notifications/read', { notification_ids: ids });
  },

  // Settings
  async getSettings() {
    return _request('GET', '/api/settings');
  },
  async updateSettings(data) {
    return _request('POST', '/api/settings', data);
  },
};

export { ApiClient, debounce };
export default ApiClient;
