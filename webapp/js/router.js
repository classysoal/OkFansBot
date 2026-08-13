/**
 * Router — Maps start parameters to screens, manages screen stack.
 * Start params are navigation context ONLY — never auth/authorization proof.
 */

import TelegramSDK from './telegram.js';
import AppState from './state.js';

// Known start params → tab IDs
const START_PARAM_MAP = {
  'home': 'home',
  'verify': 'verification',
  'quest': 'verification',
  'vip': 'vip',
  'tiers': 'vip',
  'invite': 'invite',
  'ref': 'invite',
  'profile': 'profile',
};

// Tabs that can be top-level (shown in bottom nav)
const TOP_LEVEL_TABS = new Set(['home', 'verification', 'vip', 'invite', 'profile']);

let _backCallback = null;

const Router = {
  /** Navigate to a named screen, pushing to stack */
  navigate(screenId, opts = {}) {
    const { replace = false, silent = false } = opts;
    const stack = AppState.ui.screenStack;

    if (replace) {
      stack[stack.length - 1] = screenId;
    } else if (stack[stack.length - 1] !== screenId) {
      stack.push(screenId);
    }

    this._renderActiveScreen(screenId);
    this._updateBackButton();
    if (!silent) AppState.emit('navigation', screenId);
  },

  /** Go back one screen in the stack */
  back() {
    const stack = AppState.ui.screenStack;
    if (stack.length > 1) {
      stack.pop();
    }
    const prev = stack[stack.length - 1];
    this._renderActiveScreen(prev);
    this._updateBackButton();
    AppState.emit('navigation', prev);
  },

  /** Process Telegram start parameter after auth completes */
  processStartParam() {
    const param = TelegramSDK.getStartParam();
    if (!param) return;
    const key = param.toLowerCase().split('=')[0];
    const target = START_PARAM_MAP[key];
    if (target) {
      this.navigate(target, { replace: true, silent: true });
    }
    // Unknown params fall back to 'home' — already default
  },

  _renderActiveScreen(screenId) {
    // Hide all tab views
    document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
    // Show target
    const el = document.getElementById(`view-${screenId}`);
    if (el) el.classList.add('active');
    // Update bottom nav active state
    document.querySelectorAll('.nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === screenId);
    });
    AppState.ui.currentTab = screenId;
  },

  _updateBackButton() {
    const stack = AppState.ui.screenStack;
    const atRoot = stack.length <= 1 && TOP_LEVEL_TABS.has(stack[0]);
    if (atRoot) {
      TelegramSDK.hideBackButton();
    } else {
      TelegramSDK.showBackButton(() => this.back());
    }
  },

  /** Get current screen ID */
  current() {
    const stack = AppState.ui.screenStack;
    return stack[stack.length - 1] || 'home';
  }
};

export default Router;
