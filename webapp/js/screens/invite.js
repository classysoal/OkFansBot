import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';
import TelegramSDK from '../telegram.js';
import { showToast } from '../components/toast.js';

let _container = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  renderLoading(_container, skeletonCard(4));

  const res = await ApiClient.getReferrals();
  if (!res.ok) {
    renderError(_container, res.message, () => load());
    return;
  }
  
  render(res.data);
}

function render(data) {
  const { link, stats, flash_boost } = data;
  
  const html = `
    <div class="invite-header">
      <h2>Invite Friends</h2>
      <p>Invite friends to earn credits and boost your VIP tier.</p>
    </div>
    
    <div class="invite-stats">
      <div class="stat-box">
        <div class="stat-value">${stats.invited}</div>
        <div class="stat-label">Total Invited</div>
      </div>
      <div class="stat-box">
        <div class="stat-value">${stats.qualified}</div>
        <div class="stat-label">Qualified</div>
      </div>
    </div>
    
    <div class="invite-link-section">
      <input type="text" readonly value="${link}" id="invite-link-input" class="invite-input" />
      <div class="invite-actions">
        <button id="btn-copy-link" class="btn btn-secondary">Copy</button>
        <button id="btn-share-link" class="btn btn-primary">Share</button>
      </div>
    </div>
    
    <div class="invite-boost">
      <h3>Flash Boost</h3>
      <p>Current reward: ${flash_boost ? '5 Credits' : '3 Credits'} per qualified invite.</p>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-copy-link')?.addEventListener('click', () => {
    const input = document.getElementById('invite-link-input');
    input.select();
    document.execCommand('copy');
    TelegramSDK.haptic('success');
    showToast('Link copied to clipboard!', 'success');
  });
  
  document.getElementById('btn-share-link')?.addEventListener('click', () => {
    const text = 'Join me on OkFansBot!';
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
    TelegramSDK.openLink(shareUrl);
  });
}
