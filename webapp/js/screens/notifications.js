import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';

let _container = null;
let _page = 1;
let _items = [];
let _hasMore = false;
let _isLoading = false;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  _page = 1;
  _items = [];
  _hasMore = false;
  await fetchPage();
}

async function fetchPage() {
  if (_isLoading) return;
  _isLoading = true;
  
  if (_page === 1) {
    renderLoading(_container, skeletonCard(2).repeat(4));
  } else {
    const btn = document.getElementById('btn-load-more');
    if (btn) btn.textContent = 'Loading...';
  }

  const res = await ApiClient.getNotifications(_page);
  _isLoading = false;
  
  if (!res.ok) {
    if (_page === 1) renderError(_container, res.message, () => load());
    else alert(res.message);
    return;
  }
  
  const newItems = res.data.notifications || res.data.items || [];
  _items = _items.concat(newItems);
  _hasMore = res.data.has_more || false;
  
  render();
}

function render() {
  if (_items.length === 0) {
    renderEmpty(_container, 'No notifications found.');
    return;
  }
  
  const html = `
    <div class="card mb-3">
      <div class="d-flex justify-between align-center mb-3">
        <h2 class="section-title mb-0">Notifications</h2>
        <button id="btn-mark-read" class="btn btn-sm btn-secondary">Mark All Read</button>
      </div>
      <div class="notification-list d-flex flex-column gap-2">
        ${_items.map(item => `
          <div class="list-item bg-elevated border-radius-sm p-3 ${item.read ? 'opacity-70' : 'border-card'}">
            <div class="font-weight-medium font-size-sm mb-1">${item.title}</div>
            <div class="font-size-xs text-secondary mb-1">${item.body}</div>
            <div class="font-size-xs text-muted">${item.created_at ? new Date(item.created_at).toLocaleString() : ''}</div>
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

  document.getElementById('btn-mark-read')?.addEventListener('click', async () => {
    const unreadIds = _items.filter(i => !i.read).map(i => i.id);
    const btn = document.getElementById('btn-mark-read');
    if (btn) btn.disabled = true;
    
    const res = await ApiClient.markNotificationsRead(unreadIds);
    if (res.ok) {
      _items.forEach(i => i.read = true);
      render();
    } else if (btn) {
      btn.disabled = false;
    }
  });
}
