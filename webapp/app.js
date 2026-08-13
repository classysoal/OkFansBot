/**
 * OkFansBot v2.0 Mini App — Main Orchestrator
 * Thin entry point. Business logic lives in screen modules and services.
 */
import AppState from './js/state.js';
import TelegramSDK from './js/telegram.js';
import Cache from './js/cache.js';
import ApiClient from './js/api.js';
import Router from './js/router.js';
import { showToast } from './js/components/toast.js';

// Screen modules
import * as HomeScreen from './js/screens/home.js';
import * as VerificationScreen from './js/screens/verification.js';
import * as VipScreen from './js/screens/vip.js';
import * as InviteScreen from './js/screens/invite.js';
import * as ProfileScreen from './js/screens/profile.js';
import * as HistoryRewardsScreen from './js/screens/history_rewards.js';
import * as HistoryVerifScreen from './js/screens/history_verification.js';
import * as HistoryReferralsScreen from './js/screens/history_referrals.js';
import * as NotificationsScreen from './js/screens/notifications.js';
import * as SettingsScreen from './js/screens/settings.js';

const SCREENS = {
  home: HomeScreen,
  verification: VerificationScreen,
  vip: VipScreen,
  invite: InviteScreen,
  profile: ProfileScreen,
  'history-rewards': HistoryRewardsScreen,
  'history-verification': HistoryVerifScreen,
  'history-referrals': HistoryReferralsScreen,
  notifications: NotificationsScreen,
  settings: SettingsScreen,
};

async function bootstrap() {
  // 1. Init Telegram SDK (theme, viewport, safe-area)
  TelegramSDK.init();

  // 2. Check URL for session token (Telegram OIDC callback)
  const urlParams = new URLSearchParams(window.location.search);
  const urlToken = urlParams.get('session_token');
  if (urlToken) {
    Cache.setSession(urlToken);
    if (urlParams.get('auth') === 'success') showToast('Logged in successfully', 'success');
  }

  // 3. Authenticate via initData (primary Mini App auth path)
  const initData = TelegramSDK.getInitData();
  if (initData) {
    AppState.set('auth.status', 'authenticating');
    const authResult = await ApiClient.auth(initData);
    if (authResult.ok) {
      Cache.setSession(authResult.data.session_token);
      AppState.set('auth.status', 'authenticated');
    } else if (authResult.error === 'AUTH_REQUIRED' || authResult.error === 'AUTH_EXPIRED') {
      Cache.clearSession();
      AppState.set('auth.status', 'failed');
    }
  } else if (Cache.getSession()) {
    AppState.set('auth.status', 'authenticated');
  }

  // 4. Show auth overlay if no auth available
  const overlay = document.getElementById('auth-overlay');
  if (AppState.auth.status !== 'authenticated' && !Cache.getSession() && !initData) {
    if (overlay) overlay.style.display = 'flex';
    return;
  }
  if (overlay) overlay.style.display = 'none';

  // 5. Init all screen modules & register with Router
  Router.registerScreens(SCREENS);
  for (const [id, screen] of Object.entries(SCREENS)) {
    const container = document.getElementById(`view-${id}`);
    if (container && screen.init) screen.init(container);
  }


  // 6. Wire bottom nav clicks
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      if (tab) {
        AppState.ui.screenStack = [tab];
        Router.navigate(tab, { replace: true });
        const screen = SCREENS[tab];
        if (screen?.load) screen.load();
      }
    });
  });

  // 7. Navigate to initial screen (process start param)
  Router.processStartParam();

  // 8. Load initial home data
  HomeScreen.load();
}

// Wire login button for external access fallback
window.loginWithTelegram = function() {
  if (TelegramSDK.isAvailable) {
    bootstrap();
  } else {
    window.location.href = 'https://t.me/OkFansBot/app';
  }
};

// Make Router navigable from screens
window.Router = Router;
window.showToast = showToast;
window.TelegramSDK = TelegramSDK;
window.ApiClient = ApiClient;
window.Cache = Cache;
window.AppState = AppState;

document.addEventListener('DOMContentLoaded', bootstrap);
