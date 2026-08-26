# 配置管理模块：集中读取环境变量
# 为什么独立成模块？
#   1. 全项目只有这里读环境变量，避免 API Key 散落各处
#   2. 切换模型/厂商只需改 .env，不改代码
#   3. Pydantic Settings 自带类型校验与自动补全

import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# 加载 backend/.env 文件（不存在则跳过，不影响 CI/测试）
load_dotenv()


class Settings(BaseSettings):
    """应用配置，全部来自环境变量（默认值见 .env.example）"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 阿里云百炼 API Key（默认空，由 __init__ 按优先级填充）
    dashscope_api_key: str = ""

    # 主对话模型名称
    llm_model: str = "qwen-plus"

    # 记忆提取模型（结构化输出任务，用便宜的快速模型）
    extractor_model: str = "qwen-flash"

    # 语音识别模型（qwen3-asr-flash 支持 OpenAI 兼容接口 + base64 上传）
    asr_model: str = "qwen3-asr-flash"

    # 语音合成模型（qwen3-tts-flash 走 DashScope HTTP API）
    tts_model: str = "qwen3-tts-flash"

    # 默认音色（Cherry 女声 / Serena 女声 / Ethan 男声）
    tts_voice: str = "Cherry"

    # ===== 向量检索 RAG（Phase R） =====
    # embedding_enabled: 总开关。False 时嵌入调用统一降级（走原 LIKE/importance 检索）
    embedding_enabled: bool = False
    # 嵌入模型（百炼 text-embedding-v3，OpenAI 兼容接口，默认输出 1024 维）
    embedding_model: str = "text-embedding-v3"
    # 嵌入维度（v3 默认 1024；若兼容端点不识别该参数会自动省略，不影响）
    embedding_dimensions: int = 1024

    # 百炼 OpenAI 兼容接口地址（官方推荐，无需修改）
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # LLM 采样温度（0-2，越低越稳定，工具调用场景建议偏低）
    llm_temperature: float = 0.7

    # 后端服务端口
    server_port: int = 8000

    def __init__(self, **kwargs):
        # 先让 BaseSettings 正常加载（会读 .env 与环境变量）
        super().__init__(**kwargs)
        # API Key 读取优先级：
        #   1. 环境变量 AI_CHAT_API_KEY（用户主用的配置方式）
        #   2. 环境变量 / .env 中的 DASHSCOPE_API_KEY
        #   3. 空
        self.dashscope_api_key = (
            os.getenv("AI_CHAT_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or self.dashscope_api_key
        )
        # 提取模型同样支持环境变量覆盖
        self.extractor_model = os.getenv("EXTRACTOR_MODEL", self.extractor_model)


# 全局单例：所有模块通过 from app.config import settings 使用
settings = Settings()
