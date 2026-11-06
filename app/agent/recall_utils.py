"""
召回节点共用的批量向量化工具

原先每个召回节点都是「一个关键词一次 Embedding」，扩词后动辄十几个关键词，
每次都要等一个 HTTP 往返，纯属排队。这里改成一次请求带走一批文本，
并保证返回的向量顺序和入参顺序严格一致。
"""

from app.core.log import logger

# 单次 Embedding 请求携带的关键词数量上限
# 关键词本身都很短，16 个一批既能合并往返，也不会撑爆 TEI 的单请求批量限制
EMBED_BATCH_SIZE = 16


async def embed_in_batches(
    embedding_client, texts: list[str], batch_size: int = EMBED_BATCH_SIZE
) -> list[list[float]]:
    """把文本分批向量化，返回与入参顺序一一对应的向量列表"""

    if not texts:
        return []

    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(await embedding_client.aembed_documents(batch))
        logger.debug(f"Embedding 批次完成：{len(batch)} 条")

    # 向量数量和文本数量对不上时，后续 zip 会静默丢数据，这里直接报错暴露问题
    if len(vectors) != len(texts):
        raise ValueError(
            f"Embedding 返回数量不一致：期望 {len(texts)}，实际 {len(vectors)}"
        )

    return vectors
