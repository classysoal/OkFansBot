import ApiClient from '../api.js';
import Cache from '../cache.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonStat, skeletonCard } from '../components/skeleton.js';
import TelegramSDK from '../telegram.js';
import { showToast } from '../components/toast.js';
import AppState from '../state.js';
import Router from '../router.js';

let _container = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  // Render loading state with skeleton layout
  const loadingHtml = `
    <div class="home-grid">
      ${skeletonStat()}
      ${skeletonStat()}
    </div>
    <div class="home-activity">
      ${skeletonCard(3).repeat(2)}
    </div>
  `;
  renderLoading(_container, loadingHtml);

  // Check cache first
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
  
  render(data);
}

function render(data) {
  const { user, actions, activity } = data;
  
  const html = `
    <div class="home-header">
      <h2>Hello, ${user.first_name}!</h2>
      <div class="home-rank badge">${user.rank}</div>
    </div>
    
    <div class="home-grid">
      <div class="stat-card">
        <div class="stat-label">Credits</div>
        <div class="stat-value">${user.credits}</div>
      </div>
      <div class="stat-card" id="btn-goto-vip">
        <div class="stat-label">VIP Level</div>
        <div class="stat-value">Level ${user.vip_level}</div>
        <div class="stat-sub">View Benefits &rarr;</div>
      </div>
    </div>
    
    <div class="home-actions">
      <h3>Today's Actions</h3>
      <button id="btn-claim-daily" class="btn btn-primary" ${actions.daily_claimed ? 'disabled' : ''}>
        ${actions.daily_claimed ? 'Daily Claimed ✓' : 'Claim Daily Reward'}
      </button>
      <button id="btn-verify-now" class="btn btn-secondary">
        Verify Channels
      </button>
    </div>
    
    <div class="home-activity">
      <h3>Recent Activity</h3>
      ${activity.length === 0 ? '<div class="empty-state">No recent activity</div>' : activity.map(item => `
        <div class="activity-item">
          <div class="activity-title">${item.title}</div>
          <div class="activity-time">${new Date(item.timestamp).toLocaleString()}</div>
        </div>
      `).join('')}
    </div>
  `;
  
  renderSuccess(_container, html);
  
  // Bind events
  document.getElementById('btn-claim-daily')?.addEventListener('click', async (e) => {
    e.target.disabled = true;
    const res = await ApiClient.claimDaily();
    if (res.ok) {
      TelegramSDK.haptic('success');
      showToast('Daily reward claimed!', 'success');
      Cache.evictMutable();
      load(); // Reload dashboard
    } else {
      TelegramSDK.haptic('error');
      showToast(res.message, 'error');
      e.target.disabled = false;
    }
  });

  document.getElementById('btn-verify-now')?.addEventListener('click', () => {
    Router.navigate('verification');
  });
  
  document.getElementById('btn-goto-vip')?.addEventListener('click', () => {
    Router.navigate('vip');
  });
}
