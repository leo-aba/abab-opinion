"""Embedding + 聚类分析 Service

用 Qwen3-Embedding 对评论进行向量化，UMAP 降维后 HDBSCAN 聚类，
再用 jieba 提取关键词命名话题，词表估算情感分布。
输出结构与 LLM 分析的 analyze_comments_with_llm() 完全一致。

依赖: torch, transformers, umap-learn, hdbscan, jieba, numpy, scikit-learn
"""

import logging
import re
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("embed_cluster_service")

# ── 嵌入模型路径 ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MODEL_PATH = (
    PROJECT_ROOT
    / "backend" / "models" / "embedding"
    / "embedding" / "models--Qwen--Qwen3-Embedding-0.6B"
    / "snapshots" / "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
)

# 全局单例（懒加载）
_model: Optional[any] = None
_tokenizer: Optional[any] = None


def _get_model_and_tokenizer():
    """懒加载 Qwen3 模型和分词器（直接使用 transformers，不依赖 sentence-transformers）。"""
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    if not _MODEL_PATH.exists():
        raise RuntimeError(f"嵌入模型路径不存在: {_MODEL_PATH}")

    import torch
    from transformers import AutoModel, AutoTokenizer

    logger.info("正在加载嵌入模型: %s", _MODEL_PATH)
    tokenizer = AutoTokenizer.from_pretrained(str(_MODEL_PATH), trust_remote_code=True)
    model = AutoModel.from_pretrained(
        str(_MODEL_PATH),
        trust_remote_code=True,
        torch_dtype=torch.float32,
    )
    model.eval()
    logger.info("模型加载完成")
    _model = model
    _tokenizer = tokenizer
    return model, tokenizer


def _mean_pooling(last_hidden_state, attention_mask):
    """Mean Pooling — 取所有 token 的隐层平均作为句子向量。"""
    token_embeddings = last_hidden_state
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return (token_embeddings * input_mask_expanded).sum(1) / input_mask_expanded.sum(1)


# ── 正负面情感词表（简单版） ────────────────────────────────
_POSITIVE_WORDS = {
    "好", "棒", "赞", "喜欢", "爱", "厉害", "优秀", "精彩", "不错",
    "感人", "好看", "好听", "好玩", "有趣", "搞笑", "经典", "支持",
    "良心", "满意", "享受", "佩服", "推荐", "期待", "感动", "完美",
    "舒服", "漂亮", "可爱", "美", "帅", "强", "牛", "顶", "666",
    "可以", "中", "行", "绝了", "yyds", "神仙", "宝藏", "无敌",
}

_NEGATIVE_WORDS = {
    "差", "烂", "垃圾", "恶心", "讨厌", "烦", "无聊", "失望", "糟",
    "烂片", "难看", "难听", "不好", "不行", "没用", "无趣", "低俗",
    "糟糕", "失败", "后悔", "浪费", "尴尬", "虚假", "骗子", "坑",
    "太差", "太烂", "受不了", "无语", "呵呵", "呸", "有病", "有病吧",
    "脑残", "弱智", "白痴", "蠢", "假", "恶心人", "烦人",
}

# 停用词
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "会", "到", "说", "要", "去",
    "你", "他", "她", "它", "们", "这", "那", "什么", "怎么",
    "吗", "啊", "呢", "吧", "嗯", "哦", "哈", "呀", "嘛",
    "没", "被", "把", "让", "给", "为", "从", "以", "与", "对",
    "看", "做", "能", "可以", "这个", "那个", "这些", "那些",
    "还是", "因为", "所以", "但是", "如果", "虽然", "不过",
}


# ──────────────────────────────────────────────
# 向量化
# ──────────────────────────────────────────────


