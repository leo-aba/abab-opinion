# Plan: 普通分析新增分析方式选项 (AI分析 / 模型总结)

**生成**: 2026-07-09
**复杂度**: Medium

## Overview

在创建分析页面的「普通分析」卡片上，新增两个分析方式选项：
- **AI分析**（现有）：调用 DeepSeek LLM 进行话题分类、情感分析、综述生成
- **模型总结**（新增）：用 Qwen3-Embedding 向量化 → UMAP 降维 → HDBSCAN 聚类 → 关键词命名话题，输出结构与 AI 分析一致

两种方式共享**爬取 + 清洗**流程，在「分析」阶段分岔。

## Prerequisites

- `umap-learn`、`hdbscan` 已安装（已手动安装，需同步更新 requirements.txt）
- Qwen3-Embedding 模型已下载（`backend/models/embedding/...` 已存在）

## Sprint 1: Embedding + 聚类 Service

**Goal**: 创建纯本地的向量化 + 聚类分析服务，输出结构与 AI 分析对齐。
**Demo/Validation**:
- Python 单元测试：输入假评论列表，验证输出 dict 结构正确
- 可在 REPL 中直接调用 `embed_cluster_service.analyze_comments()` 验证

### Task 1.1: 安装依赖并更新 requirements.txt
- **Location**: `requirements.txt`
- **Description**: 将 `umap-learn>=0.5` 和 `hdbscan>=0.8` 加入 requirements.txt
- **Dependencies**: 无
- **Acceptance Criteria**: `pip install -r requirements.txt` 成功安装所有依赖
- **Validation**: `python -c "import umap; import hdbscan; print('OK')"`

### Task 1.2: 创建 embed_cluster_service.py
- **Location**: `backend/service/embed_cluster_service.py`（新文件）
- **Description**: 核心分析服务，包含：

  **a) 常量与配置**
  - `MODEL_PATH` — Qwen3-Embedding 模型路径
  - 全局单例 `_model: SentenceTransformer | None = None`
  - `get_model()` — 懒加载模型实例

  **b) `embed_comments(texts: list[str]) -> np.ndarray`**
  - 调用 `SentenceTransformer.encode(batch_size=32, normalize_embeddings=True)`
  - 返回 shape `(N, 1024)` 的向量矩阵
  - 异常时 raise `RuntimeError`

  **c) `cluster_embeddings(vectors: np.ndarray) -> np.ndarray`**
  - UMAP: 1024d → 10d（`n_components=10, random_state=42`）
  - HDBSCAN: `min_cluster_size=5, min_samples=3, metric='euclidean'`
  - 返回 label 数组，-1 表示噪音
  - 如果聚类结果全为噪音或无有效簇，退回将所有评论作为一个簇

  **d) `_extract_cluster_keywords(texts: list[str], top_n=5) -> list[str]`**
  - 简单的词频统计（jieba 分词或 sklearn CountVectorizer）
  - 返回该簇最常出现的前 top_n 个关键词
  - **注意**: 安装 `jieba` 包用于中文分词

  **e) `_estimate_sentiment(texts: list[str]) -> dict`**
  - 基于简单正负面词表的情感估算
  - 返回 `{"positive": N, "negative": N, "neutral": N}`
  - 正负面词表硬编码在函数内（约 30-50 个常见词）

  **f) `generate_overall_summary(clusters_info: list[dict]) -> str`**
  - 根据各簇大小和关键词生成简单综述模板
  - 如："共分析 N 条评论，识别出 M 个话题。最大话题「xxx」占 X%。..."

  **g) `analyze_comments(comments: list[dict]) -> dict`**
  - 主入口函数
  - 输入：`[{"text": "..."}]` 格式的评论列表
  - 流程：embed → cluster → 按簇分组 → 为每簇生成 name/keywords/summary/sentiment → 组装 topics → 生成 overall_summary
  - 输出格式与 `llm_service.analyze_comments_with_llm()` 完全一致：
    ```python
    {
        "topics": [
            {
                "name": str,           # "话题_关键词1_关键词2..."
                "keywords": [str],     # 前5高频词
                "comment_indices": [int],  # 评论在原列表中的索引
                "summary": str,        # "共 N 条评论，关键词：...", LLM-style summary is skipped
                "sentiment": {"positive": int, "negative": int, "neutral": int}
            }
        ],
        "aspects": [],                 # 聚类无法生成 aspects，返回空列表
        "overall_summary": str         # 简单统计综述
    }
    ```
  - 注意：topic 的 `sentiment` 用 `_estimate_sentiment` 估算
  - **不存在的评论索引**（超出范围）跳过
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - 可独立调用并返回正确结构
  - 输出 JSON 可以被 results_service 正确消费
- **Validation**: 编写简单测试 `test/test_embed_cluster.py`

### Task 1.3: 添加 jieba 分词依赖
- **Location**: `requirements.txt`
- **Description**: 添加 `jieba>=0.42.1` 用于中文关键词提取
- **Dependencies**: 无
- **Acceptance Criteria**: 可正常 import jieba 并分词

## Sprint 2: 后端 API — 支持 analysis_method

**Goal**: 创建分析任务时支持选择 `analysis_method`，后端根据方法类型分流（LLM / 聚类）。
**Demo/Validation**:
- POST `/api/analysis/create` 传 `analysis_method: "cluster"` 成功创建任务
- 任务完成后 topics 数据正确（来自聚类而非 LLM）
- 不传 `analysis_method` 时向后兼容（默认 `"llm"`）

