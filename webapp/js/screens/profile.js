import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';
import Router from '../router.js';
import TelegramSDK from '../telegram.js';

let _container = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  renderLoading(_container, skeletonCard(4));

  const res = await ApiClient.getMe();
  if (!res.ok) {
    renderError(_container, res.message, () => load());
    return;
  }
  
  render(res.data);
}

function render(user) {
  const name = user.first_name || user.username || 'VIP User';
  const initial = name.charAt(0).toUpperCase();
  const userId = user.user_id || user.telegram_id || 0;
  
  const html = `
    <div class="card mb-3 text-center">
      <div class="avatar mx-auto mb-2" style="width: 72px; height: 72px; font-size: 28px; line-height: 72px; border-radius: 50%; background: var(--bg-elevated); border: 2px solid var(--accent-gold); color: var(--accent-gold);">
        ${initial}
      </div>
      <h2 class="section-title mb-1">${name}</h2>
      <span class="badge badge-warning mb-2">${user.vip_badge || user.vip_title || 'Novice VIP'}</span>
      <p class="text-secondary font-size-xs">ID: ${userId} • Code: <code>${user.ref_code || 'N/A'}</code></p>
      
      <div class="d-flex gap-2 mt-3 text-center">
        <div class="flex-1 p-2 bg-elevated border-radius-md">
          <div class="font-size-lg font-weight-bold">${user.credits ?? 0}</div>
          <div class="font-size-xs text-secondary">Credits</div>
        </div>
        <div class="flex-1 p-2 bg-elevated border-radius-md">
          <div class="font-size-lg font-weight-bold">Level ${user.vip_level || 1}</div>
          <div class="font-size-xs text-secondary">VIP Rank</div>
        </div>
        <div class="flex-1 p-2 bg-elevated border-radius-md">
          <div class="font-size-lg font-weight-bold">${user.referral_count ?? 0}</div>
          <div class="font-size-xs text-secondary">Invites</div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <h3 class="section-title mb-2">Settings & History</h3>
      <div class="d-flex flex-column gap-2">
        <button class="list-item w-100 border-none bg-elevated p-3 border-radius-md d-flex justify-between align-center" onclick="Router.navigate('history-rewards')">
          <div class="d-flex align-center gap-2">
            <span class="font-size-lg">🎁</span>
            <span class="font-weight-medium font-size-sm">Rewards History</span>
          </div>
          <span class="text-secondary">›</span>
        </button>
        <button class="list-item w-100 border-none bg-elevated p-3 border-radius-md d-flex justify-between align-center" onclick="Router.navigate('history-verification')">
          <div class="d-flex align-center gap-2">
            <span class="font-size-lg">✅</span>
            <span class="font-weight-medium font-size-sm">Verification History</span>
          </div>
          <span class="text-secondary">›</span>
        </button>
        <button class="list-item w-100 border-none bg-elevated p-3 border-radius-md d-flex justify-between align-center" onclick="Router.navigate('history-referrals')">
          <div class="d-flex align-center gap-2">
            <span class="font-size-lg">👥</span>
            <span class="font-weight-medium font-size-sm">Referral History</span>
          </div>
          <span class="text-secondary">›</span>
        </button>
        <button class="list-item w-100 border-none bg-elevated p-3 border-radius-md d-flex justify-between align-center" onclick="Router.navigate('notifications')">
          <div class="d-flex align-center gap-2">
            <span class="font-size-lg">🔔</span>
            <span class="font-weight-medium font-size-sm">Notifications</span>
          </div>
          <span class="text-secondary">›</span>
        </button>
        <button class="list-item w-100 border-none bg-elevated p-3 border-radius-md d-flex justify-between align-center" onclick="Router.navigate('settings')">
          <div class="d-flex align-center gap-2">
            <span class="font-size-lg">⚙️</span>
            <span class="font-weight-medium font-size-sm">Settings</span>
          </div>
          <span class="text-secondary">›</span>
        </button>
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
}
