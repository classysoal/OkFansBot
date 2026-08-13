/**
 * Toast — Non-blocking notification system.
 */

let _timer = null;

export function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  
  const icons = { success: '✓', error: '⚠', info: 'ℹ', warning: '⚠' };
  const icon = icons[type] || icons.info;
  
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-text">${message}</span>`;
  toast.className = `toast toast-${type} toast-visible`;
  
  if (_timer) clearTimeout(_timer);
  _timer = setTimeout(() => {
    toast.className = 'toast';
  }, 3500);
}
