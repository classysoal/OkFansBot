/**
 * AppState — UI/session presentation state ONLY.
 * NEVER used for authorization, credits authority, or verification results.
 * Backend is the sole authority for all domain state.
 */

const _listeners = {};

const AppState = {
  auth: {
    status: 'idle', // 'idle' | 'authenticating' | 'authenticated' | 'failed'
    sessionToken: null,
  },
  ui: {
    currentTab: 'home',
    screenStack: ['home'],
    isLoading: false,
  },
  cache: {
    dashboard: { data: null, loadedAt: null },
    verification: { data: null, loadedAt: null },
    referrals: { data: null, loadedAt: null },
  },

  set(path, value) {
    const parts = path.split('.');
    let obj = this;
    for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
    obj[parts[parts.length - 1]] = value;
    this.emit(path, value);
  },

  get(path) {
    const parts = path.split('.');
    let obj = this;
    for (const p of parts) obj = obj?.[p];
    return obj;
  },

  on(event, fn) {
    if (!_listeners[event]) _listeners[event] = [];
    _listeners[event].push(fn);
  },

  off(event, fn) {
    if (_listeners[event]) _listeners[event] = _listeners[event].filter(f => f !== fn);
  },

  emit(event, data) {
    (_listeners[event] || []).forEach(fn => fn(data));
    (_listeners['*'] || []).forEach(fn => fn(event, data));
  },

  invalidateCache(key) {
    if (this.cache[key]) {
      this.cache[key].data = null;
      this.cache[key].loadedAt = null;
    }
  }
};

export default AppState;
