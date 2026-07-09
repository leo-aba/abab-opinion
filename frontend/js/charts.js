// ============================================================
// CHART INITIALIZATION — 所有图表渲染函数
// 每个函数负责销毁旧实例 + 创建新 Chart.js 实例
// 全局变量保存各图表实例引用，用于销毁和切换
// ============================================================
let trendChartInstance, sentimentPieInstance, topicBarInstance;
let resultsTrendInstance, resultsPieInstance, sunburstInstance, radarInstance, trendsDetailInstance;

/**
 * 安全销毁 Chart.js 实例（跳过已销毁或 null 的实例）
 * @param {Chart|null} instance - Chart.js 实例
 */
function destroyChart(instance) {
  if (instance) instance.destroy();
}

// ============================================================
// Dashboard Charts
// ============================================================

/**
 * 渲染评论增长趋势折线图（Dashboard）
 * @param {{labels: string[], values: number[]}} data
 */
function renderTrendChart(data) {
  destroyChart(trendChartInstance);
  const ctx = document.getElementById('trendChart');
  if (!ctx || !data) return;
  trendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        label: '评论数',
        data: data.values,
        borderColor: '#FF7A22',
        backgroundColor: 'rgba(255,122,34,0.08)',
        fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 6, borderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 6, font: { size: 11 }, color: '#BFB59E' } },
        y: { grid: { color: '#333' }, ticks: { font: { size: 11 }, color: '#BFB59E' }, beginAtZero: false }
      },
      interaction: { mode: 'nearest', axis: 'x', intersect: false }
    }
  });
}

/**
 * 渲染情绪占比环形图（Dashboard）
 * @param {{positive: number, negative: number, neutral: number}} data
 */
function renderSentimentPie(data) {
  destroyChart(sentimentPieInstance);
  const ctx = document.getElementById('sentimentPie');
  if (!ctx || !data) return;
  sentimentPieInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['正面', '负面', '中性'],
      datasets: [{
        data: [data.positive, data.negative, data.neutral],
        backgroundColor: ['#00B4CC', '#FF7A22', '#A0A0A0'],
        borderColor: '#000000', borderWidth: 3, hoverBorderWidth: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { position: 'bottom', labels: { padding: 20, usePointStyle: true, pointStyleWidth: 8, font: { size: 12 }, color: '#BFB59E' } } },
      cutout: '65%',
    }
  });
}

/**
 * 渲染 TOP10 热门 Topic 横向柱状图（Dashboard）
 * @param {Array<{topic_name: string, comment_count: number}>} data
 */
function renderTopicBar(data) {
  destroyChart(topicBarInstance);
  const ctx = document.getElementById('topicBarChart');
  if (!ctx || !data || !data.length) return;
  topicBarInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.topic_name),
      datasets: [{
        data: data.map(d => d.comment_count),
        backgroundColor: data.map(d => d.comment_count > 1500 ? '#FF7A22' : d.comment_count > 1000 ? '#00B4CC' : '#F8F2E4'),
        borderRadius: 6, borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: '#333' }, ticks: { font: { size: 11 }, color: '#BFB59E' } },
        y: { grid: { display: false }, ticks: { font: { size: 12 }, color: '#BFB59E' } }
      }
    }
  });
}

// ============================================================
// Results Charts
// ============================================================

/**
 * 渲染结果页评论趋势折线图
 * @param {{labels: string[], values: number[]}} data
 */
function renderResultsTrend(data) {
  destroyChart(resultsTrendInstance);
  const ctx = document.getElementById('resultsTrendChart');
  if (!ctx || !data) return;
  resultsTrendInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        label: '评论数', data: data.values,
        borderColor: '#FF7A22', backgroundColor: 'rgba(255,122,34,0.08)',
        fill: true, tension: 0.4, pointRadius: 4, borderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#BFB59E' }, title: { display: true, text: '日期', color: '#BFB59E', font: { size: 12 } } },
        y: { grid: { color: '#333' }, ticks: { color: '#BFB59E' }, beginAtZero: false, title: { display: true, text: '评论数', color: '#BFB59E', font: { size: 12 } } }
      }
    }
  });
}

