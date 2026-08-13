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
  const vip = data.vip || {};
  const currentLevel = vip.level || data.user?.vip_level || 1;

  const levels = [
    { level: 1, name: 'Novice VIP', rate: '1 Credit = 5 Videos', req: '0 invites needed' },
    { level: 2, name: 'Silver VIP', rate: '1 Credit = 7 Videos', req: '1 invite needed' },
    { level: 3, name: 'Gold VIP', rate: '1 Credit = 10 Videos', req: '4 invites needed' },
    { level: 4, name: 'Diamond VIP', rate: '1 Credit = 15 Videos', req: '7 invites needed' }
  ];

  const html = `
    <div class="card mb-3">
      <h2 class="section-title mb-1">VIP Progression & Level Tiers</h2>
      <p class="text-secondary font-size-sm mb-3">
        Invite friends to upgrade your VIP level and unlock higher reward yields per credit!
      </p>
      
      <div class="d-flex flex-column gap-2">
        ${levels.map(tier => `
          <div class="list-item border-radius-md p-3 ${tier.level === currentLevel ? 'bg-elevated border-card' : 'bg-input'} d-flex justify-between align-center">
            <div>
              <div class="font-weight-semibold font-size-sm mb-1">${tier.name}</div>
              <div class="text-secondary font-size-xs">${tier.rate}</div>
              <div class="text-muted font-size-xs">${tier.req}</div>
            </div>
            ${tier.level === currentLevel ? '<span class="badge badge-success">Current Level</span>' : ''}
          </div>
        `).join('')}
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
}
