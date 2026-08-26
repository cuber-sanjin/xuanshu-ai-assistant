// 录音工具：MediaRecorder 录音 + Web Audio 转 16kHz 单声道 WAV
//
// 为什么必须转码成 WAV？
//   MediaRecorder 默认产出 webm/opus，而 ASR 接口（qwen3-asr-flash）
//   文档只保证 wav/mp3 兼容。用 Web Audio API 解码后重采样
//   为 16kHz 单声道 WAV，格式 100% 兼容且体积可控（16kHz 对语音足够）。
//
// 流程：录音(webm) → decodeAudioData 解码 → OfflineAudioContext 重采样
//       → 手动编码 WAV 头 + PCM16 → Blob

import { ref } from 'vue'
import { useToast } from './useToast'

// Toast 反馈（模块级单例，函数内使用）
const { error: toastError } = useToast()

/** 把 Float32Array 采样编码为 WAV Blob（44 字节头 + PCM16） */
function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i))
    }
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // 单声道
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // 字节率 = 采样率 * 2
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // 位深 16bit
  writeString(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

/** webm/opus Blob → 16kHz 单声道 WAV Blob */
async function convertToWav(webmBlob: Blob, targetRate = 16000): Promise<Blob> {
  const arrayBuffer = await webmBlob.arrayBuffer()

  // 1. 解码为 AudioBuffer（支持浏览器录音的 opus 编码）
  const decodeCtx = new AudioContext()
  const audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer)
  await decodeCtx.close()

  // 2. OfflineAudioContext 重采样到目标采样率 + 混单声道
  const length = Math.ceil(audioBuffer.duration * targetRate)
  const offlineCtx = new OfflineAudioContext(1, length, targetRate)
  const source = offlineCtx.createBufferSource()
  source.buffer = audioBuffer
  source.connect(offlineCtx.destination)
  source.start(0)
  const rendered = await offlineCtx.startRendering()

  // 3. 编码为 WAV
  return encodeWav(rendered.getChannelData(0), targetRate)
}

// 录音状态
const recording = ref(false)
const error = ref('')

// MediaRecorder 实例与录音数据
let mediaRecorder: MediaRecorder | null = null
let chunks: Blob[] = []

// 波形分析（Phase 9：录音时实时频谱可视化）
let audioCtx: AudioContext | null = null
let analyser: AnalyserNode | null = null

/** 获取当前录音流的 AnalyserNode（用于实时波形），无录音时返回 null */
function getAnalyser(): AnalyserNode | null {
  if (!mediaRecorder) return null
  if (!analyser) {
    audioCtx = new AudioContext()
    const source = audioCtx.createMediaStreamSource(mediaRecorder.stream)
    analyser = audioCtx.createAnalyser()
    analyser.fftSize = 64 // 低频细节足够（语音），性能友好
    analyser.smoothingTimeConstant = 0.65 // 平滑，波形不跳变
    source.connect(analyser)
  }
  return analyser
}

/** 释放分析器资源（停止录音时调用） */
function disposeAnalyser() {
  if (audioCtx) {
    audioCtx.close().catch(() => {})
    audioCtx = null
    analyser = null
  }
}

/** 开始录音（需用户已授权麦克风） */
async function startRecording(): Promise<void> {
  error.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    // 优先 opus 编码（体积小）；不可用则用默认
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : ''
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    chunks = []

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    mediaRecorder.start()
    recording.value = true
  } catch (err) {
    error.value = '无法访问麦克风，请检查浏览器权限'
    toastError(error.value)
    console.error('mic error:', err)
  }
}

/** 停止录音并转码为 WAV，返回 Blob */
async function stopRecording(): Promise<Blob | null> {
  if (!mediaRecorder) return null

  // 停止波形分析
  disposeAnalyser()

  return new Promise((resolve) => {
    mediaRecorder!.onstop = async () => {
      recording.value = false
      // 停止所有音轨（释放麦克风）
      mediaRecorder!.stream.getTracks().forEach((t) => t.stop())
      mediaRecorder = null

      try {
        const webmBlob = new Blob(chunks, { type: 'audio/webm' })
        const wavBlob = await convertToWav(webmBlob)
        resolve(wavBlob)
      } catch (err) {
        console.error('wav convert failed:', err)
        error.value = '音频转换失败'
        resolve(null)
      }
    }
    mediaRecorder!.stop()
  })
}

export function useRecorder() {
  return { recording, error, startRecording, stopRecording, getAnalyser }
}