def embed_comments(texts: list[str]) -> np.ndarray:
    """将评论文本向量化。

    Args:
        texts: 文本列表

    Returns:
        shape (N, 1024) 的归一化向量矩阵
    """
    if not texts:
        raise ValueError("评论文本列表为空")

    import torch

    model, tokenizer = _get_model_and_tokenizer()
    logger.info("正在向量化 %d 条评论...", len(texts))

    all_embeddings = []
    batch_size = 32

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        inputs = tokenizer(
            batch, padding=True, truncation=True, max_length=128,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
        embedding = _mean_pooling(outputs.last_hidden_state, inputs["attention_mask"])
        # L2 归一化
        embedding = embedding / embedding.norm(dim=1, keepdim=True)
        all_embeddings.append(embedding.numpy())

    result = np.concatenate(all_embeddings, axis=0)
    logger.info("向量化完成，形状: %s", result.shape)
    return result


# ──────────────────────────────────────────────
# 聚类
# ──────────────────────────────────────────────


def cluster_embeddings(vectors: np.ndarray) -> np.ndarray:
    """UMAP 降维 + HDBSCAN 聚类。

    Args:
        vectors: shape (N, D) 的向量矩阵

    Returns:
        label 数组，-1 表示噪音
    """
    import umap
    import hdbscan

    n = len(vectors)
    if n < 3:
        logger.info("评论数 < 3，全部归为同一簇")
        return np.zeros(n, dtype=int)

    min_cluster = max(3, min(5, n // 3))

    # UMAP 降维: n_components 必须 < n-1
    if n > 5:
        n_comp = min(10, n - 2)
        logger.info("UMAP 降维 (%dd → %dd)...", vectors.shape[1], n_comp)
        reducer = umap.UMAP(n_components=n_comp, random_state=42, verbose=False, force_approximation_algorithm=True if n_comp >= n - 1 else False)
        embedding_10d = reducer.fit_transform(vectors)
        logger.info("降维完成，形状: %s", embedding_10d.shape)
    else:
        # 数据太少，直接用原始向量
        embedding_10d = vectors

    logger.info("HDBSCAN 聚类 (min_cluster_size=%d)...", min_cluster)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster,
        min_samples=3,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(embedding_10d)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    logger.info("聚类完成: %d 个簇, %d 条噪音 (%.1f%%)",
                n_clusters, n_noise, n_noise / n * 100 if n else 0)

    if n_clusters == 0:
        logger.warning("全部评论被标记为噪音，回退到单簇")
        labels = np.zeros(n, dtype=int)

    return labels


# ──────────────────────────────────────────────
# 关键词提取
# ──────────────────────────────────────────────


def _extract_keywords(texts: list[str], top_n: int = 5) -> list[str]:
    """从一组文本中提取前 top_n 个高频关键词。"""
    import jieba

    word_counts: dict[str, int] = {}
    for t in texts:
        words = jieba.lcut(t)
        for w in words:
            w = w.strip().lower()
            if len(w) < 2:
                continue
            if w in _STOP_WORDS:
                continue
            if re.match(r'^[\d\s\.\,\!\?\!\.\，\。\！\？\《\》\-]+$', w):
                continue
            word_counts[w] = word_counts.get(w, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_words[:top_n]]


# ──────────────────────────────────────────────
# 情感估算（基于词表）
# ──────────────────────────────────────────────


def _estimate_sentiment(texts: list[str]) -> dict:
    """基于正负面词表估算一组评论的情感分布。"""
    pos = neg = neu = 0
    for t in texts:
        has_pos = any(w in t for w in _POSITIVE_WORDS)
        has_neg = any(w in t for w in _NEGATIVE_WORDS)
        if has_pos and not has_neg:
            pos += 1
        elif has_neg and not has_pos:
            neg += 1
        else:
            neu += 1
    return {"positive": pos, "negative": neg, "neutral": neu}


# ──────────────────────────────────────────────
# 综述生成（模板）
# ──────────────────────────────────────────────


def _generate_overall_summary(clusters: list[dict], total: int) -> str:
    """根据聚类结果生成简单的统计综述。"""
    if not clusters:
        return "暂无分析结果"

    lines = [f"共分析 {total} 条评论，识别出 {len(clusters)} 个话题。"]
    sorted_clusters = sorted(clusters, key=lambda c: -len(c["comment_indices"]))
    for i, c in enumerate(sorted_clusters[:3]):
        size = len(c["comment_indices"])
        pct = round(size / total * 100, 1) if total > 0 else 0
        kw = "、".join(c["keywords"][:3]) if c["keywords"] else "—"
        lines.append(f"话题「{c['name']}」共 {size} 条 ({pct}%)，关键词：{kw}。")

    if len(sorted_clusters) > 3:
        other_size = sum(len(c["comment_indices"]) for c in sorted_clusters[3:])
        other_pct = round(other_size / total * 100, 1) if total > 0 else 0
        lines.append(f"其余 {len(sorted_clusters) - 3} 个话题共 {other_size} 条 ({other_pct}%)。")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────


def analyze_comments(comments: list[dict]) -> dict:
    """嵌入 + 聚类分析评论。

    Args:
        comments: 评论列表，每项至少包含 "text" 字段。

    Returns:
        与 llm_service.analyze_comments_with_llm() 格式一致的 dict:
        {"topics": [...], "aspects": [], "overall_summary": str}
    """
    if not comments:
        logger.warning("评论列表为空，跳过聚类分析")
        return {"topics": [], "aspects": [], "overall_summary": ""}

    texts = [c.get("text", "").strip() for c in comments]
    texts = [t for t in texts if t]

    if not texts:
        logger.warning("过滤后无有效评论文本")
        return {"topics": [], "aspects": [], "overall_summary": ""}

    logger.info("开始聚类分析: %d 条评论", len(texts))

    vectors = embed_comments(texts)
    if len(vectors) == 0:
        return {"topics": [], "aspects": [], "overall_summary": ""}

    labels = cluster_embeddings(vectors)

    # 按簇分组
    cluster_map: dict[int, list[int]] = {}
    for i, label in enumerate(labels):
        cluster_map.setdefault(label, []).append(i)

    # 排除噪音
    if -1 in cluster_map:
        noise_indices = cluster_map.pop(-1)
        if noise_indices:
            logger.info("排除 %d 条噪音评论", len(noise_indices))

    topics = []
    for label, indices in cluster_map.items():
        cluster_texts = [texts[i] for i in indices]
        keywords = _extract_keywords(cluster_texts)
        topic_name = " - ".join(keywords[:2]) if keywords else f"话题 {label + 1}"
        sentiment = _estimate_sentiment(cluster_texts)

        topics.append({
            "name": topic_name,
            "keywords": keywords,
            "comment_indices": indices,
            "summary": f"共 {len(indices)} 条评论，关键词：{'、'.join(keywords)}" if keywords else f"共 {len(indices)} 条评论",
            "sentiment": sentiment,
        })

    topics.sort(key=lambda t: -len(t["comment_indices"]))
    overall_summary = _generate_overall_summary(topics, len(texts))

    logger.info("聚类分析完成: %d 个话题", len(topics))
    return {
        "topics": topics,
        "aspects": [],
        "overall_summary": overall_summary,
    }
