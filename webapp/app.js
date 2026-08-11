/**
 * Telegram Mini App Frontend Application Logic
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
  loadUserProfile();
  loadVerificationStatus();
  loadReferralData();
});

function getInitData() {
  return tg ? tg.initData : "";
}

async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  headers["X-Telegram-Init-Data"] = getInitData();
  
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Network response was not ok" }));
      throw new Error(err.detail || "API Request Failed");
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

async function loadUserProfile() {
  try {
    const data = await apiFetch("/api/me");
    document.getElementById("userName").textContent = data.first_name || "VIP User";
    document.getElementById("vipRank").textContent = `${data.vip_badge} ${data.vip_title}`;
    document.getElementById("userCredits").textContent = data.credits;
    document.getElementById("statStreak").textContent = `${data.checkin_streak} Days 🔥`;
    document.getElementById("statInvites").textContent = `${data.referral_count} 👥`;
    
    document.getElementById("profId").textContent = data.user_id;
    document.getElementById("profRank").textContent = data.vip_title;
    document.getElementById("profCredits").textContent = `${data.credits} 🪙`;
    document.getElementById("profInvites").textContent = `${data.referral_count} 👥`;
  } catch (err) {
    if (tg?.initDataUnsafe?.user) {
      const u = tg.initDataUnsafe.user;
      document.getElementById("userName").textContent = u.first_name;
    }
  }
}

async function loadVerificationStatus() {
  try {
    const data = await apiFetch("/api/verification");
    const container = document.getElementById("channelList");
    if (!container) return;
    
    if (data.is_completed) {
      container.innerHTML = `<div style="color: #10b981; font-weight:700; padding:12px;">✅ All VIP Verification Quests Completed!</div>`;
      return;
    }
    
    let html = "";
    data.required_channels.forEach((ch, idx) => {
      html += `
        <div style="background:rgba(0,0,0,0.2); padding:12px; border-radius:10px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-weight:700; font-size:14px;">${idx+1}. ${ch.title}</div>
            <div style="font-size:11px; color:#94a3b8;">${ch.verification_method === 'join_request' ? 'Request to Join' : 'Direct Join'}</div>
          </div>
          <a href="${ch.invite_link}" target="_blank" style="padding:6px 12px; background:#8b5cf6; border-radius:8px; color:white; text-decoration:none; font-size:12px; font-weight:700;">Join</a>
        </div>
      `;
    });
    container.innerHTML = html;
  } catch (err) {
    console.error("Error loading verification status:", err);
  }
}

async function loadReferralData() {
  try {
    const data = await apiFetch("/api/referrals");
    document.getElementById("refLinkInput").value = data.ref_link;
  } catch (err) {}
}

async function claimDailyReward() {
  try {
    const res = await apiFetch("/api/rewards/claim-daily", { method: "POST" });
    alert(`🎉 Daily VIP Bonus Claimed! +1 Credit added. Daily Streak: ${res.streak} days 🔥`);
    loadUserProfile();
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
