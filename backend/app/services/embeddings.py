# 嵌入服务：统一封装向量生成
#
# fail-open 设计（面试点）：
#   - EMBEDDING_ENABLED=false → 所有嵌入调用抛 EmbeddingDisabled，调用方走原检索
#   - 网络/API 异常 → 异常向上抛，调用方捕获后降级，绝不阻断主流程
#   - 查询向量缓存：同一对话内重复召回不重复调嵌入 API（省延迟省钱）
#
# 为什么用 openai 官方 SDK 而不是 langchain_openai.OpenAIEmbeddings？
#   - langchain-openai 新版把 input 包装成对象格式（{contents: [...]}），
#     百炼兼容端点不识别（实测 400 InvalidParameter）
#   - 官方 SDK 直接发 {model, input} 字符串数组，百炼兼容端点实测正常（1024 维）
#   - 嵌入调用极简（一次 HTTP 往返），不值得引入框架抽象层

import logging
from functools import lru_cache

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingDisabled(Exception):
    """RAG 总开关关闭时抛出，调用方捕获后降级为原检索。"""


@lru_cache(maxsize=1)
def get_embedder() -> OpenAI:
    """创建嵌入客户端（惰性单例）。

    与主 LLM 同用百炼 OpenAI 兼容端点，api_key 同源。
    """
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.dashscope_api_key,
    )


def embed_text(text: str) -> list[float]:
    """单条文本 → 向量。

    Args:
        text: 要嵌入的文本（笔记/记忆内容、或查询语句）

    Returns:
        嵌入向量列表

    Raises:
        EmbeddingDisabled: 功能开关关闭
        Exception: 网络/API 错误（由调用方降级处理）
    """
    if not settings.embedding_enabled:
        raise EmbeddingDisabled("EMBEDDING_ENABLED=false，嵌入已禁用")
    resp = get_embedder().embeddings.create(
        model=settings.embedding_model,
        input=[text],
    )
    return list(resp.data[0].embedding)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本 → 向量列表（同一请求，省往返）。"""
    if not settings.embedding_enabled:
        raise EmbeddingDisabled("EMBEDDING_ENABLED=false，嵌入已禁用")
    resp = get_embedder().embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    # 按请求顺序排列（API 可能乱序返回）
    ordered = sorted(resp.data, key=lambda d: d.index)
    return [list(d.embedding) for d in ordered]


# 查询向量缓存：{(text): vector}，上限 256 条防内存膨胀
_QUERY_CACHE: dict[str, list[float]] = {}
_QUERY_CACHE_MAX = 256


def get_query_embedding(text: str) -> list[float]:
    """查询文本嵌入（带缓存：同一 query 不重复调 API）。

    缓存满时清空重建（简单策略，个人场景足够）。
    """
    cached = _QUERY_CACHE.get(text)
    if cached is not None:
        return cached
    vec = embed_text(text)
    if len(_QUERY_CACHE) >= _QUERY_CACHE_MAX:
        _QUERY_CACHE.clear()
    _QUERY_CACHE[text] = vec
    return vec
