/**
 * Cache — Tiered cache strategy.
 * Static data: localStorage, 24h TTL
 * Live data: in-memory, 60s TTL, evicted on mutation
 * Never cached: verification check results, auth state, admin privileges
 */

const STATIC_TTL = 24 * 60 * 60 * 1000; // 24 hours
const LIVE_TTL = 60 * 1000; // 60 seconds

const Cache = {
  // In-memory store for live data
  _live: {},

  // --- Static cache (localStorage, 24h TTL) ---
  // Good for: tier definitions, channel metadata, rules/terms, UI config

  setStatic(key, data) {
    try {
      localStorage.setItem(`okfans_static_${key}`, JSON.stringify({
        data,
        expires: Date.now() + STATIC_TTL
      }));
    } catch (e) {}
  },

  getStatic(key) {
    try {
      const raw = localStorage.getItem(`okfans_static_${key}`);
      if (!raw) return null;
      const entry = JSON.parse(raw);
      if (Date.now() > entry.expires) {
        localStorage.removeItem(`okfans_static_${key}`);
        return null;
      }
      return entry.data;
    } catch (e) {
      return null;
    }
  },

  // --- Live cache (in-memory, 60s TTL) ---
  // Good for: dashboard payload, referral stats
  // Evicted immediately on mutation (claim, redeem, verify)

  setLive(key, data) {
    this._live[key] = { data, expires: Date.now() + LIVE_TTL };
  },

  getLive(key) {
    const entry = this._live[key];
    if (!entry) return null;
    if (Date.now() > entry.expires) {
      delete this._live[key];
      return null;
    }
    return entry.data;
  },

  evict(key) {
    delete this._live[key];
    try { localStorage.removeItem(`okfans_static_${key}`); } catch (e) {}
  },

  // Evict all mutation-sensitive keys (call after claim/redeem/verify)
  evictMutable() {
    ['dashboard', 'referrals'].forEach(k => this.evict(k));
  },

  // Session token — persisted across reloads
  getSession() {
    return localStorage.getItem('okfans_session_token');
  },

  setSession(token) {
    if (token) localStorage.setItem('okfans_session_token', token);
  },

  clearSession() {
    localStorage.removeItem('okfans_session_token');
  }
};

export default Cache;
