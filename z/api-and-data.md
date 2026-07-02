# 前端接口与数据需求文档

> 基于 `frontend/` 下所有页面分析提取，涵盖 9 个页面的完整接口需求。

---

## 目录

- [1. 通用数据](#1-通用数据所有页面)
- [2. 登录注册](#2-登录注册-loginhtml)
- [3. Dashboard](#3-dashboard-dashboardhtml)
- [4. 创建分析](#4-创建分析-create-analysishtml)
- [5. 实时分析管道](#5-实时分析管道-pipelinehtml)
- [6. 实时追踪](#6-实时追踪-trackinghtml)
- [7. 分析结果](#7-分析结果-resultshtml)
- [8. 视频管理](#8-视频管理-videoshtml)
- [9. 历史记录](#9-历史记录-historyhtml)
- [10. 系统设置](#10-系统设置-settingshtml)
- [附录：通用数据结构](#附录通用数据结构)

---

## 1. 通用数据（所有页面）

### 1.1 当前用户信息

侧边栏底部显示用户头像、姓名、角色。

**请求：**
```
GET /api/user/profile
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "user_id": 1,
    "username": "admin",
    "role": "管理员",
    "avatar_initial": "L",
    "email": "admin@opinion.ai"
  }
}
```

### 1.2 顶部统计（Header Stats）

所有 app 页面顶部显示的 4 个统计数字。

**请求：**
```
GET /api/stats/header
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "today_comments": 2567,
    "new_videos": 18,
    "analysis_completion_rate": 96,
    "hot_topic": "AI手机"
  }
}
```

### 1.3 侧边栏追踪状态

控制"实时追踪"菜单项显隐和红点。

**请求：**
```
GET /api/tracking/has-active
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "has_active": true
  }
}
```

---

## 2. 登录注册 (`login.html`)

### 2.1 登录

**请求：**
```
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password",
  "remember": false
}
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "user_id": 1,
      "username": "admin",
      "role": "管理员",
      "avatar_initial": "L"
    }
  }
}
```

### 2.2 注册

**请求：**
```
POST /api/auth/register
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "123456"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "注册成功"
}
```

---

## 3. Dashboard (`dashboard.html`)

### 3.1 仪表盘统计卡片

4 个 stat-card：评论总数、视频数量、热门Topic、平均情绪。

**请求：**
```
GET /api/dashboard/summary
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "total_comments": 123221,
    "total_comments_change": 12,
    "total_comments_change_direction": "up",
    "total_videos": 421,
    "total_videos_change": 8,
    "total_videos_change_direction": "up",
    "hot_topic_name": "AI",
    "hot_topic_comment_count": 2341,
    "avg_sentiment": "Positive",
    "avg_sentiment_change": 5,
    "avg_sentiment_change_direction": "up"
  }
}
```

### 3.2 评论增长趋势图

近 30 天的评论增长曲线。

**请求：**
```
GET /api/dashboard/trend?days=30
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "labels": ["6/1", "6/2", "6/3", "..."],
    "values": [120, 145, 168, 189, 210, 245, 278, 310, 345, 380, 420, 468, 512, 556, 601, 645, 689, 734, 780, 823, 867, 910, 954, 998, 1043, 1087, 1132, 1176, 1200, 1232]
  }
}
```

前端使用：
- labels → Chart.js x 轴
- values → 数据集，颜色 `#FF7A22`，填充面积

### 3.3 情绪占比图

**请求：**
```
GET /api/dashboard/sentiment-ratio
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "positive": 72,
    "negative": 18,
    "neutral": 10
  }
}
```

前端使用：正面 `#00B4CC`、负面 `#FF7A22`、中性 `#F8F2E4`

### 3.4 TOP10 热门 Topic 柱状图

**请求：**
```
GET /api/dashboard/top-topics?limit=10
```

**响应：**
```json
{
  "code": 0,
  "data": [
    { "topic_name": "价格", "comment_count": 2334 },
    { "topic_name": "AI功能", "comment_count": 1892 },
    { "topic_name": "性能", "comment_count": 1567 },
    { "topic_name": "续航", "comment_count": 1234 },
    { "topic_name": "屏幕", "comment_count": 1098 },
    { "topic_name": "拍照", "comment_count": 987 },
    { "topic_name": "系统体验", "comment_count": 876 },
    { "topic_name": "外观设计", "comment_count": 765 },
    { "topic_name": "发热", "comment_count": 654 },
    { "topic_name": "信号", "comment_count": 543 }
  ]
}
```

前端使用：
- `comment_count > 1500` → 橙色 `#FF7A22`
- `comment_count > 1000` → 青色 `#00B4CC`
- 其他 → 米白 `#F8F2E4`

### 3.5 活跃追踪任务卡片

Dashboard 上显示当前运行的追踪任务摘要。

**请求：**
```
GET /api/dashboard/active-tracking
```

**响应：**
```json
{
  "code": 0,
  "data": [
    {
      "task_id": 1,
      "video_title": "iPhone 16 Pro 深度评测：AI功能全面体验",
      "platform": "bilibili",
      "author": "科技美学",
      "new_comments": 326,
      "credits_remaining": 5000,
      "duration_seconds": 3720
    }
  ]
}
```

---

## 4. 创建分析 (`create-analysis.html`)

### 4.1 搜索视频

按 URL / BV号 / AV号 / 关键词搜索视频。

**请求：**
```
GET /api/videos/search
  ?platform=bilibili          // "bilibili" | "douyin"
  &type=url                   // "url" | "bv" | "av" | "keyword"
  &query=BV1xx411c7mD
```

**响应：**
```json
{
  "code": 0,
  "data": [
    {
      "video_id": "BV1xx411c7mD",
      "cover_url": "https://...",
      "title": "iPhone 16 Pro 深度评测：AI功能全面体验",
      "author": "科技美学",
      "publish_date": "2026-06-15",
      "comment_count": 12845
    },
    {
      "video_id": "BV2yy422d8nE",
      "cover_url": "https://...",
      "title": "华为Mate 70 全面评测：鸿蒙生态新体验",
      "author": "钟文泽",
      "publish_date": "2026-06-10",
      "comment_count": 23102
    }
  ]
}
```

### 4.2 查询积分

确认页显示当前可用积分和预估消耗。

**请求：**
```
GET /api/user/credits?analysis_mode=tracking&comment_count=500
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "available": 1280,
    "estimated_cost": 320,
    "cost_unit": "积分/小时",
    "can_afford": true
  }
}
```

### 4.3 创建分析任务

**请求：**
```
POST /api/analysis/create
Content-Type: application/json

{
  "platform": "bilibili",
  "video_id": "BV1xx411c7mD",
  "comment_count": 500,
  "time_range": "recent_7_days",
  "language": "zh",
  "analysis_mode": "tracking"
}
```

| 字段 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| platform | string | 平台 | `bilibili` / `douyin` |
| video_id | string | 视频ID | BV号或抖音视频ID |
| comment_count | number/string | 评论数量 | `100` / `500` / `1000` / `5000` / `all` |
| time_range | string | 时间范围 | `recent_7_days` / `recent_30_days` / `all` |
| language | string | 语言 | `zh` / `en` / `all` |
| analysis_mode | string | 分析模式 | `tracking` / `normal` |

**响应：**
```json
{
  "code": 0,
  "data": {
    "task_id": 42,
    "status": "queued",
    "message": "分析任务已创建，即将开始处理"
  }
}
```

---

## 5. 实时分析管道 (`pipeline.html`)

### 5.1 管道进度（SSE / 轮询）

需要实时获取 6 个阶段的进度、百分比和日志。

**方案 A — SSE（推荐）：**
```
GET /api/analysis/{task_id}/stream
Accept: text/event-stream
```

SSE 事件格式：
```
event: progress
data: {"step":1,"step_name":"评论采集","step_state":"running","pct":15,"hint":"正在执行: 评论采集..."}

event: progress
data: {"step":1,"step_name":"评论采集","step_state":"done","pct":30,"hint":"正在执行: 数据清洗..."}

event: log
data: {"time":"09:15:32","message":"评论采集 进行中...","type":"info"}

event: complete
data: {"total_comments":52341,"total_topics":18,"elapsed_seconds":8.2,"mode":"tracking"}

event: error
data: {"message":"API 调用失败，请重试"}
```

log type: `success` / `info` / `warn`

**方案 B — 轮询（备选）：**
```
GET /api/analysis/{task_id}/progress
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "task_id": 42,
    "status": "running",
    "overall_pct": 50,
    "overall_hint": "正在执行: Embedding 向量化...",
    "steps": [
      { "step": 1, "name": "评论采集", "state": "done" },
      { "step": 2, "name": "数据清洗", "state": "done" },
      { "step": 3, "name": "Embedding 向量化", "state": "running" },
      { "step": 4, "name": "聚类分析", "state": "waiting" },
      { "step": 5, "name": "Topic 生成", "state": "waiting" },
      { "step": 6, "name": "AI 总结生成", "state": "waiting" }
    ],
    "logs": [
      { "time": "09:15:28", "message": "分析任务已启动", "type": "info" },
      { "time": "09:15:30", "message": "评论采集 进行中...", "type": "info" },
      { "time": "09:15:31", "message": "数据清洗 进行中...", "type": "info" }
    ]
  }
}
```

step state 取值：`waiting` / `running` / `done`

### 5.2 追踪模式初始化

当 `analysis_mode = "tracking"` 时，分析完成后自动进入追踪。

**请求：**
```
POST /api/analysis/{task_id}/start-tracking
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "tracking_id": 7,
    "initial_credits": 5000,
    "credits_per_hour": 100,
    "estimated_hours": 50
  }
}
```

### 5.3 追踪状态轮询

每 3 秒轮询一次追踪实时数据。

**请求：**
```
GET /api/tracking/{tracking_id}/status
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "tracking_id": 7,
    "active": true,
    "duration_seconds": 3720,
    "new_comments": 326,
    "credits_remaining": 4890,
    "credits_total": 5000,
    "total_topics": 19,
    "total_comments": 52667
  }
}
```

### 5.4 停止追踪

**请求：**
```
POST /api/tracking/{tracking_id}/stop
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "tracking_id": 7,
    "stopped_at": "2026-06-30 10:30:00",
    "total_new_comments": 412,
    "credits_consumed": 60
  }
}
```

---

## 6. 实时追踪 (`tracking.html`)

### 6.1 追踪任务列表

**请求：**
```
GET /api/tracking/tasks
```

**响应：**
```json
{
  "code": 0,
  "data": [
    {
      "tracking_id": 7,
      "task_id": 42,
      "video_title": "iPhone 16 Pro 深度评测：AI功能全面体验",
      "platform": "bilibili",
      "author": "科技美学",
      "analysis_finished_at": "2026-06-29 15:42",
      "status": "tracking",
      "new_comments": 326,
      "total_comments": 52667,
      "credits_remaining": 4890,
      "duration_seconds": 3720,
      "total_topics": 19,
      "recent_logs": [
        { "time": "09:15:32", "message": "扫描完成: 发现 3 条新评论" },
        { "time": "09:12:45", "message": "新增评论已自动分类到 Topic「价格」" },
        { "time": "09:09:32", "message": "新增评论已自动分类到 Topic「AI功能」" },
        { "time": "09:06:18", "message": "评论向量索引已更新" },
        { "time": "09:03:05", "message": "情感分析结果已刷新" }
      ]
    }
  ]
}
```

### 6.2 停止追踪（追踪页调用）

同 [5.4](#54-停止追踪)。

---

## 7. 分析结果 (`results.html`)

### 7.1 概览数据

**请求：**
```
GET /api/results/{task_id}/overview
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "video_title": "iPhone 16 Pro 深度评测：AI功能全面体验",
    "total_comments": 52341,
    "topic_count": 18,
    "positive_pct": 72,
    "negative_pct": 18,
    "neutral_pct": 10,
    "analysis_time": "2026-06-29 15:42",
    "elapsed_seconds": 208
  }
}
```

### 7.2 评论增长趋势

**请求：**
```
GET /api/results/{task_id}/trend?granularity=day
```

granularity: `day` / `hour` / `week`

**响应：**
```json
{
  "code": 0,
  "data": {
    "labels": ["6/1", "6/5", "6/10", "6/15", "6/20", "6/25", "6/29"],
    "values": [823, 910, 1043, 1200, 1456, 1678, 1890]
  }
}
```

### 7.3 情绪占比

**请求：**
```
GET /api/results/{task_id}/sentiment-ratio
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "positive": 72,
    "negative": 18,
    "neutral": 10
  }
}
```

### 7.4 Topic 列表

**请求：**
```
GET /api/results/{task_id}/topics
```

**响应：**
```json
{
  "code": 0,
  "data": [
    { "topic_name": "价格", "comment_count": 2334, "percentage": 12.3 },
    { "topic_name": "AI功能", "comment_count": 1892, "percentage": 9.8 },
    { "topic_name": "性能", "comment_count": 1567, "percentage": 8.1 },
    { "topic_name": "续航", "comment_count": 1234, "percentage": 6.4 },
    { "topic_name": "屏幕", "comment_count": 1098, "percentage": 5.7 },
    { "topic_name": "拍照", "comment_count": 987, "percentage": 5.1 },
    { "topic_name": "系统体验", "comment_count": 876, "percentage": 4.5 },
    { "topic_name": "外观设计", "comment_count": 765, "percentage": 3.9 },
    { "topic_name": "发热", "comment_count": 654, "percentage": 3.4 },
    { "topic_name": "信号", "comment_count": 543, "percentage": 2.8 }
  ]
}
```

### 7.5 Topic 详情

**请求：**
```
GET /api/results/{task_id}/topic/{topic_name}/detail
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "topic_name": "价格",
    "comment_count": 2334,
    "percentage": 12.3,
    "sample_comments": [
      "这个价格真的有点贵了，虽然功能确实强大，但对于普通用户来说性价比不高。",
      "对比上一代，这次定价还算合理，早买早享受。",
      "等国行降价再入手，现在的价格虚高。"
    ],
    "keywords": ["贵", "性价比", "降价", "值得买", "首发", "国行"],
    "ai_summary": "用户普遍认为产品定价偏高，但对功能价值持认可态度。部分用户持观望态度，等待价格下调。建议关注国行发布后的价格变动趋势。"
  }
}
```

### 7.6 属性情感数据

**请求：**
```
GET /api/results/{task_id}/sentiment-attribute
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "sunburst": [
      { "label": "价格·负面", "value": 890, "color": "#FF7A22" },
      { "label": "价格·正面", "value": 680, "color": "#FFB380" },
      { "label": "AI功能·正面", "value": 1200, "color": "#00B4CC" },
      { "label": "AI功能·中性", "value": 320, "color": "#66D5E6" },
      { "label": "性能·正面", "value": 980, "color": "#00B4CC" },
      { "label": "续航·负面", "value": 450, "color": "#FF7A22" },
      { "label": "续航·正面", "value": 520, "color": "#00B4CC" },
      { "label": "屏幕·正面", "value": 710, "color": "#00B4CC" },
      { "label": "拍照·正面", "value": 620, "color": "#00B4CC" }
    ],
    "radar": {
      "labels": ["价格", "AI功能", "性能", "续航", "屏幕", "拍照"],
      "positive_scores": [4.2, 4.8, 4.5, 3.8, 4.3, 4.6],
      "negative_scores": [3.5, 1.5, 1.8, 3.2, 1.6, 1.9]
    }
  }
}
```

### 7.7 时间趋势（详细，按天/小时/周）

**请求：**
```
GET /api/results/{task_id}/trends-detail?granularity=day
```

granularity: `day` / `hour` / `week`

**响应：**
```json
{
  "code": 0,
  "data": {
    "labels": ["6/1", "6/2", "6/3", "..."],
    "datasets": [
      {
        "label": "总评论",
        "values": [823, 845, 867, "..."],
        "color": "#FF7A22"
      },
      {
        "label": "正面",
        "values": [580, 595, 610, "..."],
        "color": "#00B4CC"
      },
      {
        "label": "负面",
        "values": [148, 152, 155, "..."],
        "color": "#F8F2E4"
      }
    ]
  }
}
```

### 7.8 AI 总结

**请求：**
```
GET /api/results/{task_id}/ai-summary
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "title": "iPhone 16 Pro 评测评论分析报告",
    "summary_text": "本次分析共采集 52,341 条评论，识别出 18 个主要话题。整体舆论偏向正面（72%正向），用户最关注的三大维度为价格、AI功能和性能。其中 AI 功能获得最多积极评价，而价格方面存在较大争议。续航与发热问题是主要的负面情绪来源，建议产品团队重点关注。",
    "highlights": [
      { "label": "🔝 最热话题", "text": "价格 — 2,334条评论，负面情绪集中" },
      { "label": "✅ 最佳口碑", "text": "AI功能 — 89%正面评价，用户满意度最高" },
      { "label": "⚠️ 风险预警", "text": "发热问题 — 负面情绪上升趋势，需关注" },
      { "label": "⏱ 分析时间", "text": "2026-06-29 15:42 — 耗时3分28秒" }
    ]
  }
}
```

### 7.9 评论检索

**请求：**
```
GET /api/results/{task_id}/comments/search
  ?keyword=价格
  &page=1
  &page_size=20
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "total": 2334,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "comment_id": 12345,
        "text": "这个价格真的有点贵了，虽然功能确实强大，但对于普通用户来说性价比不高。",
        "highlighted_text": "这个<em>价格</em>真的有点贵了，虽然功能确实强大，但对于普通用户来说<em>性价比</em>不高。",
        "platform": "bilibili",
        "user_name": "B站用户",
        "time_ago": "2小时前",
        "likes": 128,
        "topic": "价格"
      },
      {
        "comment_id": 12346,
        "text": "AI修图太强了！这次苹果的AI功能真的是吊打安卓阵营。",
        "highlighted_text": "<em>AI修图</em>太强了！这次苹果的<em>AI功能</em>真的是吊打安卓阵营。",
        "platform": "douyin",
        "user_name": "抖音用户",
        "time_ago": "5小时前",
        "likes": 256,
        "topic": "AI功能"
      }
    ]
  }
}
```

> 注：`highlighted_text` 将匹配的关键词用 `<em>` 标签包裹，前端用 `.highlight` CSS 类渲染。

### 7.10 追踪状态条（结果页）

当 analysis_mode = "tracking" 时显示。

**请求：**
```
GET /api/results/{task_id}/tracking-status
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "is_tracking": true,
    "new_comments": 156,
    "total_comments": 52497,
    "credits_remaining": 8420,
    "duration_seconds": 8132,
    "duration_formatted": "02:15:32"
  }
}
```

---

## 8. 视频管理 (`videos.html`)

### 8.1 视频列表

**请求：**
```
GET /api/videos?page=1&page_size=20
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "total": 5,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "video_id": "BV1xx411c7mD",
        "cover_url": "https://...",
        "title": "iPhone 16 Pro 深度评测：AI功能全面体验",
        "author": "科技美学",
        "platform": "bilibili",
        "comment_count": 12845,
        "publish_date": "2026-06-15",
        "analysis_status": "tracking",
        "new_comments_since_tracking": 326,
        "last_analysis_date": "2026-06-29"
      },
      {
        "video_id": "BV2yy422d8nE",
        "cover_url": "https://...",
        "title": "华为 Mate 70 系列发布会全解析",
        "author": "钟文泽",
        "platform": "bilibili",
        "comment_count": 23102,
        "publish_date": "2026-06-10",
        "analysis_status": "analyzed",
        "new_comments_since_tracking": 0,
        "last_analysis_date": "2026-06-25"
      }
    ]
  }
}
```

`analysis_status` 取值：
- `tracking` — 实时追踪中（橙色标签）
- `analyzed` — 已分析（青色标签）
- `analyzing` — 分析中/待分析（橙色标签）
- `pending` — 尚未分析

---

## 9. 历史记录 (`history.html`)

### 9.1 历史记录列表

支持筛选、排序、分页。

**请求：**
```
GET /api/history
  ?platform=bilibili        // 可选, "bilibili" | "douyin" | 不传=全部
  &time_range=recent_30d    // 可选, "recent_7d" | "recent_30d" | "recent_3m" | 不传=全部
  &keyword=iPhone           // 可选, 搜索视频标题
  &page=1
  &page_size=10
  &sort_by=comment_count    // 可选, "video_title" | "topic_count" | "comment_count" | "analysis_time"
  &sort_order=desc          // 可选, "asc" | "desc"
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "total": 42,
    "page": 1,
    "page_size": 10,
    "total_pages": 5,
    "items": [
      {
        "task_id": 42,
        "video_title": "iPhone 16 Pro 深度评测：AI功能全面体验",
        "platform": "bilibili",
        "analysis_mode": "tracking",
        "analyzed_at": "2026-06-28 15:42",
        "topic_count": 18,
        "comment_count": 52341,
        "status": "running",
        "status_label": "运行中"
      },
      {
        "task_id": 41,
        "video_title": "华为 Mate 70 系列发布会解析",
        "platform": "bilibili",
        "analysis_mode": "normal",
        "analyzed_at": "2026-06-24 10:18",
        "topic_count": 22,
        "comment_count": 23102,
        "status": "completed",
        "status_label": "已完成"
      }
    ]
  }
}
```

`status` 取值：`running` / `completed` / `stopped`
`analysis_mode` 取值：`tracking` / `normal`

---

## 10. 系统设置 (`settings.html`)

### 10.1 获取设置

**请求：**
```
GET /api/settings
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "analysis_preferences": {
      "default_comment_count": 500,
      "auto_ai_summary": true,
      "realtime_animation": true
    },
    "notification_preferences": {
      "analysis_complete_notify": true,
      "anomaly_alert": true
    },
    "account": {
      "username": "admin",
      "email": "admin@opinion.ai",
      "api_key_masked": "sk-••••••••••••••••"
    }
  }
}
```

### 10.2 更新分析偏好

**请求：**
```
PUT /api/settings/analysis-preferences
Content-Type: application/json

{
  "default_comment_count": 1000,
  "auto_ai_summary": false,
  "realtime_animation": true
}
```

**响应：**
```json
{
  "code": 0,
  "message": "保存成功"
}
```

### 10.3 更新通知偏好

**请求：**
```
PUT /api/settings/notification-preferences
Content-Type: application/json

{
  "analysis_complete_notify": true,
  "anomaly_alert": false
}
```

**响应：**
```json
{
  "code": 0,
  "message": "保存成功"
}
```

### 10.4 修改用户名

**请求：**
```
PUT /api/user/username
Content-Type: application/json

{
  "username": "new_admin_name"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "用户名修改成功"
}
```

### 10.5 修改邮箱

**请求：**
```
PUT /api/user/email
Content-Type: application/json

{
  "email": "newemail@example.com"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "邮箱修改成功"
}
```

### 10.6 重新生成 API Key

**请求：**
```
POST /api/user/api-key/regenerate
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "api_key": "sk-new-api-key-value",
    "api_key_masked": "sk-n••••••••••••••••"
  }
}
```

---

## 附录：通用数据结构

### A.1 统一响应格式

所有接口统一使用以下响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

| code | 含义 |
|------|------|
| 0 | 成功 |
| 401 | 未登录/Token 过期 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 429 | 请求频率限制 |
| 500 | 服务器内部错误 |

### A.2 平台枚举

| 值 | 显示名称 | CSS类 |
|----|---------|-------|
| `bilibili` | B站 | `bilibili` (橙色 `#FF7A22`) |
| `douyin` | 抖音 | `douyin` (青色 `#00B4CC`) |

### A.3 分析状态枚举

| 值 | 显示名称 | CSS类 |
|----|---------|-------|
| `pending` | 待分析 | `video-card-status pending` |
| `queued` | 排队中 | — |
| `running` / `analyzing` | 分析中 | `step-icon running` |
| `completed` / `analyzed` | 已完成 | `video-card-status analyzed` |
| `tracking` | 追踪中 | `video-card-status tracking` |
| `stopped` | 已停止 | — |

### A.4 情感类型枚举

| 值 | 显示名称 | 颜色 |
|----|---------|------|
| `positive` | 正面 | `#00B4CC` |
| `negative` | 负面 | `#FF7A22` |
| `neutral` | 中性 | `#F8F2E4` |

### A.5 管道步骤枚举

| step | 名称 | 说明 |
|------|------|------|
| 1 | 评论采集 | 从平台 API 抓取评论数据 |
| 2 | 数据清洗 | 去重、过滤无效内容、格式化 |
| 3 | Embedding 向量化 | 将评论文本转为向量 |
| 4 | 聚类分析 | 对向量进行聚类 |
| 5 | Topic 生成 | 为每个簇生成主题标签 |
| 6 | AI 总结生成 | 调用大模型生成分析报告 |

### A.6 接口汇总表

| # | 方法 | 路径 | 页面 | 说明 |
|---|------|------|------|------|
| 1 | GET | `/api/user/profile` | 通用 | 当前用户信息 |
| 2 | GET | `/api/stats/header` | 通用 | 顶部统计数字 |
| 3 | GET | `/api/tracking/has-active` | 通用 | 追踪红点状态 |
| 4 | POST | `/api/auth/login` | login | 登录 |
| 5 | POST | `/api/auth/register` | login | 注册 |
| 6 | GET | `/api/dashboard/summary` | dashboard | 统计卡片 |
| 7 | GET | `/api/dashboard/trend?days=30` | dashboard | 评论增长趋势 |
| 8 | GET | `/api/dashboard/sentiment-ratio` | dashboard | 情绪占比 |
| 9 | GET | `/api/dashboard/top-topics?limit=10` | dashboard | TOP10 Topic |
| 10 | GET | `/api/dashboard/active-tracking` | dashboard | 活跃追踪卡片 |
| 11 | GET | `/api/videos/search` | create-analysis | 搜索视频 |
| 12 | GET | `/api/user/credits` | create-analysis | 查询积分 |
| 13 | POST | `/api/analysis/create` | create-analysis | 创建分析任务 |
| 14 | GET | `/api/analysis/{task_id}/stream` | pipeline | SSE 进度 |
| 15 | GET | `/api/analysis/{task_id}/progress` | pipeline | 轮询进度（备选） |
| 16 | POST | `/api/analysis/{task_id}/start-tracking` | pipeline | 启动追踪 |
| 17 | GET | `/api/tracking/{tracking_id}/status` | pipeline/tracking | 追踪状态 |
| 18 | POST | `/api/tracking/{tracking_id}/stop` | pipeline/tracking/results | 停止追踪 |
| 19 | GET | `/api/tracking/tasks` | tracking | 追踪任务列表 |
| 20 | GET | `/api/results/{task_id}/overview` | results | 概览数据 |
| 21 | GET | `/api/results/{task_id}/trend` | results | 评论趋势 |
| 22 | GET | `/api/results/{task_id}/sentiment-ratio` | results | 情绪占比 |
| 23 | GET | `/api/results/{task_id}/topics` | results | Topic 列表 |
| 24 | GET | `/api/results/{task_id}/topic/{topic_name}/detail` | results | Topic 详情 |
| 25 | GET | `/api/results/{task_id}/sentiment-attribute` | results | 属性情感 |
| 26 | GET | `/api/results/{task_id}/trends-detail` | results | 详细趋势 |
| 27 | GET | `/api/results/{task_id}/ai-summary` | results | AI 总结 |
| 28 | GET | `/api/results/{task_id}/comments/search` | results | 评论检索 |
| 29 | GET | `/api/results/{task_id}/tracking-status` | results | 追踪状态条 |
| 30 | GET | `/api/videos` | videos | 视频列表 |
| 31 | GET | `/api/history` | history | 历史记录 |
| 32 | GET | `/api/settings` | settings | 获取设置 |
| 33 | PUT | `/api/settings/analysis-preferences` | settings | 更新分析偏好 |
| 34 | PUT | `/api/settings/notification-preferences` | settings | 更新通知偏好 |
| 35 | PUT | `/api/user/username` | settings | 修改用户名 |
| 36 | PUT | `/api/user/email` | settings | 修改邮箱 |
| 37 | POST | `/api/user/api-key/regenerate` | settings | 重新生成 API Key |
