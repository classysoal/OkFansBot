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
  
  renderLoading(_container, skeletonCard(3).repeat(3));

  const res = await ApiClient.getVerification();
  if (!res.ok) {
    renderError(_container, res.message, () => load());
    return;
  }
  
  render(res.data);
}

function getStatusBadge(status) {
  switch (status) {
    case 'MEMBER':
    case 'ADMINISTRATOR':
    case 'OWNER':
    case 'COMPLETED':
      return `<span class="badge badge-success">✓ Completed</span>`;
    case 'REQUEST_PENDING':
    case 'PENDING':
      return `<span class="badge badge-pending">⏳ Request Pending</span>`;
    case 'NOT_JOINED':
    case 'ACTION_REQUIRED':
      return `<span class="badge badge-warning">○ Action Required</span>`;
    case 'LEFT':
      return `<span class="badge badge-warning">↻ Membership No Longer Active</span>`;
    case 'BANNED':
      return `<span class="badge badge-error">🚫 Account Restricted</span>`;
    case 'CHECK_ERROR':
      return `<span class="badge badge-error">⚠ Unable to Verify Right Now</span>`;
    default:
      return `<span class="badge badge-warning">○ Action Required</span>`;
  }
}

function render(data) {
  const channels = data.required_channels || data.channels || [];
  const totalRequired = data.total_required || channels.length;
  const isCompleted = data.is_completed;
  
  if (channels.length === 0) {
    renderEmpty(_container, 'No verification channels required.');
    return;
  }

  const html = `
    <div class="card mb-3">
      <div class="d-flex justify-between align-center mb-2">
        <h2 class="section-title mb-0">Quests</h2>
        <span class="badge ${isCompleted ? 'badge-success' : 'badge-pending'}">
          ${isCompleted ? 'All Verified' : `0/${totalRequired} Done`}
        </span>
      </div>
      <p class="text-secondary font-size-sm mb-3">
        Join the channels below to verify your account and unlock VIP features.
      </p>
      
      <div class="channel-list d-flex flex-column gap-2 mb-3">
        ${channels.map(ch => `
          <div class="list-item bg-elevated border-radius-md p-3 d-flex justify-between align-center">
            <div class="channel-info">
              <div class="font-weight-semibold font-size-sm mb-1">${ch.title || ch.label || ch.name || 'Channel'}</div>
              <div class="channel-status">${getStatusBadge(ch.status)}</div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="TelegramSDK.openLink('${ch.invite_link || ch.url}')">
              Join
            </button>
          </div>
        `).join('')}
      </div>
      
      <div class="verification-action mt-2">
        <button id="btn-check-verification" class="btn btn-primary w-100">
          ✅ Check Verification
        </button>
        <div id="check-cooldown" class="cooldown-text text-center text-muted font-size-xs mt-2"></div>
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-check-verification')?.addEventListener('click', async (e) => {
    const btn = e.target;
    btn.disabled = true;
    btn.textContent = 'Checking...';
    
    const res = await ApiClient.checkVerification();
    
    if (res.ok) {
      TelegramSDK.haptic('success');
      showToast(res.data.message || 'Verification complete!', 'success');
      load();
    } else {
      TelegramSDK.haptic('error');
      showToast(res.message, 'error');
      btn.disabled = false;
      btn.textContent = '✅ Check Verification';
      
      if (res.error === 'RATE_LIMITED') {
        let seconds = 30;
        const cd = document.getElementById('check-cooldown');
        const iv = setInterval(() => {
          if (seconds <= 0) {
            clearInterval(iv);
            btn.disabled = false;
            if (cd) cd.textContent = '';
          } else {
            if (cd) cd.textContent = `Please wait ${seconds}s`;
            seconds--;
          }
        }, 1000);
      }
    }
  });
}
