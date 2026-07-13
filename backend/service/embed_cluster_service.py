"""Embedding + 聚类分析 Service

用 Qwen3-Embedding 对评论进行向量化，UMAP 降维后 HDBSCAN 聚类，
再用 jieba 提取关键词命名话题，词表估算情感分布。
输出结构与 LLM 分析的 analyze_comments_with_llm() 完全一致。

依赖: torch, transformers, umap-learn, hdbscan, jieba, numpy, scikit-learn
"""

import json
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
    / "models" / "embedding"
    / "models--Qwen--Qwen3-Embedding-0.6B"
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


# ── 正负面情感词表 ──────────────────────────────────────────
_POSITIVE_WORDS = {
    "好", "棒", "赞", "喜欢", "爱", "厉害", "优秀", "精彩", "不错",
    "感人", "好看", "好听", "好玩", "有趣", "搞笑", "经典", "支持",
    "良心", "满意", "享受", "佩服", "推荐", "期待", "感动", "完美",
    "舒服", "漂亮", "可爱", "美", "帅", "强", "牛", "顶", "666",
    "可以", "中", "行", "绝了", "yyds", "神仙", "宝藏", "无敌",
    "泪目", "绷不住", "净化", "治愈", "催泪", "炸裂", "燃", "封神",
    "神曲", "神作", "牛逼", "NB", "nb", "好评", "安利", "真香",
    "吹爆", "爱了", "惊艳", "值了", "过瘾", "上头", "入坑", "回坑",
    "大爱", "超爱", "赛高", "神中神", "豪庭", "豪刊", "好耶",
    "回忆", "青春", "怀念", "怀旧", "百看不厌", "百听不腻",
    "哭了", "看哭", "听哭", "感动哭了", "催泪弹",
}