### Task 2.1: 更新 CreateAnalysisRequest Schema
- **Location**: `backend/schemas/analysis.py`
- **Description**: 新增字段 `analysis_method: str = "llm"`，validator 校验值为 `"llm" | "cluster"`
- **Dependencies**: 无
- **Acceptance Criteria**:
  - 请求体可选 `analysis_method`
  - 默认 `"llm"`（不影响现有前端）
  - 非法值返回 422

### Task 2.2: 在 AnalysisTask Model 中持久化 analysis_method
- **Location**: `backend/models/analysis_task.py`
- **Description**: 新增字段 `analysis_method: Mapped[str] = mapped_column(String(8), nullable=False, default="llm")`，comment="分析方法: llm | cluster"
- **Dependencies**: 无
- **Acceptance Criteria**: 数据库表 `analysis_tasks` 新增列 `analysis_method`

### Task 2.3: 更新 analysis_service.py 分流
- **Location**: `backend/service/analysis_service.py`
- **Description**: 
  - `create_analysis_task()` 函数签名增加 `analysis_method` 参数，透传到 AnalysisTask
  - `run_crawl_task()` 函数签名增加 `analysis_method` 参数
  - 在清洗评论完成后，根据 `analysis_method` 分流：
    - `"llm"` → 走现有 LLM 分析逻辑（不变）
    - `"cluster"` → 调用 `embed_cluster_service.analyze_comments()`，拿到结果后以相同格式写入 Topic 表和更新 Comment 的 topic_id/sentiment
  - **复用现有 Topic 写入逻辑**：两种路径产出的 dict 结构一致，写入 topics 和更新评论的代码可共用
- **Dependencies**: Task 2.1, Task 2.2, Sprint 1
- **Acceptance Criteria**:
  - `analysis_method="cluster"` 的任务正常完成
  - results API 返回的话题数据格式与 AI 分析一致
- **Validation**: 创建一个 cluster 模式的分析任务，验证 topics 和 results API

### Task 2.4: 更新 history service 返回 analysis_method
- **Location**: `backend/service/history_service.py`
- **Description**: 查询历史记录时返回 `analysis_method` 字段，方便前端展示
- **Dependencies**: 无
- **Acceptance Criteria**: 历史列表每条记录包含 `analysis_method` 字段

## Sprint 3: 前端 — 分析方式选择 UI

**Goal**: 在普通分析卡片右下角添加「AI分析」和「模型总结」两个选项。
**Demo/Validation**:
- 打开创建分析页面，普通分析卡片右下角可见两个 radio 按钮
- 默认选中「AI分析」
- 切换到「模型总结」后，创建任务时带上 `analysis_method: "cluster"`

### Task 3.1: 更新普通分析卡片 UI
- **Location**: `frontend/create-analysis.html`
- **Description**: 
  - 在普通分析卡片（`#modeNormal`）的底部添加一排两个 radio/button 选项：
    - `○ AI分析`（选中状态，紫色/橙色主题）
    - `○ 模型总结`（未选中，灰色主题）
  - 使用简单的行内样式或已有 CSS 变量
  - 添加对应 JS 变量 `selectedAnalysisMethod = 'llm'` 和切换函数
  - 确保选中状态样式可区分
- **Dependencies**: 无
- **Acceptance Criteria**: UI 上可见两个可点击的选项

### Task 3.2: 在创建分析请求中传递 analysis_method
- **Location**: `frontend/create-analysis.html`
- **Description**: 
  - `startAnalysis()` 函数中，将 `selectedAnalysisMethod` 加入请求参数
- **Dependencies**: Task 3.1
- **Acceptance Criteria**: 创建分析的网络请求中包含 `analysis_method` 字段

### Task 3.3: 在确认摘要页展示 analysis_method
- **Location**: `frontend/create-analysis.html`
- **Description**: `updateWizardSummary()` 中显示当前选中的分析方式（AI 分析 / 模型总结）
- **Dependencies**: Task 3.1
- **Acceptance Criteria**: Step 3 摘要中可见"分析方式：AI 分析"或"分析方式：模型总结"

## Testing Strategy

| Sprint | 验证方式 |
|--------|---------|
| Sprint 1 | 单元测试 `test/test_embed_cluster.py` — 用少量假评论测试 embed → cluster → format 全流程 |
| Sprint 2 | 创建分析任务（`analysis_method=cluster`），查看 topic 数据和 results 页面 |
| Sprint 3 | 手动 UI 验收：点击切换、确认摘要、查看网络请求 |

## Potential Risks & Gotchas

1. **embed_comments 性能**：Qwen3-Embedding 首次加载约 5-10 秒，后续编码每条约 10ms。建议使用模块级缓存（单例模型）
2. **聚类质量**：HDBSCAN 对短文本聚类效果不稳定，`min_cluster_size` 参数可能需要调优。首次上线时保留默认值 `5`
3. **关键词提取**：纯词频在评论数据上可能不够准确。用 `jieba` 分词 + TF 过滤停用词
4. **情感估算**：基于词表的估算精度远低于 LLM，但能满足基本需求。正负面词表需要覆盖评论常见情感词
5. **全噪音聚类**：如果 HDBSCAN 把所有点标为 -1（噪音），需回退到将所有评论作为一个簇处理
6. **向后兼容**：已有任务没有 `analysis_method` 字段，前端历史记录页需做空值处理
7. **数据库迁移**：`analysis_method` 是新加列，需确保 MySQL 表结构同步。可以使用 `ALTER TABLE analysis_tasks ADD COLUMN analysis_method VARCHAR(8) DEFAULT 'llm'`

## Rollback Plan

- **代码回滚**：`git revert` 相关 commit
- **数据库回滚**：`ALTER TABLE analysis_tasks DROP COLUMN analysis_method`
- **前端回滚**：恢复 `create-analysis.html` 到修改前版本
