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

// ============================================================
// SIDEBAR COMPONENT — 所有页面的共用侧边栏（单一定义，改一处全生效）
// ============================================================

/** 导航菜单数据结构 */
var SIDEBAR_NAV = [
  { section: '主菜单' },
  { page: 'dashboard',       href: 'dashboard.html',       label: 'Dashboard',  svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
  { page: 'create-analysis', href: 'create-analysis.html', label: '创建分析',   svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>' },
  { page: 'pipeline',        href: 'pipeline.html',        label: '实时分析',   svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>' },
  { page: 'tracking',        href: 'tracking.html',        label: '实时追踪',   svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4" fill="currentColor"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></svg>', tracking: true },
  { section: '管理' },
  { page: 'videos',          href: 'videos.html',          label: '视频管理',   svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>' },
  { page: 'history',         href: 'history.html',         label: '历史记录',   svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' },
  { page: 'settings',        href: 'settings.html',        label: '系统设置',   svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>' }
];

/**
 * 动态注入侧边栏到 #sidebar-container
 * 必须在 initPage() 之前调用，因为 initPage() 会往侧边栏 DOM 元素写入用户信息
 *
 * @param {string} activePage - 当前页面标识符，如 'dashboard'、'pipeline' 等
 */
function loadSidebar(activePage) {
  var container = document.getElementById('sidebar-container');
  if (!container) return;

  // 构建导航项 HTML
  var navItemsHtml = '';
  for (var i = 0; i < SIDEBAR_NAV.length; i++) {
    var item = SIDEBAR_NAV[i];
    if (item.section) {
      navItemsHtml += '<div class="nav-section">' + item.section + '</div>';
      continue;
    }
    var isActive = item.page === activePage ? ' active' : '';
    var trackingId = item.tracking ? ' id="nav-tracking"' : '';
    var trackingDot = item.tracking ? '<span class="tracking-live-dot" id="sidebar-tracking-dot" style="display:none;"></span>' : '';
    navItemsHtml += '<a href="' + item.href + '" class="nav-item' + isActive + '"' + trackingId + '>' +
      item.svg +
      '<span>' + item.label + '</span>' +
      trackingDot +
      '</a>';
  }

  // 注入侧边栏 HTML
  container.innerHTML =
    '<!-- Sidebar overlay (mobile) -->' +
    '<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>' +
    '<!-- Sidebar -->' +
    '<aside class="sidebar" id="sidebar">' +
    '  <div class="sidebar-logo">' +
    '    <img src="logo.png" alt="Opinion AI" style="width:32px;height:32px;">' +
    '    Opinion AI' +
    '  </div>' +
    '  <nav class="sidebar-nav">' +
    navItemsHtml +
    '  </nav>' +
    '  <div class="sidebar-footer">' +
    '    <div class="sidebar-user">' +
    '      <div class="sidebar-avatar" id="sidebar-avatar-text">L</div>' +
    '      <div class="sidebar-user-info">' +
    '        <div class="sidebar-user-name" id="sidebar-display-name">加载中...</div>' +
    '        <div class="sidebar-user-role" id="sidebar-role">—</div>' +
    '      </div>' +
    '    </div>' +
    '    <button class="logout-btn" onclick="doLogout()">' +
    '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>' +
    '      退出登录' +
    '    </button>' +
    '  </div>' +
    '</aside>';
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
 * 安全设置 DOM 元素属性（自动忽略不存在的元素）
 * @param {string} id    - DOM 元素 ID
 * @param {string} attr  - 属性名
 * @param {string} value - 属性值
 */
function setAttr(id, attr, value) {
  const el = document.getElementById(id);
  if (el) el.setAttribute(attr, value);
}

/**
 * 格式化数字（万、亿），视频信息卡片用
 * @param {number|string} n - 数字
 * @returns {string} 格式化后的字符串
 */
function formatCount(n) {
  if (!n && n !== 0) return '—';
  n = parseInt(n, 10);
  if (isNaN(n)) return '—';
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
  if (n >= 10000) return (n / 10000).toFixed(1) + '万';
  return n.toLocaleString();
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
    if (!options || options.loadUser !== false) {
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
