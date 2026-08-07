"""降维 + 聚类演示脚本

基于 demo_comment_vectors.npy 中的 10×1024 向量矩阵，先 UMAP 降维到
2D/5D，再 HDBSCAN 聚类，保存并展示结果。

用法:
    python demo_reduce_cluster.py
"""

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
VECTOR_FILE = PROJECT_ROOT / "data" / "vector" / "demo_comment_vectors.npy"
OUTPUT_DIR = PROJECT_ROOT / "data" / "vector"

# 停用词（与项目 embed_cluster_service.py 保持一致）
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "会", "到", "说", "要", "去",
    "你", "他", "她", "它", "们", "这", "那", "什么", "怎么",
    "吗", "啊", "呢", "吧", "嗯", "哦", "哈", "呀", "嘛",
    "没", "被", "把", "让", "给", "为", "从", "以", "与", "对",
    "看", "做", "能", "可以", "这个", "那个", "这些", "那些",
    "还是", "因为", "所以", "但是", "如果", "虽然", "不过",
}


def load_vectors() -> tuple[np.ndarray, list[str]]:
    """加载向量和对应评论文本。"""
    if not VECTOR_FILE.exists():
        print(f"[错误] 向量文件不存在: {VECTOR_FILE}")
        sys.exit(1)

    vectors = np.load(str(VECTOR_FILE))
    print(f"📥 加载向量: {vectors.shape}")

    # 从 JSON 摘要中提取评论文本
    json_path = OUTPUT_DIR / "demo_comment_vectors.json"
    texts = []
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        texts = [r["text"] for r in records]
        print(f"📥 加载文本: {len(texts)} 条")
    return vectors, texts


def umap_reduce(vectors: np.ndarray, n_components: int = 2) -> np.ndarray:
    """UMAP 降维。"""
    import umap

    n = len(vectors)
    print(f"\n🔽 UMAP 降维: {vectors.shape[1]}D → {n_components}D ...")
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=min(5, n - 1),
        min_dist=0.1,
        random_state=42,
        verbose=True,
    )
    reduced = reducer.fit_transform(vectors)
    print(f"   降维完成: {reduced.shape}")
    return reduced


def hdbscan_cluster(vectors_2d: np.ndarray) -> np.ndarray:
    """HDBSCAN 聚类。"""
    import hdbscan

    n = len(vectors_2d)
    min_cluster = max(2, min(3, n // 3))
    print(f"\n🧩 HDBSCAN 聚类 (min_cluster_size={min_cluster})...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster,
        min_samples=2,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(vectors_2d)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    print(f"   聚类完成: {n_clusters} 个簇, {n_noise} 条噪音")
    return labels


def extract_keywords(texts: list[str]) -> list[str]:
    """提取高频关键词。"""
    import jieba
    import re

    word_counts: dict[str, int] = {}
    for t in texts:
        for w in jieba.lcut(t):
            w = w.strip().lower()
            if len(w) < 2 or w in _STOP_WORDS:
                continue
            if re.match(r'^[\d\s\.\,\!\?\!\.\，\。\！\？\《\》\-\+\=\(\)\[\]\/\\\|@#\$%\^&\*\_\"\'\;\:]+$', w):
                continue
            word_counts[w] = word_counts.get(w, 0) + 1
    sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_words[:5]]


def main():
    vectors, texts = load_vectors()

    # ═══════════════════════════════════════════
    # 第一阶段：UMAP 降维 (1024D → 2D)
    # ═══════════════════════════════════════════
    coords_2d = umap_reduce(vectors, n_components=2)

    print("\n" + "=" * 70)
    print("📍 2D 降维坐标（可用于可视化散点图）")
    print("=" * 70)
    for i, (t, c) in enumerate(zip(texts, coords_2d)):
        preview = t[:45] + "..." if len(t) > 45 else t
        print(f"  [{i}] ({c[0]:+.4f}, {c[1]:+.4f})  {preview}")

    # 保存 2D 坐标
    np.save(str(OUTPUT_DIR / "demo_coords_2d.npy"), coords_2d)
    print(f"\n💾 2D 坐标已保存: data/vector/demo_coords_2d.npy")

    # ═══════════════════════════════════════════
    # 第二阶段：UMAP 降维 (1024D → 5D) + HDBSCAN 聚类
    # ═══════════════════════════════════════════
    coords_5d = umap_reduce(vectors, n_components=5)
    labels = hdbscan_cluster(coords_5d)

    # 保存聚类标签
    np.save(str(OUTPUT_DIR / "demo_cluster_labels.npy"), labels)

    # ═══════════════════════════════════════════
    # 聚类结果分析
    # ═══════════════════════════════════════════
    cluster_map: dict[int, list[int]] = {}
    for i, lbl in enumerate(labels):
        cluster_map.setdefault(int(lbl), []).append(i)

    print("\n" + "=" * 70)
    print("🏷️  聚类结果详情")
    print("=" * 70)

    for label in sorted(cluster_map.keys()):
        indices = cluster_map[label]
        cluster_texts = [texts[i] for i in indices]

        if label == -1:
            print(f"\n  🚫 噪音 ({len(indices)} 条):")
        else:
            keywords = extract_keywords(cluster_texts)
            print(f"\n  📌 簇 {label} ({len(indices)} 条) | 关键词: {', '.join(keywords)}:")

        for idx in indices:
            preview = texts[idx][:60] + "..." if len(texts[idx]) > 60 else texts[idx]
            print(f"     [{idx}] {preview}")

    # 保存聚类结果 JSON
    result = {
        "total_comments": len(texts),
        "n_clusters": len([k for k in cluster_map if k != -1]),
        "n_noise": len(cluster_map.get(-1, [])),
        "clusters": [
            {
                "label": int(lbl),
                "size": len(indices),
                "indices": [int(i) for i in indices],
                "texts": [texts[i] for i in indices],
                "keywords": extract_keywords([texts[i] for i in indices]) if lbl != -1 else [],
            }
            for lbl, indices in sorted(cluster_map.items())
        ],
    }
    json_path = OUTPUT_DIR / "demo_cluster_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 聚类结果已保存: {json_path}")
    print(f"💾 聚类标签已保存: data/vector/demo_cluster_labels.npy")
    print(f"💾 5D 降维坐标已保存: data/vector/demo_coords_5d.npy")

    # ═══════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════
    print(f"\n✅ 降维+聚类全部完成。")
    print(f"   输出文件列表:")
    for f in sorted(OUTPUT_DIR.glob("demo_*.npy")):
        print(f"     {f.name}")
    for f in sorted(OUTPUT_DIR.glob("demo_*.json")):
        print(f"     {f.name}")
    for f in sorted(OUTPUT_DIR.glob("demo_*.csv")):
        print(f"     {f.name}")


if __name__ == "__main__":
    main()
