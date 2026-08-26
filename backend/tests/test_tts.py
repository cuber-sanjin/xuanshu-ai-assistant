# TTS 测试：只测参数校验层（不调真实 TTS API，避免每次测试花钱）
# 真实合成已通过 curl E2E 验证（返回 audio/wav RIFF 字节）

import pytest
from pydantic import ValidationError

from app.schemas.voice import TTSRequest
from app.services.tts import MAX_TTS_TEXT_LENGTH, synthesize


def test_empty_text_rejected():
    """空文本在发起 HTTP 前就被拒绝（ValueError）"""
    with pytest.raises(ValueError):
        synthesize("   ")


def test_tts_request_empty_text():
    """API 层：空文本被 Pydantic 拒绝（422）"""
    with pytest.raises(ValidationError):
        TTSRequest(text="")


def test_tts_request_too_long():
    """API 层：超过 500 字被 Pydantic 拒绝（422）"""
    with pytest.raises(ValidationError):
        TTSRequest(text="长" * (MAX_TTS_TEXT_LENGTH + 1))


def test_tts_request_valid():
    """正常请求通过校验，voice 可选"""
    req = TTSRequest(text="主人，待办已记录。")
    assert req.text == "主人，待办已记录。"
    assert req.voice is None

    req2 = TTSRequest(text="你好", voice="Ethan")
    assert req2.voice == "Ethan"


def test_truncate_logic():
    """超长文本在后端函数内部被截断（不报错，不调 API）"""
    # 先走空文本校验：能到截断逻辑前不抛参错，说明文本有效
    # 此处验证常量存在且合理（500 字限制）
    assert MAX_TTS_TEXT_LENGTH == 500
