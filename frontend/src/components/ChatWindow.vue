<script setup lang="ts">
// 聊天窗口：消息列表 + 空状态引导 + 智能滚动
//
// 智能滚动（区别于旧的"无条件滚到底"）：
//   - 用户在底部（stickToBottom=true）→ 新消息/流式增量自动跟随滚动（打字机效果）
//   - 用户上翻查看历史（stickToBottom=false）→ 不强制拉回底部，
//     改为底部悬浮"↓ 新消息"提示条，点击才回到底部

import { computed, nextTick, ref, watch } from 'vue'
import AiCore from './AiCore.vue'
import ChatMessage from './ChatMessage.vue'
import type { MessageItem } from '../composables/useChat'
import { useChat } from '../composables/useChat'

const props = defineProps<{
  messages: MessageItem[]
  toolStatus?: string // 工具执行状态条（来自 useChat）
}>()

// 复用模块级聊天状态：loading（禁用重新生成）、regenerate（重生成入口）
const { loading, regenerate } = useChat()

// 滚动容器引用
const container = ref<HTMLElement | null>(null)

// 是否"贴底"跟随滚动；距底部超过阈值视为用户在上方阅读
const stickToBottom = ref(true)
const showNewMsgHint = ref(false)
const BOTTOM_THRESHOLD = 80

// 最后一条 assistant 消息索引（仅它对"重新生成"语义成立）
const lastAssistantIdx = computed(() => {
  for (let i = props.messages.length - 1; i >= 0; i--) {
    if (props.messages[i].role === 'assistant') return i
  }
  return -1
})

// 滚动事件：判断用户是否在底部，并清除提示
function onScroll() {
  const el = container.value
  if (!el) return
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_THRESHOLD
  if (nearBottom) {
    stickToBottom.value = true
    showNewMsgHint.value = false
  } else {
    stickToBottom.value = false
  }
}

// 消息变化（新增/增量）：贴底则跟随，否则提示"新消息"
watch(
  () => props.messages,
  async () => {
    await nextTick()
    const el = container.value
    if (!el) return
    if (stickToBottom.value) {
      el.scrollTop = el.scrollHeight
    } else {
      showNewMsgHint.value = true
    }
  },
  { deep: true }, // 流式输出是修改已存在消息的 content，需深度监听
)

// 点击"↓ 新消息"回到最新
function jumpToBottom() {
  const el = container.value
  if (!el) return
  el.scrollTop = el.scrollHeight
  stickToBottom.value = true
  showNewMsgHint.value = false
}
</script>

<template>
  <div ref="container" class="chat-window" @scroll.passive="onScroll">
    <!-- 空状态：首次打开时的引导语（AI 核心动画 + 引导文案） -->
    <div v-if="messages.length === 0" class="empty">
      <AiCore :size="64" :active="false" />
      <p class="empty-text">“玄枢，听候吩咐。”</p>
      <p class="empty-sub">试试问我：「今天几点了？」「帮我记个待办」或按住 🎙 说话</p>
    </div>

    <div v-else class="messages">
      <ChatMessage
        v-for="(m, i) in messages"
        :key="i"
        :role="m.role"
        :content="m.content"
        :model="m.model"
        :created-at="m.createdAt"
        :streaming="m.streaming"
        :is-last="m.role === 'assistant' && i === lastAssistantIdx"
        :can-regenerate="loading"
        @regenerate="regenerate"
      />
    </div>

    <!-- 新消息提示条：用户在上方时悬浮显示，点击回到底部 -->
    <button v-if="showNewMsgHint" class="new-msg-hint" @click="jumpToBottom">
      ↓ 新消息
    </button>

    <!-- 工具执行状态条：只显示可读状态，不暴露内部推理细节 -->
    <div v-if="toolStatus" class="tool-status">
      <span class="spinner"></span>{{ toolStatus }}
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  position: relative;
}
.empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #7dd3fc;
}
.empty-text {
  margin: 6px 0 0;
  font-size: 15px;
  letter-spacing: 2px;
}
.empty-sub {
  font-size: 13px;
  color: #5a7a9a;
}
/* 新消息提示：sticky 悬浮在滚动容器底部 */
.new-msg-hint {
  position: sticky;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(14, 165, 233, 0.9);
  border: 1px solid rgba(34, 211, 238, 0.6);
  border-radius: 999px;
  color: #062b3a;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  transition: all 0.2s;
  display: block;
  margin: 0 auto;
}
.new-msg-hint:hover {
  background: #22d3ee;
  box-shadow: 0 4px 20px rgba(34, 211, 238, 0.5);
}
.tool-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 12px 48px;
  font-size: 13px;
  color: #7dd3fc;
  opacity: 0.9;
}
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(34, 211, 238, 0.3);
  border-top-color: #22d3ee;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
