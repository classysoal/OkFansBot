/**
 * Skeleton — Loading state and component lifecycle management.
 * Every async component must cycle through: IDLE → LOADING → SUCCESS | EMPTY | ERROR → [RETRY]
 * No '-' placeholders. No infinite spinners.
 */

export const ComponentState = {
  IDLE: 'idle',
  LOADING: 'loading',
  SUCCESS: 'success',
  EMPTY: 'empty',
  ERROR: 'error',
  RETRY: 'retry'
};

/**
 * Creates a skeleton card HTML for a standard list item.
 */
export function skeletonCard(lines = 2) {
  const lineHtml = Array(lines).fill(0).map((_, i) =>
    `<div class="skeleton-line" style="width:${i === 0 ? '70%' : '45%'}"></div>`
  ).join('');
  return `<div class="skeleton-card">${lineHtml}</div>`;
}

/**
 * Creates a skeleton stat block (for credits, rank, etc.)
 */
export function skeletonStat() {
  return `<div class="skeleton-card skeleton-stat"><div class="skeleton-line" style="width:40%"></div><div class="skeleton-line" style="width:60%"></div></div>`;
}

/**
 * Renders a loading state into a container element.
 */
export function renderLoading(container, skeletonHtml = skeletonCard(3)) {
  if (!container) return;
  container.innerHTML = `<div class="component-loading">${skeletonHtml.repeat ? skeletonHtml.repeat(3) : skeletonHtml}</div>`;
  container.setAttribute('data-state', ComponentState.LOADING);
}

/**
 * Renders an error state with retry button.
 */
export function renderError(container, message, onRetry) {
  if (!container) return;
  const id = `retry-${Math.random().toString(36).slice(2)}`;
  container.innerHTML = `
    <div class="component-error">
      <div class="error-icon">⚠</div>
      <div class="error-message">${message}</div>
      <button class="btn-retry" id="${id}">Try Again</button>
    </div>
  `;
  container.setAttribute('data-state', ComponentState.ERROR);
  if (onRetry) {
    // We defer the event listener attachment to let the DOM update
    setTimeout(() => {
      document.getElementById(id)?.addEventListener('click', onRetry);
    }, 0);
  }
}

/**
 * Renders an empty state.
 */
export function renderEmpty(container, message) {
  if (!container) return;
  container.innerHTML = `
    <div class="component-empty">
      <div class="empty-icon">📭</div>
      <div class="empty-message">${message}</div>
    </div>
  `;
  container.setAttribute('data-state', ComponentState.EMPTY);
}

/**
 * Renders success content into a container.
 */
export function renderSuccess(container, html) {
  if (!container) return;
  container.innerHTML = html;
  container.setAttribute('data-state', ComponentState.SUCCESS);
}
