"""RRF（Reciprocal Rank Fusion）融合算法。"""

from app.aitc.retrieval.common.config import RRF_K


def rrf_fusion(
    vector_results: list[tuple[int, float, int]],    # [(doc_id, score, rank)]
    bm25_results: list[tuple[int, float, int]],       # [(doc_id, score, rank)]
    k: int = RRF_K,
    top_k: int = 20,
) -> list[dict]:
    """RRF 融合两路召回结果。

    Args:
        vector_results: Milvus 返回的 [(case_id, similarity_score, rank)]
        bm25_results: ES BM25 返回的 [(case_id, bm25_score, rank)]
        k: RRF 平滑参数 (默认 60)
        top_k: 最终返回数量

    Returns:
        [{case_id, rrf_score, vector_score, bm25_score, rank_vector, rank_bm25}, ...]
    """
    # 构建一个聚合 dict: case_id → 各路信息
    merged: dict[int, dict] = {}

    for case_id, score, rank in vector_results:
        merged[case_id] = {
            "case_id": case_id,
            "vector_score": round(score, 4),
            "bm25_score": None,
            "rank_vector": rank,
            "rank_bm25": None,
        }

    for case_id, score, rank in bm25_results:
        if case_id in merged:
            merged[case_id]["bm25_score"] = round(score, 4)
            merged[case_id]["rank_bm25"] = rank
        else:
            merged[case_id] = {
                "case_id": case_id,
                "vector_score": None,
                "bm25_score": round(score, 4),
                "rank_vector": None,
                "rank_bm25": rank,
            }

    # RRF 计算
    for item in merged.values():
        rrf = 0.0
        if item["rank_vector"] is not None:
            rrf += 1.0 / (k + item["rank_vector"])
        if item["rank_bm25"] is not None:
            rrf += 1.0 / (k + item["rank_bm25"])
        item["rrf_score"] = round(rrf, 6)

    # 按 rrf_score 降序
    sorted_items = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)

    return sorted_items[:top_k]


def normalize_ranking(results: list[dict]) -> list[dict]:
    """对融合结果重排 rank 序号（从 1 开始）。"""
    for i, item in enumerate(results):
        item["rank"] = i + 1
    return results
