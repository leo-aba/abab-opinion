// ============================================================
// SHARED STATE & UTILITIES
// ============================================================

// Mobile sidebar toggle
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('show');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('show');
}

// Logout — clear token and redirect
function doLogout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = 'login.html';
}

// Format duration helper
function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return h + 'h ' + m.toString().padStart(2, '0') + 'm';
  return m.toString().padStart(2, '0') + ':' + s.toString().padStart(2, '0');
}

// Get time string helper
function getTimeStr() {
  return new Date().toTimeString().slice(0, 8);
}

// ============================================================
// UI STATE HELPERS
// ============================================================

// 显示加载状态 — 替换容器内容
function showLoading(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-secondary-dark);"><div style="text-align:center;"><div style="font-size:32px;margin-bottom:12px;">⏳</div><p>加载中...</p></div></div>';
}

// 显示空状态
function showEmpty(containerId, message, icon) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-secondary-dark);"><div style="text-align:center;"><div style="font-size:40px;margin-bottom:12px;">' + (icon || '📭') + '</div><p style="font-size:15px;font-weight:500;">' + message + '</p></div></div>';
}

// 显示错误状态
function showError(containerId, message) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-secondary-dark);"><div style="text-align:center;"><div style="font-size:40px;margin-bottom:12px;">⚠️</div><p style="font-size:15px;font-weight:500;">' + (message || '加载失败，请重试') + '</p><button class="btn-sm" style="margin-top:12px;" onclick="location.reload()">重试</button></div></div>';
}

// 更新单个文本元素（忽略 null）
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

// 更新单个 HTML 元素（忽略 null）
function setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

// 页面初始化：检查登录 + 加载用户/统计信息
async function initPage(options) {
  const token = localStorage.getItem('token');
  if (!token && window.location.pathname.indexOf('login.html') === -1) {
    window.location.href = 'login.html';
    return null;
  }

  const result = {};

  try {
    // 加载用户信息
    if (options && options.loadUser !== false) {
      result.user = await api.getUserProfile();
      setText('sidebar-display-name', result.user.display_name);
      setText('sidebar-role', result.user.role);
      // 更新头像首字母
      setText('sidebar-avatar-text', result.user.avatar_initial || result.user.display_name.charAt(0));
    }

    // 加载顶部统计
    if (options && options.loadHeaderStats !== false) {
      result.headerStats = await api.getHeaderStats();
      setText('stat-today-comments', (result.headerStats.today_comments || 0).toLocaleString());
      setText('stat-new-videos', (result.headerStats.new_videos || 0).toString());
      setText('stat-completion', (result.headerStats.analysis_completion_rate || 0) + '%');
      setText('stat-hot-topic', result.headerStats.hot_topic || '—');
    }

    // 检查追踪状态（仅控制实时指示点）
    try {
      const trackingStatus = await api.hasActiveTracking();
      const navDot = document.getElementById('sidebar-tracking-dot');
      if (navDot && trackingStatus.has_active) {
        navDot.style.display = '';
      }
      result.hasTracking = trackingStatus.has_active;
    } catch (e) {
      // 静默失败
    }
  } catch (e) {
    console.error('initPage error:', e);
  }

  return result;
}
