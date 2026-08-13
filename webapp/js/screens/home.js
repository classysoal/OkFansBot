import ApiClient from '../api.js';
import Cache from '../cache.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonStat, skeletonCard } from '../components/skeleton.js';
import TelegramSDK from '../telegram.js';
import { showToast } from '../components/toast.js';
import Router from '../router.js';

let _container = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  const loadingHtml = `
    <div class="card mb-3">
      ${skeletonCard(3)}
    </div>
    <div class="card mb-3">
      ${skeletonStat()}
    </div>
    <div class="home-activity">
      ${skeletonCard(2)}
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
  const credits = user.credits ?? 0;
  const bundleSize = vip.bundle_size || 5;
  const creditCost = vip.credit_cost || 1;

  const html = `
    <!-- PRIMARY HERO CTA: GET VIDEO / REDEEM REWARD -->
    <div class="card mb-3 p-4" style="background: linear-gradient(135deg, rgba(30, 41, 69, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1.5px solid rgba(255, 215, 0, 0.25); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);">
      <div class="d-flex justify-between align-center mb-3">
        <div>
          <div class="font-size-xs text-gold font-weight-bold text-uppercase" style="letter-spacing: 0.5px;">
            ${!isStarterCompleted ? '⚡ Verification Quest Required' : credits > 0 ? '🎁 Instant VIP Reward Ready' : '🪙 Balance Top-Up Needed'}
          </div>
          <h2 class="font-size-xl font-weight-bold text-primary mt-1 mb-0">
            ${bundleSize} Videos Bundle
          </h2>
        </div>
        <div class="badge badge-warning font-size-xs p-2">
          ${creditCost} Credit ${creditCost === 1 ? '' : 's'}
        </div>
      </div>
      
      <p class="text-secondary font-size-sm mb-4">
        ${!isStarterCompleted 
          ? 'Complete partner channel quests to unlock instant video reward claims.' 
          : credits > 0 
            ? `Redeem <b>${bundleSize} VIP Videos</b> delivered directly to your Telegram chat.` 
            : 'You need at least 1 credit to redeem video rewards. Invite friends or claim daily bonus!'}
      </p>

      <div class="hero-cta-action mb-2">
        ${!isStarterCompleted ? `
          <button id="btn-hero-action" class="btn btn-primary w-100 font-size-md" style="min-height: 52px;">
            ⚡ Complete VIP Verification Quest
          </button>
        ` : credits > 0 ? `
          <button id="btn-hero-action" class="btn btn-gold w-100 font-size-lg" style="min-height: 54px; font-size: 17px;">
            🎬 GET VIDEO (${bundleSize} Videos • ${creditCost} Credit)
          </button>
        ` : `
          <button id="btn-hero-action" class="btn btn-secondary w-100 font-size-md" style="min-height: 52px;">
            👥 Invite Friends to Earn Credits
          </button>
        `}
      </div>

      <div class="d-flex justify-between align-center font-size-xs text-muted mt-2">
        <span>Available Balance: <b class="text-gold">${credits} 🪙</b></span>
        <span>VIP Yield: <b>${bundleSize}x</b></span>
      </div>
    </div>

    <!-- VIP PROGRESSION CARD -->
    <div class="card mb-3">
      <div class="d-flex justify-between align-center mb-2">
        <span class="font-weight-bold font-size-md text-primary">${vip.title || 'Novice VIP'}</span>
        <span class="badge ${isStarterCompleted ? 'badge-success' : 'badge-pending'}">
          ${isStarterCompleted ? '✓ VIP Active' : 'Quest Pending'}
        </span>
      </div>
      
      <div class="progress-container mb-3">
        <div class="progress-track">
          <div class="progress-fill" style="width: ${vip.progress_pct || 0}%;"></div>
        </div>
        <div class="progress-labels mt-1">
          <span class="font-size-xs text-secondary">${vip.progress_pct || 0}% to ${vip.next_target || 'Next VIP Rank'}</span>
        </div>
      </div>
      
      <div class="d-flex gap-2 text-center">
        <div class="flex-1 p-2 bg-elevated border-radius-md border-card">
          <div class="font-size-lg font-weight-bold text-gold">${credits} 🪙</div>
          <div class="font-size-xs text-secondary">Credits</div>
        </div>
        <div class="flex-1 p-2 bg-elevated border-radius-md border-card">
          <div class="font-size-lg font-weight-bold text-primary">${bundleSize} 🎬</div>
          <div class="font-size-xs text-secondary">Per Credit</div>
        </div>
        <div class="flex-1 p-2 bg-elevated border-radius-md border-card">
          <div class="font-size-lg font-weight-bold text-teal">Level ${vip.level || 1}</div>
          <div class="font-size-xs text-secondary">VIP Rank</div>
        </div>
      </div>
    </div>
    
    <!-- SECONDARY ACTIONS CARD -->
    <div class="card mb-3">
      <h3 class="section-title mb-2">Daily Rewards</h3>
      <button id="btn-claim-daily" class="btn btn-secondary w-100">
        🔥 Claim Daily Streak (+1 🪙) • ${streak} Day Streak
      </button>
    </div>
    
    <!-- RECENT ACTIVITY LOG -->
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
  
  // HERO CTA ACTION HANDLER
  document.getElementById('btn-hero-action')?.addEventListener('click', async (e) => {
    if (!isStarterCompleted) {
      Router.navigate('verification');
      return;
    }
    
    if (credits <= 0) {
      Router.navigate('invite');
      return;
    }

    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = '🎬 Getting Reward...';
    
    const res = await ApiClient.redeemBundle();
    if (res.ok) {
      TelegramSDK.haptic('success');
      showToast(res.data.message || '✓ Reward sent! Check your Telegram chat.', 'success');
      btn.textContent = '✓ Reward Sent to Bot!';
      Cache.evictMutable();
      
      const dash = await ApiClient.getDashboard();
      if (dash.ok) {
        Cache.setLive('dashboard', dash.data);
        updateAppHeader(dash.data);
        setTimeout(() => render(dash.data), 1200);
      }
    } else {
      TelegramSDK.haptic('error');
      showToast(res.message, 'error');
      btn.disabled = false;
      btn.textContent = `🎬 GET VIDEO (${bundleSize} Videos • ${creditCost} Credit)`;
    }
  });

  // DAILY STREAK HANDLER
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
