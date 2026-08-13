import ApiClient from '../api.js';
import { renderLoading, renderError, renderEmpty, renderSuccess, skeletonCard } from '../components/skeleton.js';
import { showToast } from '../components/toast.js';

let _container = null;
let _settings = null;

export function init(container) {
  _container = container;
}

export async function load() {
  if (!_container) return;
  
  renderLoading(_container, skeletonCard(2));

  const res = await ApiClient.getSettings();
  if (!res.ok) {
    renderError(_container, res.message, () => load());
    return;
  }
  
  _settings = res.data.settings || res.data;
  render();
}

function render() {
  const settings = _settings || {};
  
  const html = `
    <div class="card mb-3">
      <h2 class="section-title mb-3">Settings</h2>
      
      <div class="d-flex flex-column gap-3">
        <div class="d-flex justify-between align-center p-2 bg-elevated border-radius-md">
          <span class="font-weight-medium font-size-sm">Push Notifications</span>
          <input type="checkbox" id="toggle-notifications" ${settings.notifications_enabled ? 'checked' : ''} style="width: 20px; height: 20px;" />
        </div>
        
        <div class="d-flex justify-between align-center p-2 bg-elevated border-radius-md">
          <span class="font-weight-medium font-size-sm">Language</span>
          <select id="select-language" class="p-1 bg-input border-card border-radius-sm text-primary font-size-sm">
            <option value="en" ${settings.language === 'en' ? 'selected' : ''}>English</option>
          </select>
        </div>
        
        <button id="btn-save-settings" class="btn btn-primary w-100 mt-2">Save Changes</button>
      </div>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-save-settings')?.addEventListener('click', async (e) => {
    const btn = e.target;
    btn.disabled = true;
    btn.textContent = 'Saving...';
    
    const payload = {
      notifications_enabled: document.getElementById('toggle-notifications')?.checked ?? True,
      language: document.getElementById('select-language')?.value || 'en'
    };
    
    const res = await ApiClient.updateSettings(payload);
    
    btn.disabled = false;
    btn.textContent = 'Save Changes';
    
    if (res.ok) {
      showToast('Settings saved successfully', 'success');
      _settings = res.data.settings || payload;
    } else {
      showToast(res.message, 'error');
    }
  });
}
