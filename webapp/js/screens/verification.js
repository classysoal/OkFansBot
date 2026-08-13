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
  
  renderLoading(_container, skeletonCard(3).repeat(4));

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
    case 'COMPLETED': // legacy
      return `<span class="badge badge-success">✓ Completed</span>`;
    case 'REQUEST_PENDING':
    case 'PENDING': // legacy
      return `<span class="badge badge-pending">⏳ Request Pending</span>`;
    case 'NOT_JOINED':
    case 'ACTION_REQUIRED': // legacy
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
  const channels = data.channels || [];
  
  if (channels.length === 0) {
    renderEmpty(_container, 'No verification channels available.');
    return;
  }

  const html = `
    <div class="verification-header">
      <h2>Channel Verification</h2>
      <p>Join the channels below to unlock rewards and features.</p>
    </div>
    
    <div class="channel-list">
      ${channels.map(ch => `
        <div class="channel-card">
          <div class="channel-info">
            <div class="channel-name">${ch.name}</div>
            <div class="channel-status">${getStatusBadge(ch.status)}</div>
          </div>
          <button class="btn btn-sm" onclick="TelegramSDK.openLink('${ch.url}')">Join</button>
        </div>
      `).join('')}
    </div>
    
    <div class="verification-action">
      <button id="btn-check-verification" class="btn btn-primary btn-large">Check Verification</button>
      <div id="check-cooldown" class="cooldown-text"></div>
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
      showToast('Verification complete!', 'success');
      load(); // Reload status
    } else {
      TelegramSDK.haptic('error');
      showToast(res.message, 'error');
      btn.disabled = false;
      btn.textContent = 'Check Verification';
      
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
