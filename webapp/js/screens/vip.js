import ApiClient from '../api.js';
import Cache from '../cache.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';

let _container = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  renderLoading(_container, skeletonCard(3).repeat(4));

  // Get current user VIP level from dashboard data
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
  
  render(data.user);
}

function render(user) {
  const levels = [
    { level: 1, name: 'Novice VIP', rate: '1 Credit = 5 Videos', req: '0 invites needed' },
    { level: 2, name: 'Silver VIP', rate: '1 Credit = 7 Videos', req: '1 invite needed' },
    { level: 3, name: 'Gold VIP', rate: '1 Credit = 10 Videos', req: '4 invites needed' },
    { level: 4, name: 'Diamond VIP', rate: '1 Credit = 15 Videos', req: '7 invites needed' }
  ];
  
  const currentLevel = user.vip_level || 1;

  const html = `
    <div class="vip-header">
      <h2>VIP Tiers</h2>
      <p>Invite friends to upgrade your VIP level and get better conversion rates!</p>
    </div>
    
    <div class="vip-list">
      ${levels.map(tier => `
        <div class="vip-card ${tier.level === currentLevel ? 'active' : ''}">
          <div class="vip-info">
            <div class="vip-name">${tier.name}</div>
            <div class="vip-rate">${tier.rate}</div>
            <div class="vip-req">${tier.req}</div>
          </div>
          ${tier.level === currentLevel ? '<div class="vip-current-badge">Current</div>' : ''}
        </div>
      `).join('')}
    </div>
  `;
  
  renderSuccess(_container, html);
}
