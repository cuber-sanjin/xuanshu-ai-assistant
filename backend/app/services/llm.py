# LLM 统一抽象层 —— 全项目唯一创建大模型实例的地方
# 为什么必须集中？
#   1. 避免各模块到处用 openai / dashscope 原生 SDK（换厂商要改全项目）
#   2. 以后切换 Qwen/DeepSeek/Kimi/GLM/Ollama，只需改 .env 的 base_url + model
#   3. 通过 langchain-openai 的 ChatOpenAI 走百炼官方 OpenAI 兼容接口（阿里云文档推荐方式）

from langchain_openai import ChatOpenAI

from app.config import settings


def get_chat_llm() -> ChatOpenAI:
    """创建主对话 LLM。

    参数说明：
    - base_url: 百炼 OpenAI 兼容接口地址（chat.completions 路径由 SDK 自动拼接）
    - api_key : 从 .env 读取的 DASHSCOPE_API_KEY
    - model   : 模型名称，通过 .env 的 LLM_MODEL 配置，不硬编码
    - temperature: 采样温度，工具调用场景建议偏低（0.5~0.7）保证稳定
    - streaming: 是否流式输出。Phase 3（SSE）依赖此参数为 True，
                 否则 LLM 内部缓冲完整响应，astream_events 拿不到逐 token 效果
    """
    if not settings.dashscope_api_key:
        raise RuntimeError(
            "未检测到 API Key。"
            "请设置环境变量 AI_CHAT_API_KEY（或 DASHSCOPE_API_KEY），"
            "或复制 backend/.env.example 为 backend/.env 并填写。"
        )

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.dashscope_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        streaming=True,
    )


def get_extractor_llm() -> ChatOpenAI:
    """创建记忆提取 LLM（结构化输出专用）。

    与主对话模型分离的原因（面试点）：
    - 任务性质不同：提取是"判断+分类"的简单结构化任务，快模型够用且便宜
    - 成本/延迟：每次对话都会跑一次提取，用 qwen-flash 大幅降低开销
    - 独立性：主模型切换/升级不影响提取质量基线
    temperature 设低（0.1）：结构化判定要稳定，不要发散。
    """
    if not settings.dashscope_api_key:
        raise RuntimeError(
            "未检测到 API Key。"
            "请设置环境变量 AI_CHAT_API_KEY（或 DASHSCOPE_API_KEY）。"
        )

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.dashscope_api_key,
        model=settings.extractor_model,
        temperature=0.1,
    )
