"""文本向量化演示脚本

从 b站一级评论.json 中取若干样本评论，用 Qwen3-Embedding-0.6B
对其进行向量化，展示每条评论对应的 1024 维向量结果。

用法:
    python demo_vectorize.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent

MODEL_PATH = (
    PROJECT_ROOT
    / "models" / "embedding"
    / "models--Qwen--Qwen3-Embedding-0.6B"
    / "snapshots" / "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
)

COMMENT_FILE = PROJECT_ROOT / "test" / "b站一级评论.json"


def load_comments(path: Path, limit: int = 10) -> list[str]:
    """从 JSON 文件加载评论文本。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    texts = []
    for item in data[:limit]:
        content = item.get("content", {})
        if isinstance(content, dict):
            msg = content.get("message", "")
        else:
            msg = str(content)
        if msg.strip():
            texts.append(msg.strip())
    return texts


def main():
    texts = load_comments(COMMENT_FILE, limit=10)
    if not texts:
        print("[错误] 没有有效评论")
        sys.exit(1)

    print("=" * 70)
    print(f"📋 待向量化的评论文本（共 {len(texts)} 条）")
    print("=" * 70)
    for i, t in enumerate(texts):
        preview = t[:60] + "..." if len(t) > 60 else t
        print(f"  [{i}] {preview}")

    # ── 加载模型 ──
    print(f"\n⏳ 正在加载 Qwen3-Embedding-0.6B 模型...")
    print(f"   模型路径: {MODEL_PATH}")
    t0 = time.time()

    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), trust_remote_code=True)
    model = AutoModel.from_pretrained(
        str(MODEL_PATH),
        trust_remote_code=True,
        torch_dtype=torch.float32,
    )
    model.eval()
    print(f"   ✅ 模型加载完成，耗时 {time.time() - t0:.1f}s")

    # ── 向量化 ──
    print(f"\n🔢 正在向量化...")
    t1 = time.time()

    inputs = tokenizer(
        texts, padding=True, truncation=True, max_length=128, return_tensors="pt"
    )
    with torch.no_grad():
        outputs = model(**inputs)

    # Mean Pooling
    attention_mask = inputs["attention_mask"]
    token_embeddings = outputs.last_hidden_state
    mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    embeddings = (token_embeddings * mask_expanded).sum(1) / mask_expanded.sum(1)

    # L2 归一化
    embeddings = embeddings / embeddings.norm(dim=1, keepdim=True)
    vectors = embeddings.numpy()

    print(f"   ✅ 向量化完成，耗时 {time.time() - t1:.2f}s")
    print(f"   输出形状: {vectors.shape}  (N={vectors.shape[0]}, dim={vectors.shape[1]})")
    print(f"   内存占用: {vectors.nbytes / 1024:.1f} KB")

    # ── 验证 ──
    norms = np.linalg.norm(vectors, axis=1)
    has_nan = np.isnan(vectors).sum()
    has_inf = np.isinf(vectors).sum()
    print(f"\n📊 质量检查:")
    print(f"   L2 范数范围: [{norms.min():.6f}, {norms.max():.6f}]  (应 ≈ 1.0)")
    print(f"   NaN 数量:    {has_nan}")
    print(f"   Inf 数量:    {has_inf}")
    print(f"   值范围:       [{vectors.min():.4f}, {vectors.max():.4f}]")

    # ── 展示每条评论的向量结果 ──
    print(f"\n" + "=" * 70)
    print(f"📐 文本向量化结果展示")
    print(f"   每行 = 1条评论的 1024 维向量（前16维 + 后8维 + 统计摘要）")
    print(f"=" * 70)

    for i, (text, vec) in enumerate(zip(texts, vectors)):
        preview = text[:50] + "..." if len(text) > 50 else text
        print(f"\n{'─' * 70}")
        print(f"  评论 [{i}]: {preview}")
        print(f"  文本长度: {len(text)} 字")
        print(f"  向量维度: {len(vec)}")
        print(f"  前 16 维: [{', '.join(f'{v:+.4f}' for v in vec[:16])}]")
        print(f"  后 8 维:  [{', '.join(f'{v:+.4f}' for v in vec[-8:])}]")
        print(f"  统计:     mean={vec.mean():+.6f}  std={vec.std():.4f}  "
              f"min={vec.min():+.4f}  max={vec.max():+.4f}")

    # ── 计算相似度矩阵 ──
    print(f"\n" + "=" * 70)
    print(f"🔗 评论间余弦相似度矩阵（向量已 L2 归一化，dot 即 cosine）")
    print(f"=" * 70)
    sim = np.dot(vectors, vectors.T)
    print(f"\n   ", end="")
    for j in range(len(texts)):
        print(f"  [{j}]  ", end="")
    print()
    for i in range(len(texts)):
        print(f"  [{i}]", end="")
        for j in range(len(texts)):
            print(f" {sim[i][j]:+.3f}", end="")
        print()

    # ── 找最相似的评论对 ──
    print(f"\n💡 最相似的评论对（对角线除外）:")
    max_sim = -1
    max_pair = (0, 0)
    min_sim = 2
    min_pair = (0, 0)
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if sim[i][j] > max_sim:
                max_sim = sim[i][j]
                max_pair = (i, j)
            if sim[i][j] < min_sim:
                min_sim = sim[i][j]
                min_pair = (i, j)

    i, j = max_pair
    print(f"   最相似: [{i}] 和 [{j}], cos={max_sim:.4f}")
    print(f"     [{i}]: {texts[i][:60]}...")
    print(f"     [{j}]: {texts[j][:60]}...")
    i, j = min_pair
    print(f"   最不相似: [{i}] 和 [{j}], cos={min_sim:.4f}")
    print(f"     [{i}]: {texts[i][:60]}...")
    print(f"     [{j}]: {texts[j][:60]}...")

    # ── 保存结果 ──
    output_dir = PROJECT_ROOT / "data" / "vector"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) 向量矩阵 → .npy
    npy_path = output_dir / "demo_comment_vectors.npy"
    np.save(str(npy_path), vectors)
    print(f"\n💾 向量矩阵已保存: {npy_path}  ({vectors.shape})")

    # 2) 文本 + 向量摘要 → .json（人类可读）
    json_path = output_dir / "demo_comment_vectors.json"
    records = []
    for i, (text, vec) in enumerate(zip(texts, vectors)):
        records.append({
            "id": i,
            "text": text,
            "dim": int(vec.shape[0]),
            "first_16": [round(float(v), 4) for v in vec[:16]],
            "last_8": [round(float(v), 4) for v in vec[-8:]],
            "stats": {
                "mean": round(float(vec.mean()), 6),
                "std": round(float(vec.std()), 4),
                "min": round(float(vec.min()), 4),
                "max": round(float(vec.max()), 4),
            }
        })
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"💾 向量摘要已保存: {json_path}")

    # 3) 相似度矩阵 → .csv
    csv_path = output_dir / "demo_similarity_matrix.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        header = "id,text_preview," + ",".join(f"[{j}]" for j in range(len(texts)))
        f.write(header + "\n")
        for i in range(len(texts)):
            preview = texts[i][:30].replace(",", "，")
            row = f"[{i}],\"{preview}\"," + ",".join(f"{sim[i][j]:.4f}" for j in range(len(texts)))
            f.write(row + "\n")
    print(f"💾 相似度矩阵已保存: {csv_path}")

    print(f"\n✅ 演示完成。")


if __name__ == "__main__":
    main()
