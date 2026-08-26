# ASR 语音识别服务：把音频转成文字
#
# 为什么选 qwen3-asr-flash（而不是 spec 里的 filetrans 模式）？
#   - filetrans 是"异步任务 + 要求公网文件 URL"：本地浏览器录音没有 URL，
#     还要搭文件托管，不适合个人项目
#   - qwen3-asr-flash 走 OpenAI 兼容接口：直接传 base64 data URL，
#     同步返回文本，零轮询零托管，与主 LLM 同一套调用方式
#
# 全项目不装 dashscope SDK：聊天走 langchain、语音走 openai 兼容接口，
# 统一用 base_url + api_key，依赖干净。

import base64
import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# 单次识别最大音频大小（qwen3-asr-flash 限制 10MB，留余量）
MAX_AUDIO_BYTES = 8 * 1024 * 1024


def _asr_client() -> OpenAI:
    """创建 OpenAI 兼容客户端（百炼接口地址）"""
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.dashscope_api_key,
    )


def transcribe_audio(audio_bytes: bytes, audio_format: str = "wav") -> str:
    """同步语音转文字。

    audio_bytes: 音频原始字节（前端已转码为 16kHz 单声道 WAV）
    audio_format: 音频格式（wav / mp3 等），默认 wav

    返回：识别出的文本（空音频可能返回空串或占位内容）
    """
    if not audio_bytes:
        raise ValueError("音频为空")

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(f"音频过大（>{MAX_AUDIO_BYTES // 1024 // 1024}MB），请缩短录音")

    # 构造 data URL：data:audio/wav;base64,<内容>
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    data_url = f"data:audio/{audio_format};base64,{b64}"

    client = _asr_client()
    response = client.chat.completions.create(
        model=settings.asr_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": data_url,
                            "format": audio_format,
                        },
                    }
                ],
            }
        ],
    )

    text = response.choices[0].message.content or ""
    logger.info("asr done, text_len=%d", len(text))
    return text
