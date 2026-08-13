import ApiClient from '../api.js';
import Cache from '../cache.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonStat, skeletonCard } from '../components/skeleton.js';
import TelegramSDK from '../telegram.js';
import { showToast } from '../components/toast.js';
import Router from '../router.js';
import AppState from '../state.js';

let _container = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  const loadingHtml = `
    <div class="card mb-3">
      ${skeletonStat()}
    </div>
    <div class="home-actions mb-3">
      ${skeletonCard(2)}
    </div>
    <div class="home-activity">
      ${skeletonCard(3).repeat(2)}
    </div>
  `;
  renderLoading(_container, loadingHtml);

  let data = Cache.getLive('dashboard');
  if (!data) {
    const res = await ApiClient.getDashboard();
    if (!res.ok) {
      renderError(_container, res.message, () => load());
      return;
    }
    data = res.data;
    Cache.setLive('dashboard', data);
  }
  
  updateAppHeader(data);
  render(data);
}

function updateAppHeader(data) {
  const user = data?.user || {};
  const vip = data?.vip || {};
  
  const userNameEl = document.getElementById('userName');
  if (userNameEl) {
    userNameEl.textContent = user.first_name || user.username || 'VIP User';
  }
  
  const userCreditsEl = document.getElementById('userCredits');
  if (userCreditsEl) {
    userCreditsEl.textContent = user.credits ?? 0;
  }
  
  const vipRankEl = document.getElementById('vipRank');
  if (vipRankEl) {
    vipRankEl.textContent = vip.badge || vip.title || 'Novice VIP';
  }
  
  const userAvatarEl = document.getElementById('userAvatar');
  if (userAvatarEl) {
    if (user.photo_url) {
      userAvatarEl.style.backgroundImage = `url(${user.photo_url})`;
      userAvatarEl.style.backgroundSize = 'cover';
      userAvatarEl.textContent = '';
    } else if (user.first_name) {
      userAvatarEl.textContent = user.first_name.charAt(0).toUpperCase();
    }
  }
}

function render(data) {
  const user = data.user || {};
  const vip = data.vip || {};
  const activity = data.recent_activity || data.activity || [];
  const isStarterCompleted = user.starter_completed;
  const streak = user.checkin_streak || 0;

  const html = `
    <div class="card mb-3">
      <div class="d-flex justify-between align-center mb-2">
        <span class="font-weight-bold font-size-md text-primary" id="homeRankTitle">${vip.title || 'Novice VIP'}</span>
        <span class="badge ${isStarterCompleted ? 'badge-success' : 'badge-pending'}" id="homeRankTarget">
          ${isStarterCompleted ? '✓ VIP Active' : 'Quest Pending'}
        </span>
      </div>
      
      <div class="progress-container mb-3">
        <div class="progress-track">
          <div class="progress-fill" id="homeProgressBar" style="width: ${vip.progress_pct || 0}%;"></div>
        </div>
        <div class="progress-labels mt-1" id="homeProgressFooter">
          <span class="font-size-xs text-secondary">${vip.progress_pct || 0}% to ${vip.next_target || 'Next VIP Tier'}</span>
        </div>
      </div>
      
      <div class="d-flex gap-2 text-center">
        <div class="flex-1 p-2 bg-elevated border-radius-md border-card">
          <div class="font-size-lg font-weight-bold text-gold" id="dashCredits">${user.credits ?? 0} 🪙</div>
          <div class="font-size-xs text-secondary">Credits</div>
        </div>
        <div class="flex-1 p-2 bg-elevated border-radius-md border-card">
          <div class="font-size-lg font-weight-bold text-primary">${vip.bundle_size || 5} 🎬</div>
          <div class="font-size-xs text-secondary">Per Credit</div>
        </div>
        <div class="flex-1 p-2 bg-elevated border-radius-md border-card">
          <div class="font-size-lg font-weight-bold text-teal">Level ${vip.level || 1}</div>
          <div class="font-size-xs text-secondary">VIP Rank</div>
        </div>
      </div>
    </div>
    
    <div class="card mb-3">
      <h3 class="section-title mb-2">Primary Actions</h3>
      <div class="d-flex flex-column gap-2">
        ${!isStarterCompleted ? `
          <button id="btn-verify-now" class="btn btn-primary w-100">
            ⚡ Complete VIP Verification Quest
          </button>
        ` : `
          <button id="btn-claim-bundle" class="btn btn-gold w-100" ${user.credits <= 0 ? 'disabled' : ''}>
            🎁 Redeem ${vip.bundle_size || 5}-Video Bundle (${vip.credit_cost || 1} Credit)
          </button>
        `}
        
        <button id="btn-claim-daily" class="btn btn-secondary w-100">
          🔥 Claim Daily Streak (+1 🪙) • ${streak} Day Streak
        </button>
      </div>
    </div>
    
    <div class="card">
      <h3 class="section-title mb-2">Recent Activity Log</h3>
      ${activity.length === 0 ? '<p class="text-secondary font-size-sm">No recent transactions.</p>' : `
        <div class="activity-list d-flex flex-column gap-2">
          ${activity.map(item => `
            <div class="list-item bg-elevated border-radius-sm p-2 d-flex justify-between align-center border-card">
              <div class="list-item-content">
                <span class="font-size-lg mr-2">${item.icon || '⚡'}</span>
                <div>
                  <div class="font-weight-medium font-size-sm text-primary">${item.title}</div>
                  <div class="font-size-xs text-secondary">${item.time || 'Recent'}</div>
                </div>
              </div>
              <span class="badge ${item.status === 'Verified' || item.status === 'Passed' || item.status === 'Claimed' ? 'badge-success' : 'badge-pending'}">${item.status || 'Active'}</span>
            </div>
          `).join('')}
        </div>
      `}
    </div>
  `;
  
  renderSuccess(_container, html);
  
  // Event handlers
  document.getElementById('btn-verify-now')?.addEventListener('click', () => {
    Router.navigate('verification');
  });

  document.getElementById('btn-claim-bundle')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Redeeming Bundle...';
    
    const res = await ApiClient.redeemBundle();
    if (res.ok) {
      TelegramSDK.haptic('success');
      showToast(res.data.message || 'Reward bundle sent to your Telegram chat!', 'success');
      Cache.evictMutable();
      const dash = await ApiClient.getDashboard();
      if (dash.ok) {
        Cache.setLive('dashboard', dash.data);
        updateAppHeader(dash.data);
        render(dash.data);
      }
    } else {
      TelegramSDK.haptic('error');
      showToast(res.message, 'error');
      btn.disabled = false;
      btn.textContent = `🎁 Redeem ${vip.bundle_size || 5}-Video Bundle (${vip.credit_cost || 1} Credit)`;
    }
  });

  document.getElementById('btn-claim-daily')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Claiming Check-In...';
    
    const res = await ApiClient.claimDaily();
    if (res.ok) {
      TelegramSDK.haptic('success');
      showToast(res.data.message || `+1 Credit Claimed! Streak: ${res.data.streak || streak + 1} Days`, 'success');
      Cache.evictMutable();
      const dash = await ApiClient.getDashboard();
      if (dash.ok) {
        Cache.setLive('dashboard', dash.data);
        updateAppHeader(dash.data);
        render(dash.data);
      }
    } else {
      TelegramSDK.haptic('warning');
      showToast(res.message, 'warning');
      btn.disabled = false;
      btn.textContent = `🔥 Claim Daily Streak (+1 🪙) • ${streak} Day Streak`;
    }
  });
}
