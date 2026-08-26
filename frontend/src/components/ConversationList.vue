<script setup lang="ts">
// 会话列表：新建 / 切换 / 删除历史对话
// 与 useChat 共享会话状态（conversationId），选中项高亮
// 数据刷新：首条消息自动标题等变化通过 useDataRefresh('conversation') 触发重载

import { onMounted, ref, watch } from 'vue'
import { deleteConversation, listConversations, type Conversation } from '../services/api'
import { useRefreshVersion } from '../composables/useDataRefresh'
import { useToast } from '../composables/useToast'
import { useChat } from '../composables/useChat'

const { conversationId, newConversation, selectConversation } = useChat()
const { success: toastSuccess, error: toastError } = useToast()

const conversations = ref<Conversation[]>([])
const refreshVersion = useRefreshVersion('conversation')
watch(refreshVersion, () => load())

async function load() {
  try {
    conversations.value = await listConversations()
  } catch (err) {
    console.error('load conversations failed:', err)
  }
}

/** 切换会话：载入该会话历史消息 */
async function pick(conv: Conversation) {
  if (conv.id === conversationId.value) return // 已在当前会话
  await selectConversation(conv.id)
}

/** 删除会话：若删的是当前会话则回到新对话 */
async function remove(conv: Conversation) {
  if (!window.confirm(`删除会话「${conv.title}」？此操作不可恢复。`)) return
  try {
    await deleteConversation(conv.id)
    if (conversationId.value === conv.id) newConversation()
    await load()
    toastSuccess(`已删除会话「${conv.title}」`)
  } catch (err) {
    console.error('delete conversation failed:', err)
    toastError('删除会话失败，请重试')
  }
}

onMounted(load)
</script>

<template>
  <aside class="conv-list">
    <button class="new-btn" @click="newConversation">＋ 新对话</button>

    <ul v-if="conversations.length > 0" class="conv-items">
      <li
        v-for="c in conversations"
        :key="c.id"
        class="conv-item"
        :class="{ active: c.id === conversationId }"
        @click="pick(c)"
      >
        <div class="conv-main">
          <p class="conv-title">{{ c.title }}</p>
          <p class="conv-preview">{{ c.last_message ?? '（空）' }}</p>
        </div>
        <button class="del-btn" title="删除会话" @click.stop="remove(c)">✕</button>
      </li>
    </ul>

    <p v-else class="empty-tip">暂无历史会话</p>
  </aside>
</template>

<style scoped>
.conv-list {
  width: 210px;
  flex-shrink: 0;
  border-right: 1px solid rgba(148, 197, 255, 0.12);
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  background: rgba(9, 20, 38, 0.5);
}
.new-btn {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.25), rgba(34, 211, 238, 0.25));
  border: 1px solid rgba(34, 211, 238, 0.4);
  border-radius: 8px;
  color: #7dd3fc;
  font-size: 13px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.new-btn:hover {
  background: rgba(14, 165, 233, 0.35);
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.25);
}
.conv-items {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0;
}
.conv-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
}
.conv-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(148, 197, 255, 0.15);
}
.conv-item.active {
  background: rgba(14, 165, 233, 0.18);
  border-color: rgba(34, 211, 238, 0.45);
}
.conv-main {
  flex: 1;
  min-width: 0;
}
.conv-title {
  font-size: 13px;
  color: #cfe0ff;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-preview {
  font-size: 11px;
  color: #5a7a9a;
  margin: 2px 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.del-btn {
  background: none;
  border: none;
  color: #3f5a7a;
  font-size: 11px;
  cursor: pointer;
  flex-shrink: 0;
  visibility: hidden;
}
.conv-item:hover .del-btn {
  visibility: visible;
}
.del-btn:hover {
  color: #f87171;
}
.empty-tip {
  font-size: 12px;
  color: #3f5a7a;
  text-align: center;
  padding: 12px 0;
}
</style>
