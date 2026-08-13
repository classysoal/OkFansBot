import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';
import TelegramSDK from '../telegram.js';
import { showToast } from '../components/toast.js';
import Cache from '../cache.js';

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

function getStatusBadge(status, result) {
  const effective = status || (result === 'PASS' ? 'MEMBER' : 'NOT_JOINED');
  
  switch (effective) {
    case 'MEMBER':
    case 'ADMINISTRATOR':
    case 'OWNER':
    case 'COMPLETED':
      return `<span class="badge badge-success">✓ Verified Member</span>`;
    case 'REQUEST_PENDING':
    case 'PENDING':
      return `<span class="badge badge-pending">⏳ Request Sent (Requirement Met)</span>`;
    case 'NOT_JOINED':
    case 'ACTION_REQUIRED':
      return `<span class="badge badge-warning">○ Action Required</span>`;
    case 'LEFT':
      return `<span class="badge badge-warning">↻ Membership No Longer Active</span>`;
    case 'BANNED':
      return `<span class="badge badge-error">🚫 Account Restricted</span>`;
    case 'CHECK_ERROR':
      return `<span class="badge badge-error">⚠ Unable to Verify</span>`;
    default:
      return `<span class="badge badge-warning">○ Action Required</span>`;
  }
}

function render(data) {
  const channels = data.required_channels || data.requirements || data.channels || [];
  const totalRequired = data.total_required || channels.length;
  const isCompleted = data.is_completed || data.all_passed;
  
  const passedCount = data.passed_count !== undefined 
    ? data.passed_count 
    : channels.filter(c => ['MEMBER', 'ADMINISTRATOR', 'OWNER', 'REQUEST_PENDING', 'COMPLETED'].includes(c.telegram_status || c.status) || c.application_result === 'PASS').length;

  if (channels.length === 0) {
    renderEmpty(_container, 'No verification channels required.');
    return;
  }

  const html = `
    <div class="card mb-3">
      <div class="d-flex justify-between align-center mb-2">
        <h2 class="section-title mb-0">Channel Quests</h2>
        <span class="badge ${isCompleted ? 'badge-success' : 'badge-pending'}">
          ${isCompleted ? 'All Verified' : `${passedCount}/${totalRequired} Completed`}
        </span>
      </div>
      <p class="text-secondary font-size-sm mb-3">
        Join the partner channels below to complete verification and unlock your VIP rewards.
      </p>
      
      <div class="channel-list d-flex flex-column gap-2 mb-3">
        ${channels.map((ch, idx) => {
          const title = ch.title || ch.label || ch.name || `Channel #${idx + 1}`;
          const link = ch.invite_link || ch.url || '#';
          const status = ch.telegram_status || ch.status;
          const result = ch.application_result;
          
          return `
            <div class="list-item bg-elevated border-radius-md p-3 d-flex justify-between align-center">
              <div class="channel-info" style="min-width: 0; flex: 1; padding-right: 8px;">
                <div class="font-weight-semibold font-size-sm mb-1 text-truncate">${title}</div>
                <div class="channel-status">${getStatusBadge(status, result)}</div>
              </div>
              <button class="btn btn-sm btn-secondary" style="width: auto; padding: 6px 14px; min-height: 36px; flex-shrink: 0;" onclick="window.openTelegramChannel('${link}')">
                Join Channel ↗
              </button>
            </div>
          `;
        }).join('')}
      </div>
      
      <div class="verification-action mt-2">
        <button id="btn-check-verification" class="btn btn-primary w-100">
          ⚡ Check Verification
        </button>
        <div id="check-cooldown" class="cooldown-text text-center text-muted font-size-xs mt-2"></div>
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  // Helper for telegram SDK channel open
  window.openTelegramChannel = (url) => {
    if (!url || url === '#') return;
    TelegramSDK.openLink(url);
  };
  
  document.getElementById('btn-check-verification')?.addEventListener('click', async (e) => {
    const btn = e.target;
    btn.disabled = true;
    btn.textContent = 'Checking Membership...';
    
    const res = await ApiClient.checkVerification();
    
    if (res.ok) {
      TelegramSDK.haptic('success');
      showToast(res.data.message || 'Verification complete!', 'success');
      Cache.evictMutable();
      render(res.data);
    } else {
      TelegramSDK.haptic('error');
      showToast(res.message, 'error');
      btn.disabled = false;
      btn.textContent = '⚡ Check Verification';
      
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
