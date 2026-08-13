import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';
import Router from '../router.js';

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
  const html = `
    <div class="profile-header">
      <div class="profile-avatar">${user.first_name.charAt(0).toUpperCase()}</div>
      <div class="profile-name">${user.first_name} ${user.last_name || ''}</div>
      <div class="profile-id">ID: ${user.telegram_id}</div>
    </div>
    
    <div class="profile-menu">
      <div class="menu-item" data-route="history-rewards">
        <span>Reward History</span>
        <span>&rsaquo;</span>
      </div>
      <div class="menu-item" data-route="history-referrals">
        <span>Referral History</span>
        <span>&rsaquo;</span>
      </div>
      <div class="menu-item" data-route="history-verification">
        <span>Verification Log</span>
        <span>&rsaquo;</span>
      </div>
      <div class="menu-item" data-route="notifications">
        <span>Notifications</span>
        <span>&rsaquo;</span>
      </div>
      <div class="menu-item" data-route="settings">
        <span>Settings</span>
        <span>&rsaquo;</span>
      </div>
      <div class="menu-item" id="btn-rules">
        <span>Rules & Terms</span>
        <span>&rsaquo;</span>
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.querySelectorAll('.menu-item[data-route]').forEach(el => {
    el.addEventListener('click', () => {
      Router.navigate(el.dataset.route);
    });
  });
  
  document.getElementById('btn-rules')?.addEventListener('click', () => {
    // Open terms modal or external link
    alert('Rules & Terms content');
  });
}
