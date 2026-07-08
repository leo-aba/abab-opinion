"""评论向量聚类脚本

流程: 加载向量 → UMAP 降维 → HDBSCAN 聚类 → 结果分析 → 可视化

用法:
    .venv/Scripts/python test/cluster_comments.py
"""

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTOR_DIR = PROJECT_ROOT / "data" / "vector"
OUTPUT_DIR = PROJECT_ROOT / "data" / "cluster"


def main():
    # ── 1) 加载数据 ──
    vectors_path = VECTOR_DIR / "comment_vectors.npy"
    map_path = VECTOR_DIR / "comment_source_map.json"

    if not vectors_path.exists():
        print(f"[错误] 找不到向量文件: {vectors_path}")
        print("请先运行 test/embed_comments.py")
        sys.exit(1)

    print("正在加载向量...")
    vectors = np.load(str(vectors_path))
    with open(map_path, "r", encoding="utf-8") as f:
        sources = json.load(f)

    texts = [s["text_preview"] for s in sources]
    n = len(vectors)
    print(f"共 {n} 条评论，维度 {vectors.shape[1]}")

    # ── 2) UMAP 降维 ──
    print("\n正在 UMAP 降维 (1024 → 10)...")
    import umap

    reducer = umap.UMAP(n_components=10, random_state=42, verbose=False)
    embedding_10d = reducer.fit_transform(vectors)
    print(f"降维完成，形状: {embedding_10d.shape}")

    # ── 3) HDBSCAN 聚类 ──
    print("\n正在 HDBSCAN 聚类...")
    import hdbscan

    clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=3, metric="euclidean")
    labels = clusterer.fit_predict(embedding_10d)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    print(f"聚类完成: {n_clusters} 个簇, {n_noise} 条噪音 ({n_noise/n*100:.1f}%)")

    # ── 4) 统计每个簇 ──
    print("\n=== 各簇统计 ===")
    cluster_sizes = {}
    cluster_texts = {}
    for i, label in enumerate(labels):
        cluster_sizes[label] = cluster_sizes.get(label, 0) + 1
        if label not in cluster_texts:
            cluster_texts[label] = []
        cluster_texts[label].append(texts[i])

    for label in sorted(cluster_sizes.keys(), key=lambda x: cluster_sizes[x], reverse=True):
        size = cluster_sizes[label]
        pct = size / n * 100
        label_str = "噪音" if label == -1 else f"簇 {label}"
        print(f"  {label_str}: {size} 条 ({pct:.1f}%)")

    # ── 5) 保存结果 ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 每条评论的聚类结果
    results = []
    for i, label in enumerate(labels):
        results.append({
            "index": i,
            "text": texts[i],
            "cluster": int(label),
            "file": sources[i]["file"],
        })

    result_path = OUTPUT_DIR / "cluster_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n聚类结果已保存: {result_path}")

    # 各簇的关键词摘要（高频词）
    print("\n=== 各簇文本预览 ===")
    for label in sorted(cluster_sizes.keys(), key=lambda x: cluster_sizes[x], reverse=True):
        if label == -1:
            continue
        top_texts = cluster_texts[label][:5]
        print(f"\n--- 簇 {label} ({cluster_sizes[label]} 条) ---")
        for t in top_texts:
            print(f"  {t}")

    # ── 6) 可视化 ──
    print("\n正在生成可视化...")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 2D UMAP 用于绘图
        reducer_2d = umap.UMAP(n_components=2, random_state=42, verbose=False)
        embedding_2d = reducer_2d.fit_transform(vectors)

        plt.figure(figsize=(12, 8))
        unique_labels = sorted(set(labels), key=lambda x: (x == -1, x))
        colors = plt.cm.tab20(np.linspace(0, 1, len(unique_labels)))

        for label, color in zip(unique_labels, colors):
            mask = labels == label
            label_name = "噪音" if label == -1 else f"簇 {label}"
            plt.scatter(
                embedding_2d[mask, 0], embedding_2d[mask, 1],
                c=[color], label=f"{label_name} ({mask.sum()})",
                s=8, alpha=0.7,
            )

        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", markerscale=2)
        plt.title("评论聚类分布 (UMAP 2D)")
        plt.tight_layout()

        viz_path = OUTPUT_DIR / "cluster_visualization.png"
        plt.savefig(str(viz_path), dpi=150)
        plt.close()
        print(f"可视化已保存: {viz_path}")
    except ImportError:
        print("(跳过可视化: 需要 matplotlib)")

    print("\n✓ 聚类完成")
    print(f"  聚类结果: {result_path}")
    print(f"  可视化:   {OUTPUT_DIR / 'cluster_visualization.png'}")


if __name__ == "__main__":
    main()
