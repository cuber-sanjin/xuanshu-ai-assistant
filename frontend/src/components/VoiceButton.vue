<script setup lang="ts">
// 语音按钮：点击录音（实时波形可视化）→ 转 WAV → ASR 识别 → 把文字交给父组件
// Phase 9：录音中用 AnalyserNode 实时频谱驱动 canvas 柱条波形

import { ref } from 'vue'
import { useRecorder } from '../composables/useRecorder'
import { useToast } from '../composables/useToast'
import { transcribeAudio } from '../services/api'

const emit = defineEmits<{ (e: 'transcribed', text: string): void }>()

const { recording, startRecording, stopRecording, getAnalyser } = useRecorder()
const { error: toastError, info: toastInfo } = useToast()
const processing = ref(false) // 识别中状态

// 波形 canvas
const canvasRef = ref<HTMLCanvasElement | null>(null)
let rafId = 0
let analyser: AnalyserNode | null = null

/** 开始实时波形绘制（rAF 循环读频谱数据） */
function startWaveform() {
  analyser = getAnalyser()
  const canvas = canvasRef.value
  if (!analyser || !canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const BARS = 18
  const data = new Uint8Array(analyser.frequencyBinCount)

  const draw = () => {
    analyser!.getByteFrequencyData(data)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const barW = canvas.width / BARS
    for (let i = 0; i < BARS; i++) {
      // 语音能量集中在低频段，只取前一半频率数据即可
      const v = data[Math.min(i * 2, data.length - 1)] / 255
      const h = Math.max(2, v * (canvas.height - 4))
      const x = i * barW + barW * 0.15
      const grad = ctx.createLinearGradient(0, canvas.height - h, 0, canvas.height)
      grad.addColorStop(0, '#22d3ee')
      grad.addColorStop(1, '#0ea5e9')
      ctx.fillStyle = grad
      ctx.fillRect(x, canvas.height - h, barW * 0.7, h)
    }
    rafId = requestAnimationFrame(draw)
  }
  draw()
}

/** 停止波形绘制 */
function stopWaveform() {
  cancelAnimationFrame(rafId)
  analyser = null
}

async function toggleRecording() {
  if (recording.value) {
    // 停止 → 转码 → 上传识别
    stopWaveform()
    processing.value = true
    const wav = await stopRecording()
    if (wav) {
      try {
        const text = (await transcribeAudio(wav)).trim()
        if (text) {
          emit('transcribed', text)
        } else {
          toastInfo('没有听清，请再说一次')
        }
      } catch (err) {
        console.error('asr failed:', err)
        toastError('语音识别失败，请检查网络后重试')
      }
    }
    processing.value = false
  } else {
    await startRecording()
    // 录音就绪后启动波形（下一帧保证 canvas 已渲染）
    requestAnimationFrame(() => startWaveform())
  }
}
</script>

<template>
  <div class="voice-wrap">
    <button
      class="voice-btn"
      :class="{ recording, processing }"
      :disabled="processing"
      :title="recording ? '停止录音' : '语音输入'"
      @click="toggleRecording"
    >
      <!-- 录音中：实时波形 -->
      <canvas
        v-if="recording"
        ref="canvasRef"
        class="wave"
        width="26"
        height="26"
      ></canvas>
      <!-- 空闲/处理中：图标 -->
      <span v-else class="mic-icon">{{ processing ? '…' : '🎙' }}</span>
    </button>
  </div>
</template>

<style scoped>
.voice-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.voice-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid rgba(148, 197, 255, 0.3);
  background: rgba(255, 255, 255, 0.06);
  color: #7dd3fc;
  font-size: 16px;
  cursor: pointer;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.voice-btn:hover {
  border-color: #22d3ee;
}
.voice-btn.recording {
  background: rgba(248, 113, 113, 0.15);
  border-color: #f87171;
  animation: pulse-ring 1.5s ease-in-out infinite;
}
.voice-btn.processing {
  opacity: 0.5;
  cursor: wait;
}
.wave {
  display: block;
}
@keyframes pulse-ring {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(248, 113, 113, 0);
  }
}
</style>
