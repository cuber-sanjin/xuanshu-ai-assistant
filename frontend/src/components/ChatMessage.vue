<script setup lang="ts">
// 单条消息气泡：区分用户/玄枢，玄枢显示名称与头像标识
// streaming 为 true 时在文本末尾显示闪烁光标（模拟打字机效果）
// 玄枢消息输出完成后显示语音播放按钮（TTS，Phase 8）
// assistant 消息支持 Markdown 渲染（utils/markdown.ts 带 XSS 消毒）
// 操作条（优化三）：复制回复 + 重新生成（仅最后一条 assistant 显示）

import { computed } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import { useToast } from '../composables/useToast'
import PlaybackButton from './PlaybackButton.vue'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  model?: string // 玄枢消息可附带模型名（调试用）
  createdAt?: string // HH:MM 时间戳
  streaming?: boolean // 是否正在流式输出
  isLast?: boolean // 是否为最后一条 assistant（决定是否显示"重新生成"）
  canRegenerate?: boolean // 全局 loading 状态（重生成/发送中禁用）
}>()

const emit = defineEmits<{ (e: 'regenerate'): void }>()

const { success: toastSuccess, error: toastError } = useToast()

// assistant 内容转安全 HTML（user 内容保持纯文本 {{ }}，天然防注入）
const renderedHtml = computed(() =>
  props.role === 'assistant' ? renderMarkdown(props.content) : '',
)

/** 复制回复到剪贴板（需 secure context：localhost/https 可用） */
async function copy() {
  try {
    await navigator.clipboard.writeText(props.content)
    toastSuccess('已复制到剪贴板')
  } catch (err) {
    console.error('copy failed:', err)
    toastError('复制失败，请手动选择文本')
  }
}
</script>

<template>
  <div class="msg" :class="role === 'user' ? 'msg-user' : 'msg-assistant'">
    <div class="avatar" :class="role === 'user' ? 'avatar-user' : 'avatar-assistant'">
      {{ role === 'user' ? '我' : '玄' }}
    </div>
    <div class="bubble">
      <div class="name">
        {{ role === 'user' ? '你' : '玄枢' }}
        <span v-if="model" class="model">· {{ model }}</span>
        <span v-if="createdAt" class="time">{{ createdAt }}</span>
      </div>

      <!-- 用户消息：纯文本（防注入）；玄枢消息：Markdown（已消毒） -->
      <div v-if="role === 'user'" class="text">
        {{ content }}
        <span v-if="streaming" class="cursor">▍</span>
      </div>
      <div v-else class="text md">
        <div v-html="renderedHtml" class="md-body"></div>
        <span v-if="streaming" class="cursor">▍</span>
        <!-- 玄枢回复完成后可点击播放语音 -->
        <PlaybackButton
          v-if="role === 'assistant' && content && !streaming"
          :text="content"
        />
      </div>

      <!-- 操作条：复制 + 重新生成（仅玄枢回复，hover 显示） -->
      <div
        v-if="role === 'assistant' && content && !streaming"
        class="actions"
      >
        <button class="act-btn" title="复制回复" @click="copy">复制</button>
        <button
          v-if="isLast"
          class="act-btn"
          title="重新生成回复"
          :disabled="canRegenerate"
          @click="emit('regenerate')"
        >
          重新生成
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.msg-user {
  flex-direction: row-reverse;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}
.avatar-user {
  background: #3a4a6b;
  color: #cfe0ff;
}
.avatar-assistant {
  background: linear-gradient(135deg, #0ea5e9, #22d3ee);
  color: #062b3a;
  font-weight: 700;
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.35); /* 微光描边 */
}
.bubble {
  max-width: 75%;
}
.msg-user .bubble {
  text-align: right;
}
.name {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  color: #7dd3fc;
  margin-bottom: 4px;
  opacity: 0.8;
}
.model {
  color: #5a7a9a;
}
.time {
  color: #3f5a7a;
  font-size: 11px;
}
.text {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(148, 197, 255, 0.18);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.7;
  color: #e2ecff;
  white-space: pre-wrap;
  word-break: break-word;
  transition: border-color 0.2s;
  text-align: left;
}
.text:hover {
  border-color: rgba(34, 211, 238, 0.4);
}
.msg-user .text {
  background: rgba(14, 165, 233, 0.15);
  border-color: rgba(14, 165, 233, 0.35);
}

/* 操作条：气泡下方小字按钮，hover 显示 */
.actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.msg:hover .actions,
.actions:focus-within {
  opacity: 1;
}
.act-btn {
  background: none;
  border: 1px solid rgba(148, 197, 255, 0.2);
  border-radius: 6px;
  color: #5a7a9a;
  font-size: 11px;
  padding: 3px 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.act-btn:hover:not(:disabled) {
  color: #7dd3fc;
  border-color: #22d3ee;
}
.act-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ===== Markdown 内容样式（md-body 内元素） ===== */
.md-body {
  display: inline-block;
  width: 100%;
}
.md-body :deep(p) {
  margin: 0 0 8px;
}
.md-body :deep(p:last-child) {
  margin-bottom: 0;
}
.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}
.md-body :deep(li) {
  margin-bottom: 2px;
}
.md-body :deep(strong) {
  color: #7dd3fc;
}
.md-body :deep(code) {
  background: rgba(14, 165, 233, 0.15);
  border: 1px solid rgba(34, 211, 238, 0.25);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 13px;
  color: #a5f3fc;
}
.md-body :deep(pre) {
  background: rgba(8, 20, 40, 0.8);
  border: 1px solid rgba(148, 197, 255, 0.15);
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.md-body :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
}
/* 高亮代码块：hljs 主题负责着色，去掉其自带 padding（pre 已有） */
.md-body :deep(pre code.hljs) {
  padding: 0;
  background: transparent;
}
.md-body :deep(a) {
  color: #22d3ee;
  text-decoration: underline;
}
.md-body :deep(blockquote) {
  border-left: 3px solid #22d3ee;
  margin: 8px 0;
  padding-left: 10px;
  color: #9fb8d8;
}
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3) {
  margin: 8px 0 6px;
  color: #cfe0ff;
}
.md-body :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid rgba(148, 197, 255, 0.2);
  padding: 4px 10px;
  font-size: 13px;
}

/* 流式光标：闪烁动画 */
.cursor {
  display: inline-block;
  color: #22d3ee;
  animation: blink 0.8s step-end infinite;
}
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
