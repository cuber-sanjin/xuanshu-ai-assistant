<script setup lang="ts">
// Toast 全局宿主：右上角悬浮，渲染 useToast 的全部条目
// 挂载在 App.vue（全局单例），任何组件 push 的消息都会在这里显示

import { useToast } from '../composables/useToast'

const { toasts, remove } = useToast()

const ICONS: Record<string, string> = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
}
</script>

<template>
  <div class="toast-host">
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">
        <span class="icon">{{ ICONS[t.type] }}</span>
        <span class="msg">{{ t.message }}</span>
        <button class="close" title="关闭" @click="remove(t.id)">✕</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  top: 14px;
  right: 14px;
  z-index: 999; /* 高于所有抽屉(200)与遮罩(150) */
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none; /* 空白区域不挡点击 */
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 220px;
  max-width: 360px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  color: #e2ecff;
  background: rgba(13, 27, 48, 0.95);
  border: 1px solid rgba(148, 197, 255, 0.2);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4);
}
.toast.success {
  border-color: rgba(52, 211, 153, 0.5);
}
.toast.success .icon {
  color: #34d399;
}
.toast.error {
  border-color: rgba(248, 113, 113, 0.55);
}
.toast.error .icon {
  color: #f87171;
}
.toast.info {
  border-color: rgba(34, 211, 238, 0.5);
}
.toast.info .icon {
  color: #22d3ee;
}
.icon {
  font-size: 14px;
  flex-shrink: 0;
}
.msg {
  flex: 1;
  line-height: 1.5;
}
.close {
  background: none;
  border: none;
  color: #5a7a9a;
  font-size: 11px;
  cursor: pointer;
  padding: 2px;
  flex-shrink: 0;
}
.close:hover {
  color: #e2ecff;
}

/* 进入：右侧滑入 + 淡入；离开：淡出 */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(24px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
