# 语音路由：ASR（Phase 7）/ TTS（Phase 8）
# 语音走普通 HTTP（非 SSE）：一次性请求，返回结构化结果或音频字节

import logging

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.schemas.voice import TTSRequest
from app.services.asr import MAX_AUDIO_BYTES, transcribe_audio
from app.services.tts import synthesize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/asr", summary="语音转文字（ASR）")
async def asr(file: UploadFile = File(...)):
    """接收浏览器录音文件（WAV），返回识别文本。

    请求：multipart/form-data，字段名 file
    响应：{"text": "识别出的文字"}
    """
    audio = await file.read()

    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="音频文件过大")

    try:
        # ASR 是同步 HTTP 调用，放线程池避免阻塞事件循环
        text = await run_in_threadpool(transcribe_audio, audio, "wav")
        return {"text": text}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("asr failed")
        raise HTTPException(status_code=500, detail=f"语音识别失败：{e}") from e


@router.post("/tts", summary="文本转语音（TTS）")
async def tts(req: TTSRequest) -> Response:
    """把文本合成为语音音频（WAV），直接返回音频字节。

    请求：{"text": "要朗读的文本", "voice": "Cherry"(可选)}
    响应：audio/wav 音频字节（前端 <audio> 直接播放）
    """
    try:
        # TTS 是两步同步 HTTP（合成+下载），放线程池避免阻塞事件循环
        audio, media_type = await run_in_threadpool(synthesize, req.text, req.voice)
        return Response(content=audio, media_type=media_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("tts failed")
        raise HTTPException(status_code=500, detail=f"语音合成失败：{e}") from e
