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
  
  _settings = res.data;
  render();
}

function render() {
  const html = `
    <div class="settings-header">
      <h2>Settings</h2>
    </div>
    
    <div class="settings-form">
      <div class="form-group">
        <label class="form-label">
          <span>Enable Notifications</span>
          <input type="checkbox" id="toggle-notifications" ${_settings.notifications_enabled ? 'checked' : ''} />
        </label>
      </div>
      
      <div class="form-group">
        <label class="form-label">
          <span>Language</span>
        </label>
        <select id="select-language" class="form-control">
          <option value="en" ${_settings.language === 'en' ? 'selected' : ''}>English</option>
        </select>
      </div>
      
      <button id="btn-save-settings" class="btn btn-primary w-full mt-4">Save Changes</button>
    </div>
  `;
  
  renderSuccess(_container, html);
  
  document.getElementById('btn-save-settings')?.addEventListener('click', async (e) => {
    const btn = e.target;
    btn.disabled = true;
    btn.textContent = 'Saving...';
    
    const data = {
      notifications_enabled: document.getElementById('toggle-notifications').checked,
      language: document.getElementById('select-language').value
    };
    
    const res = await ApiClient.updateSettings(data);
    
    btn.disabled = false;
    btn.textContent = 'Save Changes';
    
    if (res.ok) {
      showToast('Settings saved successfully', 'success');
      _settings = res.data;
    } else {
      showToast(res.message, 'error');
    }
  });
}
