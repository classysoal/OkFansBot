/**
 * OkFans VIP Club Mini App JavaScript Engine
 * Single Aggregated Request (/api/dashboard), Skeleton Loaders, Local Caching, Error Retry States.
 */

const tg = window.Telegram?.WebApp;
const API_BASE = window.location.hostname.includes("vercel.app") 
  ? "https://okfansbot-826r.onrender.com" 
  : window.location.origin;

document.addEventListener("DOMContentLoaded", () => {
  if (tg) {
    tg.expand();
    tg.ready();
  }
  
  // 1. Instantly render cached state if available
  loadCachedState();
  
  // 2. Fetch authoritative live aggregated dashboard
  loadDashboardData();
});

function getInitData() {
  return tg ? tg.initData : "";
}

function loadCachedState() {
  try {
    const cached = localStorage.getItem("okfans_dashboard_cache");
    if (cached) {
      const data = JSON.parse(cached);
      renderDashboard(data, true);
    }
  } catch (e) {}
}

async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  headers["X-Telegram-Init-Data"] = getInitData();
  
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "API Error" }));
      throw new Error(err.detail || "Server request failed");
    }
    return await res.json();
  } catch (err) {
    console.error(`API Fetch Error [${endpoint}]:`, err);
    throw err;
  }
}

async function loadDashboardData(isRetry = false) {
  try {
    const data = await apiFetch("/api/dashboard");
    localStorage.setItem("okfans_dashboard_cache", JSON.stringify(data));
    renderDashboard(data, false);
  } catch (err) {
    console.warn("Failed to fetch live dashboard:", err);
    renderErrorState(err.message || "Unable to connect to server.");
  }
}

function renderDashboard(data, isFromCache = false) {
  const user = data.user || {};
  const vip = data.vip || {};
  const ref = data.referrals || {};
  const verif = data.verification || {};
  const act = data.recent_activity || [];

  // 1. Header Info
  document.getElementById("userName").textContent = user.first_name || "VIP User";
  document.getElementById("vipRank").textContent = `${vip.badge || '🌟'} ${vip.title || 'Novice VIP'}`;
  document.getElementById("userCredits").textContent = user.credits !== undefined ? user.credits : 0;
  
  const avatarInit = (user.first_name || "VIP").substring(0, 3).toUpperCase();
  document.getElementById("userAvatar").textContent = avatarInit;
  document.getElementById("profAvatar").textContent = avatarInit;

  // 2. Home Progress Card
  document.getElementById("homeRankTitle").textContent = `${vip.badge || '🌟'} ${vip.title || 'Novice VIP'}`;
  document.getElementById("homeRankTarget").textContent = `Target: ${vip.next_target || 'Silver VIP'}`;
  document.getElementById("homeProgressBar").style.width = `${vip.progress_pct || 0}%`;
  document.getElementById("homeProgressFooter").innerHTML = `
    <span>${ref.verified_count || 0} verified referrals</span>
    <span>${vip.invites_needed || 0} more needed</span>
  `;

  // 3. Quest / Verification Center
  document.getElementById("questProgressBadge").textContent = `${verif.completed_count || 0} / ${verif.total_required || 0} Completed`;
  renderVerificationList(verif.channels || []);

  // 4. VIP Tiers Progress
  document.getElementById("currentVipTitle").textContent = vip.title || "Novice VIP";
  document.getElementById("vipProgressBar").style.width = `${vip.progress_pct || 0}%`;
  document.getElementById("vipProgressSub").textContent = `Next Target: ${vip.next_target || 'Silver VIP'} (${vip.invites_needed || 0} invite needed)`;

  // 5. Referrals / Invite Center
  document.getElementById("refLinkInput").value = ref.ref_link || "https://t.me/OkFansBot";
  document.getElementById("refStatInvited").textContent = ref.verified_count || 0;
  document.getElementById("refStatQualified").textContent = ref.qualified_count || 0;

  // 6. Profile View
  document.getElementById("profName").textContent = user.first_name || "VIP User";
  document.getElementById("profRankBadge").textContent = `${vip.badge || '🌟'} ${vip.title || 'Novice VIP'}`;
  document.getElementById("profId").textContent = user.user_id || "-";
  document.getElementById("profCredits").textContent = `${user.credits !== undefined ? user.credits : 0} 🪙`;
  document.getElementById("profStreak").textContent = `${user.checkin_streak || 0} Days 🔥`;
  document.getElementById("profInvites").textContent = `${ref.verified_count || 0} 👥`;

  // 7. Activity List
  renderActivityList(act);
}

function renderVerificationList(channels) {
  const container = document.getElementById("channelList");
  if (!container) return;

  if (channels.length === 0) {
    container.innerHTML = `<div style="color:#10b981; font-weight:700; padding:12px;">✅ All VIP Verification Quests Completed!</div>`;
    return;
  }

  let html = "";
  channels.forEach((ch, idx) => {
    let badgeClass = "badge-warning";
    let badgeText = "Action Required";
    if (ch.status === "COMPLETED") {
      badgeClass = "badge-success";
      badgeText = "✓ Completed";
    } else if (ch.status === "PENDING") {
      badgeClass = "badge-info";
      badgeText = "⏳ Pending Request";
    }

    html += `
      <div style="background:rgba(0,0,0,0.2); padding:12px; border-radius:10px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:700; font-size:13px;">${idx+1}. ${ch.title}</div>
          <span class="badge ${badgeClass}" style="margin-top:4px; display:inline-block;">${badgeText}</span>
        </div>
        <a href="${ch.invite_link}" target="_blank" class="btn-secondary" style="text-decoration:none; display:inline-block;">Open</a>
      </div>
    `;
  });
  container.innerHTML = html;
}

function renderActivityList(activities) {
  const container = document.getElementById("homeActivityList");
  if (!container) return;

  if (activities.length === 0) {
    container.innerHTML = `<div style="font-size:12px; color:#94a3b8; padding:8px;">No recent activity logged.</div>`;
    return;
  }

  let html = "";
  activities.forEach(item => {
    html += `
      <div class="activity-item">
        <span class="activity-icon">${item.icon || '⚡'}</span>
        <div class="activity-details">
          <span class="activity-title">${item.title}</span>
          <span class="activity-time">${item.time}</span>
        </div>
        <span class="badge badge-success">${item.status}</span>
      </div>
    `;
  });
  container.innerHTML = html;
}

function renderErrorState(message) {
  const refInput = document.getElementById("refLinkInput");
  if (refInput && refInput.value.includes("Loading")) {
    refInput.value = "https://t.me/OkFansBot";
  }
}

async function claimDailyReward() {
  try {
    const res = await apiFetch("/api/rewards/claim-daily", { method: "POST" });
    alert(`🎉 Daily VIP Bonus Claimed! +1 Credit added. Daily Streak: ${res.streak} days 🔥`);
    loadDashboardData();
  } catch (err) {
    alert(err.message || "Could not claim daily bonus right now.");
  }
}

function copyRefLink() {
  const input = document.getElementById("refLinkInput");
  input.select();
  document.execCommand("copy");
  alert("📋 Referral link copied to clipboard!");
}

function switchTab(viewId, btnEl) {
  document.querySelectorAll(".tab-view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
  
  const target = document.getElementById(viewId);
  if (target) target.classList.add("active");
  if (btnEl) btnEl.classList.add("active");
}
