// ============================================================
// API Module — 所有后端接口的封装
// 用法: 导入此文件后直接调用 api.xxx()，如 api.getUserProfile()
// 统一自动处理 JWT 鉴权、HTTP 错误和业务错误
// ============================================================

const API_BASE = '/api';

/**
 * 从 localStorage 读取登录 token
 * @returns {string} JWT token，未登录时返回空字符串
 */
function getToken() {
  return localStorage.getItem('token') || '';
}

/**
 * 统一 HTTP 请求封装 — 所有 API 调用都经过此函数
 * 自动携带 Authorization header、解析 JSON 响应、统一错误处理
 * @param {string} method - HTTP 方法 (GET / POST / PUT)
 * @param {string} path   - 接口路径，如 '/auth/login'
 * @param {object} [body] - 请求体（JSON），GET 请求不需要
 * @returns {Promise<any>} 响应中的 data 字段
 * @throws {Error} 网络错误、HTTP 错误或业务错误
 */
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

  // 检查 HTTP 状态码 — 优先读取后端的错误信息
  if (!res.ok) {
    let detail = '请求失败 (HTTP ' + res.status + ')';
    try {
      const errJson = await res.json();
      // FastAPI 默认错误格式: {"detail": "..."} 或 {"detail": [...]}
      if (errJson.message) detail = errJson.message;
      else if (typeof errJson.detail === 'string') detail = errJson.detail;
      else if (Array.isArray(errJson.detail) && errJson.detail.length > 0) {
        detail = errJson.detail.map(e => e.msg).join('; ');
      }
    } catch (_) {}
    throw new Error(detail);
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

/**
 * GET 请求简写
 * @param {string} path - 接口路径
 * @returns {Promise<any>}
 */
function get(path) { return request('GET', path); }
/**
 * POST 请求简写
 * @param {string} path  - 接口路径
 * @param {object} body  - 请求体
 * @returns {Promise<any>}
 */
function post(path, body) { return request('POST', path, body); }
/**
 * PUT 请求简写
 * @param {string} path  - 接口路径
 * @param {object} body  - 请求体
 * @returns {Promise<any>}
 */
function put(path, body) { return request('PUT', path, body); }

const api = {

  // ============================
  // 通用
  // ============================

  /** 获取当前用户信息 → 侧边栏头像、姓名、角色 */
  getUserProfile() { return get('/user/profile'); },
  /** 获取顶部 4 个统计数字（今日评论/新视频/完成率/热门话题） */
  getHeaderStats() { return get('/stats/header'); },
  /** 检查是否有活跃追踪任务 → 控制侧边栏红点 */
  hasActiveTracking() { return get('/tracking/has-active'); },

  // ============================
  // 登录注册
  // ============================

  /**
   * 用户登录
   * @param {string}  username - 用户名
   * @param {string}  password - 密码
   * @param {boolean} remember - 是否记住登录
   * @returns {Promise<{token: string, user: object}>}
   */
  login(username, password, remember) { return post('/auth/login', { username, password, remember }); },
  /**
   * 用户注册
   * @param {string} username         - 用户名（>=3 位）
   * @param {string} email            - 邮箱
   * @param {string} password         - 密码（>=6 位）
   * @param {string} confirmPassword  - 确认密码
   * @returns {Promise<null>}
   */
  register(username, email, password, confirmPassword) { return post('/auth/register', { username, email, password, confirm_password: confirmPassword }); },

  // ============================
  // Dashboard
  // ============================

  /** 获取 Dashboard 4 个统计卡片数据 */
  getDashboardSummary() { return get('/dashboard/summary'); },
  /**
   * 获取评论增长趋势数据
   * @param {number} [days=30] - 查询天数
   * @returns {Promise<{labels: string[], values: number[]}>}
   */
  getDashboardTrend(days) { return get('/dashboard/trend?days=' + (days || 30)); },
  /** 获取情绪占比（正面/负面/中性） */
  getDashboardSentimentRatio() { return get('/dashboard/sentiment-ratio'); },
  /**
   * 获取 TOP N 热门 Topic
   * @param {number} [limit=10] - 返回数量
   * @returns {Promise<Array<{topic_name: string, comment_count: number}>>}
   */
  getDashboardTopTopics(limit) { return get('/dashboard/top-topics?limit=' + (limit || 10)); },
  /** 获取活跃追踪任务摘要列表 */
  getDashboardActiveTracking() { return get('/dashboard/active-tracking'); },

  // ============================
  // 创建分析
  // ============================

  /**
   * 搜索视频
   * @param {string} platform - 平台: 'bilibili' | 'douyin'
   * @param {string} type     - 搜索类型: 'url' | 'bv' | 'av' | 'keyword'
   * @param {string} query    - 搜索内容
   * @returns {Promise<Array<{video_id: string, title: string, cover_url: string, uploader: string, comment_count: number}>>}
   */
  searchVideos(platform, type, query) {
    return get('/videos/search?platform=' + encodeURIComponent(platform) +
      '&type=' + encodeURIComponent(type) + '&query=' + encodeURIComponent(query));
  },
  /**
   * 查询用户积分
   * @param {string} analysisMode - 分析模式: 'tracking' | 'normal'
   * @param {string} commentCount - 评论数量
   * @returns {Promise<{available: number, estimated_cost: number, can_afford: boolean}>}
   */
  getUserCredits(analysisMode, commentCount) {
    return get('/user/credits?analysis_mode=' + encodeURIComponent(analysisMode) +
      '&comment_count=' + encodeURIComponent(commentCount));
  },
  /**
   * 创建分析任务
   * @param {{mode: string, video_title: string, video_url: string, comment_count: number, time_range: string, language: string}} params
   * @returns {Promise<{task_id: string, status: string}>}
   */
  createAnalysis(params) { return post('/analysis/create', params); },

  // ============================
  // Pipeline / 追踪
  // ============================

  /**
   * 创建 SSE 连接 → 实时获取分析进度
   * @param {string} taskId - 分析任务 ID
   * @returns {EventSource}
   */
  createEventSource(taskId) {
    return new EventSource(API_BASE + '/analysis/' + taskId + '/stream?token=' + getToken());
  },
  /**
   * 轮询获取分析进度（SSE 备选方案）
   * @param {string} taskId - 分析任务 ID
   * @returns {Promise<{overall_pct: number, steps: Array, logs: Array}>}
   */
  getAnalysisProgress(taskId) { return get('/analysis/' + taskId + '/progress'); },
  /**
   * 分析完成后启动追踪模式
   * @param {string} taskId - 分析任务 ID
   * @returns {Promise<{tracking_id: number, initial_credits: number, estimated_hours: number}>}
   */
  startTracking(taskId) { return post('/analysis/' + taskId + '/start-tracking'); },
  /**
   * 轮询追踪实时状态（每 3-5 秒调用）
   * @param {number} trackingId - 追踪任务 ID
   * @returns {Promise<{active: boolean, new_comments: number, credits_remaining: number}>}
   */
  getTrackingStatus(trackingId) { return get('/tracking/' + trackingId + '/status'); },
  /**
   * 停止追踪任务
   * @param {number} trackingId - 追踪任务 ID
   * @returns {Promise<{stopped_at: string, total_new_comments: number, credits_consumed: number}>}
   */
  stopTracking(trackingId) { return post('/tracking/' + trackingId + '/stop'); },
  /** 获取所有追踪任务列表 */
  getTrackingTasks() { return get('/tracking/tasks'); },

  // ============================
  // 分析结果
  // ============================

  /**
   * 获取结果页概览数据
   * @param {string} taskId - 分析任务 ID
   * @returns {Promise<{video_title: string, total_comments: number, topic_count: number, positive_pct: number, negative_pct: number}>}
   */
  getResultsOverview(taskId) { return get('/results/' + taskId + '/overview'); },
  /**
   * 获取结果页评论趋势
   * @param {string} taskId - 分析任务 ID
   * @param {string} [granularity='day'] - 粒度: 'day' | 'hour' | 'week'
   * @returns {Promise<{labels: string[], values: number[]}>}
   */
  getResultsTrend(taskId, granularity) { return get('/results/' + taskId + '/trend?granularity=' + (granularity || 'day')); },
  /** 获取结果页情绪占比 */
  getResultsSentimentRatio(taskId) { return get('/results/' + taskId + '/sentiment-ratio'); },
  /** 获取 Topic 列表 */
  getResultsTopics(taskId) { return get('/results/' + taskId + '/topics'); },
  /**
   * 获取单个 Topic 详情
   * @param {string} taskId - 分析任务 ID
   * @param {string} topicName - Topic 名称（中文需前端自行 encodeURIComponent）
   * @returns {Promise<{topic_name: string, sample_comments: string[], keywords: string[], ai_summary: string}>}
   */
  getResultsTopicDetail(taskId, topicName) { return get('/results/' + taskId + '/topic/' + encodeURIComponent(topicName) + '/detail'); },
  /** 获取属性情感数据（旭日图 + 雷达图） */
  getResultsSentimentAttribute(taskId) { return get('/results/' + taskId + '/sentiment-attribute'); },
  /**
   * 获取详细时间趋势（多数据集）
   * @param {string} taskId - 分析任务 ID
   * @param {string} [granularity='day'] - 粒度: 'day' | 'hour' | 'week'
   * @returns {Promise<{labels: string[], datasets: Array<{label: string, values: number[], color: string}>}>}
   */
  getResultsTrendsDetail(taskId, granularity) { return get('/results/' + taskId + '/trends-detail?granularity=' + (granularity || 'day')); },
  /** 获取 AI 总结报告 */
  getResultsAISummary(taskId) { return get('/results/' + taskId + '/ai-summary'); },
  /**
   * 按关键词搜索评论
   * @param {string} taskId - 分析任务 ID
   * @param {string} keyword  - 搜索关键词
   * @param {number} [page=1] - 页码
   * @param {number} [pageSize=20] - 每页数量
   * @returns {Promise<{total: number, items: Array}>}
   */
  searchComments(taskId, keyword, page, pageSize) {
    return get('/results/' + taskId + '/comments/search?keyword=' + encodeURIComponent(keyword) +
      '&page=' + (page || 1) + '&page_size=' + (pageSize || 20));
  },
  /** 获取结果页追踪状态条数据 */
  getResultsTrackingStatus(taskId) { return get('/results/' + taskId + '/tracking-status'); },

  // ============================
  // 视频管理
  // ============================

  /**
   * 获取视频列表
   * @param {number} [page=1]       - 页码
   * @param {number} [pageSize=20]  - 每页数量
   * @returns {Promise<{total: number, items: Array}>}
   */
  getVideos(page, pageSize) { return get('/videos?page=' + (page || 1) + '&page_size=' + (pageSize || 20)); },

  // ============================
  // 历史记录
  // ============================

  /**
   * 获取历史分析记录（支持筛选、排序、分页）
   * @param {{platform?: string, time_range?: string, keyword?: string, page?: number, page_size?: number, sort_by?: string, sort_order?: string}} params
   * @returns {Promise<{total: number, total_pages: number, items: Array}>}
   */
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

  /** 获取用户设置（分析偏好 + 通知偏好 + 账户信息） */
  getSettings() { return get('/settings'); },
  /** 更新分析偏好 */
  updateAnalysisPreferences(prefs) { return put('/settings/analysis-preferences', prefs); },
  /** 更新通知偏好 */
  updateNotificationPreferences(prefs) { return put('/settings/notification-preferences', prefs); },
  /** 修改用户名 */
  updateUsername(username) { return put('/user/username', { username }); },
  /** 修改邮箱 */
  updateEmail(email) { return put('/user/email', { email }); },
  /** 重新生成 API Key */
  regenerateApiKey() { return post('/user/api-key/regenerate'); },
};
