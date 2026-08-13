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

  const res = await ApiClient.getNotifications(_page);
  _isLoading = false;
  
  if (!res.ok) {
    if (_page === 1) renderError(_container, res.message, () => load());
    else alert(res.message);
    return;
  }
  
  const newItems = res.data.items || [];
  _items = _items.concat(newItems);
  _hasMore = res.data.has_more;
  
  render();
}

function render() {
  if (_items.length === 0) {
    renderEmpty(_container, 'No notifications.');
    return;
  }
  
  const html = `
    <div class="notifications-header">
      <button id="btn-mark-read" class="btn btn-sm btn-secondary">Mark All Read</button>
    </div>
    <div class="notification-list">
      ${_items.map(item => `
        <div class="notification-item ${item.read ? 'read' : 'unread'}">
          <div class="notification-title">${item.title}</div>
          <div class="notification-body">${item.body}</div>
          <div class="notification-time">${new Date(item.timestamp).toLocaleString()}</div>
        </div>
      `).join('')}
    </div>
    ${_hasMore ? `<button id="btn-load-more" class="btn btn-secondary w-full mt-4">Load More</button>` : ''}
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-load-more')?.addEventListener('click', () => {
    _page++;
    fetchPage();
  });

  document.getElementById('btn-mark-read')?.addEventListener('click', async () => {
    const unreadIds = _items.filter(i => !i.read).map(i => i.id);
    if (unreadIds.length === 0) return;
    
    document.getElementById('btn-mark-read').disabled = true;
    const res = await ApiClient.markNotificationsRead(unreadIds);
    if (res.ok) {
      _items.forEach(i => i.read = true);
      render();
    } else {
      document.getElementById('btn-mark-read').disabled = false;
      alert(res.message);
    }
  });
}
