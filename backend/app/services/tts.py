# TTS 语音合成服务：把文本转成语音（MP3）
#
# 与 ASR 不同，qwen3-tts-flash 没有 OpenAI 兼容接口，走 DashScope 原生 HTTP API：
#   1. POST 合成请求（JSON: model/text/voice）→ 返回音频下载 URL
#   2. 再 GET 下载 URL → 得到 MP3 字节
# 两步调用的原因（面试点）：TTS 音频是大文件，DashScope 走对象存储返回 URL，
# 业务侧需多一步下载——真实企业同理：大响应走存储服务而非响应体。
#
# 全项目不装 dashscope SDK：聊天走 langchain、ASR 走 openai 兼容、TTS 走 httpx，
# 依赖干净统一。

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# DashScope 多模态生成接口地址（TTS 专用）
_TTS_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 单次合成最大字符数（qwen3-tts-flash 限制 500）
MAX_TTS_TEXT_LENGTH = 500

# 音频下载超时（音频文件可能较大）
_DOWNLOAD_TIMEOUT = 30.0


def synthesize(text: str, voice: str | None = None) -> tuple[bytes, str]:
    """把文本合成为音频字节。

    text: 要朗读的文本（1~500 字符，超长截断）
    voice: 音色名（Cherry/Serena/Ethan），空则用配置默认

    返回：(音频字节, MIME 类型)
    说明：实测 qwen3-tts-flash 无论请求 mp3 还是 wav，均返回 WAV 格式
    （RIFF 头），因此固定请求 wav 并按 audio/wav 返回，保证前后端一致。

    异常：ValueError（参数错误）、RuntimeError（API/下载失败）
    """
    text = text.strip()
    if not text:
        raise ValueError("文本不能为空")

    # 超长截断（而不是报错）：用户消息/长回复直接截断最友好
    if len(text) > MAX_TTS_TEXT_LENGTH:
        logger.info("tts text truncated: %d -> %d", len(text), MAX_TTS_TEXT_LENGTH)
        text = text[:MAX_TTS_TEXT_LENGTH]

    voice = voice or settings.tts_voice

    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
        # 同步等待结果（非异步任务模式）
        "X-DashScope-Async": "disable",
    }
    payload = {
        "model": settings.tts_model,
        "input": {"text": text, "voice": voice},
        "parameters": {"format": "wav", "sample_rate": 24000},
    }

    with httpx.Client(timeout=60.0) as client:
        # 第 1 步：提交合成任务，拿音频 URL
        resp = client.post(_TTS_ENDPOINT, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("tts api error: %d %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"TTS 服务返回异常（HTTP {resp.status_code}）")

        data = resp.json()
        try:
            audio_url = data["output"]["audio"]["url"]
        except (KeyError, TypeError) as e:
            logger.error("tts response unexpected: %s", str(data)[:300])
            raise RuntimeError("TTS 响应缺少音频地址") from e

        # 第 2 步：下载音频字节（URL 有有效期，拿到立刻下载）
        audio_resp = client.get(audio_url, timeout=_DOWNLOAD_TIMEOUT)
        if audio_resp.status_code != 200:
            raise RuntimeError(f"音频下载失败（HTTP {audio_resp.status_code}）")

        audio = audio_resp.content
        logger.info("tts done: text_len=%d audio_bytes=%d", len(text), len(audio))
        return audio, "audio/wav"