/**
 * 渲染结果页情绪占比环形图
 * @param {{positive: number, negative: number, neutral: number}} data
 */
function renderResultsPie(data) {
  destroyChart(resultsPieInstance);
  const ctx = document.getElementById('resultsPieChart');
  if (!ctx || !data) return;
  resultsPieInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['正面', '负面', '中性'],
      datasets: [{
        data: [data.positive, data.negative, data.neutral],
        backgroundColor: ['#00B4CC', '#FF7A22', '#A0A0A0'],
        borderColor: '#000000', borderWidth: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { position: 'bottom', labels: { padding: 20, usePointStyle: true, font: { size: 12 }, color: '#BFB59E' } } },
      cutout: '65%',
    }
  });
}

/**
 * 渲染属性情感旭日图（多级环形图）
 * @param {Array<{label: string, value: number, color: string}>} data
 */
function renderSunburst(data) {
  destroyChart(sunburstInstance);
  const ctx = document.getElementById('sunburstChart');
  if (!ctx || !data || !data.length) return;
  sunburstInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        data: data.map(d => d.value),
        backgroundColor: data.map(d => d.color),
        borderColor: '#000000', borderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { position: 'right', labels: { font: { size: 10 }, padding: 8, color: '#BFB59E' } } },
      cutout: '30%',
    }
  });
}

/**
 * 渲染情感雷达图（正面 vs 负面各维度对比）
 * @param {{labels: string[], positive_scores: number[], negative_scores: number[]}} data
 */
function renderRadar(data) {
  destroyChart(radarInstance);
  const ctx = document.getElementById('radarChart');
  if (!ctx || !data) return;
  radarInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: data.labels,
      datasets: [
        { label: '正面', data: data.positive_scores, borderColor: '#00B4CC', backgroundColor: 'rgba(0,180,204,0.08)', borderWidth: 2, pointBackgroundColor: '#00B4CC' },
        { label: '负面', data: data.negative_scores, borderColor: '#FF7A22', backgroundColor: 'rgba(255,122,34,0.08)', borderWidth: 2, pointBackgroundColor: '#FF7A22' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { position: 'bottom', labels: { color: '#BFB59E' } } },
      scales: { r: { beginAtZero: true, max: 5, ticks: { stepSize: 1, font: { size: 10 }, color: '#BFB59E', backdropColor: 'transparent' }, grid: { color: '#333' }, pointLabels: { color: '#BFB59E' } } }
    }
  });
}

/**
 * 渲染时间趋势详情多线图（按天/小时/周，正面/负面/总计）
 * @param {{labels: string[], datasets: Array<{label: string, values: number[], color: string}>}} data
 */
function renderTrendsDetail(data) {
  destroyChart(trendsDetailInstance);
  const ctx = document.getElementById('trendsDetailChart');
  if (!ctx || !data) return;
  trendsDetailInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: (data.datasets || []).map(ds => ({
        label: ds.label, data: ds.values, borderColor: ds.color,
        tension: 0.4, pointRadius: 0, borderWidth: 2,
      }))
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { color: '#BFB59E' } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#BFB59E' }, title: { display: true, text: '日期', color: '#BFB59E', font: { size: 12 } } },
        y: { grid: { color: '#333' }, ticks: { color: '#BFB59E' }, title: { display: true, text: '评论数', color: '#BFB59E', font: { size: 12 } } }
      },
      interaction: { mode: 'nearest', axis: 'x', intersect: false }
    }
  });
}

// ============================================================
// Dashboard 整体渲染
// ============================================================

/**
 * Dashboard 页面 — 并行拉取 3 个图表接口并渲染
 * @returns {Promise<{trend: object, sentiment: object, topics: Array}|null>}
 */
async function initDashboardCharts() {
  try {
    const [trend, sentiment, topics] = await Promise.all([
      api.getDashboardTrend(30),
      api.getDashboardSentimentRatio(),
      api.getDashboardTopTopics(10),
    ]);
    renderTrendChart(trend);
    renderSentimentPie(sentiment);
    renderTopicBar(topics);
    return { trend, sentiment, topics };
  } catch (e) {
    console.error('Dashboard charts failed:', e);
    return null;
  }
}
