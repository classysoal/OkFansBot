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
  const link = data.ref_link || data.link || 'https://t.me/OkFansBot';
  const count = data.verified_count ?? (data.stats ? data.stats.invited : 0);
  const bonus = data.flash_bonus_credits || 5;
  const standard = data.standard_credits || 3;
  
  const html = `
    <div class="card mb-3 text-center">
      <h2 class="section-title mb-1">Invite Friends</h2>
      <p class="text-secondary font-size-sm mb-3">
        Earn credits for every friend who joins and verifies their account.
      </p>
      
      <div class="d-flex gap-2 justify-center mb-3">
        <div class="flex-1 p-3 bg-elevated border-radius-md">
          <div class="font-size-2xl font-weight-bold">${count}</div>
          <div class="font-size-xs text-secondary">Total Invited</div>
        </div>
        <div class="flex-1 p-3 bg-elevated border-radius-md">
          <div class="font-size-2xl font-weight-bold">${count}</div>
          <div class="font-size-xs text-secondary">Qualified</div>
        </div>
      </div>
      
      <div class="invite-link-section mb-3">
        <label class="font-size-xs text-secondary d-block mb-1 text-left">Your Referral Link</label>
        <input type="text" readonly value="${link}" id="invite-link-input" class="w-100 p-2 bg-input border-card border-radius-md text-primary font-size-sm mb-2" />
        <div class="d-flex gap-2">
          <button id="btn-copy-link" class="btn btn-secondary flex-1">📋 Copy Link</button>
          <button id="btn-share-link" class="btn btn-primary flex-1">✈️ Share Link</button>
        </div>
      </div>
      
      <div class="p-3 bg-elevated border-radius-md text-left">
        <div class="font-weight-semibold font-size-sm mb-1">⚡ Flash Bonus Boost Active!</div>
        <div class="text-secondary font-size-xs">
          Earn <b>${bonus} Credits</b> (boosted from ${standard}) for every verified friend invited!
        </div>
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-copy-link')?.addEventListener('click', () => {
    const input = document.getElementById('invite-link-input');
    input.select();
    navigator.clipboard?.writeText(link) || document.execCommand('copy');
    TelegramSDK.haptic('success');
    showToast('Link copied to clipboard!', 'success');
  });
  
  document.getElementById('btn-share-link')?.addEventListener('click', () => {
    const text = '🎁 Join me on OkFans VIP Club and claim exclusive media rewards!';
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
    TelegramSDK.openLink(shareUrl);
  });
}
