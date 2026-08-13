/**
 * TelegramSDK — Telegram Mini App SDK integration module.
 * All methods degrade gracefully when running outside Telegram.
 */

const tg = window?.Telegram?.WebApp;

const TelegramSDK = {
  isAvailable: Boolean(tg),

  init() {
    if (!tg) return;
    tg.ready();
    tg.expand();
    this._applyTheme();
    this._applySafeArea();
    this._applyViewport();
  },

  _applyTheme() {
    if (!tg?.themeParams) return;
    const root = document.documentElement;
    const p = tg.themeParams;
    // Map Telegram theme to our CSS custom properties
    if (p.bg_color) root.style.setProperty('--tg-bg', p.bg_color);
    if (p.text_color) root.style.setProperty('--tg-text', p.text_color);
    if (p.hint_color) root.style.setProperty('--tg-hint', p.hint_color);
    if (p.link_color) root.style.setProperty('--tg-link', p.link_color);
    if (p.button_color) root.style.setProperty('--tg-button', p.button_color);
    if (p.button_text_color) root.style.setProperty('--tg-button-text', p.button_text_color);
    if (p.secondary_bg_color) root.style.setProperty('--tg-secondary-bg', p.secondary_bg_color);
  },

  _applySafeArea() {
    // Safe area is handled via CSS env() — this just sets a JS-accessible variable
    const root = document.documentElement;
    root.style.setProperty('--safe-area-bottom', tg?.safeAreaInset?.bottom ? `${tg.safeAreaInset.bottom}px` : 'env(safe-area-inset-bottom, 16px)');
    root.style.setProperty('--safe-area-top', tg?.safeAreaInset?.top ? `${tg.safeAreaInset.top}px` : 'env(safe-area-inset-top, 0px)');
  },

  _applyViewport() {
    const root = document.documentElement;
    const vh = tg?.viewportStableHeight || tg?.viewportHeight || window.innerHeight;
    root.style.setProperty('--tg-viewport-height', `${vh}px`);
    if (tg) {
      tg.onEvent('viewportChanged', () => {
        const h = tg.viewportStableHeight || tg.viewportHeight || window.innerHeight;
        root.style.setProperty('--tg-viewport-height', `${h}px`);
      });
    }
  },

  getInitData() {
    return tg?.initData || '';
  },

  getStartParam() {
    return tg?.initDataUnsafe?.start_param
      || new URLSearchParams(window.location.search).get('startapp')
      || null;
  },

  showBackButton(callback) {
    if (!tg?.BackButton) return;
    tg.BackButton.onClick(callback);
    tg.BackButton.show();
  },

  hideBackButton() {
    tg?.BackButton?.hide();
  },

  haptic(type = 'light') {
    // type: 'light' | 'medium' | 'heavy' (impact) or 'success' | 'error' | 'warning' (notification)
    if (!tg?.HapticFeedback) return;
    try {
      if (['success', 'error', 'warning'].includes(type)) {
        tg.HapticFeedback.notificationOccurred(type);
      } else {
        tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {}
  },

  openLink(url) {
    if (!url) return;
    if (tg?.openTelegramLink && url.includes('t.me/')) {
      tg.openTelegramLink(url);
    } else if (tg?.openLink) {
      tg.openLink(url);
    } else {
      window.open(url, '_blank');
    }
  },

  close() {
    tg?.close();
  },

  showMainButton(text, callback) {
    if (!tg?.MainButton) return;
    tg.MainButton.setText(text);
    tg.MainButton.onClick(callback);
    tg.MainButton.show();
  },

  hideMainButton() {
    tg?.MainButton?.hide();
  },

  expand() {
    tg?.expand();
  }
};

export default TelegramSDK;
