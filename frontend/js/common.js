// ============================================================
// SHARED STATE & UTILITIES — 所有页面共用的状态管理和 UI 工具函数
// ============================================================

/** 移动端侧边栏展开/收起切换 */
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('show');
}

/** 关闭移动端侧边栏 */
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('show');
}

/** 退出登录 — 清除 token 和用户缓存，跳转登录页 */
function doLogout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = 'login.html';
}

/**
 * 将秒数格式化为可读时长字符串
 * @param {number} seconds - 秒数
 * @returns {string} 如 "2h 05m" 或 "05:30"
 */
function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return h + 'h ' + m.toString().padStart(2, '0') + 'm';
  return m.toString().padStart(2, '0') + ':' + s.toString().padStart(2, '0');
}

/**
 * 获取当前时间字符串 HH:MM:SS（用于日志显示）
 * @returns {string}
 */
function getTimeStr() {
  return new Date().toTimeString().slice(0, 8);
}

// ============================================================
// UI STATE HELPERS
// ============================================================

/**
 * 显示加载状态 — 替换容器内容为 loading 动画
 * @param {string} containerId - 容器 DOM 元素 ID
 */
function showLoading(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-secondary-dark);"><div style="text-align:center;"><div style="font-size:32px;margin-bottom:12px;">⏳</div><p>加载中...</p></div></div>';
}

/**
 * 显示空状态占位
 * @param {string} containerId - 容器 DOM 元素 ID
 * @param {string} message     - 提示文案
 * @param {string} [icon]      - 图标 emoji，默认 📭
 */
function showEmpty(containerId, message, icon) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-secondary-dark);"><div style="text-align:center;"><div style="font-size:40px;margin-bottom:12px;">' + (icon || '📭') + '</div><p style="font-size:15px;font-weight:500;">' + message + '</p></div></div>';
}

/**
 * 显示错误状态，含重试按钮
 * @param {string} containerId - 容器 DOM 元素 ID
 * @param {string} [message]   - 错误提示，默认"加载失败，请重试"
 */
function showError(containerId, message) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-secondary-dark);"><div style="text-align:center;"><div style="font-size:40px;margin-bottom:12px;">⚠️</div><p style="font-size:15px;font-weight:500;">' + (message || '加载失败，请重试') + '</p><button class="btn-sm" style="margin-top:12px;" onclick="location.reload()">重试</button></div></div>';
}

/**
 * 安全更新 DOM 元素的文本内容（自动忽略不存在的元素）
 * @param {string} id    - DOM 元素 ID
 * @param {string} value - 要显示的文本
 */
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

/**
 * 安全更新 DOM 元素的 HTML 内容
 * @param {string} id   - DOM 元素 ID
 * @param {string} html - 要渲染的 HTML 字符串
 */
function setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

/**
 * 页面初始化：检查登录状态、加载用户信息和顶部统计
 * 所有需要登录的页面在 DOMContentLoaded 时应首先调用此函数
 * @param {{loadUser?: boolean, loadHeaderStats?: boolean}} [options] - 控制加载内容
 *   - loadUser: 是否加载用户信息（默认 true）
 *   - loadHeaderStats: 是否加载顶部统计（默认 true）
 * @returns {Promise<{user?: object, headerStats?: object, hasTracking?: boolean}|null>}
 *   未登录时跳转登录页并返回 null
 */
async function initPage(options) {
  const token = localStorage.getItem('token');
  if (!token && window.location.pathname.indexOf('login.html') === -1) {
    window.location.href = 'login.html';
    return null;
  }

  const result = {};

  try {
    // 加载用户信息 — 侧边栏头像、姓名、角色
    if (options && options.loadUser !== false) {
      result.user = await api.getUserProfile();
      setText('sidebar-display-name', result.user.username);
      setText('sidebar-role', result.user.role);
      setText('sidebar-avatar-text', result.user.avatar_initial || result.user.username.charAt(0));
    }

    // 加载顶部统计数字 — 今日评论/新视频/完成率/热门话题
    if (options && options.loadHeaderStats !== false) {
      result.headerStats = await api.getHeaderStats();
      setText('stat-today-comments', (result.headerStats.today_comments || 0).toLocaleString());
      setText('stat-new-videos', (result.headerStats.new_videos || 0).toString());
      setText('stat-completion', (result.headerStats.analysis_completion_rate || 0) + '%');
      setText('stat-hot-topic', result.headerStats.hot_topic || '—');
    }

    // 检查追踪状态 — 控制侧边栏实时追踪菜单项的红点
    try {
      const trackingStatus = await api.hasActiveTracking();
      const navDot = document.getElementById('sidebar-tracking-dot');
      if (navDot && trackingStatus.has_active) {
        navDot.style.display = '';
      }
      result.hasTracking = trackingStatus.has_active;
    } catch (e) {
      // 追踪检查失败不影响页面正常使用
    }
  } catch (e) {
    console.error('initPage error:', e);
  }

  return result;
}
