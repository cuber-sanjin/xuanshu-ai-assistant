<script setup lang="ts">
// 语音播放按钮：点击 → TTS 合成 → 播放玄枢的声音
// 播放中显示旋转动画；再点一次停止；自动释放 ObjectURL 防内存泄漏

import { ref } from 'vue'
import { useToast } from '../composables/useToast'
import { synthesizeSpeech } from '../services/api'

const props = defineProps<{ text: string }>()

const { error: toastError } = useToast()

const playing = ref(false)

// 当前播放的音频（用于再次点击时停止）
let currentAudio: HTMLAudioElement | null = null

async function togglePlay() {
  // 正在播放 → 停止
  if (playing.value) {
    currentAudio?.pause()
    currentAudio = null
    playing.value = false
    return
  }

  try {
    // 1. 调后端 TTS 合成（返回 WAV Blob）
    const blob = await synthesizeSpeech(props.text)
    // 2. ObjectURL 播放；结束后必须 revoke 释放内存
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    currentAudio = audio

    audio.onended = () => {
      playing.value = false
      URL.revokeObjectURL(url)
      currentAudio = null
    }
    audio.onerror = () => {
      playing.value = false
      URL.revokeObjectURL(url)
      currentAudio = null
      toastError('语音播放失败')
    }

    await audio.play()
    playing.value = true
  } catch (err) {
    console.error('tts failed:', err)
    toastError('语音合成失败，请稍后重试')
  }
}
</script>

<template>
  <button
    class="play-btn"
    :class="{ playing }"
    :title="playing ? '停止播放' : '播放语音'"
    @click="togglePlay"
  >
    <span class="icon" :class="{ spinning: playing }">🔊</span>
  </button>
</template>

<style scoped>
.play-btn {
  background: none;
  border: 1px solid rgba(148, 197, 255, 0.25);
  border-radius: 6px;
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-left: 8px;
  vertical-align: middle;
  transition: all 0.2s;
}
.play-btn:hover {
  border-color: #22d3ee;
}
.play-btn.playing {
  border-color: #22d3ee;
  background: rgba(34, 211, 238, 0.15);
}
.icon {
  font-size: 13px;
}
.icon.spinning {
  animation: spin 1s linear infinite;
  display: inline-block;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
