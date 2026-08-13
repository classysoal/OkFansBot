import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';

let _container = null;
let _page = 1;
let _items = [];
let _hasMore = true;
let _isLoading = false;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  _page = 1;
  _items = [];
  _hasMore = true;
  await fetchPage();
}

async function fetchPage() {
  if (_isLoading) return;
  _isLoading = true;
  
  if (_page === 1) {
    renderLoading(_container, skeletonCard(2).repeat(5));
  } else {
    const btn = document.getElementById('btn-load-more');
    if (btn) btn.textContent = 'Loading...';
  }

  const res = await ApiClient.getVerificationHistory(_page);
  _isLoading = false;
  
  if (!res.ok) {
    if (_page === 1) renderError(_container, res.message, () => load());
    else alert(res.message);
    return;
  }
  
  const newItems = res.data.history || res.data.items || [];
  _items = _items.concat(newItems);
  _hasMore = res.data.has_more || false;
  
  render();
}

function render() {
  if (_items.length === 0) {
    renderEmpty(_container, 'No verification log found.');
    return;
  }
  
  const html = `
    <div class="card">
      <h2 class="section-title mb-3">Verification Log</h2>
      <div class="history-list d-flex flex-column gap-2">
        ${_items.map(item => `
          <div class="list-item bg-elevated border-radius-sm p-3 d-flex justify-between align-center">
            <div>
              <div class="font-weight-medium font-size-sm">${item.channel_name || item.title || 'Channel Verification'}</div>
              <div class="font-size-xs text-secondary">${item.checked_at || item.timestamp ? new Date(item.checked_at || item.timestamp).toLocaleString() : ''}</div>
            </div>
            <span class="badge ${item.result === 'PASS' || item.result === 'COMPLETED' ? 'badge-success' : 'badge-warning'}">
              ${item.result || 'CHECKED'}
            </span>
          </div>
        `).join('')}
      </div>
      ${_hasMore ? `<button id="btn-load-more" class="btn btn-secondary w-100 mt-3">Load More</button>` : ''}
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-load-more')?.addEventListener('click', () => {
    _page++;
    fetchPage();
  });
}
