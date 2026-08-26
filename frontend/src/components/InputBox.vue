<script setup lang="ts">
// 输入框：语音按钮 + 文本输入 + 发送按钮
// 语音识别结果自动填入输入框（用户可编辑后再发送）

import { ref } from 'vue'
import VoiceButton from './VoiceButton.vue'

const emit = defineEmits<{ (e: 'send', text: string): void }>()

// v-model 双向绑定输入内容；isLoading 控制发送按钮禁用态；autoSpeak 自动播报开关
const text = ref('')
const isLoading = defineModel<boolean>('loading', { default: false })
const autoSpeak = defineModel<boolean>('autoSpeak', { default: false })

function onSend() {
  const t = text.value.trim()
  if (!t || isLoading.value) return
  emit('send', t)
  text.value = '' // 发送后清空输入框
}

// 语音识别结果 → 填入输入框
function onTranscribed(recognized: string) {
  text.value = recognized
}

// 回车发送（Shift+Enter 换行）
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

// 快捷指令 chips（优化四）：点击直接发送，引导体验核心能力
// 文案与 Agent 工具一一对应，不会触发"无能力"回答
const QUICK_ACTIONS = ['现在几点了', '帮我记个待办', '总结今天的待办', '记住我叫小玄']
</script>

<template>
  <div class="input-area">
    <!-- 快捷指令：一键发送，聊天中随时可用 -->
    <div class="chips-row">
      <button
        v-for="act in QUICK_ACTIONS"
        :key="act"
        class="chip"
        :disabled="isLoading"
        @click="emit('send', act)"
      >
        {{ act }}
      </button>
    </div>

    <div class="input-box">
      <VoiceButton @transcribed="onTranscribed" />
      <input
        v-model="text"
        class="input"
        type="text"
        placeholder="和玄枢说点什么，或按住 🎙 说话…"
        :disabled="isLoading"
        @keydown="onKeydown"
      />
      <label class="auto-speak" title="回复完成后自动朗读">
        <input v-model="autoSpeak" type="checkbox" :disabled="isLoading" />
        语音回复
      </label>
      <button class="btn" :disabled="isLoading || !text.trim()" @click="onSend">
        {{ isLoading ? '思考中…' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-area {
  border-top: 1px solid rgba(148, 197, 255, 0.15);
  background: rgba(9, 20, 38, 0.4);
}
/* 快捷指令横排 */
.chips-row {
  display: flex;
  gap: 8px;
  padding: 10px 14px 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.chips-row::-webkit-scrollbar {
  display: none;
}
.chip {
  flex-shrink: 0;
  background: rgba(14, 165, 233, 0.1);
  border: 1px solid rgba(34, 211, 238, 0.25);
  border-radius: 999px;
  color: #7dd3fc;
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.chip:hover:not(:disabled) {
  background: rgba(14, 165, 233, 0.25);
  border-color: #22d3ee;
}
.chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.input-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px 14px;
}
.auto-speak {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #7dd3fc;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}
.auto-speak input {
  accent-color: #22d3ee;
  cursor: pointer;
}
.input {
  flex: 1;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(148, 197, 255, 0.2);
  border-radius: 10px;
  padding: 12px 16px;
  color: #e2ecff;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.input:focus {
  border-color: #22d3ee;
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.15), 0 0 18px rgba(34, 211, 238, 0.2);
}
.input::placeholder {
  color: #5a7a9a;
}
.btn {
  background: linear-gradient(135deg, #0ea5e9, #22d3ee);
  border: none;
  border-radius: 10px;
  padding: 0 22px;
  color: #062b3a;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.2s, transform 0.1s;
}
.btn:hover:not(:disabled) {
  box-shadow: 0 0 16px rgba(34, 211, 238, 0.5);
}
.btn:active:not(:disabled) {
  transform: scale(0.97);
}
.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
/* 极窄屏：隐藏快捷指令节省空间 */
@media (max-width: 480px) {
  .chips-row {
    display: none;
  }
}
</style>