_NEGATIVE_WORDS = {
    "差", "烂", "垃圾", "恶心", "讨厌", "烦", "无聊", "失望", "糟",
    "烂片", "难看", "难听", "不好", "不行", "没用", "无趣", "低俗",
    "糟糕", "失败", "后悔", "浪费", "尴尬", "虚假", "骗子", "坑",
    "太差", "太烂", "受不了", "无语", "呵呵", "呸", "有病", "有病吧",
    "脑残", "弱智", "白痴", "蠢", "假", "恶心人", "烦人",
    "退坑", "弃坑", "劝退", "拉胯", "翻车", "注水", "水货",
    "割韭菜", "骗氪", "屑", "恶心到了", "太水", "太假",
    "敷衍", "摆烂", "下头", "抠门", "难绷", "尴了",
    "太拉了", "太坑", "不值", "血亏", "上当",
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
# 属性情感：从聚类结果构建
# ──────────────────────────────────────────────


def _build_aspects_from_clusters(clusters: list[dict]) -> list[dict]:
    """将聚类话题映射为 LLM 兼容的 aspects 结构。

    每个话题簇视为一个评价维度，名称用聚类关键词，
    情感分布直接复用簇内的词表估算结果。
    """
    aspects = []
    for c in clusters:
        sent = c.get("sentiment", {})
        # 跳过过小的簇（< 3 条），噪音
        if len(c.get("comment_indices", [])) < 3:
            continue
        aspects.append({
            "name": c.get("name", "未命名"),
            "positive": sent.get("positive", 0),
            "negative": sent.get("negative", 0),
            "neutral": sent.get("neutral", 0),
        })
    # 按评论数排序（从高到低，和 clusters 排序一致）
    aspects.sort(key=lambda a: -(a["positive"] + a["negative"] + a["neutral"]))
    return aspects


# ──────────────────────────────────────────────
# 综述生成（自然段落）
# ──────────────────────────────────────────────


def _generate_overall_summary(clusters: list[dict], total: int) -> str:
    """根据聚类结果生成自然的中文综述段落。"""
    if not clusters or total == 0:
        return "暂无足够数据生成分析综述。"

    # ── 整体情感 ──
    all_pos = sum(c.get("sentiment", {}).get("positive", 0) for c in clusters)
    all_neg = sum(c.get("sentiment", {}).get("negative", 0) for c in clusters)
    all_neu = sum(c.get("sentiment", {}).get("neutral", 0) for c in clusters)
    grand = all_pos + all_neg + all_neu or 1

    pos_pct = round(all_pos / grand * 100, 1)
    neg_pct = round(all_neg / grand * 100, 1)

    if pos_pct >= 60:
        tone = "整体舆论以正面为主"
    elif neg_pct >= 40:
        tone = "整体舆论偏负面"
    elif neg_pct >= 25:
        tone = "评论褒贬不一，存在一定争议"
    else:
        tone = "整体舆论温和，多数评论偏中性或正面"

    # ── 话题列表 ──
    sorted_clusters = sorted(clusters, key=lambda c: -len(c.get("comment_indices", [])))
    top_clusters = sorted_clusters[:5]

    # 找最正面 / 最负面的簇
    def _sent_score(c):
        s = c.get("sentiment", {})
        ps = s.get("positive", 0)
        ns = s.get("negative", 0)
        total = ps + ns + s.get("neutral", 0) or 1
        return round((ps - ns) / total * 100)

    best = max(top_clusters, key=_sent_score) if top_clusters else None
    worst = min(top_clusters, key=_sent_score) if top_clusters else None

    # ── 组装段落 ──
    lines = [
        f"{tone}。共分析 {total} 条评论，识别出 {len(clusters)} 个主要话题。",
    ]

    # 逐话题简述
    for i, c in enumerate(top_clusters):
        size = len(c.get("comment_indices", []))
        pct = round(size / total * 100, 1) if total > 0 else 0
        s = c.get("sentiment", {})
        sp = s.get("positive", 0)
        sn = s.get("negative", 0)
        st = s.get("neutral", 0)
        s_total = sp + sn + st or 1

        if sp >= sn and sp >= st:
            s_label = "以正面评价为主"
        elif sn >= sp and sn >= st:
            s_label = "偏负面"
        else:
            s_label = "评价较为中性"

        lines.append(f"「{c['name']}」共 {size} 条（{pct}%），{s_label}。")

    # 最正面 / 最负面
    if best and worst and best != worst:
        lines.append(
            f"其中「{best['name']}」情感最为积极，"
            f"而「{worst['name']}」存在较多批评声音。"
        )

    # 结尾
    if pos_pct >= 50:
        lines.append("总体来看，评论社区的反馈偏向正面。")
    elif neg_pct >= 40:
        lines.append("评论中存在较多负面声音，值得关注。")
    else:
        lines.append("整体而言，评论社区讨论活跃，意见多元。")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# LLM 精修：用 DeepSeek 给聚类话题命名 + 写摘要 + 综述
# ──────────────────────────────────────────────


def _llm_polish_clusters(
    topics: list[dict], texts: list[str], total: int
) -> tuple[list[dict], str, list[dict]]:
    """调用 DeepSeek 对聚类结果进行命名和摘要。

    Args:
        topics: 含 comment_indices / keywords / sentiment 的原始话题列表
        texts: 对应所有评论的原始文本列表
        total: 总评论数

    Returns:
        (topics, overall_summary, aspects) — topics 的 name 和 summary 已被 LLM 重写
    """
    from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
    from openai import OpenAI

    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置")

    # 每个簇取 8 条样本
    cluster_descs = []
    for i, t in enumerate(topics):
        indices = t.get("comment_indices", [])[:8]
        samples = []
        for idx in indices:
            txt = texts[idx] if idx < len(texts) else ""
            if len(txt) > 120:
                txt = txt[:120] + "..."
            samples.append(txt)
        cluster_descs.append({
            "id": i,
            "size": len(t["comment_indices"]),
            "pct": round(len(t["comment_indices"]) / total * 100, 1) if total > 0 else 0,
            "samples": samples,
        })

    # 构造 prompt
    prompt = f"""下面是 {len(cluster_descs)} 个聚类话题，每个话题包含若干条样本评论。

请为每个话题起一个简短中文名称（≤8字）并写一句话摘要（≤80字）。
同时写一段 100-200 字的整体综述。

严格按以下 JSON 格式返回：
{{"names":["话题1名","话题2名",...],"summaries":["摘要1","摘要2",...],"overall_summary":"综述"}}

话题列表：
"""
    for cd in cluster_descs:
        prompt += f"\n话题{cd['id']}（{cd['size']}条, {cd['pct']}%）：\n"
        for s in cd["samples"]:
            prompt += f"  - {s}\n"

    logger.info("LLM 精修: 发送 %d 个话题的样本评论", len(cluster_descs))

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    resp = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=2048,
        response_format={"type": "json_object"},
        timeout=60,
    )

    raw = resp.choices[0].message.content
    result = json.loads(raw)

    # 用 LLM 返回的 name/summary 替换原有
    llm_names = result.get("names", [])
    llm_summaries = result.get("summaries", [])
    for i, t in enumerate(topics):
        if i < len(llm_names):
            t["name"] = llm_names[i]
            t["keywords"] = []  # 保留空列表，避免前端显示旧的关键词
        if i < len(llm_summaries):
            t["summary"] = llm_summaries[i]

    overall_summary = result.get("overall_summary", "")
    aspects = _build_aspects_from_clusters(topics)

    logger.info("LLM 精修完成: %d 个话题命名, 综述 %d 字",
                len(topics), len(overall_summary))
    return topics, overall_summary, aspects


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

    # ── 尝试用 LLM 精修话题名称和摘要 ──
    try:
        topics, overall_summary, aspects = _llm_polish_clusters(topics, texts, len(texts))
    except Exception as e:
        logger.warning("LLM 精修失败，使用规则生成: %s", e)
        overall_summary = _generate_overall_summary(topics, len(texts))
        aspects = _build_aspects_from_clusters(topics)

    logger.info("聚类分析完成: %d 个话题, %d 个属性维度, 综述 %d 字",
                len(topics), len(aspects), len(overall_summary))
    return {
        "topics": topics,
        "aspects": aspects,
        "overall_summary": overall_summary,
    }
