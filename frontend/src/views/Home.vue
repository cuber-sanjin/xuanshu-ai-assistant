<script setup lang="ts">
// 主页：品牌区（AI 核心 + 标题）+ 会话列表 + 聊天区 + 待办/记忆面板
// 响应式：桌面三栏；窄屏(<768px)会话列表与面板变抽屉，通过品牌区按钮切换

import { ref } from 'vue'
import AiCore from '../components/AiCore.vue'
import ChatWindow from '../components/ChatWindow.vue'
import ConversationList from '../components/ConversationList.vue'
import InputBox from '../components/InputBox.vue'
import MemoryPanel from '../components/MemoryPanel.vue'
import TodoPanel from '../components/TodoPanel.vue'
import { useChat } from '../composables/useChat'

const { messages, loading, toolStatus, autoSpeak, sendMessage, newConversation } =
  useChat()

// 移动端抽屉开关
const showConvList = ref(false)
const showSidePanels = ref(false)

function toggleConv() {
  showConvList.value = !showConvList.value
  showSidePanels.value = false
}
function toggleSide() {
  showSidePanels.value = !showSidePanels.value
  showConvList.value = false
}
</script>

<template>
  <div class="home">
    <!-- 顶部品牌区 -->
    <header class="brand">
      <div class="brand-main">
        <AiCore :size="40" :active="loading" />
        <div class="brand-text">
          <h1 class="title">玄 枢</h1>
          <p class="subtitle">PERSONAL AI ASSISTANT</p>
        </div>
      </div>
      <!-- 移动端抽屉开关 -->
      <div class="drawer-btns">
        <button class="drawer-btn" @click="toggleConv" title="会话列表">☰ 会话</button>
        <button class="drawer-btn" @click="toggleSide" title="待办与记忆">≡ 面板</button>
      </div>
      <button class="new-conv" title="开启新对话" @click="newConversation">新对话</button>
    </header>

    <!-- 主体：左会话 + 中聊天 + 右面板 -->
    <main class="main-area">
      <div v-show="showConvList" class="mask" @click="toggleConv"></div>
      <ConversationList :class="{ open: showConvList }" />

      <section class="chat-area">
        <ChatWindow :messages="messages" :tool-status="toolStatus" />
        <InputBox v-model:loading="loading" v-model:auto-speak="autoSpeak" @send="sendMessage" />
      </section>

      <div v-show="showSidePanels" class="mask" @click="toggleSide"></div>
      <aside class="side-panels" :class="{ open: showSidePanels }">
        <TodoPanel />
        <MemoryPanel />
      </aside>
    </main>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}
.brand {
  position: relative;
  text-align: center;
  padding: 16px 0 10px;
  border-bottom: 1px solid rgba(148, 197, 255, 0.12);
  flex-shrink: 0;
}
.brand-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}
.brand-text {
  text-align: left;
}
.title {
  font-size: 28px;
  letter-spacing: 12px;
  margin: 0;
  background: linear-gradient(90deg, #7dd3fc, #22d3ee);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 0 30px rgba(34, 211, 238, 0.25);
}
.subtitle {
  font-size: 10px;
  letter-spacing: 4px;
  color: #5a7a9a;
  margin: 4px 0 0;
}
.new-conv {
  position: absolute;
  right: 18px;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(14, 165, 233, 0.15);
  border: 1px solid rgba(34, 211, 238, 0.4);
  border-radius: 8px;
  color: #7dd3fc;
  font-size: 12px;
  padding: 6px 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.new-conv:hover {
  background: rgba(14, 165, 233, 0.3);
}
.drawer-btns {
  display: none;
}
.main-area {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.side-panels {
  width: 260px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid rgba(148, 197, 255, 0.12);
  overflow-y: auto;
  flex-shrink: 0;
}
.mask {
  display: none;
}

/* ===== 移动端响应式（<768px） ===== */
@media (max-width: 768px) {
  .brand {
    padding: 10px 0 8px;
  }
  .title {
    font-size: 22px;
    letter-spacing: 8px;
  }
  .subtitle {
    letter-spacing: 3px;
    font-size: 9px;
  }
  /* 品牌区抽屉按钮（替代桌面新对话按钮位置） */
  .drawer-btns {
    display: flex;
    gap: 6px;
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
  }
  .drawer-btn {
    background: rgba(14, 165, 233, 0.15);
    border: 1px solid rgba(34, 211, 238, 0.4);
    border-radius: 6px;
    color: #7dd3fc;
    font-size: 11px;
    padding: 5px 8px;
    cursor: pointer;
  }
  .new-conv {
    right: 10px;
    padding: 5px 10px;
    font-size: 11px;
  }

  /* 会话列表 → 左侧抽屉（:deep 穿透子组件根元素） */
  :deep(.conv-list) {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 240px;
    z-index: 200;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
  }
  :deep(.conv-list.open) {
    transform: translateX(0);
  }

  /* 侧栏 → 右侧抽屉 */
  .side-panels {
    position: fixed;
    right: 0;
    top: 0;
    bottom: 0;
    width: 260px;
    z-index: 200;
    transform: translateX(100%);
    transition: transform 0.25s ease;
    background: rgba(10, 22, 40, 0.98);
  }
  .side-panels.open {
    transform: translateX(0);
  }

  /* 抽屉遮罩 */
  .mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 150;
  }

  .chat-window {
    padding: 16px;
  }
  .msg {
    gap: 8px;
  }
  .bubble {
    max-width: 85%;
  }
  .input-box {
    padding: 10px;
  }
  .auto-speak {
    display: none; /* 窄屏隐藏自动播报开关，节省空间 */
  }
}
</style>
