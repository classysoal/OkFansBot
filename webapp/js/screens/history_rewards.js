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

  const res = await ApiClient.getRewardHistory(_page);
  _isLoading = false;
  
  if (!res.ok) {
    if (_page === 1) renderError(_container, res.message, () => load());
    else alert(res.message); // simple fallback for pagination error
    return;
  }
  
  const newItems = res.data.items || [];
  _items = _items.concat(newItems);
  _hasMore = res.data.has_more;
  
  render();
}

function render() {
  if (_items.length === 0) {
    renderEmpty(_container, 'No reward history found.');
    return;
  }
  
  const html = `
    <div class="history-list">
      ${_items.map(item => `
        <div class="history-item">
          <div class="history-info">
            <div class="history-reason">${item.reason}</div>
            <div class="history-time">${new Date(item.timestamp).toLocaleString()}</div>
          </div>
          <div class="history-amount ${item.amount > 0 ? 'positive' : 'negative'}">
            ${item.amount > 0 ? '+' : ''}${item.amount}
          </div>
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
}
