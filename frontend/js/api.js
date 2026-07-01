// ============================================================
// API Module — 所有后端接口的封装
// 用法: import 此文件后直接调用函数，如 api.getUserProfile()
// ============================================================

const API_BASE = '/api';

// 从 localStorage 获取 token
function getToken() {
  return localStorage.getItem('token') || '';
}

// 统一请求封装
async function request(method, path, body) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + getToken()
    }
  };
  if (body) opts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(API_BASE + path, opts);
  } catch (e) {
    throw new Error('网络错误，无法连接服务器');
  }

  // 检查 HTTP 状态码
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('接口不存在 (404)');
    }
    if (res.status === 500) {
      throw new Error('服务器内部错误 (500)');
    }
    throw new Error('请求失败 (HTTP ' + res.status + ')');
  }

  // 检查响应是否是 JSON
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    const text = await res.text();
    throw new Error('后端返回了非 JSON 响应。请确认后端服务已启动，接口路径: ' + path);
  }

  let json;
  try {
    json = await res.json();
  } catch (e) {
    throw new Error('响应不是有效的 JSON 格式');
  }

  if (json.code !== 0) {
    throw new Error(json.message || '请求失败');
  }
  return json.data;
}

// GET 简写
function get(path) { return request('GET', path); }
// POST 简写
function post(path, body) { return request('POST', path, body); }
// PUT 简写
function put(path, body) { return request('PUT', path, body); }

const api = {

  // ============================
  // 通用
  // ============================
  getUserProfile() { return get('/user/profile'); },
  getHeaderStats() { return get('/stats/header'); },
  hasActiveTracking() { return get('/tracking/has-active'); },

  // ============================
  // 登录注册
  // ============================
  login(username, password, remember) { return post('/auth/login', { username, password, remember }); },
  register(username, email, password) { return post('/auth/register', { username, email, password }); },

  // ============================
  // Dashboard
  // ============================
  getDashboardSummary() { return get('/dashboard/summary'); },
  getDashboardTrend(days) { return get('/dashboard/trend?days=' + (days || 30)); },
  getDashboardSentimentRatio() { return get('/dashboard/sentiment-ratio'); },
  getDashboardTopTopics(limit) { return get('/dashboard/top-topics?limit=' + (limit || 10)); },
  getDashboardActiveTracking() { return get('/dashboard/active-tracking'); },

  // ============================
  // 创建分析
  // ============================
  searchVideos(platform, type, query) {
    return get('/videos/search?platform=' + encodeURIComponent(platform) +
      '&type=' + encodeURIComponent(type) + '&query=' + encodeURIComponent(query));
  },
  getUserCredits(analysisMode, commentCount) {
    return get('/user/credits?analysis_mode=' + encodeURIComponent(analysisMode) +
      '&comment_count=' + encodeURIComponent(commentCount));
  },
  createAnalysis(params) { return post('/analysis/create', params); },

  // ============================
  // Pipeline / 追踪
  // ============================
  createEventSource(taskId) {
    return new EventSource(API_BASE + '/analysis/' + taskId + '/stream?token=' + getToken());
  },
  getAnalysisProgress(taskId) { return get('/analysis/' + taskId + '/progress'); },
  startTracking(taskId) { return post('/analysis/' + taskId + '/start-tracking'); },
  getTrackingStatus(trackingId) { return get('/tracking/' + trackingId + '/status'); },
  stopTracking(trackingId) { return post('/tracking/' + trackingId + '/stop'); },
  getTrackingTasks() { return get('/tracking/tasks'); },

  // ============================
  // 分析结果
  // ============================
  getResultsOverview(taskId) { return get('/results/' + taskId + '/overview'); },
  getResultsTrend(taskId, granularity) { return get('/results/' + taskId + '/trend?granularity=' + (granularity || 'day')); },
  getResultsSentimentRatio(taskId) { return get('/results/' + taskId + '/sentiment-ratio'); },
  getResultsTopics(taskId) { return get('/results/' + taskId + '/topics'); },
  getResultsTopicDetail(taskId, topicName) { return get('/results/' + taskId + '/topic/' + encodeURIComponent(topicName) + '/detail'); },
  getResultsSentimentAttribute(taskId) { return get('/results/' + taskId + '/sentiment-attribute'); },
  getResultsTrendsDetail(taskId, granularity) { return get('/results/' + taskId + '/trends-detail?granularity=' + (granularity || 'day')); },
  getResultsAISummary(taskId) { return get('/results/' + taskId + '/ai-summary'); },
  searchComments(taskId, keyword, page, pageSize) {
    return get('/results/' + taskId + '/comments/search?keyword=' + encodeURIComponent(keyword) +
      '&page=' + (page || 1) + '&page_size=' + (pageSize || 20));
  },
  getResultsTrackingStatus(taskId) { return get('/results/' + taskId + '/tracking-status'); },

  // ============================
  // 视频管理
  // ============================
  getVideos(page, pageSize) { return get('/videos?page=' + (page || 1) + '&page_size=' + (pageSize || 20)); },

  // ============================
  // 历史记录
  // ============================
  getHistory(params) {
    const qs = new URLSearchParams();
    if (params.platform) qs.set('platform', params.platform);
    if (params.time_range) qs.set('time_range', params.time_range);
    if (params.keyword) qs.set('keyword', params.keyword);
    if (params.page) qs.set('page', params.page);
    if (params.page_size) qs.set('page_size', params.page_size);
    if (params.sort_by) qs.set('sort_by', params.sort_by);
    if (params.sort_order) qs.set('sort_order', params.sort_order);
    const q = qs.toString();
    return get('/history' + (q ? '?' + q : ''));
  },

  // ============================
  // 系统设置
  // ============================
  getSettings() { return get('/settings'); },
  updateAnalysisPreferences(prefs) { return put('/settings/analysis-preferences', prefs); },
  updateNotificationPreferences(prefs) { return put('/settings/notification-preferences', prefs); },
  updateUsername(username) { return put('/user/username', { username }); },
  updateEmail(email) { return put('/user/email', { email }); },
  regenerateApiKey() { return post('/user/api-key/regenerate'); },
};
